"""
API v2 路由定义
实现异步任务提交与查询接口

使用 Celery 进行异步任务处理：
- POST /api/v2/analyze: 提交分析任务
- GET /api/v2/task/{task_id}: 查询任务状态
- GET /api/v2/task/{task_id}/result: 获取任务结果
- GET /api/v2/task/{task_id}/progress: 获取各 Agent 进度
- GET /api/v2/tasks: 列出所有任务
- GET /api/v2/health: 健康检查
"""

from flask import Blueprint, request, jsonify, Response
from .task_manager import TaskManager

api_v2 = Blueprint('api_v2', __name__, url_prefix='/api/v2')

# 使用单例 TaskManager
task_manager = TaskManager()


@api_v2.route('/analyze', methods=['POST'])
def create_analysis():
    """
    提交分析任务

    Request Body:
        {
            "query": "查询内容",
            "options": {
                "priority": "normal"  # 预留字段
            }
        }

    Response:
        {
            "success": true,
            "task_id": "task_xxx",
            "status": "pending",
            "message": "任务已提交",
            "poll_url": "/api/v2/task/task_xxx"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求体不能为空'
            }), 400

        query = data.get('query', '').strip()

        if not query:
            return jsonify({
                'success': False,
                'error': '查询内容不能为空'
            }), 400

        if len(query) > 500:
            return jsonify({
                'success': False,
                'error': '查询内容不能超过500字符'
            }), 400

        # 创建任务记录
        task = task_manager.create_task(query)

        # 获取执行模式（默认使用阶段性 Orchestrator 模式）
        options = data.get('options', {})
        mode = options.get('mode', 'phased')  # 'phased' 或 'standard'

        if mode == 'phased':
            # 新模式：Blackboard + Orchestrator（三阶段）
            from tasks.analysis import analyze_task_phased
            analyze_task_phased.delay(task.task_id, query)
            message = '任务已提交（Orchestrator 模式）'
        else:
            # 旧模式：直接并行执行
            from tasks.analysis import analyze_task
            analyze_task.delay(task.task_id, query)
            message = '任务已提交（标准模式）'

        return jsonify({
            'success': True,
            'task_id': task.task_id,
            'status': task.status,
            'mode': mode,
            'message': message,
            'poll_url': f'/api/v2/task/{task.task_id}'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器错误: {str(e)}'
        }), 500


@api_v2.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id: str):
    """
    查询任务状态

    Response:
        {
            "task_id": "task_xxx",
            "status": "running",
            "progress": 45,
            "query": "查询内容",
            "created_at": "2026-01-24T10:00:00",
            "updated_at": "2026-01-24T10:05:00",
            "message": "Agent 正在执行研究..."
        }
    """
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404

    return jsonify(task.to_dict())


@api_v2.route('/task/<task_id>/progress', methods=['GET'])
def get_task_progress(task_id: str):
    """
    获取任务各 Agent 的详细进度

    Response:
        {
            "success": true,
            "task_id": "task_xxx",
            "agents": {
                "query": {"status": "completed", "progress": 100},
                "media": {"status": "running", "progress": 50},
                "insight": {"status": "pending", "progress": 0}
            }
        }
    """
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404

    progress = task_manager.get_agent_progress(task_id)

    return jsonify({
        'success': True,
        'task_id': task_id,
        'status': task.status,
        'overall_progress': task.progress,
        'agents': progress
    })


@api_v2.route('/task/<task_id>/result', methods=['GET'])
def get_task_result(task_id: str):
    """
    获取任务结果

    Query Parameters:
        format: json|html|pdf|md (默认 json)

    Response:
        根据 format 返回对应格式的内容
    """
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404

    if task.status != 'completed':
        return jsonify({
            'success': False,
            'error': f'任务未完成，当前状态: {task.status}',
            'status': task.status,
            'progress': task.progress
        }), 400

    # 从 Redis 获取结果
    result = task_manager.get_result(task_id)
    if not result:
        return jsonify({
            'success': False,
            'error': '结果不存在或已过期'
        }), 404

    format_type = request.args.get('format', 'json').lower()

    if format_type == 'json':
        return jsonify({
            'success': True,
            'data': result
        })

    elif format_type == 'html':
        # 如果结果已包含 html_content，直接返回
        if isinstance(result, dict) and result.get('html_content'):
            html_content = result['html_content']
        else:
            # 调用 HTMLRenderer 生成 HTML
            try:
                from ReportEngine.renderers.html_renderer import HTMLRenderer
                html_content = HTMLRenderer().render(result)
            except ImportError:
                # 降级：使用简单 HTML 生成
                html_content = _generate_simple_html(task.query, result)

        return Response(
            html_content,
            mimetype='text/html',
            headers={
                'Content-Disposition': f'inline; filename="report_{task_id}.html"'
            }
        )

    elif format_type == 'md':
        # 生成 Markdown 格式
        md_content = _generate_markdown(task.query, result)
        return Response(
            md_content,
            mimetype='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename="report_{task_id}.md"'
            }
        )

    elif format_type == 'pdf':
        # PDF 生成需要额外依赖，暂时返回提示
        return jsonify({
            'success': False,
            'error': 'PDF 格式暂未实现，请使用 json/html/md 格式'
        }), 501

    else:
        return jsonify({
            'success': False,
            'error': f'不支持的格式: {format_type}，可选: json, html, md, pdf'
        }), 400


@api_v2.route('/tasks', methods=['GET'])
def list_tasks():
    """
    列出所有任务

    Query Parameters:
        limit: 返回数量限制 (默认 50)
        offset: 偏移量 (默认 0)

    Response:
        {
            "success": true,
            "tasks": [...],
            "total": 100,
            "stats": {
                "pending": 5,
                "running": 3,
                "completed": 90,
                "failed": 2
            }
        }
    """
    try:
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'limit 和 offset 必须是整数'
        }), 400

    tasks = task_manager.list_tasks(limit=limit, offset=offset)
    stats = task_manager.get_task_count()

    return jsonify({
        'success': True,
        'tasks': [t.to_dict() for t in tasks],
        'total': stats['total'],
        'stats': stats
    })


@api_v2.route('/task/<task_id>/phases', methods=['GET'])
def get_task_phases(task_id: str):
    """
    获取任务的阶段性进度（ForumEngine Orchestrator 模式）

    返回每个 Agent 的当前阶段、各阶段结果、Forum 讨论日志等

    Response:
        {
            "success": true,
            "task_id": "task_xxx",
            "phases": {
                "query": "research",
                "media": "plan",
                "insight": "completed"
            },
            "plans": {
                "query": {...},
                "media": {...}
            },
            "research": {
                "query": {...}
            },
            "reports": {},
            "supplement_round": 0,
            "guidance": {
                "plan": "...",
                "research": null
            },
            "forum_log": [
                {"speaker": "orchestrator", "content": "...", "timestamp": "..."},
                ...
            ]
        }
    """
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({
            'success': False,
            'error': '任务不存在'
        }), 404

    # 从 Blackboard 获取阶段信息
    try:
        from tasks.blackboard import Blackboard

        blackboard = Blackboard()
        agents = ['query', 'media', 'insight']

        # 获取完整的任务摘要
        summary = blackboard.get_task_summary(task_id, agents)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'phases': summary['phases'],
            'plans': summary['plans'],
            'research': summary['research'],
            'reports': summary['reports'],
            'supplement_round': summary['supplement_round'],
            'guidance': summary['guidance'],
            'forum_log': summary['forum_log']
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取阶段信息失败: {str(e)}'
        }), 500


@api_v2.route('/health', methods=['GET'])
def health_check():
    """
    健康检查端点

    检查 Redis 连接和 Celery 状态
    """
    health = {
        'status': 'healthy',
        'service': 'BettaFish API v2',
        'components': {}
    }

    # 检查 Redis 连接
    try:
        import redis
        from .task_manager import REDIS_URL
        r = redis.from_url(REDIS_URL)
        r.ping()
        health['components']['redis'] = 'healthy'
    except Exception as e:
        health['components']['redis'] = f'unhealthy: {str(e)}'
        health['status'] = 'degraded'

    # 获取任务统计
    try:
        stats = task_manager.get_task_count()
        health['task_stats'] = stats
    except Exception:
        health['task_stats'] = {}

    return jsonify(health)


def _generate_simple_html(query: str, result: dict) -> str:
    """生成简单的 HTML 报告"""
    metadata = result.get('metadata', {})
    title = metadata.get('title', query)
    summary = result.get('summary', {})
    sections = result.get('sections', [])

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .highlight {{ background: #fff3cd; padding: 10px; margin: 10px 0; border-left: 4px solid #ffc107; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
"""

    # 摘要
    if summary:
        html += '<div class="summary"><h2>摘要</h2>'
        if summary.get('highlights'):
            for h in summary['highlights']:
                html += f'<div class="highlight">{h}</div>'
        html += '</div>'

    # 章节
    for section in sections:
        html += f'<div class="section">'
        html += f'<h2>{section.get("title", "")}</h2>'
        html += f'<p>{section.get("content", "")}</p>'
        html += '</div>'

    html += '</body></html>'
    return html


def _generate_markdown(query: str, result: dict) -> str:
    """生成 Markdown 格式报告"""
    metadata = result.get('metadata', {})
    title = metadata.get('title', query)
    summary = result.get('summary', {})
    sections = result.get('sections', [])

    md = f"# {title}\n\n"

    # 摘要
    if summary:
        md += "## 摘要\n\n"
        if summary.get('highlights'):
            for h in summary['highlights']:
                md += f"- {h}\n"
        md += "\n"

    # 章节
    for section in sections:
        md += f"## {section.get('title', '')}\n\n"
        md += f"{section.get('content', '')}\n\n"

    return md
