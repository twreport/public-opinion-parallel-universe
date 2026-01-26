"""
Mock 数据生成模块
用于在 Celery 改造前模拟任务执行过程
"""

import threading
import time
import hashlib
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .task_manager import TaskManager


def generate_mock_ir_json(query: str, task_id: str) -> dict:
    """
    生成模拟的 IR JSON 数据

    Args:
        query: 用户查询
        task_id: 任务ID

    Returns:
        模拟的 IR JSON 结构
    """
    # 基于 query 生成一些变化的内容
    query_hash = hashlib.md5(query.encode()).hexdigest()[:8]

    return {
        "reportId": task_id,
        "metadata": {
            "query": query,
            "title": f"{query}分析报告",
            "subtitle": "基于多源数据的综合分析",
            "generatedAt": datetime.now().isoformat(),
            "version": "1.0"
        },
        "summary": {
            "highlights": [
                f"发现 {3 + int(query_hash[:2], 16) % 5} 个主要舆情热点",
                f"整体情感倾向偏正面 ({50 + int(query_hash[2:4], 16) % 30}%)",
                "主要传播平台为微博和抖音",
                "建议持续关注后续发展"
            ],
            "kpis": [
                {
                    "label": "舆情热度",
                    "value": f"{6 + int(query_hash[4:6], 16) % 4}.{int(query_hash[6:8], 16) % 10}/10",
                    "trend": "up"
                },
                {
                    "label": "讨论量",
                    "value": f"{10 + int(query_hash[:2], 16) % 20}.{int(query_hash[2:4], 16) % 10}万",
                    "trend": "up"
                },
                {
                    "label": "正面占比",
                    "value": f"{50 + int(query_hash[4:6], 16) % 30}%",
                    "trend": "stable"
                }
            ]
        },
        "chapters": [
            {
                "chapterId": "S1",
                "title": "报告摘要",
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": f"本报告针对「{query}」进行了全面的舆情分析。通过对多个数据源的综合分析，我们识别出了主要的舆论观点、情感倾向和传播趋势。"
                    }
                ]
            },
            {
                "chapterId": "S2",
                "title": "舆情概览",
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": "本章节概述了当前舆情的整体态势，包括热度变化、关键节点和主要传播路径。"
                    },
                    {
                        "type": "list",
                        "items": [
                            "热度在过去7天呈上升趋势",
                            "微博为主要讨论平台",
                            "意见领袖参与度较高"
                        ]
                    }
                ]
            },
            {
                "chapterId": "S3",
                "title": "情感分析",
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": "通过自然语言处理技术，对相关讨论进行情感分析，识别正面、负面和中性观点的分布。"
                    },
                    {
                        "type": "kpiGrid",
                        "items": [
                            {"label": "正面", "value": f"{50 + int(query_hash[4:6], 16) % 30}%"},
                            {"label": "中性", "value": f"{20 + int(query_hash[2:4], 16) % 15}%"},
                            {"label": "负面", "value": f"{10 + int(query_hash[:2], 16) % 15}%"}
                        ]
                    }
                ]
            },
            {
                "chapterId": "S4",
                "title": "结论与建议",
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": f"综合以上分析，「{query}」当前舆情态势整体可控，但仍需关注以下几个方面的风险点。"
                    },
                    {
                        "type": "list",
                        "items": [
                            "建立常态化舆情监测机制",
                            "及时回应公众关切",
                            "加强正面信息传播"
                        ]
                    }
                ]
            }
        ],
        "sources": [
            {
                "engine": "QueryEngine",
                "source": "综合网络搜索",
                "count": 15 + int(query_hash[:2], 16) % 10
            },
            {
                "engine": "MediaEngine",
                "source": "社交媒体分析",
                "count": 20 + int(query_hash[2:4], 16) % 15
            },
            {
                "engine": "InsightEngine",
                "source": "深度洞察分析",
                "count": 8 + int(query_hash[4:6], 16) % 5
            }
        ]
    }


def generate_mock_html(query: str, ir_json: dict) -> str:
    """
    生成模拟的 HTML 报告

    Args:
        query: 用户查询
        ir_json: IR JSON 数据

    Returns:
        HTML 字符串
    """
    metadata = ir_json.get("metadata", {})
    summary = ir_json.get("summary", {})
    chapters = ir_json.get("chapters", [])

    chapters_html = ""
    for chapter in chapters:
        blocks_html = ""
        for block in chapter.get("blocks", []):
            if block["type"] == "paragraph":
                blocks_html += f"<p>{block['content']}</p>\n"
            elif block["type"] == "list":
                items = "".join(f"<li>{item}</li>" for item in block.get("items", []))
                blocks_html += f"<ul>{items}</ul>\n"
            elif block["type"] == "kpiGrid":
                items = "".join(
                    f"<div class='kpi'><span class='label'>{item['label']}</span><span class='value'>{item['value']}</span></div>"
                    for item in block.get("items", [])
                )
                blocks_html += f"<div class='kpi-grid'>{items}</div>\n"

        chapters_html += f"""
        <section id="{chapter['chapterId']}">
            <h2>{chapter['title']}</h2>
            {blocks_html}
        </section>
        """

    highlights_html = "".join(f"<li>{h}</li>" for h in summary.get("highlights", []))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{metadata.get('title', '分析报告')}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 30px; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .summary {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .kpi-grid {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .kpi {{ background: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 6px; text-align: center; }}
        .kpi .label {{ display: block; color: #666; font-size: 0.85em; }}
        .kpi .value {{ display: block; font-size: 1.5em; font-weight: bold; color: #007bff; }}
        ul {{ line-height: 1.8; }}
        section {{ margin-bottom: 30px; }}
    </style>
</head>
<body>
    <h1>{metadata.get('title', '分析报告')}</h1>
    <p class="meta">{metadata.get('subtitle', '')} | 生成时间: {metadata.get('generatedAt', '')}</p>

    <div class="summary">
        <h3>核心发现</h3>
        <ul>{highlights_html}</ul>
    </div>

    {chapters_html}

    <footer style="margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 0.85em;">
        <p>本报告由 BettaFish 舆情分析系统自动生成</p>
    </footer>
</body>
</html>"""


def generate_mock_markdown(query: str, ir_json: dict) -> str:
    """
    生成模拟的 Markdown 报告

    Args:
        query: 用户查询
        ir_json: IR JSON 数据

    Returns:
        Markdown 字符串
    """
    metadata = ir_json.get("metadata", {})
    summary = ir_json.get("summary", {})
    chapters = ir_json.get("chapters", [])

    md = f"# {metadata.get('title', '分析报告')}\n\n"
    md += f"> {metadata.get('subtitle', '')} | 生成时间: {metadata.get('generatedAt', '')}\n\n"

    md += "## 核心发现\n\n"
    for h in summary.get("highlights", []):
        md += f"- {h}\n"
    md += "\n"

    for chapter in chapters:
        md += f"## {chapter['title']}\n\n"
        for block in chapter.get("blocks", []):
            if block["type"] == "paragraph":
                md += f"{block['content']}\n\n"
            elif block["type"] == "list":
                for item in block.get("items", []):
                    md += f"- {item}\n"
                md += "\n"
            elif block["type"] == "kpiGrid":
                md += "| 指标 | 数值 |\n|------|------|\n"
                for item in block.get("items", []):
                    md += f"| {item['label']} | {item['value']} |\n"
                md += "\n"

    md += "---\n\n*本报告由 BettaFish 舆情分析系统自动生成*\n"

    return md


def start_mock_execution(task_id: str, task_manager: "TaskManager"):
    """
    启动模拟任务执行
    使用后台线程模拟任务进度更新

    Args:
        task_id: 任务ID
        task_manager: 任务管理器实例
    """
    def mock_execute():
        task = task_manager.get_task(task_id)
        if not task:
            return

        # 阶段 1: 2秒后变为 running (10%)
        time.sleep(2)
        task_manager.update_task(task_id, status="running", progress=10)

        # 阶段 2: 3秒后 (30%)
        time.sleep(3)
        task_manager.update_task(task_id, progress=30)

        # 阶段 3: 2秒后 (50%)
        time.sleep(2)
        task_manager.update_task(task_id, progress=50)

        # 阶段 4: 2秒后 (75%)
        time.sleep(2)
        task_manager.update_task(task_id, progress=75)

        # 阶段 5: 1秒后完成 (100%)
        time.sleep(1)

        # 生成 mock 结果
        task = task_manager.get_task(task_id)
        if task:
            mock_result = generate_mock_ir_json(task.query, task_id)
            task_manager.update_task(
                task_id,
                status="completed",
                progress=100,
                result=mock_result
            )

    # 启动后台线程
    thread = threading.Thread(target=mock_execute, daemon=True)
    thread.start()
