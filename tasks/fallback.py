"""
Fallback 容错与降级策略

提供系统级的容错机制：
1. Orchestrator LLM 失败自动通过
2. Agent 任务超时/失败降级处理
3. 补充研究轮次限制
4. 单个 Agent 失败时其他 Agent 继续
"""

import os
import sys
from typing import Dict, Any, Optional, List
from celery.utils.log import get_task_logger

from tasks.blackboard import Blackboard

logger = get_task_logger(__name__)

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ==================== Agent 任务降级 ====================

def get_fallback_plan(agent: str, query: str) -> Dict[str, Any]:
    """
    获取 Agent 的降级 Plan

    当 Plan 阶段失败或超时时，返回默认 Plan

    Args:
        agent: Agent 名称
        query: 原始查询

    Returns:
        默认 Plan 数据
    """
    logger.warning(f"使用降级 Plan for {agent}")

    base_plan = {
        'keywords': [query],
        'fallback': True,
        'reason': 'plan_phase_failed'
    }

    if agent == 'query':
        base_plan.update({
            'search_strategy': 'broad',
            'report_structure': ['introduction', 'findings', 'conclusion']
        })
    elif agent == 'media':
        base_plan.update({
            'media_types': ['video', 'image'],
            'report_structure': ['media_summary', 'analysis']
        })
    elif agent == 'insight':
        base_plan.update({
            'analysis_aspects': ['trends', 'insights', 'recommendations'],
            'report_structure': ['overview', 'deep_dive', 'summary']
        })

    return base_plan


def get_fallback_research(agent: str, query: str, error: str = None) -> Dict[str, Any]:
    """
    获取 Agent 的降级 Research 结果

    当 Research 阶段失败或超时时，返回默认结果

    Args:
        agent: Agent 名称
        query: 原始查询
        error: 错误信息

    Returns:
        降级 Research 数据
    """
    logger.warning(f"使用降级 Research for {agent}: {error}")

    return {
        'result': f"# {agent.capitalize()} 研究结果（降级模式）\n\n查询：{query}\n\n由于技术问题，无法完成完整研究。",
        'plan': get_fallback_plan(agent, query),
        'guidance_applied': False,
        'fallback': True,
        'error': error
    }


def get_fallback_report(agent: str, query: str, error: str = None) -> str:
    """
    获取 Agent 的降级 Report

    当 Report 阶段失败或超时时，返回默认报告

    Args:
        agent: Agent 名称
        query: 原始查询
        error: 错误信息

    Returns:
        降级报告内容
    """
    logger.warning(f"使用降级 Report for {agent}: {error}")

    return f"""# {agent.capitalize()} 报告（降级模式）

**查询**：{query}

**状态**：由于技术问题，无法生成完整报告

**错误信息**：{error or '未知错误'}

---
注：此为降级结果，可能缺少部分内容
"""


# ==================== Orchestrator 决策降级 ====================

def should_force_approve_plan(task_id: str) -> bool:
    """
    判断是否应该强制通过 Plan 阶段

    条件：
    - Orchestrator LLM 调用失败
    - Plan 阶段超时

    Args:
        task_id: 任务 ID

    Returns:
        是否强制通过
    """
    # 默认策略：始终通过（简化第一期）
    return True


def should_force_approve_research(task_id: str, blackboard: Blackboard) -> bool:
    """
    判断是否应该强制通过 Research 阶段

    条件：
    - Orchestrator LLM 调用失败
    - 已达到最大补充轮次
    - Research 阶段超时

    Args:
        task_id: 任务 ID
        blackboard: Blackboard 实例

    Returns:
        是否强制通过
    """
    # 检查补充轮次
    current_round = blackboard.get_supplement_round(task_id)
    if current_round >= 1:
        logger.info(f"[{task_id}] 已达到最大补充轮次，强制通过")
        return True

    return False


# ==================== 任务异常处理 ====================

def handle_agent_task_error(
    task_id: str,
    agent: str,
    phase: str,
    error: Exception,
    blackboard: Blackboard
) -> Any:
    """
    处理 Agent 任务错误

    记录错误并返回降级结果，不阻塞整体流程

    Args:
        task_id: 任务 ID
        agent: Agent 名称
        phase: 阶段名称（plan/research/report）
        error: 异常对象
        blackboard: Blackboard 实例

    Returns:
        降级结果
    """
    error_msg = str(error)
    logger.error(f"[{task_id}] {agent} {phase} 阶段失败: {error_msg}")

    # 记录到 Forum 日志
    blackboard.append_forum_log(
        task_id,
        agent,
        f"{phase} 阶段失败：{error_msg}，使用降级结果"
    )

    # 根据阶段返回不同的降级结果
    if phase == 'plan':
        fallback = get_fallback_plan(agent, '')
        blackboard.save_plan_result(task_id, agent, fallback)
        return fallback

    elif phase == 'research':
        fallback = get_fallback_research(agent, '', error_msg)
        blackboard.save_research_result(task_id, agent, fallback)
        return fallback

    elif phase == 'report':
        fallback = get_fallback_report(agent, '', error_msg)
        blackboard.save_report_result(task_id, agent, fallback)
        return fallback

    return None


# ==================== 结果收集与验证 ====================

def collect_agent_results(
    task_id: str,
    agents: List[str],
    phase: str,
    blackboard: Blackboard
) -> Dict[str, Any]:
    """
    收集所有 Agent 的阶段结果，包含降级处理

    Args:
        task_id: 任务 ID
        agents: Agent 列表
        phase: 阶段名称（plan/research/report）
        blackboard: Blackboard 实例

    Returns:
        Agent -> 结果的映射
    """
    results = {}

    for agent in agents:
        try:
            if phase == 'plan':
                result = blackboard.get_plan_result(task_id, agent)
            elif phase == 'research':
                result = blackboard.get_research_result(task_id, agent)
            elif phase == 'report':
                result = blackboard.get_report_result(task_id, agent)
            else:
                result = None

            if result:
                results[agent] = result
            else:
                # 结果缺失，使用降级
                logger.warning(f"[{task_id}] {agent} {phase} 结果缺失，使用降级")
                results[agent] = _get_fallback_by_phase(agent, phase, task_id, blackboard)

        except Exception as exc:
            logger.error(f"[{task_id}] 收集 {agent} {phase} 结果失败: {exc}")
            results[agent] = _get_fallback_by_phase(agent, phase, task_id, blackboard)

    return results


def _get_fallback_by_phase(
    agent: str,
    phase: str,
    task_id: str,
    blackboard: Blackboard
) -> Any:
    """根据阶段获取降级结果"""
    query = ''  # 简化版本，可从 Blackboard 或任务元数据读取

    if phase == 'plan':
        return get_fallback_plan(agent, query)
    elif phase == 'research':
        return get_fallback_research(agent, query, 'result_missing')
    elif phase == 'report':
        return get_fallback_report(agent, query, 'result_missing')
    else:
        return None


# ==================== 超时保护 ====================

class TimeoutProtection:
    """任务超时保护"""

    # 超时配置（秒）
    TIMEOUTS = {
        'plan': 600,      # 10 分钟
        'research': 1800,  # 30 分钟
        'report': 600,     # 10 分钟
        'orchestrate': 300 # 5 分钟
    }

    @classmethod
    def get_timeout(cls, phase: str) -> int:
        """获取阶段超时配置"""
        return cls.TIMEOUTS.get(phase, 600)

    @classmethod
    def is_timeout(cls, phase: str, elapsed: float) -> bool:
        """判断是否超时"""
        timeout = cls.get_timeout(phase)
        return elapsed > timeout


# ==================== 健康检查 ====================

def check_agent_health(agent: str) -> bool:
    """
    检查 Agent 是否健康可用

    Args:
        agent: Agent 名称

    Returns:
        是否健康
    """
    try:
        if agent == 'query':
            from QueryEngine.agent import DeepSearchAgent
            DeepSearchAgent()
        elif agent == 'media':
            from MediaEngine.agent import DeepSearchAgent
            DeepSearchAgent()
        elif agent == 'insight':
            from InsightEngine.agent import DeepSearchAgent
            DeepSearchAgent()
        else:
            return False

        return True

    except Exception as exc:
        logger.error(f"Agent {agent} 健康检查失败: {exc}")
        return False


def get_healthy_agents(agents: List[str]) -> List[str]:
    """
    获取健康的 Agent 列表

    Args:
        agents: 待检查的 Agent 列表

    Returns:
        健康的 Agent 列表
    """
    healthy = []
    for agent in agents:
        if check_agent_health(agent):
            healthy.append(agent)
        else:
            logger.warning(f"Agent {agent} 不健康，跳过")

    return healthy


# ==================== 错误恢复 ====================

def try_recover_from_error(
    task_id: str,
    agent: str,
    phase: str,
    blackboard: Blackboard,
    max_retries: int = 2
) -> bool:
    """
    尝试从错误中恢复

    Args:
        task_id: 任务 ID
        agent: Agent 名称
        phase: 阶段名称
        blackboard: Blackboard 实例
        max_retries: 最大重试次数

    Returns:
        是否恢复成功
    """
    # 简化版本：不实现自动重试，由 Celery 的 retry 机制处理
    # 这里只记录日志
    logger.info(f"[{task_id}] {agent} {phase} 错误恢复由 Celery 处理")
    return False
