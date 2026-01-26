"""
Orchestrator - ForumEngine 编排与决策

实现 ForumEngine 作为 Orchestrator 的角色：
1. 在 Plan 阶段后评审所有 Agent 的计划
2. 在 Research 阶段后评审研究结果
3. 使用 LLM 进行决策（approve/revise/supplement）
4. 生成 Guidance 指导 Agent 调整
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple
from celery.utils.log import get_task_logger

from celery_app import celery_app
from tasks.blackboard import Blackboard

logger = get_task_logger(__name__)

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ==================== LLM 提示词模板 ====================

PLAN_REVIEW_PROMPT = """
你是一个研究项目的协调者，正在评审三个 Agent 的研究计划。

**当前日期**：{current_date}

**原始查询**：{query}

**Agent 计划**：

**QueryEngine**：
{query_plan}

**MediaEngine**：
{media_plan}

**InsightEngine**：
{insight_plan}

请分析这三个计划是否：
1. 充分覆盖了查询主题的各个方面
2. 计划之间是否互补，没有重大遗漏
3. 关键词和搜索策略是否合理

**请给出你的决策**：

- 如果计划整体合理，回复：APPROVE
- 如果需要调整，回复：REVISE，并说明调整建议

格式：
```
DECISION: [APPROVE/REVISE]
GUIDANCE: [如果是 REVISE，说明具体建议；否则留空]
```
"""


RESEARCH_REVIEW_PROMPT = """
你是一个研究项目的协调者，正在评审三个 Agent 的研究结果。

**当前日期**：{current_date}

**原始查询**：{query}

**研究结果摘要**：

**QueryEngine**：
{query_summary}

**MediaEngine**：
{media_summary}

**InsightEngine**：
{insight_summary}

请分析这三个研究结果是否：
1. 充分回答了原始查询
2. 内容质量是否达标
3. 是否需要补充更多信息

**请给出你的决策**：

- 如果研究结果充分，回复：APPROVE
- 如果需要补充，回复：SUPPLEMENT，并说明补充方向

注意：补充研究最多进行 1 轮，请慎重决策。

格式：
```
DECISION: [APPROVE/SUPPLEMENT]
GUIDANCE: [如果是 SUPPLEMENT，说明具体补充方向；否则留空]
```
"""


# ==================== Orchestrator 任务 ====================

@celery_app.task(bind=True, soft_time_limit=300, time_limit=360)
def orchestrate_plan(self, task_id: str, query: str, agents: List[str] = None) -> Dict[str, str]:
    """
    Orchestrate Plan 阶段评审

    收集所有 Agent 的 Plan，使用 LLM 评审，决定是否通过

    Args:
        task_id: 任务 ID
        query: 原始查询
        agents: Agent 列表（默认 ['query', 'media', 'insight']）

    Returns:
        决策结果 {'decision': 'approve/revise', 'guidance': '...'}
    """
    if agents is None:
        agents = ['query', 'media', 'insight']

    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] Orchestrator 开始评审 Plan 阶段")
        blackboard.append_forum_log(task_id, 'orchestrator', '开始评审所有 Agent 的 Plan')

        # 收集所有 Agent 的 Plan
        all_plans = blackboard.get_all_plans(task_id, agents)

        if len(all_plans) < len(agents):
            logger.warning(f"[{task_id}] 只收集到 {len(all_plans)}/{len(agents)} 个 Plan")

        # 构造 LLM 提示词
        prompt = PLAN_REVIEW_PROMPT.format(
            current_date=datetime.now().strftime('%Y年%m月%d日'),
            query=query,
            query_plan=_format_plan(all_plans.get('query', {})),
            media_plan=_format_plan(all_plans.get('media', {})),
            insight_plan=_format_plan(all_plans.get('insight', {}))
        )

        # 调用 LLM 进行决策
        decision, guidance = _call_llm_for_decision(prompt, task_id, 'plan')

        # 保存 Guidance
        if guidance:
            blackboard.save_guidance(task_id, 'plan', guidance)
            blackboard.append_forum_log(task_id, 'orchestrator', f'Plan 评审：{decision}，生成 Guidance')
        else:
            blackboard.append_forum_log(task_id, 'orchestrator', f'Plan 评审：{decision}')

        logger.info(f"[{task_id}] Orchestrator Plan 评审完成：{decision}")

        return {
            'decision': decision,
            'guidance': guidance or ''
        }

    except Exception as exc:
        logger.error(f"[{task_id}] Orchestrator Plan 评审失败: {exc}")
        blackboard.append_forum_log(task_id, 'orchestrator', f'Plan 评审失败：{str(exc)}，自动通过')

        # 容错：失败时自动通过
        return {
            'decision': 'approve',
            'guidance': ''
        }


@celery_app.task(bind=True, soft_time_limit=300, time_limit=360)
def orchestrate_research(self, task_id: str, query: str, agents: List[str] = None) -> Dict[str, str]:
    """
    Orchestrate Research 阶段评审

    收集所有 Agent 的 Research 结果，使用 LLM 评审，决定是否需要补充

    Args:
        task_id: 任务 ID
        query: 原始查询
        agents: Agent 列表

    Returns:
        决策结果 {'decision': 'approve/supplement', 'guidance': '...'}
    """
    if agents is None:
        agents = ['query', 'media', 'insight']

    blackboard = Blackboard()

    try:
        logger.info(f"[{task_id}] Orchestrator 开始评审 Research 阶段")
        blackboard.append_forum_log(task_id, 'orchestrator', '开始评审所有 Agent 的 Research')

        # 检查补充轮次
        current_round = blackboard.get_supplement_round(task_id)
        if current_round >= 1:
            logger.info(f"[{task_id}] 已达到最大补充轮次 ({current_round})，强制通过")
            blackboard.append_forum_log(task_id, 'orchestrator', '已达到最大补充轮次，强制通过')
            return {
                'decision': 'approve',
                'guidance': ''
            }

        # 收集所有 Agent 的 Research 结果
        all_research = blackboard.get_all_research(task_id, agents)

        if len(all_research) < len(agents):
            logger.warning(f"[{task_id}] 只收集到 {len(all_research)}/{len(agents)} 个 Research 结果")

        # 构造 LLM 提示词
        prompt = RESEARCH_REVIEW_PROMPT.format(
            current_date=datetime.now().strftime('%Y年%m月%d日'),
            query=query,
            query_summary=_summarize_research(all_research.get('query', {})),
            media_summary=_summarize_research(all_research.get('media', {})),
            insight_summary=_summarize_research(all_research.get('insight', {}))
        )

        # 调用 LLM 进行决策
        decision, guidance = _call_llm_for_decision(prompt, task_id, 'research')

        # 如果决定补充，记录轮次
        if decision == 'supplement':
            new_round = blackboard.increment_supplement_round(task_id)
            logger.info(f"[{task_id}] 触发补充研究，轮次：{new_round}")
            blackboard.append_forum_log(task_id, 'orchestrator', f'Research 评审：需要补充（轮次 {new_round}）')

            # 保存 Guidance
            if guidance:
                blackboard.save_guidance(task_id, 'research', guidance)
        else:
            blackboard.append_forum_log(task_id, 'orchestrator', f'Research 评审：{decision}')

        logger.info(f"[{task_id}] Orchestrator Research 评审完成：{decision}")

        return {
            'decision': decision,
            'guidance': guidance or ''
        }

    except Exception as exc:
        logger.error(f"[{task_id}] Orchestrator Research 评审失败: {exc}")
        blackboard.append_forum_log(task_id, 'orchestrator', f'Research 评审失败：{str(exc)}，自动通过')

        # 容错：失败时自动通过
        return {
            'decision': 'approve',
            'guidance': ''
        }


# ==================== LLM 调用封装 ====================

def _call_llm_for_decision(prompt: str, task_id: str, phase: str) -> Tuple[str, str]:
    """
    调用 LLM 进行决策

    Args:
        prompt: LLM 提示词
        task_id: 任务 ID（用于日志）
        phase: 阶段名称（plan/research）

    Returns:
        (decision, guidance) 元组
    """
    try:
        # 使用 Orchestrator 专用的 LLM 配置，fallback 到 REPORT_ENGINE（qwen3-max）
        import os
        from openai import OpenAI
        from dotenv import load_dotenv

        # 确保加载环境变量
        load_dotenv()

        # 优先使用 ORCHESTRATOR 配置，否则使用 REPORT_ENGINE 配置
        api_key = os.getenv('ORCHESTRATOR_API_KEY') or os.getenv('REPORT_ENGINE_API_KEY') or os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('ORCHESTRATOR_BASE_URL') or os.getenv('REPORT_ENGINE_BASE_URL')
        model_name = os.getenv('ORCHESTRATOR_MODEL_NAME') or os.getenv('REPORT_ENGINE_MODEL_NAME', 'qwen3-max')

        if not api_key:
            logger.warning(f"[{task_id}] 未配置 ORCHESTRATOR/REPORT_ENGINE API_KEY，自动通过")
            return 'approve', ''

        logger.info(f"[{task_id}] 开始调用 LLM ({model_name}) 进行 {phase} 阶段决策...")

        # 创建客户端（不重试）
        client_kwargs = {"api_key": api_key, "max_retries": 0}
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)

        # 构造消息（简化 prompt）
        system_prompt = "你是一个研究项目的协调者，负责评审 Agent 的工作成果。请简洁回复。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            # 调用 API，30秒超时，限制输出长度
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                timeout=30.0,
                max_tokens=300,  # 限制输出长度，加快响应
                temperature=0.3  # 降低随机性
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content or ""
                logger.info(f"[{task_id}] LLM 响应已收到（{len(content)} 字符）")

                # 解析响应
                decision, guidance = _parse_llm_response(content)
                logger.info(f"[{task_id}] LLM 决策：{decision}")
                return decision, guidance

        except Exception as e:
            error_msg = str(e).lower()

            # 检测内容审查错误，使用 DeepSeek 备用模型
            if 'inappropriate content' in error_msg or 'content policy' in error_msg:
                logger.warning(f"[{task_id}] Orchestrator 内容审查触发，尝试使用 DeepSeek 备用模型...")

                deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
                deepseek_base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
                deepseek_model = os.getenv('DEEPSEEK_MODEL_NAME', 'deepseek-chat')

                if not deepseek_api_key:
                    logger.error(f"[{task_id}] DeepSeek 配置未设置，自动通过")
                    return 'approve', ''

                try:
                    deepseek_client = OpenAI(
                        api_key=deepseek_api_key,
                        base_url=deepseek_base_url,
                        max_retries=0,
                    )

                    response = deepseek_client.chat.completions.create(
                        model=deepseek_model,
                        messages=messages,
                        timeout=30.0,
                        max_tokens=300,
                        temperature=0.3
                    )

                    if response.choices and response.choices[0].message:
                        content = response.choices[0].message.content or ""
                        logger.info(f"[{task_id}] DeepSeek 备用模型调用成功")
                        decision, guidance = _parse_llm_response(content)
                        return decision, guidance

                except Exception as deepseek_error:
                    logger.error(f"[{task_id}] DeepSeek 备用模型也失败: {deepseek_error}")
                    return 'approve', ''

            # 其他错误，记录并 fallback
            raise

        # 空响应，fallback
        logger.warning(f"[{task_id}] LLM 返回空响应，自动通过")
        return 'approve', ''

    except Exception as exc:
        logger.error(f"[{task_id}] LLM 调用失败: {exc}，自动通过")
        # 容错：LLM 失败时自动 approve
        return 'approve', ''


def _parse_llm_response(content: str) -> Tuple[str, str]:
    """
    解析 LLM 响应，提取决策和指导

    Args:
        content: LLM 响应内容

    Returns:
        (decision, guidance) 元组
    """
    decision = 'approve'  # 默认
    guidance = ''

    lines = content.strip().split('\n')
    for line in lines:
        line = line.strip()

        if line.startswith('DECISION:'):
            decision_text = line.split(':', 1)[1].strip().lower()
            if 'revise' in decision_text:
                decision = 'revise'
            elif 'supplement' in decision_text:
                decision = 'supplement'
            else:
                decision = 'approve'

        elif line.startswith('GUIDANCE:'):
            guidance = line.split(':', 1)[1].strip()

    return decision, guidance


# ==================== 辅助函数 ====================

def _format_plan(plan: Dict[str, Any]) -> str:
    """格式化 Plan 为可读文本"""
    if not plan:
        return "(无 Plan)"

    lines = []
    if 'keywords' in plan:
        lines.append(f"关键词：{', '.join(plan['keywords'])}")
    if 'search_strategy' in plan:
        lines.append(f"搜索策略：{plan['search_strategy']}")
    if 'report_structure' in plan:
        lines.append(f"报告结构：{', '.join(plan['report_structure'])}")
    if 'media_types' in plan:
        lines.append(f"媒体类型：{', '.join(plan['media_types'])}")
    if 'analysis_aspects' in plan:
        lines.append(f"分析维度：{', '.join(plan['analysis_aspects'])}")

    return '\n'.join(lines) if lines else str(plan)


def _summarize_research(research: Dict[str, Any]) -> str:
    """生成 Research 结果摘要"""
    if not research:
        return "(无研究结果)"

    # 方式1: 检查 paragraphs 结构 (Agent 实际使用的格式)
    paragraphs = research.get('paragraphs', [])
    if paragraphs:
        summaries = []
        for p in paragraphs[:3]:  # 最多取前3个段落
            title = p.get('title', '')
            content = p.get('latest_summary', '') or p.get('summary', '')
            if title and content:
                # 取每个段落的前200字符
                summaries.append(f"【{title}】{content[:200]}...")
        if summaries:
            return '\n'.join(summaries)

    # 方式2: 兼容旧的 result 字段格式
    result = research.get('result', '')
    if isinstance(result, str) and result:
        summary = result[:500]
        if len(result) > 500:
            summary += '...'
        return summary

    # 方式3: 直接转换整个对象
    return str(research)[:500] if research else "(无研究结果)"
