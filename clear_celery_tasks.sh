#!/bin/bash
# 清除所有 Celery 残留任务和 Redis 数据
# 适用于开发调试阶段

set -e

REDIS_URL=${REDIS_URL:-redis://127.0.0.1:6379/10}
REDIS_DB=10  # 从 REDIS_URL 提取的数据库编号

echo "========================================="
echo "清除 Celery 残留任务"
echo "Redis URL: $REDIS_URL"
echo "========================================="
echo ""

# 检查 redis-cli 是否可用
if ! command -v redis-cli &> /dev/null; then
    echo "错误: redis-cli 未安装"
    echo "请先安装 Redis: brew install redis (macOS)"
    exit 1
fi

# 检查 Redis 连接
echo "[1/6] 检查 Redis 连接..."
if ! redis-cli -n $REDIS_DB ping &> /dev/null; then
    echo "错误: 无法连接到 Redis"
    echo "请确保 Redis 服务正在运行: redis-server"
    exit 1
fi
echo "✓ Redis 连接正常"
echo ""

# 清除 Celery 任务队列
echo "[2/6] 清除 Celery 任务队列..."
QUEUES=("celery" "agents" "orchestrator" "report")
for queue in "${QUEUES[@]}"; do
    COUNT=$(redis-cli -n $REDIS_DB LLEN "$queue" 2>/dev/null || echo "0")
    if [ "$COUNT" != "0" ]; then
        redis-cli -n $REDIS_DB DEL "$queue" > /dev/null
        echo "  - 清除队列 '$queue': $COUNT 个任务"
    fi
done
echo "✓ 队列清除完成"
echo ""

# 清除 Celery 结果（celery-task-meta-* 键）
echo "[3/6] 清除 Celery 任务结果..."
RESULT_COUNT=$(redis-cli -n $REDIS_DB KEYS "celery-task-meta-*" | wc -l | tr -d ' ')
if [ "$RESULT_COUNT" != "0" ]; then
    redis-cli -n $REDIS_DB KEYS "celery-task-meta-*" | xargs redis-cli -n $REDIS_DB DEL > /dev/null
    echo "  - 清除 $RESULT_COUNT 个任务结果"
fi
echo "✓ 任务结果清除完成"
echo ""

# 清除自定义任务数据（task:* 键）
echo "[4/6] 清除自定义任务数据..."
TASK_COUNT=$(redis-cli -n $REDIS_DB KEYS "task:*" | wc -l | tr -d ' ')
if [ "$TASK_COUNT" != "0" ]; then
    redis-cli -n $REDIS_DB KEYS "task:*" | xargs redis-cli -n $REDIS_DB DEL > /dev/null
    echo "  - 清除 $TASK_COUNT 个任务相关键"
fi
echo "✓ 任务数据清除完成"
echo ""

# 清除任务列表（tasks:all sorted set）
echo "[5/6] 清除任务列表..."
if redis-cli -n $REDIS_DB EXISTS "tasks:all" | grep -q "1"; then
    TASK_LIST_COUNT=$(redis-cli -n $REDIS_DB ZCARD "tasks:all")
    redis-cli -n $REDIS_DB DEL "tasks:all" > /dev/null
    echo "  - 清除任务列表: $TASK_LIST_COUNT 个任务ID"
fi
echo "✓ 任务列表清除完成"
echo ""

# 可选：清除查询缓存
read -p "[6/6] 是否清除查询缓存 (cache:query:*)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CACHE_COUNT=$(redis-cli -n $REDIS_DB KEYS "cache:query:*" | wc -l | tr -d ' ')
    if [ "$CACHE_COUNT" != "0" ]; then
        redis-cli -n $REDIS_DB KEYS "cache:query:*" | xargs redis-cli -n $REDIS_DB DEL > /dev/null
        echo "  - 清除 $CACHE_COUNT 个缓存条目"
    fi
    echo "✓ 查询缓存清除完成"
else
    echo "✓ 跳过查询缓存清除"
fi
echo ""

# 统计剩余键数量
REMAINING_KEYS=$(redis-cli -n $REDIS_DB DBSIZE | grep -oE '[0-9]+')
echo "========================================="
echo "清除完成！"
echo "剩余 Redis 键数量: $REMAINING_KEYS"
echo "========================================="
