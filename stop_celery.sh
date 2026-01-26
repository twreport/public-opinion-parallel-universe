#!/bin/bash
# 停止所有 Celery Worker

echo "正在停止所有 Celery Worker..."

# 通过 PID 文件停止
if [ -d "run" ]; then
  for pidfile in run/celery-*.pid; do
    if [ -f "$pidfile" ]; then
      PID=$(cat "$pidfile")
      echo "停止 worker (PID: $PID)..."
      kill -TERM $PID 2>/dev/null || echo "进程 $PID 不存在"
      rm -f "$pidfile"
    fi
  done
fi

# 查找并停止所有 celery worker 进程
pkill -f "celery.*worker" || echo "没有找到运行中的 celery worker"

echo "所有 worker 已停止"
