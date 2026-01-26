"""
阶段性 Agent 任务模块

将每个 Agent 拆分为三个阶段：
1. Plan - 生成研究计划（关键词、报告结构）
2. Research - 执行研究（基于 Plan 和 Guidance）
3. Report - 生成报告（基于 Research 结果）

支持：
- Blackboard 状态共享
- Guidance 机制
- 补充研究轮次
"""

import os
import sys
from typing import Dict, Any, Optional
from celery.utils.log import get_task_logger

from celery_app import celery_app
from tasks.blackboard import Blackboard

logger = get_task_logger(__name__)

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ==================== QueryEngine 三阶段任务 ====================

@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def query_plan(self, task_id: str, query: str, agent: str = 'query') -> Dict[str, Any]:
    """
    QueryEngine - Plan 阶段

    调用 Agent 的 generate_plan() 方法生成研究计划，包括：
    - 报告结构（paragraphs）
    - 完整状态序列化（state_dict）

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称（默认 'query'）

    Returns:
        Plan 数据字典（包含 state_dict）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] QueryEngine Plan 阶段开始: {query}")
        blackboard.set_agent_phase(task_id, agent, 'plan')
        blackboard.append_forum_log(task_id, agent, f"开始 Plan 阶段: {query}")

        # 获取可能的 Guidance
        guidance = blackboard.get_guidance(task_id, 'plan')
        if guidance:
            logger.info(f"[{task_id}] 收到 Plan Guidance: {guidance[:100]}...")

        # 调用 Agent 的 generate_plan 方法
        from QueryEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        plan = agent_instance.generate_plan(query, guidance=guidance)

        # 保存到 Blackboard（包含 state_dict）
        blackboard.save_plan_result(task_id, agent, plan)
        blackboard.append_forum_log(
            task_id, agent,
            f"Plan 完成，生成 {plan.get('paragraph_count', 0)} 个段落"
        )

        logger.info(f"[{task_id}] QueryEngine Plan 完成")
        return plan

    except Exception as exc:
        logger.error(f"[{task_id}] QueryEngine Plan 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Plan 阶段失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=1800, time_limit=1860)
def query_research(self, task_id: str, query: str, agent: str = 'query') -> Dict[str, Any]:
    """
    QueryEngine - Research 阶段

    从 Blackboard 读取 Plan（包含 state_dict），调用 Agent 的 execute_research() 方法

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        Research 数据字典（包含 state_dict）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] QueryEngine Research 阶段开始")
        blackboard.set_agent_phase(task_id, agent, 'research')

        # 读取 Plan（必须包含 state_dict）
        plan = blackboard.get_plan_result(task_id, agent)
        if not plan or 'state_dict' not in plan:
            raise ValueError("未找到有效的 Plan 结果（缺少 state_dict）")

        # 读取 Guidance（如果有）
        guidance = blackboard.get_guidance(task_id, 'research')
        if guidance:
            logger.info(f"[{task_id}] 收到 Research Guidance: {guidance[:100]}...")
            blackboard.append_forum_log(task_id, agent, f"收到 Guidance，调整研究策略")

        # 调用 Agent 的 execute_research 方法
        from QueryEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        research_data = agent_instance.execute_research(plan, guidance=guidance)

        # 保存到 Blackboard
        blackboard.save_research_result(task_id, agent, research_data)
        blackboard.append_forum_log(task_id, agent, "Research 阶段完成")

        logger.info(f"[{task_id}] QueryEngine Research 完成")
        return research_data

    except Exception as exc:
        logger.error(f"[{task_id}] QueryEngine Research 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Research 阶段失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def query_report(self, task_id: str, query: str, agent: str = 'query') -> str:
    """
    QueryEngine - Report 阶段

    从 Blackboard 读取 Research（包含 state_dict），调用 Agent 的 generate_report() 方法

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        报告内容（Markdown/Text）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] QueryEngine Report 阶段开始")
        blackboard.set_agent_phase(task_id, agent, 'report')

        # 读取 Research 结果（必须包含 state_dict）
        research_data = blackboard.get_research_result(task_id, agent)
        if not research_data or 'state_dict' not in research_data:
            raise ValueError("未找到有效的 Research 结果（缺少 state_dict）")

        # 调用 Agent 的 generate_report 方法
        from QueryEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        report = agent_instance.generate_report(research_data)

        # 保存到 Blackboard
        blackboard.save_report_result(task_id, agent, report)
        blackboard.append_forum_log(task_id, agent, "Report 阶段完成")

        logger.info(f"[{task_id}] QueryEngine Report 完成")
        return report

    except Exception as exc:
        logger.error(f"[{task_id}] QueryEngine Report 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Report 阶段失败: {str(exc)}")
        raise


# ==================== MediaEngine 三阶段任务 ====================

@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def media_plan(self, task_id: str, query: str, agent: str = 'media') -> Dict[str, Any]:
    """
    MediaEngine - Plan 阶段

    调用 Agent 的 generate_plan() 方法生成研究计划

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        Plan 数据字典（包含 state_dict）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] MediaEngine Plan 阶段开始: {query}")
        blackboard.set_agent_phase(task_id, agent, 'plan')
        blackboard.append_forum_log(task_id, agent, f"开始 Plan 阶段: {query}")

        # 获取可能的 Guidance
        guidance = blackboard.get_guidance(task_id, 'plan')
        if guidance:
            logger.info(f"[{task_id}] 收到 Plan Guidance: {guidance[:100]}...")

        # 调用 Agent 的 generate_plan 方法
        from MediaEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        plan = agent_instance.generate_plan(query, guidance=guidance)

        # 保存到 Blackboard
        blackboard.save_plan_result(task_id, agent, plan)
        blackboard.append_forum_log(
            task_id, agent,
            f"Plan 完成，生成 {plan.get('paragraph_count', 0)} 个段落"
        )

        logger.info(f"[{task_id}] MediaEngine Plan 完成")
        return plan

    except Exception as exc:
        logger.error(f"[{task_id}] MediaEngine Plan 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Plan 阶段失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=1800, time_limit=1860)
def media_research(self, task_id: str, query: str, agent: str = 'media') -> Dict[str, Any]:
    """
    MediaEngine - Research 阶段

    从 Blackboard 读取 Plan（包含 state_dict），调用 Agent 的 execute_research() 方法

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        Research 数据字典（包含 state_dict）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] MediaEngine Research 阶段开始")
        blackboard.set_agent_phase(task_id, agent, 'research')

        # 读取 Plan（必须包含 state_dict）
        plan = blackboard.get_plan_result(task_id, agent)
        if not plan or 'state_dict' not in plan:
            raise ValueError("未找到有效的 Plan 结果（缺少 state_dict）")

        # 读取 Guidance
        guidance = blackboard.get_guidance(task_id, 'research')
        if guidance:
            logger.info(f"[{task_id}] 收到 Research Guidance: {guidance[:100]}...")
            blackboard.append_forum_log(task_id, agent, f"收到 Guidance")

        # 调用 Agent 的 execute_research 方法
        from MediaEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        research_data = agent_instance.execute_research(plan, guidance=guidance)

        # 保存到 Blackboard
        blackboard.save_research_result(task_id, agent, research_data)
        blackboard.append_forum_log(task_id, agent, "Research 阶段完成")

        logger.info(f"[{task_id}] MediaEngine Research 完成")
        return research_data

    except Exception as exc:
        logger.error(f"[{task_id}] MediaEngine Research 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Research 阶段失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def media_report(self, task_id: str, query: str, agent: str = 'media') -> str:
    """
    MediaEngine - Report 阶段

    从 Blackboard 读取 Research（包含 state_dict），调用 Agent 的 generate_report() 方法

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        报告内容（Markdown/Text）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] MediaEngine Report 阶段开始")
        blackboard.set_agent_phase(task_id, agent, 'report')

        # 读取 Research 结果（必须包含 state_dict）
        research_data = blackboard.get_research_result(task_id, agent)
        if not research_data or 'state_dict' not in research_data:
            raise ValueError("未找到有效的 Research 结果（缺少 state_dict）")

        # 调用 Agent 的 generate_report 方法
        from MediaEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        report = agent_instance.generate_report(research_data)

        # 保存到 Blackboard
        blackboard.save_report_result(task_id, agent, report)
        blackboard.append_forum_log(task_id, agent, "Report 阶段完成")

        logger.info(f"[{task_id}] MediaEngine Report 完成")
        return report

    except Exception as exc:
        logger.error(f"[{task_id}] MediaEngine Report 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Report 阶段失败: {str(exc)}")
        raise


# ==================== InsightEngine 三阶段任务 ====================

@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def insight_plan(self, task_id: str, query: str, agent: str = 'insight') -> Dict[str, Any]:
    """
    InsightEngine - Plan 阶段

    调用 Agent 的 generate_plan() 方法生成研究计划

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        Plan 数据字典（包含 state_dict）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] InsightEngine Plan 阶段开始: {query}")
        blackboard.set_agent_phase(task_id, agent, 'plan')
        blackboard.append_forum_log(task_id, agent, f"开始 Plan 阶段: {query}")

        # 获取可能的 Guidance
        guidance = blackboard.get_guidance(task_id, 'plan')
        if guidance:
            logger.info(f"[{task_id}] 收到 Plan Guidance: {guidance[:100]}...")

        # 调用 Agent 的 generate_plan 方法
        from InsightEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        plan = agent_instance.generate_plan(query, guidance=guidance)

        # 保存到 Blackboard
        blackboard.save_plan_result(task_id, agent, plan)
        blackboard.append_forum_log(
            task_id, agent,
            f"Plan 完成，生成 {plan.get('paragraph_count', 0)} 个段落"
        )

        logger.info(f"[{task_id}] InsightEngine Plan 完成")
        return plan

    except Exception as exc:
        logger.error(f"[{task_id}] InsightEngine Plan 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Plan 阶段失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=1800, time_limit=1860)
def insight_research(self, task_id: str, query: str, agent: str = 'insight') -> Dict[str, Any]:
    """
    InsightEngine - Research 阶段

    从 Blackboard 读取 Plan（包含 state_dict），调用 Agent 的 execute_research() 方法

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        Research 数据字典（包含 state_dict）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] InsightEngine Research 阶段开始")
        blackboard.set_agent_phase(task_id, agent, 'research')

        # 读取 Plan（必须包含 state_dict）
        plan = blackboard.get_plan_result(task_id, agent)
        if not plan or 'state_dict' not in plan:
            raise ValueError("未找到有效的 Plan 结果（缺少 state_dict）")

        # 读取 Guidance
        guidance = blackboard.get_guidance(task_id, 'research')
        if guidance:
            logger.info(f"[{task_id}] 收到 Research Guidance: {guidance[:100]}...")
            blackboard.append_forum_log(task_id, agent, f"收到 Guidance")

        # 调用 Agent 的 execute_research 方法
        from InsightEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        research_data = agent_instance.execute_research(plan, guidance=guidance)

        # 保存到 Blackboard
        blackboard.save_research_result(task_id, agent, research_data)
        blackboard.append_forum_log(task_id, agent, "Research 阶段完成")

        logger.info(f"[{task_id}] InsightEngine Research 完成")
        return research_data

    except Exception as exc:
        logger.error(f"[{task_id}] InsightEngine Research 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Research 阶段失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=600, time_limit=660)
def insight_report(self, task_id: str, query: str, agent: str = 'insight') -> str:
    """
    InsightEngine - Report 阶段

    从 Blackboard 读取 Research（包含 state_dict），调用 Agent 的 generate_report() 方法

    Args:
        task_id: 任务 ID
        query: 原始查询
        agent: Agent 名称

    Returns:
        报告内容（Markdown/Text）
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] InsightEngine Report 阶段开始")
        blackboard.set_agent_phase(task_id, agent, 'report')

        # 读取 Research 结果（必须包含 state_dict）
        research_data = blackboard.get_research_result(task_id, agent)
        if not research_data or 'state_dict' not in research_data:
            raise ValueError("未找到有效的 Research 结果（缺少 state_dict）")

        # 调用 Agent 的 generate_report 方法
        from InsightEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        report = agent_instance.generate_report(research_data)

        # 保存到 Blackboard
        blackboard.save_report_result(task_id, agent, report)
        blackboard.append_forum_log(task_id, agent, "Report 阶段完成")

        logger.info(f"[{task_id}] InsightEngine Report 完成")
        return report

    except Exception as exc:
        logger.error(f"[{task_id}] InsightEngine Report 失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"Report 阶段失败: {str(exc)}")
        raise


# ==================== 补充研究任务（可选）====================

@celery_app.task(bind=True, soft_time_limit=1200, time_limit=1260)
def query_supplemental_research(self, task_id: str, query: str, guidance: str, agent: str = 'query') -> Dict[str, Any]:
    """
    QueryEngine - 补充研究

    基于 Orchestrator 的 Guidance 执行额外一轮反思循环

    Args:
        task_id: 任务 ID
        query: 原始查询
        guidance: Orchestrator 提供的补充研究指导
        agent: Agent 名称

    Returns:
        更新后的 Research 数据字典
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] QueryEngine 补充研究开始")
        blackboard.append_forum_log(task_id, agent, f"开始补充研究: {guidance[:50]}...")

        # 读取当前 Research 结果
        research_data = blackboard.get_research_result(task_id, agent)
        if not research_data or 'state_dict' not in research_data:
            raise ValueError("未找到有效的 Research 结果（缺少 state_dict）")

        # 调用 Agent 的 execute_supplemental_research 方法
        from QueryEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        updated_research = agent_instance.execute_supplemental_research(research_data, guidance)

        # 更新 Blackboard
        blackboard.save_research_result(task_id, agent, updated_research)
        blackboard.append_forum_log(task_id, agent, "补充研究完成")

        logger.info(f"[{task_id}] QueryEngine 补充研究完成")
        return updated_research

    except Exception as exc:
        logger.error(f"[{task_id}] QueryEngine 补充研究失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"补充研究失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=1200, time_limit=1260)
def media_supplemental_research(self, task_id: str, query: str, guidance: str, agent: str = 'media') -> Dict[str, Any]:
    """
    MediaEngine - 补充研究

    基于 Orchestrator 的 Guidance 执行额外一轮反思循环
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] MediaEngine 补充研究开始")
        blackboard.append_forum_log(task_id, agent, f"开始补充研究: {guidance[:50]}...")

        research_data = blackboard.get_research_result(task_id, agent)
        if not research_data or 'state_dict' not in research_data:
            raise ValueError("未找到有效的 Research 结果（缺少 state_dict）")

        from MediaEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        updated_research = agent_instance.execute_supplemental_research(research_data, guidance)

        blackboard.save_research_result(task_id, agent, updated_research)
        blackboard.append_forum_log(task_id, agent, "补充研究完成")

        logger.info(f"[{task_id}] MediaEngine 补充研究完成")
        return updated_research

    except Exception as exc:
        logger.error(f"[{task_id}] MediaEngine 补充研究失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"补充研究失败: {str(exc)}")
        raise


@celery_app.task(bind=True, soft_time_limit=1200, time_limit=1260)
def insight_supplemental_research(self, task_id: str, query: str, guidance: str, agent: str = 'insight') -> Dict[str, Any]:
    """
    InsightEngine - 补充研究

    基于 Orchestrator 的 Guidance 执行额外一轮反思循环
    """
    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] InsightEngine 补充研究开始")
        blackboard.append_forum_log(task_id, agent, f"开始补充研究: {guidance[:50]}...")

        research_data = blackboard.get_research_result(task_id, agent)
        if not research_data or 'state_dict' not in research_data:
            raise ValueError("未找到有效的 Research 结果（缺少 state_dict）")

        from InsightEngine.agent import DeepSearchAgent
        agent_instance = DeepSearchAgent()
        updated_research = agent_instance.execute_supplemental_research(research_data, guidance)

        blackboard.save_research_result(task_id, agent, updated_research)
        blackboard.append_forum_log(task_id, agent, "补充研究完成")

        logger.info(f"[{task_id}] InsightEngine 补充研究完成")
        return updated_research

    except Exception as exc:
        logger.error(f"[{task_id}] InsightEngine 补充研究失败: {exc}")
        blackboard.append_forum_log(task_id, agent, f"补充研究失败: {str(exc)}")
        raise
