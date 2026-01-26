"""
Blackboard - Redis 共享状态管理

提供 Agent 间共享中间状态的接口，包括：
- Agent 阶段状态追踪
- Plan/Research/Report 结果存储
- Guidance 机制支持
- Forum 讨论日志
"""

import os
import json
import redis
from typing import Optional, Dict, Any, List
from datetime import datetime


def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端"""
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/10')
    return redis.from_url(redis_url, decode_responses=True)


class Blackboard:
    """
    Blackboard 黑板系统 - Agent 间共享状态管理

    使用 Redis 作为后端存储，所有数据默认 7 天过期
    """

    DEFAULT_TTL = 86400 * 7  # 7 天

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        初始化 Blackboard

        Args:
            redis_client: Redis 客户端（可选，默认创建新连接）
        """
        self._redis = redis_client or get_redis_client()

    # ==================== Agent 阶段管理 ====================

    def set_agent_phase(self, task_id: str, agent: str, phase: str) -> None:
        """
        设置 Agent 当前阶段

        Args:
            task_id: 任务 ID
            agent: Agent 名称 (query/media/insight)
            phase: 阶段名称 (plan/research/report)
        """
        key = f"task:{task_id}:agent:{agent}:phase"
        data = {
            'phase': phase,
            'updated_at': datetime.now().isoformat()
        }
        self._redis.set(key, json.dumps(data), ex=self.DEFAULT_TTL)

    def get_agent_phase(self, task_id: str, agent: str) -> Optional[str]:
        """
        获取 Agent 当前阶段

        Args:
            task_id: 任务 ID
            agent: Agent 名称

        Returns:
            阶段名称，如果不存在则返回 None
        """
        key = f"task:{task_id}:agent:{agent}:phase"
        data = self._redis.get(key)
        if data:
            return json.loads(data).get('phase')
        return None

    def get_all_agent_phases(self, task_id: str, agents: List[str]) -> Dict[str, str]:
        """
        批量获取所有 Agent 的当前阶段

        Args:
            task_id: 任务 ID
            agents: Agent 名称列表

        Returns:
            Agent -> 阶段的映射字典
        """
        result = {}
        for agent in agents:
            phase = self.get_agent_phase(task_id, agent)
            if phase:
                result[agent] = phase
        return result

    # ==================== Plan 阶段结果 ====================

    def save_plan_result(self, task_id: str, agent: str, plan_data: Dict[str, Any]) -> None:
        """
        保存 Plan 阶段结果

        Args:
            task_id: 任务 ID
            agent: Agent 名称
            plan_data: Plan 数据（包含报告结构、关键词等）
        """
        key = f"task:{task_id}:agent:{agent}:plan"
        data = {
            'agent': agent,
            'plan': plan_data,
            'created_at': datetime.now().isoformat()
        }
        self._redis.set(key, json.dumps(data, ensure_ascii=False), ex=self.DEFAULT_TTL)

    def get_plan_result(self, task_id: str, agent: str) -> Optional[Dict[str, Any]]:
        """
        获取 Plan 阶段结果

        Args:
            task_id: 任务 ID
            agent: Agent 名称

        Returns:
            Plan 数据，如果不存在则返回 None
        """
        key = f"task:{task_id}:agent:{agent}:plan"
        data = self._redis.get(key)
        if data:
            return json.loads(data).get('plan')
        return None

    def get_all_plans(self, task_id: str, agents: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取所有 Agent 的 Plan 结果

        Args:
            task_id: 任务 ID
            agents: Agent 名称列表

        Returns:
            Agent -> Plan 数据的映射字典
        """
        result = {}
        for agent in agents:
            plan = self.get_plan_result(task_id, agent)
            if plan:
                result[agent] = plan
        return result

    # ==================== Research 阶段结果 ====================

    def save_research_result(self, task_id: str, agent: str, research_data: Dict[str, Any]) -> None:
        """
        保存 Research 阶段结果

        Args:
            task_id: 任务 ID
            agent: Agent 名称
            research_data: 研究数据（包含搜索结果、分析等）
        """
        key = f"task:{task_id}:agent:{agent}:research"
        data = {
            'agent': agent,
            'research': research_data,
            'created_at': datetime.now().isoformat()
        }
        self._redis.set(key, json.dumps(data, ensure_ascii=False), ex=self.DEFAULT_TTL)

    def get_research_result(self, task_id: str, agent: str) -> Optional[Dict[str, Any]]:
        """
        获取 Research 阶段结果

        Args:
            task_id: 任务 ID
            agent: Agent 名称

        Returns:
            Research 数据，如果不存在则返回 None
        """
        key = f"task:{task_id}:agent:{agent}:research"
        data = self._redis.get(key)
        if data:
            return json.loads(data).get('research')
        return None

    def get_all_research(self, task_id: str, agents: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        批量获取所有 Agent 的 Research 结果

        Args:
            task_id: 任务 ID
            agents: Agent 名称列表

        Returns:
            Agent -> Research 数据的映射字典
        """
        result = {}
        for agent in agents:
            research = self.get_research_result(task_id, agent)
            if research:
                result[agent] = research
        return result

    # ==================== Report 阶段结果 ====================

    def save_report_result(self, task_id: str, agent: str, report_data: str) -> None:
        """
        保存 Report 阶段结果

        Args:
            task_id: 任务 ID
            agent: Agent 名称
            report_data: 报告内容（Markdown/Text）
        """
        key = f"task:{task_id}:agent:{agent}:report"
        data = {
            'agent': agent,
            'report': report_data,
            'created_at': datetime.now().isoformat()
        }
        self._redis.set(key, json.dumps(data, ensure_ascii=False), ex=self.DEFAULT_TTL)

    def get_report_result(self, task_id: str, agent: str) -> Optional[str]:
        """
        获取 Report 阶段结果

        Args:
            task_id: 任务 ID
            agent: Agent 名称

        Returns:
            报告内容，如果不存在则返回 None
        """
        key = f"task:{task_id}:agent:{agent}:report"
        data = self._redis.get(key)
        if data:
            return json.loads(data).get('report')
        return None

    def get_all_reports(self, task_id: str, agents: List[str]) -> Dict[str, str]:
        """
        批量获取所有 Agent 的 Report 结果

        Args:
            task_id: 任务 ID
            agents: Agent 名称列表

        Returns:
            Agent -> 报告内容的映射字典
        """
        result = {}
        for agent in agents:
            report = self.get_report_result(task_id, agent)
            if report:
                result[agent] = report
        return result

    # ==================== Guidance 机制 ====================

    def save_guidance(self, task_id: str, phase: str, guidance: str) -> None:
        """
        保存 Orchestrator 生成的 Guidance

        Args:
            task_id: 任务 ID
            phase: 阶段名称 (plan/research)
            guidance: 指导意见（给 Agent 的建议）
        """
        key = f"task:{task_id}:guidance:{phase}"
        data = {
            'phase': phase,
            'guidance': guidance,
            'created_at': datetime.now().isoformat()
        }
        self._redis.set(key, json.dumps(data, ensure_ascii=False), ex=self.DEFAULT_TTL)

    def get_guidance(self, task_id: str, phase: str) -> Optional[str]:
        """
        获取 Guidance

        Args:
            task_id: 任务 ID
            phase: 阶段名称

        Returns:
            指导意见，如果不存在则返回 None
        """
        key = f"task:{task_id}:guidance:{phase}"
        data = self._redis.get(key)
        if data:
            return json.loads(data).get('guidance')
        return None

    # ==================== 补充研究轮次 ====================

    def increment_supplement_round(self, task_id: str) -> int:
        """
        增加补充研究轮次计数

        Args:
            task_id: 任务 ID

        Returns:
            当前轮次（从 1 开始）
        """
        key = f"task:{task_id}:supplement:round"
        count = self._redis.incr(key)
        self._redis.expire(key, self.DEFAULT_TTL)
        return count

    def get_supplement_round(self, task_id: str) -> int:
        """
        获取当前补充研究轮次

        Args:
            task_id: 任务 ID

        Returns:
            当前轮次（0 表示未补充）
        """
        key = f"task:{task_id}:supplement:round"
        count = self._redis.get(key)
        return int(count) if count else 0

    # ==================== Forum 讨论日志 ====================

    def append_forum_log(self, task_id: str, speaker: str, content: str) -> None:
        """
        追加 Forum 讨论日志

        Args:
            task_id: 任务 ID
            speaker: 发言者（orchestrator/agent名称）
            content: 发言内容
        """
        key = f"task:{task_id}:forum:log"
        log_entry = {
            'speaker': speaker,
            'content': content,
            'timestamp': datetime.now().isoformat()
        }
        self._redis.rpush(key, json.dumps(log_entry, ensure_ascii=False))
        self._redis.expire(key, self.DEFAULT_TTL)

    def get_forum_log(self, task_id: str) -> List[Dict[str, str]]:
        """
        获取完整的 Forum 讨论日志

        Args:
            task_id: 任务 ID

        Returns:
            日志列表，每个条目包含 speaker, content, timestamp
        """
        key = f"task:{task_id}:forum:log"
        logs = self._redis.lrange(key, 0, -1)
        return [json.loads(log) for log in logs]

    def get_forum_log_text(self, task_id: str) -> str:
        """
        获取 Forum 讨论日志的文本格式

        Args:
            task_id: 任务 ID

        Returns:
            格式化的日志文本
        """
        logs = self.get_forum_log(task_id)
        lines = []
        for log in logs:
            timestamp = log.get('timestamp', '')
            speaker = log.get('speaker', 'unknown')
            content = log.get('content', '')
            lines.append(f"[{timestamp}] {speaker}: {content}")
        return '\n'.join(lines)

    def get_forum_log_summary(self, task_id: str, max_chars: int = 2000) -> str:
        """
        获取 Forum 讨论日志的精简摘要（用于 ReportEngine）

        只保留关键决策信息，过滤掉状态消息，控制总长度

        Args:
            task_id: 任务 ID
            max_chars: 最大字符数限制

        Returns:
            精简的日志摘要文本
        """
        logs = self.get_forum_log(task_id)

        # 关键词：需要保留的重要消息
        important_keywords = ['评审', '决策', 'Guidance', '补充', 'approve', 'revise', 'supplement', '调整']
        # 过滤词：可以跳过的状态消息
        skip_keywords = ['开始 Plan', '开始 Research', '开始 Phase', '阶段开始', '初始化']

        important_lines = []
        other_lines = []

        for log in logs:
            speaker = log.get('speaker', 'unknown')
            content = log.get('content', '')

            # 检查是否应该跳过
            should_skip = any(kw in content for kw in skip_keywords)
            if should_skip and speaker != 'orchestrator':
                continue

            # 检查是否是重要消息
            is_important = (
                speaker == 'orchestrator' or
                any(kw in content for kw in important_keywords)
            )

            line = f"[{speaker}] {content}"
            if is_important:
                important_lines.append(line)
            else:
                other_lines.append(line)

        # 优先保留重要消息，然后填充其他消息
        result_lines = important_lines.copy()
        current_length = sum(len(line) for line in result_lines)

        for line in other_lines:
            if current_length + len(line) + 1 > max_chars:
                break
            result_lines.append(line)
            current_length += len(line) + 1

        result = '\n'.join(result_lines)

        # 如果仍然超长，截断
        if len(result) > max_chars:
            result = result[:max_chars - 20] + '\n...(讨论记录已截断)'

        return result

    # ==================== 工具方法 ====================

    def clear_task_data(self, task_id: str) -> int:
        """
        清理任务的所有 Blackboard 数据（用于测试或手动清理）

        Args:
            task_id: 任务 ID

        Returns:
            删除的 key 数量
        """
        pattern = f"task:{task_id}:*"
        keys = self._redis.keys(pattern)
        if keys:
            return self._redis.delete(*keys)
        return 0

    def get_task_summary(self, task_id: str, agents: List[str]) -> Dict[str, Any]:
        """
        获取任务在 Blackboard 中的完整状态摘要

        Args:
            task_id: 任务 ID
            agents: Agent 列表

        Returns:
            包含所有阶段、结果、日志的摘要
        """
        return {
            'task_id': task_id,
            'phases': self.get_all_agent_phases(task_id, agents),
            'plans': self.get_all_plans(task_id, agents),
            'research': self.get_all_research(task_id, agents),
            'reports': self.get_all_reports(task_id, agents),
            'supplement_round': self.get_supplement_round(task_id),
            'guidance': {
                'plan': self.get_guidance(task_id, 'plan'),
                'research': self.get_guidance(task_id, 'research'),
            },
            'forum_log': self.get_forum_log(task_id)
        }
