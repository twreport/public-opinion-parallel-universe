"""
任务管理器模块 - Redis 存储版本

负责任务的创建、查询和状态管理
使用 Redis 作为存储后端，支持：
- 任务元数据存储
- 任务状态跟踪（由 Celery 任务更新）
- 任务结果存储
- 任务列表管理
"""

import os
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any


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


@dataclass
class AnalysisTask:
    """分析任务数据模型"""
    task_id: str
    query: str
    status: str = "pending"  # pending, running, generating_report, completed, failed
    progress: int = 0  # 0-100
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 响应）"""
        data = {
            "task_id": self.task_id,
            "query": self.query,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        if self.completed_at:
            data["completed_at"] = self.completed_at

        if self.status == "completed":
            # 返回结果获取地址
            data["result_url"] = f"/api/v2/task/{self.task_id}/result"

        if self.status == "failed" and self.error_message:
            data["error_message"] = self.error_message

        # 添加状态描述
        status_messages = {
            "pending": "任务已提交，等待执行",
            "running": "Agent 正在执行研究...",
            "generating_report": "正在生成报告...",
            "completed": "分析完成",
            "failed": "任务执行失败"
        }
        data["message"] = status_messages.get(self.status, "")

        return data


class TaskManager:
    """
    任务管理器 - Redis 存储版本

    单例模式，确保全局共享同一个实例。
    """

    _instance = None

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._key_prefix = "task:"
        self._ttl = 86400 * 7  # 7 天过期
        self._initialized = True

    def _get_redis(self):
        """获取 Redis 连接（延迟初始化）"""
        import redis
        return redis.from_url(REDIS_URL)

    def _task_key(self, task_id: str) -> str:
        """任务元数据 key"""
        return f"{self._key_prefix}{task_id}:meta"

    def _status_key(self, task_id: str) -> str:
        """任务状态 key（由 Celery 任务更新）"""
        return f"{self._key_prefix}{task_id}:status"

    def _result_key(self, task_id: str) -> str:
        """任务结果 key"""
        return f"{self._key_prefix}{task_id}:result"

    def create_task(self, query: str) -> AnalysisTask:
        """
        创建新任务

        Args:
            query: 用户查询内容

        Returns:
            创建的任务对象
        """
        # 生成唯一任务 ID
        task_id = f"task_{int(time.time() * 1000)}"
        now = datetime.now().isoformat()

        task = AnalysisTask(
            task_id=task_id,
            query=query,
            status="pending",
            progress=0,
            created_at=now,
            updated_at=now
        )

        # 存储任务元数据
        r = self._get_redis()
        r.set(
            self._task_key(task_id),
            json.dumps(asdict(task), ensure_ascii=False),
            ex=self._ttl
        )

        # 添加到任务列表（按时间排序）
        r.zadd("tasks:all", {task_id: time.time()})

        return task

    def get_task(self, task_id: str) -> Optional[AnalysisTask]:
        """
        获取任务

        合并元数据和最新状态（由 Celery 任务更新）。

        Args:
            task_id: 任务 ID

        Returns:
            任务对象，不存在则返回 None
        """
        r = self._get_redis()

        # 读取元数据
        meta_data = r.get(self._task_key(task_id))
        if not meta_data:
            return None

        if isinstance(meta_data, bytes):
            meta_data = meta_data.decode('utf-8')

        meta = json.loads(meta_data)

        # 读取最新状态（由 Celery 任务更新）
        status_data = r.get(self._status_key(task_id))
        if status_data:
            if isinstance(status_data, bytes):
                status_data = status_data.decode('utf-8')

            status = json.loads(status_data)
            meta['status'] = status.get('status', meta['status'])
            meta['progress'] = status.get('progress', meta['progress'])
            meta['updated_at'] = status.get('updated_at', meta['updated_at'])

            if status.get('error'):
                meta['error_message'] = status['error']

            if status.get('status') == 'completed':
                meta['completed_at'] = status.get('updated_at')

        return AnalysisTask(**meta)

    def get_result(self, task_id: str) -> Optional[dict]:
        """
        获取任务结果

        Args:
            task_id: 任务 ID

        Returns:
            结果数据（IR JSON），不存在则返回 None
        """
        r = self._get_redis()
        result_data = r.get(self._result_key(task_id))

        if result_data:
            if isinstance(result_data, bytes):
                result_data = result_data.decode('utf-8')
            return json.loads(result_data)

        return None

    def get_agent_progress(self, task_id: str) -> Dict[str, Any]:
        """
        获取各 Agent 的进度

        Args:
            task_id: 任务 ID

        Returns:
            各 Agent 进度信息
        """
        r = self._get_redis()
        agents = ['query', 'media', 'insight']
        progress = {}

        for agent in agents:
            key = f"{self._key_prefix}{task_id}:agent:{agent}"
            data = r.get(key)

            if data:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                progress[agent] = json.loads(data)
            else:
                progress[agent] = {'status': 'pending', 'progress': 0}

        return progress

    def list_tasks(self, limit: int = 50, offset: int = 0) -> List[AnalysisTask]:
        """
        列出任务（按创建时间倒序）

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            任务列表
        """
        r = self._get_redis()

        # 获取任务 ID 列表（按时间倒序）
        task_ids = r.zrevrange("tasks:all", offset, offset + limit - 1)

        tasks = []
        for tid in task_ids:
            if isinstance(tid, bytes):
                tid = tid.decode('utf-8')

            task = self.get_task(tid)
            if task:
                tasks.append(task)

        return tasks

    def get_task_count(self) -> Dict[str, int]:
        """
        获取各状态任务数量统计

        Returns:
            状态统计字典
        """
        r = self._get_redis()

        # 获取所有任务 ID
        total = r.zcard("tasks:all")
        task_ids = r.zrange("tasks:all", 0, -1)

        counts = {
            "pending": 0,
            "running": 0,
            "generating_report": 0,
            "completed": 0,
            "failed": 0,
            "total": total
        }

        # 统计各状态数量
        for tid in task_ids:
            if isinstance(tid, bytes):
                tid = tid.decode('utf-8')

            status_data = r.get(self._status_key(tid))
            if status_data:
                if isinstance(status_data, bytes):
                    status_data = status_data.decode('utf-8')
                status = json.loads(status_data).get('status', 'pending')
            else:
                # 没有状态数据，检查元数据
                meta_data = r.get(self._task_key(tid))
                if meta_data:
                    if isinstance(meta_data, bytes):
                        meta_data = meta_data.decode('utf-8')
                    status = json.loads(meta_data).get('status', 'pending')
                else:
                    status = 'pending'

            if status in counts:
                counts[status] += 1

        return counts

    def update_task(self, task_id: str, **kwargs) -> bool:
        """
        更新任务状态（供 API 层直接调用）

        注意：正常情况下任务状态由 Celery 任务更新，
        此方法仅用于特殊情况（如取消任务）。

        Args:
            task_id: 任务 ID
            **kwargs: 要更新的字段

        Returns:
            是否更新成功
        """
        r = self._get_redis()

        # 读取当前状态
        status_data = r.get(self._status_key(task_id))
        if status_data:
            if isinstance(status_data, bytes):
                status_data = status_data.decode('utf-8')
            current = json.loads(status_data)
        else:
            current = {}

        # 更新字段
        current.update(kwargs)
        current['updated_at'] = datetime.now().isoformat()

        # 写回 Redis
        r.set(
            self._status_key(task_id),
            json.dumps(current, ensure_ascii=False),
            ex=86400
        )

        return True
