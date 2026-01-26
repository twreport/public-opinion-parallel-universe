#!/bin/bash
# BettaFish Celery 生产环境启动脚本
#
# 使用方法：
# ./start_celery_production.sh [small|medium|large]
#
# 配置级别：
# - small: 适合 10 以下并发（单worker，gevent pool）
# - medium: 适合 10-30 并发（多worker专用化）
# - large: 适合 30+ 并发（需要多机部署）

set -e

PROFILE=${1:-medium}
REDIS_URL=${REDIS_URL:-redis://127.0.0.1:6379/10}

echo "========================================="
echo "BettaFish Celery Worker 启动"
echo "配置级别: $PROFILE"
echo "Redis: $REDIS_URL"
echo "========================================="

case $PROFILE in
  small)
    echo "启动小规模配置（10以下并发）..."
    echo "Worker: 1个，Gevent pool，并发100"

    celery -A celery_app worker \
      -n bettafish-worker@%h \
      -Q celery,agents,orchestrator,report \
      --pool=gevent \
      --concurrency=100 \
      --loglevel=info \
      --logfile=logs/celery-worker.log \
      --pidfile=run/celery-worker.pid
    ;;

  medium)
    echo "启动中规模配置（10-30并发）..."
    echo "需要在不同终端启动3个worker实例"
    echo ""
    echo "请选择要启动的worker："
    echo "1) Agent Worker (agents队列)"
    echo "2) Main Worker (celery, orchestrator队列)"
    echo "3) Report Worker (report队列)"
    echo "4) 全部启动（后台模式）"
    read -p "选择 [1-4]: " choice

    case $choice in
      1)
        celery -A celery_app worker \
          -n agent-worker@%h \
          -Q agents \
          --pool=gevent \
          --concurrency=50 \
          --loglevel=info \
          --logfile=logs/celery-agent-worker.log
        ;;
      2)
        celery -A celery_app worker \
          -n main-worker@%h \
          -Q celery,orchestrator \
          --concurrency=4 \
          --loglevel=info \
          --logfile=logs/celery-main-worker.log
        ;;
      3)
        celery -A celery_app worker \
          -n report-worker@%h \
          -Q report \
          --concurrency=2 \
          --loglevel=info \
          --logfile=logs/celery-report-worker.log
        ;;
      4)
        mkdir -p logs run

        # 启动 Agent Worker
        celery -A celery_app worker \
          -n agent-worker@%h \
          -Q agents \
          --pool=gevent \
          --concurrency=50 \
          --loglevel=info \
          --logfile=logs/celery-agent-worker.log \
          --pidfile=run/celery-agent-worker.pid \
          --detach

        # 启动 Main Worker
        celery -A celery_app worker \
          -n main-worker@%h \
          -Q celery,orchestrator \
          --concurrency=4 \
          --loglevel=info \
          --logfile=logs/celery-main-worker.log \
          --pidfile=run/celery-main-worker.pid \
          --detach

        # 启动 Report Worker
        celery -A celery_app worker \
          -n report-worker@%h \
          -Q report \
          --concurrency=2 \
          --loglevel=info \
          --logfile=logs/celery-report-worker.log \
          --pidfile=run/celery-report-worker.pid \
          --detach

        echo ""
        echo "所有worker已在后台启动！"
        echo ""
        echo "查看状态："
        echo "  tail -f logs/celery-agent-worker.log"
        echo "  tail -f logs/celery-main-worker.log"
        echo "  tail -f logs/celery-report-worker.log"
        echo ""
        echo "停止所有worker："
        echo "  ./stop_celery.sh"
        ;;
      *)
        echo "无效选择"
        exit 1
        ;;
    esac
    ;;

  large)
    echo "大规模配置（30+并发）需要多机部署"
    echo "请使用 Docker Compose 或 Kubernetes"
    echo ""
    echo "Docker Compose: docker-compose -f docker-compose.prod.yml up -d"
    echo "Kubernetes: kubectl apply -f k8s/"
    exit 1
    ;;

  *)
    echo "未知配置: $PROFILE"
    echo "可选: small, medium, large"
    exit 1
    ;;
esac
