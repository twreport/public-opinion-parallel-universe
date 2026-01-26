#!/usr/bin/env python3
"""
清除所有 Celery 残留任务和 Redis 数据
适用于开发调试阶段

使用方法:
    python clear_celery_tasks.py              # 交互模式
    python clear_celery_tasks.py --all        # 清除所有（包括缓存）
    python clear_celery_tasks.py --cache-only # 仅清除缓存
"""

import os
import sys
import argparse
import redis
from typing import Dict, List


def get_redis_client() -> redis.Redis:
    """获取 Redis 客户端"""
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/10')
    try:
        client = redis.from_url(redis_url)
        client.ping()
        return client
    except redis.ConnectionError:
        print("❌ 错误: 无法连接到 Redis")
        print(f"   Redis URL: {redis_url}")
        print("   请确保 Redis 服务正在运行: redis-server")
        sys.exit(1)


def clear_celery_queues(r: redis.Redis) -> Dict[str, int]:
    """清除 Celery 任务队列"""
    queues = ['celery', 'agents', 'orchestrator', 'report']
    result = {}

    for queue in queues:
        count = r.llen(queue)
        if count > 0:
            r.delete(queue)
            result[queue] = count

    return result


def clear_celery_results(r: redis.Redis) -> int:
    """清除 Celery 任务结果（celery-task-meta-* 键）"""
    pattern = 'celery-task-meta-*'
    keys = list(r.scan_iter(match=pattern, count=1000))

    if keys:
        r.delete(*keys)

    return len(keys)


def clear_task_data(r: redis.Redis) -> int:
    """清除自定义任务数据（task:* 键）"""
    pattern = 'task:*'
    keys = list(r.scan_iter(match=pattern, count=1000))

    if keys:
        r.delete(*keys)

    return len(keys)


def clear_task_list(r: redis.Redis) -> int:
    """清除任务列表（tasks:all sorted set）"""
    if r.exists('tasks:all'):
        count = r.zcard('tasks:all')
        r.delete('tasks:all')
        return count
    return 0


def clear_query_cache(r: redis.Redis) -> int:
    """清除查询缓存（cache:query:* 键）"""
    pattern = 'cache:query:*'
    keys = list(r.scan_iter(match=pattern, count=1000))

    if keys:
        r.delete(*keys)

    return len(keys)


def print_separator(char='=', length=60):
    """打印分隔线"""
    print(char * length)


def main():
    parser = argparse.ArgumentParser(
        description='清除 Celery 残留任务和 Redis 数据',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='清除所有数据（包括缓存）'
    )
    parser.add_argument(
        '--cache-only',
        action='store_true',
        help='仅清除查询缓存'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='跳过确认提示'
    )

    args = parser.parse_args()

    print_separator()
    print("Celery 任务清除工具")
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/10')
    print(f"Redis URL: {redis_url}")
    print_separator()
    print()

    # 获取 Redis 客户端
    r = get_redis_client()
    print("✓ Redis 连接正常\n")

    # 仅清除缓存模式
    if args.cache_only:
        print("[1/1] 清除查询缓存...")
        cache_count = clear_query_cache(r)
        if cache_count > 0:
            print(f"  ✓ 清除 {cache_count} 个缓存条目")
        else:
            print("  ✓ 没有缓存需要清除")
        print()
        print_separator()
        print(f"完成！剩余 Redis 键数量: {r.dbsize()}")
        print_separator()
        return

    # 清除 Celery 队列
    print("[1/5] 清除 Celery 任务队列...")
    queue_result = clear_celery_queues(r)
    if queue_result:
        for queue, count in queue_result.items():
            print(f"  ✓ 清除队列 '{queue}': {count} 个任务")
    else:
        print("  ✓ 没有队列任务需要清除")
    print()

    # 清除 Celery 结果
    print("[2/5] 清除 Celery 任务结果...")
    result_count = clear_celery_results(r)
    if result_count > 0:
        print(f"  ✓ 清除 {result_count} 个任务结果")
    else:
        print("  ✓ 没有任务结果需要清除")
    print()

    # 清除任务数据
    print("[3/5] 清除自定义任务数据...")
    task_count = clear_task_data(r)
    if task_count > 0:
        print(f"  ✓ 清除 {task_count} 个任务相关键")
    else:
        print("  ✓ 没有任务数据需要清除")
    print()

    # 清除任务列表
    print("[4/5] 清除任务列表...")
    list_count = clear_task_list(r)
    if list_count > 0:
        print(f"  ✓ 清除任务列表: {list_count} 个任务ID")
    else:
        print("  ✓ 没有任务列表需要清除")
    print()

    # 清除查询缓存（可选）
    print("[5/5] 清除查询缓存...")
    if args.all or args.yes:
        should_clear = True
    else:
        try:
            response = input("  是否清除查询缓存 (cache:query:*)? [y/N] ").strip().lower()
            should_clear = response in ['y', 'yes']
        except (KeyboardInterrupt, EOFError):
            print()
            should_clear = False

    if should_clear:
        cache_count = clear_query_cache(r)
        if cache_count > 0:
            print(f"  ✓ 清除 {cache_count} 个缓存条目")
        else:
            print("  ✓ 没有缓存需要清除")
    else:
        print("  ✓ 跳过查询缓存清除")
    print()

    # 显示最终统计
    print_separator()
    print(f"清除完成！剩余 Redis 键数量: {r.dbsize()}")
    print_separator()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(0)
