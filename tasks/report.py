"""
报告生成任务模块

汇总各 Agent 的研究结果，调用 ReportEngine 生成最终的 IR JSON 报告。
"""

import os
import sys
import json
from datetime import datetime
from celery.utils.log import get_task_logger

from celery_app import celery_app

logger = get_task_logger(__name__)

# 确保项目根目录在 Python 路径中（解决 fork 进程的导入问题）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


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
    """
    更新任务状态到 Redis

    Args:
        task_id: 任务 ID
        status: 状态 (pending/running/generating_report/completed/failed)
        progress: 进度百分比 (0-100)
        result: 任务结果（IR JSON）
        error: 错误信息
    """
    try:
        r = _get_redis_client()
        status_key = f"task:{task_id}:status"

        data = {
            'status': status,
            'progress': progress,
            'updated_at': datetime.now().isoformat()
        }

        if result:
            # 结果单独存储（可能很大）
            result_key = f"task:{task_id}:result"
            r.set(result_key, json.dumps(result, ensure_ascii=False), ex=86400)
            data['has_result'] = True

        if error:
            data['error'] = error

        r.set(status_key, json.dumps(data), ex=86400)

    except Exception as exc:
        logger.warning(f"[{task_id}] 更新任务状态失败: {exc}")


@celery_app.task(bind=True)
def generate_report(self, agent_results: list, task_id: str, query: str) -> dict:
    """
    汇总各 Agent 结果，生成最终报告

    使用 Celery chord 时，agent_results 是前置任务组的返回值列表。

    Args:
        agent_results: 各 Agent 的研究结果列表
        task_id: 任务 ID
        query: 原始查询

    Returns:
        完整的 IR JSON 报告
    """
    try:
        logger.info(f"[{task_id}] 开始生成报告，收到 {len(agent_results)} 个 Agent 结果")

        # 更新状态：正在生成报告
        update_task_status(task_id, 'generating_report', 80)

        # 提取各 Agent 的报告内容
        reports = []
        failed_engines = []

        for result in agent_results:
            if result and result.get('status') == 'completed':
                report_content = result.get('report', '')
                if report_content:
                    reports.append(report_content)
            else:
                # 记录失败的 Agent
                engine = result.get('engine', 'Unknown') if result else 'Unknown'
                failed_engines.append(engine)

        if not reports:
            error_msg = "没有可用的 Agent 报告"
            if failed_engines:
                error_msg += f"，失败的引擎: {', '.join(failed_engines)}"
            logger.error(f"[{task_id}] {error_msg}")
            update_task_status(task_id, 'failed', 0, error=error_msg)
            raise ValueError(error_msg)

        logger.info(f"[{task_id}] 有效报告数: {len(reports)}")
        if failed_engines:
            logger.warning(f"[{task_id}] 部分引擎失败: {failed_engines}")

        # 调用 ReportEngine 生成最终报告
        from ReportEngine.agent import ReportAgent
        report_agent = ReportAgent()

        # generate_report 方法接受查询和报告列表
        # 返回的是 HTML 字符串，我们需要获取 IR JSON
        ir_json = report_agent.generate_report(
            query=query,
            reports=reports,
            forum_logs="",
            save_report=False
        )

        # 如果返回的是字符串（HTML），转换为简单的 IR 结构
        if isinstance(ir_json, str):
            ir_json = {
                'metadata': {
                    'query': query,
                    'title': f'{query} 分析报告',
                    'generatedAt': datetime.now().isoformat()
                },
                'summary': {
                    'highlights': [f'基于 {len(reports)} 个引擎的研究结果生成']
                },
                'content': ir_json,
                'sources': [
                    {'engine': 'QueryEngine', 'count': 1 if any('QueryEngine' not in failed_engines for _ in [1]) else 0},
                    {'engine': 'MediaEngine', 'count': 1 if any('MediaEngine' not in failed_engines for _ in [1]) else 0},
                    {'engine': 'InsightEngine', 'count': 1 if any('InsightEngine' not in failed_engines for _ in [1]) else 0},
                ]
            }

        # 更新完成状态
        update_task_status(task_id, 'completed', 100, result=ir_json)

        logger.info(f"[{task_id}] 报告生成完成")

        # 设置查询结果缓存
        _set_query_cache(query, ir_json)

        return ir_json

    except ValueError:
        # 已经更新了状态，直接抛出
        raise

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"[{task_id}] 报告生成失败: {error_msg}")
        update_task_status(task_id, 'failed', 0, error=error_msg)
        raise


def _tokenize(text: str) -> list:
    """
    对文本进行分词，返回词列表

    使用 jieba 分词，过滤掉停用词和单字符词
    """
    try:
        import jieba
        # 分词并过滤
        words = jieba.lcut(text)
        # 过滤单字符词和常见停用词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        return [w for w in words if len(w) > 1 and w not in stopwords]
    except ImportError:
        # 如果没有 jieba，使用简单的字符级分割
        return list(text)


def _set_query_cache(query: str, result: dict, ttl: int = 86400):
    """
    设置查询结果缓存（支持相似度匹配）

    用于任务去重，相同或相似查询可直接返回缓存结果。

    存储两个 key：
    1. cache:query:{hash} - 存储完整结果（用于精确匹配）
    2. cache:query:{hash}:meta - 存储查询元数据（用于相似度匹配）

    Args:
        query: 查询内容
        result: 结果数据
        ttl: 缓存过期时间（秒）
    """
    try:
        import hashlib
        r = _get_redis_client()
        query_hash = hashlib.md5(query.encode()).hexdigest()

        # 1. 存储完整结果（用于精确匹配）
        cache_key = f"cache:query:{query_hash}"
        r.set(cache_key, json.dumps(result, ensure_ascii=False), ex=ttl)

        # 2. 存储元数据（用于相似度匹配）
        tokens = _tokenize(query)
        meta = {
            'query': query,
            'tokens': tokens,
            'result_key': cache_key,
            'created_at': datetime.now().isoformat()
        }
        meta_key = f"cache:query:{query_hash}:meta"
        r.set(meta_key, json.dumps(meta, ensure_ascii=False), ex=ttl)

        logger.info(f"查询缓存已设置: '{query[:30]}...' (tokens: {len(tokens)})")

    except Exception as exc:
        logger.warning(f"设置查询缓存失败: {exc}")


@celery_app.task(bind=True)
def generate_report_with_forum(self, agent_results: list, task_id: str, query: str, forum_log: str = "") -> dict:
    """
    汇总各 Agent 结果和 Forum 日志，生成最终报告

    这是阶段性任务的报告生成函数，包含 Forum 讨论日志

    Args:
        agent_results: 各 Agent 的报告内容列表
        task_id: 任务 ID
        query: 原始查询
        forum_log: Forum 讨论日志文本

    Returns:
        完整的 IR JSON 报告
    """
    try:
        logger.info(f"[{task_id}] 开始生成最终报告（含 Forum 日志），收到 {len(agent_results)} 个 Agent 报告")

        # 更新状态：正在生成报告
        update_task_status(task_id, 'generating_final_report', 85)

        # 提取报告内容
        reports = []
        for result in agent_results:
            if result:
                # 阶段性任务返回的是字符串（报告内容），不是字典
                if isinstance(result, str):
                    reports.append(result)
                elif isinstance(result, dict) and result.get('report'):
                    reports.append(result['report'])

        if not reports:
            error_msg = "没有可用的 Agent 报告"
            logger.error(f"[{task_id}] {error_msg}")
            update_task_status(task_id, 'failed', 0, error=error_msg)
            raise ValueError(error_msg)

        logger.info(f"[{task_id}] 有效报告数: {len(reports)}")
        if forum_log:
            logger.info(f"[{task_id}] Forum 日志长度: {len(forum_log)} 字符")

        # 调用 ReportEngine 生成最终报告
        from ReportEngine.agent import ReportAgent
        report_agent = ReportAgent()

        # 传递 forum_log
        ir_json = report_agent.generate_report(
            query=query,
            reports=reports,
            forum_logs=forum_log,
            save_report=False
        )

        # 如果返回的是字符串（HTML），转换为简单的 IR 结构
        if isinstance(ir_json, str):
            ir_json = {
                'metadata': {
                    'query': query,
                    'title': f'{query} 分析报告',
                    'generatedAt': datetime.now().isoformat(),
                    'phased': True,  # 标记为阶段性任务
                    'hasForumLog': bool(forum_log)
                },
                'summary': {
                    'highlights': [f'基于 {len(reports)} 个引擎的研究结果生成']
                },
                'content': ir_json,
                'forum_log': forum_log if forum_log else None,
                'sources': [
                    {'engine': 'QueryEngine', 'count': 1},
                    {'engine': 'MediaEngine', 'count': 1},
                    {'engine': 'InsightEngine', 'count': 1},
                ]
            }
        else:
            # 如果返回的是字典，添加 forum_log
            ir_json['forum_log'] = forum_log if forum_log else None
            if 'metadata' not in ir_json:
                ir_json['metadata'] = {}
            ir_json['metadata']['phased'] = True
            ir_json['metadata']['hasForumLog'] = bool(forum_log)

        # 更新完成状态
        update_task_status(task_id, 'completed', 100, result=ir_json)

        logger.info(f"[{task_id}] 最终报告生成完成")

        # 设置查询结果缓存
        _set_query_cache(query, ir_json)

        return ir_json

    except ValueError:
        # 已经更新了状态，直接抛出
        raise

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"[{task_id}] 最终报告生成失败: {error_msg}")
        update_task_status(task_id, 'failed', 0, error=error_msg)
        raise
