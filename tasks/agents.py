"""
Agent 研究任务模块

实现三个独立的 Agent 研究任务：
- QueryEngine: 搜索查询研究
- MediaEngine: 媒体内容研究
- InsightEngine: 深度洞察研究

每个任务支持：
- 失败重试（最多2次）
- 进度更新到 Redis
- 错误记录
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


def update_agent_progress(task_id: str, agent: str, status: str,
                          progress: int, error: str = None):
    """
    更新 Agent 进度到 Redis

    Args:
        task_id: 任务 ID
        agent: Agent 名称 (query/media/insight)
        status: 状态 (pending/running/completed/failed)
        progress: 进度百分比 (0-100)
        error: 错误信息（可选）
    """
    try:
        r = _get_redis_client()
        key = f"task:{task_id}:agent:{agent}"

        data = {
            'status': status,
            'progress': progress,
            'updated_at': datetime.now().isoformat()
        }
        if error:
            data['error'] = error

        r.set(key, json.dumps(data), ex=86400)  # 24小时过期
    except Exception as exc:
        logger.warning(f"[{task_id}] 更新 {agent} 进度失败: {exc}")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def query_research(self, task_id: str, query: str) -> dict:
    """
    QueryEngine 研究任务

    执行基于搜索引擎的查询研究，收集相关信息。

    Args:
        task_id: 任务 ID
        query: 研究查询

    Returns:
        dict: 包含研究结果的字典
    """
    try:
        logger.info(f"[{task_id}] QueryEngine 开始研究: {query}")

        # 更新进度：开始
        update_agent_progress(task_id, 'query', 'running', 10)

        # 调用实际的 Agent
        from QueryEngine.agent import DeepSearchAgent
        agent = DeepSearchAgent()

        # 更新进度：Agent 创建完成
        update_agent_progress(task_id, 'query', 'running', 30)

        # 执行研究（不保存报告文件）
        result = agent.research(query, save_report=False)

        # 更新进度：研究完成
        update_agent_progress(task_id, 'query', 'completed', 100)

        logger.info(f"[{task_id}] QueryEngine 研究完成")

        return {
            'engine': 'QueryEngine',
            'status': 'completed',
            'report': result
        }

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"[{task_id}] QueryEngine 研究失败: {error_msg}")
        update_agent_progress(task_id, 'query', 'failed', 0, error_msg)

        # 重试机制
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def media_research(self, task_id: str, query: str) -> dict:
    """
    MediaEngine 研究任务

    执行媒体内容研究，分析相关视频、图片等媒体信息。

    Args:
        task_id: 任务 ID
        query: 研究查询

    Returns:
        dict: 包含研究结果的字典
    """
    try:
        logger.info(f"[{task_id}] MediaEngine 开始研究: {query}")

        # 更新进度：开始
        update_agent_progress(task_id, 'media', 'running', 10)

        # 调用实际的 Agent
        from MediaEngine.agent import DeepSearchAgent
        agent = DeepSearchAgent()

        # 更新进度：Agent 创建完成
        update_agent_progress(task_id, 'media', 'running', 30)

        # 执行研究
        result = agent.research(query, save_report=False)

        # 更新进度：研究完成
        update_agent_progress(task_id, 'media', 'completed', 100)

        logger.info(f"[{task_id}] MediaEngine 研究完成")

        return {
            'engine': 'MediaEngine',
            'status': 'completed',
            'report': result
        }

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"[{task_id}] MediaEngine 研究失败: {error_msg}")
        update_agent_progress(task_id, 'media', 'failed', 0, error_msg)

        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def insight_research(self, task_id: str, query: str) -> dict:
    """
    InsightEngine 研究任务

    执行深度洞察研究，提供专业分析和见解。

    Args:
        task_id: 任务 ID
        query: 研究查询

    Returns:
        dict: 包含研究结果的字典
    """
    try:
        logger.info(f"[{task_id}] InsightEngine 开始研究: {query}")

        # 更新进度：开始
        update_agent_progress(task_id, 'insight', 'running', 10)

        # 调用实际的 Agent
        from InsightEngine.agent import DeepSearchAgent
        agent = DeepSearchAgent()

        # 更新进度：Agent 创建完成
        update_agent_progress(task_id, 'insight', 'running', 30)

        # 执行研究
        result = agent.research(query, save_report=False)

        # 更新进度：研究完成
        update_agent_progress(task_id, 'insight', 'completed', 100)

        logger.info(f"[{task_id}] InsightEngine 研究完成")

        return {
            'engine': 'InsightEngine',
            'status': 'completed',
            'report': result
        }

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"[{task_id}] InsightEngine 研究失败: {error_msg}")
        update_agent_progress(task_id, 'insight', 'failed', 0, error_msg)

        raise self.retry(exc=exc)
