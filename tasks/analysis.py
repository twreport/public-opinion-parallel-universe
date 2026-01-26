"""
主分析任务模块

使用 Celery chord 编排任务流程：
1. 3 个 Agent 并行执行研究任务（group）
2. 全部完成后触发报告生成（callback）

支持：
- 查询结果缓存（任务去重）
- 任务状态持久化
- 过期数据清理
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from celery import chord, group
from celery.utils.log import get_task_logger

from celery_app import celery_app
from .agents import query_research, media_research, insight_research
from .report import generate_report
from tasks.blackboard import Blackboard

logger = get_task_logger(__name__)

# 确保项目根目录在 Python 路径中（解决 fork 进程的导入问题）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 相似度缓存配置
SIMILARITY_THRESHOLD = 0.80  # 相似度阈值，超过此值认为是相似查询（0.8 = 80% 词重叠）
MAX_CACHE_SCAN = 100  # 最多扫描多少个缓存条目


def _tokenize(text: str) -> set:
    """
    对文本进行分词，返回词集合

    使用 jieba 分词，过滤掉停用词和单字符词
    """
    try:
        import jieba
        # 分词并过滤
        words = jieba.lcut(text)
        # 过滤单字符词和常见停用词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        return {w for w in words if len(w) > 1 and w not in stopwords}
    except ImportError:
        # 如果没有 jieba，使用简单的字符级分割
        return set(text)


def _jaccard_similarity(set1: set, set2: set) -> float:
    """计算两个集合的 Jaccard 相似度"""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def get_redis_url() -> str:
    """获取 Redis URL，优先使用环境变量"""
    env_url = os.getenv('REDIS_URL')
    if env_url:
        return env_url
    try:
        from config import settings
        return settings.REDIS_URL
    except ImportError:
        return 'redis://127.0.0.1:6379/10'


REDIS_URL = get_redis_url()


def _get_redis_client():
    """获取 Redis 客户端"""
    import redis
    return redis.from_url(REDIS_URL)


def update_task_status(task_id: str, status: str, progress: int,
                       result: dict = None, error: str = None):
    """更新任务状态到 Redis"""
    try:
        r = _get_redis_client()
        status_key = f"task:{task_id}:status"

        data = {
            'status': status,
            'progress': progress,
            'updated_at': datetime.now().isoformat()
        }

        if result:
            result_key = f"task:{task_id}:result"
            r.set(result_key, json.dumps(result, ensure_ascii=False), ex=86400)
            data['has_result'] = True

        if error:
            data['error'] = error

        r.set(status_key, json.dumps(data), ex=86400)

    except Exception as exc:
        logger.warning(f"[{task_id}] 更新任务状态失败: {exc}")


def check_query_cache(query: str) -> dict | None:
    """
    检查查询结果缓存（支持相似度匹配）

    匹配策略：
    1. 精确匹配：查询完全相同
    2. 相似匹配：基于分词的 Jaccard 相似度 > 阈值

    Args:
        query: 查询内容

    Returns:
        缓存的结果，不存在则返回 None
    """
    try:
        r = _get_redis_client()

        # 1. 先尝试精确匹配
        query_hash = hashlib.md5(query.encode()).hexdigest()
        cache_key = f"cache:query:{query_hash}"
        cached = r.get(cache_key)
        if cached:
            logger.info(f"缓存精确命中: {query[:30]}...")
            return json.loads(cached)

        # 2. 尝试相似度匹配
        query_tokens = _tokenize(query)
        if not query_tokens:
            return None

        # 获取缓存索引
        index_keys = r.keys("cache:query:*:meta")
        if not index_keys:
            return None

        best_match = None
        best_similarity = 0.0

        for meta_key in index_keys[:MAX_CACHE_SCAN]:
            try:
                meta_data = r.get(meta_key)
                if not meta_data:
                    continue
                meta = json.loads(meta_data)
                cached_tokens = set(meta.get('tokens', []))

                similarity = _jaccard_similarity(query_tokens, cached_tokens)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = meta
            except Exception:
                continue

        # 如果相似度超过阈值，返回缓存结果
        if best_match and best_similarity >= SIMILARITY_THRESHOLD:
            result_key = best_match.get('result_key')
            if result_key:
                cached_result = r.get(result_key)
                if cached_result:
                    logger.info(f"缓存相似命中 (相似度={best_similarity:.2f}): '{query[:20]}...' ≈ '{best_match.get('query', '')[:20]}...'")
                    return json.loads(cached_result)

    except Exception as exc:
        logger.warning(f"检查查询缓存失败: {exc}")

    return None


@celery_app.task(bind=True)
def analyze_task(self, task_id: str, query: str) -> str:
    """
    主分析任务：编排 3 个 Agent 并行执行，完成后生成报告

    使用 Celery chord 实现：
    - group: 3 个 Agent 并行执行
    - callback: 全部完成后触发报告生成

    Args:
        task_id: 任务 ID
        query: 研究查询

    Returns:
        任务 ID
    """
    logger.info(f"[{task_id}] 开始分析任务: {query}")

    # 更新任务状态：开始
    update_task_status(task_id, 'running', 5)

    # 检查缓存（任务去重）
    cached_result = check_query_cache(query)
    if cached_result:
        logger.info(f"[{task_id}] 命中缓存，直接返回")
        update_task_status(task_id, 'completed', 100, result=cached_result)
        return task_id

    # 使用 chord 编排任务流程
    # group: 3 个 Agent 并行执行
    # callback: 全部完成后触发 generate_report
    #
    # 注意：chord callback 会将 group 的所有结果作为第一个参数传入
    # 所以 generate_report 的签名是 (agent_results, task_id, query)
    workflow = chord(
        group(
            query_research.s(task_id, query),
            media_research.s(task_id, query),
            insight_research.s(task_id, query),
        ),
        generate_report.s(task_id, query)
    )

    # 异步执行工作流
    workflow.apply_async()

    logger.info(f"[{task_id}] 工作流已提交")

    return task_id


@celery_app.task
def cleanup_expired_tasks():
    """
    清理过期的任务数据

    定时任务（由 Celery Beat 调度），清理超过7天的任务记录。
    """
    logger.info("开始清理过期任务数据")

    try:
        r = _get_redis_client()

        # 获取所有任务 ID
        task_ids = r.zrangebyscore(
            "tasks:all",
            '-inf',
            datetime.now().timestamp() - 7 * 86400  # 7天前
        )

        cleaned = 0
        for task_id in task_ids:
            if isinstance(task_id, bytes):
                task_id = task_id.decode()

            # 删除任务相关的所有 key
            keys_to_delete = [
                f"task:{task_id}:meta",
                f"task:{task_id}:status",
                f"task:{task_id}:result",
                f"task:{task_id}:agent:query",
                f"task:{task_id}:agent:media",
                f"task:{task_id}:agent:insight",
            ]

            for key in keys_to_delete:
                r.delete(key)

            # 从任务列表中移除
            r.zrem("tasks:all", task_id)
            cleaned += 1

        logger.info(f"清理完成，共清理 {cleaned} 个过期任务")

    except Exception as exc:
        logger.error(f"清理过期任务失败: {exc}")


# ==================== 阶段性分析任务（Phase-based Workflow）====================

@celery_app.task(bind=True)
def analyze_task_phased(self, task_id: str, query: str) -> str:
    """
    阶段性分析任务 - Orchestrator 模式

    将分析流程拆分为三个阶段：
    1. Plan - 所有 Agent 生成研究计划
    2. Research - 所有 Agent 执行研究（可补充）
    3. Report - 生成最终报告

    每个阶段结束后，Orchestrator 进行 LLM 决策

    Args:
        task_id: 任务 ID
        query: 研究查询

    Returns:
        任务 ID
    """
    logger.info(f"[{task_id}] 开始阶段性分析任务: {query}")

    # 初始化 Blackboard
    blackboard = Blackboard()
    blackboard.append_forum_log(task_id, 'system', f'开始阶段性分析: {query}')

    # 更新任务状态：开始
    update_task_status(task_id, 'running', 5)

    # 检查缓存（任务去重）
    cached_result = check_query_cache(query)
    if cached_result:
        logger.info(f"[{task_id}] 命中缓存，直接返回")
        update_task_status(task_id, 'completed', 100, result=cached_result)
        return task_id

    # 启动 Phase 1: Plan
    # 使用 chord 等待所有 Agent 完成 Plan，然后触发 Orchestrator 评审
    from tasks.agents_phased import query_plan, media_plan, insight_plan
    from tasks.orchestrator import orchestrate_plan

    workflow_phase1 = chord(
        group(
            query_plan.s(task_id, query, 'query'),
            media_plan.s(task_id, query, 'media'),
            insight_plan.s(task_id, query, 'insight'),
        ),
        on_all_plans_complete.s(task_id, query)
    )

    # 异步执行 Phase 1
    workflow_phase1.apply_async()

    logger.info(f"[{task_id}] Phase 1 (Plan) 已提交")
    update_task_status(task_id, 'phase1_plan', 20)

    return task_id


@celery_app.task(bind=True)
def on_all_plans_complete(self, plan_results: list, task_id: str, query: str):
    """
    所有 Agent Plan 完成后的回调

    触发 Orchestrator 评审，然后启动 Phase 2

    Args:
        plan_results: 所有 Agent 的 Plan 结果
        task_id: 任务 ID
        query: 原始查询
    """
    logger.info(f"[{task_id}] 所有 Plan 完成，开始 Orchestrator 评审")

    blackboard = Blackboard()
    blackboard.append_forum_log(task_id, 'system', 'Phase 1 完成，等待 Orchestrator 评审')

    update_task_status(task_id, 'orchestrating_plan', 35)

    # 调用 Orchestrator 评审
    from tasks.orchestrator import orchestrate_plan

    # 链式调用：orchestrate_plan -> trigger_phase2_research
    chain_workflow = (
        orchestrate_plan.s(task_id, query) |
        trigger_phase2_research.s(task_id, query)
    )

    chain_workflow.apply_async()


@celery_app.task(bind=True)
def trigger_phase2_research(self, orchestrate_result: dict, task_id: str, query: str):
    """
    触发 Phase 2: Research

    基于 Orchestrator 的决策启动 Research 阶段

    Args:
        orchestrate_result: Orchestrator 决策结果
        task_id: 任务 ID
        query: 原始查询
    """
    logger.info(f"[{task_id}] 触发 Phase 2 (Research)")

    blackboard = Blackboard()

    decision = orchestrate_result.get('decision', 'approve')
    guidance = orchestrate_result.get('guidance', '')

    if decision == 'revise':
        # 第一期只实现 approve，revise 留作扩展
        logger.warning(f"[{task_id}] Orchestrator 建议 revise，但第一期未实现，自动 approve")
        blackboard.append_forum_log(task_id, 'system', 'Plan 需要调整，但自动通过（未实现 revise）')

    blackboard.append_forum_log(task_id, 'system', f'开始 Phase 2 (Research)')

    update_task_status(task_id, 'phase2_research', 40)

    # 启动 Research 阶段
    from tasks.agents_phased import query_research, media_research, insight_research

    workflow_phase2 = chord(
        group(
            query_research.s(task_id, query, 'query'),
            media_research.s(task_id, query, 'media'),
            insight_research.s(task_id, query, 'insight'),
        ),
        on_all_research_complete.s(task_id, query)
    )

    workflow_phase2.apply_async()

    logger.info(f"[{task_id}] Phase 2 (Research) 已提交")


@celery_app.task(bind=True)
def on_all_research_complete(self, research_results: list, task_id: str, query: str):
    """
    所有 Agent Research 完成后的回调

    触发 Orchestrator 评审，决定是否补充或进入 Phase 3

    Args:
        research_results: 所有 Agent 的 Research 结果
        task_id: 任务 ID
        query: 原始查询
    """
    logger.info(f"[{task_id}] 所有 Research 完成，开始 Orchestrator 评审")

    blackboard = Blackboard()
    blackboard.append_forum_log(task_id, 'system', 'Phase 2 完成，等待 Orchestrator 评审')

    update_task_status(task_id, 'orchestrating_research', 65)

    # 调用 Orchestrator 评审
    from tasks.orchestrator import orchestrate_research

    chain_workflow = (
        orchestrate_research.s(task_id, query) |
        handle_research_decision.s(task_id, query)
    )

    chain_workflow.apply_async()


@celery_app.task(bind=True)
def handle_research_decision(self, orchestrate_result: dict, task_id: str, query: str):
    """
    处理 Research 阶段的 Orchestrator 决策

    如果需要 supplement，触发补充研究
    如果 approve，进入 Phase 3: Report

    Args:
        orchestrate_result: Orchestrator 决策结果
        task_id: 任务 ID
        query: 原始查询
    """
    logger.info(f"[{task_id}] 处理 Research 决策")

    blackboard = Blackboard()

    decision = orchestrate_result.get('decision', 'approve')
    guidance = orchestrate_result.get('guidance', '')

    if decision == 'supplement':
        logger.info(f"[{task_id}] 需要补充研究")
        blackboard.append_forum_log(task_id, 'system', f'需要补充研究，Guidance: {guidance}')

        # 保存补充指导
        if guidance:
            blackboard.save_guidance(task_id, 'research', guidance)

        # 触发补充研究（再次执行 Research，Agent 会读取 Guidance）
        update_task_status(task_id, 'phase2_supplement', 70)

        from tasks.agents_phased import query_research, media_research, insight_research

        workflow_supplement = chord(
            group(
                query_research.s(task_id, query, 'query'),
                media_research.s(task_id, query, 'media'),
                insight_research.s(task_id, query, 'insight'),
            ),
            trigger_phase3_report.s(task_id, query)  # 补充后直接进入 Report
        )

        workflow_supplement.apply_async()

        logger.info(f"[{task_id}] 补充研究已提交")

    else:
        # Approve，直接进入 Phase 3
        logger.info(f"[{task_id}] Research 通过，进入 Phase 3")
        blackboard.append_forum_log(task_id, 'system', 'Research 通过，开始生成报告')

        trigger_phase3_report.apply_async(args=([], task_id, query))


@celery_app.task(bind=True)
def trigger_phase3_report(self, research_results: list, task_id: str, query: str):
    """
    触发 Phase 3: Report

    收集所有 Agent 的报告，生成最终汇总报告

    Args:
        research_results: Research 结果（可能为空）
        task_id: 任务 ID
        query: 原始查询
    """
    logger.info(f"[{task_id}] 触发 Phase 3 (Report)")

    blackboard = Blackboard()
    blackboard.append_forum_log(task_id, 'system', '开始 Phase 3 (Report)')

    update_task_status(task_id, 'phase3_report', 75)

    # 启动 Report 阶段
    from tasks.agents_phased import query_report, media_report, insight_report

    workflow_phase3 = chord(
        group(
            query_report.s(task_id, query, 'query'),
            media_report.s(task_id, query, 'media'),
            insight_report.s(task_id, query, 'insight'),
        ),
        generate_final_report.s(task_id, query)
    )

    workflow_phase3.apply_async()

    logger.info(f"[{task_id}] Phase 3 (Report) 已提交")


@celery_app.task(bind=True)
def generate_final_report(self, report_results: list, task_id: str, query: str):
    """
    生成最终汇总报告

    收集所有 Agent 的报告 + Forum 日志，生成最终 IR JSON

    Args:
        report_results: 所有 Agent 的报告内容
        task_id: 任务 ID
        query: 原始查询
    """
    logger.info(f"[{task_id}] 开始生成最终报告")

    blackboard = Blackboard()
    blackboard.append_forum_log(task_id, 'system', '开始生成最终报告')

    update_task_status(task_id, 'generating_final_report', 85)

    # 获取 Forum 日志（精简摘要，控制长度）
    forum_log = blackboard.get_forum_log_summary(task_id, max_chars=2000)

    # 调用 ReportEngine 生成报告（传递 forum_log）
    from tasks.report import generate_report_with_forum

    generate_report_with_forum.apply_async(
        args=(report_results, task_id, query, forum_log)
    )

    logger.info(f"[{task_id}] 最终报告生成任务已提交")
