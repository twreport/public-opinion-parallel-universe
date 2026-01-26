"""
Celery 应用配置

配置 Redis 作为 Broker 和 Backend，支持：
- 任务队列管理
- 任务结果存储
- Worker 并发控制
- 任务超时和重试
"""

import os
import sys

# 确保项目根目录在 Python 路径中
# 这样 Celery worker 可以正确导入 QueryEngine, MediaEngine 等模块
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from celery import Celery

# 从配置文件读取 Redis URL，支持环境变量覆盖
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

# 创建 Celery 应用
celery_app = Celery(
    'bettafish',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        'tasks.analysis',
        'tasks.agents',
        'tasks.agents_phased',
        'tasks.orchestrator',
        'tasks.report'
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],

    # 时区设置
    timezone='Asia/Shanghai',
    enable_utc=True,

    # 任务结果过期时间 (24小时)
    result_expires=86400,

    # Worker 并发控制（默认值，可在启动时通过 --concurrency 覆盖）
    # 生产环境建议：
    # - prefork pool: --concurrency=8~16 (根据CPU核心数)
    # - gevent pool: --concurrency=50~100 (I/O密集型任务)
    worker_concurrency=4,

    # 任务确认机制
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # 任务路由（启用多队列提高并发）
    # 启动 worker 时指定: celery -A celery_app worker -Q celery,agents,orchestrator,report
    task_routes={
        'tasks.agents.*': {'queue': 'agents'},
        'tasks.agents_phased.*': {'queue': 'agents'},
        'tasks.orchestrator.*': {'queue': 'orchestrator'},
        'tasks.report.*': {'queue': 'report'},
    },

    # 任务超时配置（默认值，具体任务可在 @task 装饰器中覆盖）
    task_soft_time_limit=3600,  # 60 分钟软超时（发送信号）
    task_time_limit=3900,       # 65 分钟硬超时（强制终止）

    # 阶段性任务超时配置说明：
    # - agent_plan: 10分钟 (soft_time_limit=600, time_limit=660)
    # - agent_research: 30分钟 (soft_time_limit=1800, time_limit=1860)
    # - agent_report: 10分钟 (soft_time_limit=600, time_limit=660)
    # - orchestrate_*: 5分钟 (soft_time_limit=300, time_limit=360)

    # 任务追踪
    task_track_started=True,

    # 结果扩展配置
    result_extended=True,

    # 任务预取配置（生产环境优化）
    # worker_prefetch_multiplier=1 可以防止单个worker抢占过多任务
    # 提高任务分配的公平性，适合长时间运行的任务
    worker_prefetch_multiplier=4,  # 默认4，可设为1提高公平性

    # 任务消息最大大小限制（防止大型结果导致内存问题）
    task_compression='gzip',  # 压缩任务消息
    result_compression='gzip',  # 压缩结果
)


# 配置定时任务（可选，用于清理过期数据等）
celery_app.conf.beat_schedule = {
    # 每天凌晨 3 点清理过期任务数据
    'cleanup-expired-tasks': {
        'task': 'tasks.analysis.cleanup_expired_tasks',
        'schedule': 86400,  # 每24小时执行一次
        'options': {'queue': 'default'}
    },
}
