# BettaFish 现有 API 接口文档

本文档列出了项目中所有可直接使用的 API 接口，便于独立前端对接。

---

## 目录

- [1. 系统管理 API](#1-系统管理-api)
- [2. 配置管理 API](#2-配置管理-api)
- [3. 应用管理 API](#3-应用管理-api)
- [4. 论坛管理 API](#4-论坛管理-api)
- [5. 搜索 API](#5-搜索-api)
- [6. 报告引擎 API](#6-报告引擎-api)
- [7. 知识图谱 API](#7-知识图谱-api)
- [8. 异步任务 API (v2)](#8-异步任务-api-v2)
  - [执行模式](#执行模式)
  - [Orchestrator 模式阶段进度](#orchestrator-模式阶段进度)
- [9. WebSocket 事件](#9-websocket-事件)

---

## 1. 系统管理 API

### GET /api/system/status

获取系统启动状态。

**响应示例：**
```json
{
  "success": true,
  "started": true,
  "starting": false
}
```

---

### POST /api/system/start

启动完整系统（包括所有 Streamlit 子应用、ForumEngine、ReportEngine）。

**响应示例：**
```json
{
  "success": true,
  "message": "系统启动成功",
  "logs": ["检查文件: ...", "insight: 应用启动中...", ...]
}
```

**错误响应：**
```json
{
  "success": false,
  "message": "系统启动失败",
  "logs": [...],
  "errors": ["insight 启动失败: ..."]
}
```

---

### POST /api/system/shutdown

优雅停止所有组件并关闭服务进程。

**响应示例：**
```json
{
  "success": true,
  "message": "关闭系统指令已下发，正在停止进程",
  "ports": ["insight:8501", "media:8502", "query:8503"]
}
```

---

## 2. 配置管理 API

### GET /api/config

获取当前配置值。

**响应示例：**
```json
{
  "success": true,
  "config": {
    "HOST": "127.0.0.1",
    "PORT": "5000",
    "DB_DIALECT": "mysql",
    "DB_HOST": "localhost",
    "DB_PORT": "3306",
    "DB_USER": "root",
    "DB_PASSWORD": "****",
    "DB_NAME": "bettafish",
    "INSIGHT_ENGINE_API_KEY": "sk-xxx",
    "INSIGHT_ENGINE_BASE_URL": "https://api.openai.com/v1",
    "INSIGHT_ENGINE_MODEL_NAME": "gpt-4",
    "MEDIA_ENGINE_API_KEY": "...",
    "QUERY_ENGINE_API_KEY": "...",
    "REPORT_ENGINE_API_KEY": "...",
    "TAVILY_API_KEY": "...",
    "SEARCH_TOOL_TYPE": "tavily",
    "GRAPHRAG_ENABLED": "True",
    "GRAPHRAG_MAX_QUERIES": "10"
  }
}
```

---

### POST /api/config

更新配置值（持久化到 .env 文件）。

**请求体：**
```json
{
  "HOST": "0.0.0.0",
  "PORT": "8080",
  "INSIGHT_ENGINE_API_KEY": "new-api-key"
}
```

**响应示例：**
```json
{
  "success": true,
  "config": { ... }
}
```

---

## 3. 应用管理 API

### GET /api/status

获取所有子应用状态。

**响应示例：**
```json
{
  "insight": {
    "status": "running",
    "port": 8501,
    "output_lines": 42
  },
  "media": {
    "status": "running",
    "port": 8502,
    "output_lines": 38
  },
  "query": {
    "status": "stopped",
    "port": 8503,
    "output_lines": 0
  },
  "forum": {
    "status": "running",
    "port": null,
    "output_lines": 15
  }
}
```

**status 可能的值：** `stopped` | `starting` | `running`

---

### GET /api/start/{app_name}

启动指定应用。

**路径参数：**
- `app_name`: `insight` | `media` | `query` | `forum`

**响应示例：**
```json
{
  "success": true,
  "message": "insight 应用启动中..."
}
```

---

### GET /api/stop/{app_name}

停止指定应用。

**响应示例：**
```json
{
  "success": true,
  "message": "insight 应用已停止"
}
```

---

### GET /api/restart/{app_name}

重启指定应用。

**响应示例：**
```json
{
  "success": true,
  "message": "insight 应用已重启",
  "stop_message": "insight 应用已停止",
  "start_message": "insight 应用启动中..."
}
```

---

### GET /api/output/{app_name}

获取应用日志输出。

**响应示例：**
```json
{
  "success": true,
  "output": [
    "[10:30:15] 启动 insight 应用...",
    "[10:30:18] Streamlit server running on port 8501"
  ]
}
```

---

## 4. 论坛管理 API

### GET /api/forum/start

启动 ForumEngine 论坛监控。

**响应示例：**
```json
{
  "success": true,
  "message": "ForumEngine论坛已启动"
}
```

---

### GET /api/forum/stop

停止 ForumEngine 论坛监控。

**响应示例：**
```json
{
  "success": true,
  "message": "ForumEngine论坛已停止"
}
```

---

### GET /api/forum/log

获取论坛日志内容（已解析的对话消息）。

**响应示例：**
```json
{
  "success": true,
  "log_lines": [
    "[10:30:15] [HOST] 欢迎来到论坛...",
    "[10:30:20] [QUERY] 正在分析用户问题..."
  ],
  "parsed_messages": [
    {
      "type": "host",
      "sender": "Forum Host",
      "content": "欢迎来到论坛...",
      "timestamp": "10:30:15",
      "source": "HOST"
    },
    {
      "type": "agent",
      "sender": "Query Engine",
      "content": "正在分析用户问题...",
      "timestamp": "10:30:20",
      "source": "QUERY"
    }
  ],
  "total_lines": 2
}
```

---

### POST /api/forum/log/history

获取论坛历史日志（支持分页）。

**请求体：**
```json
{
  "position": 0,
  "max_lines": 1000
}
```

**响应示例：**
```json
{
  "success": true,
  "log_lines": [...],
  "position": 2048,
  "has_more": true
}
```

---

## 5. 搜索 API

### POST /api/search

统一搜索接口（向运行中的引擎发送搜索请求）。

**请求体：**
```json
{
  "query": "搜索关键词"
}
```

**响应示例：**
```json
{
  "success": true,
  "query": "搜索关键词",
  "results": {
    "insight": { "success": true, ... },
    "media": { "success": true, ... },
    "query": { "success": false, "message": "应用未运行" }
  }
}
```

---

## 6. 报告引擎 API

所有报告引擎接口前缀为 `/api/report`。

### GET /api/report/status

获取报告引擎状态。

**响应示例：**
```json
{
  "success": true,
  "initialized": true,
  "engines_ready": true,
  "files_found": ["insight_report.md", "media_report.md", "query_report.md"],
  "missing_files": [],
  "current_task": null
}
```

---

### POST /api/report/generate

开始生成报告（异步任务）。

**请求体：**
```json
{
  "query": "智能舆情分析报告",
  "custom_template": ""
}
```

**响应示例：**
```json
{
  "success": true,
  "task_id": "report_1705632000",
  "message": "报告生成已启动",
  "task": {
    "task_id": "report_1705632000",
    "query": "智能舆情分析报告",
    "status": "pending",
    "progress": 0,
    "error_message": "",
    "created_at": "2024-01-19T10:00:00",
    "updated_at": "2024-01-19T10:00:00",
    "has_result": false,
    "report_file_ready": false
  },
  "stream_url": "/api/report/stream/report_1705632000"
}
```

---

### GET /api/report/progress/{task_id}

查询任务进度。

**响应示例：**
```json
{
  "success": true,
  "task": {
    "task_id": "report_1705632000",
    "status": "running",
    "progress": 45,
    "error_message": "",
    "has_result": false,
    "report_file_ready": false
  }
}
```

**status 可能的值：** `pending` | `running` | `completed` | `error` | `cancelled`

---

### GET /api/report/stream/{task_id}

SSE 实时事件流（用于进度推送）。

**Content-Type:** `text/event-stream`

**事件类型：**
| 事件类型 | 说明 |
|---------|------|
| `status` | 状态变更 |
| `progress` | 进度更新 |
| `stage` | 阶段信息 |
| `log` | 日志输出 |
| `warning` | 警告信息 |
| `html_ready` | HTML 渲染完成 |
| `completed` | 任务完成 |
| `error` | 任务失败 |
| `cancelled` | 任务取消 |
| `heartbeat` | 心跳保活 |

**事件格式示例：**
```
id: 1
event: status
data: {"type":"status","task_id":"report_1705632000","payload":{"status":"running","progress":10}}

id: 2
event: stage
data: {"type":"stage","task_id":"report_1705632000","payload":{"message":"正在生成报告","stage":"agent_running"}}
```

---

### GET /api/report/result/{task_id}

获取报告 HTML 内容。

**Content-Type:** `text/html`

返回完整的 HTML 报告内容。

---

### GET /api/report/result/{task_id}/json

获取报告结果（JSON 格式）。

**响应示例：**
```json
{
  "success": true,
  "task": { ... },
  "html_content": "<html>...</html>"
}
```

---

### GET /api/report/download/{task_id}

下载报告 HTML 文件。

**Content-Type:** `text/html`
**Content-Disposition:** `attachment; filename="report_xxx.html"`

---

### POST /api/report/cancel/{task_id}

取消报告生成任务。

**响应示例：**
```json
{
  "success": true,
  "message": "任务已取消"
}
```

---

### GET /api/report/templates

获取可用的报告模板列表。

**响应示例：**
```json
{
  "success": true,
  "templates": [
    {
      "name": "default",
      "filename": "default.md",
      "description": "# 默认模板",
      "size": 1024
    }
  ],
  "template_dir": "ReportEngine/templates"
}
```

---

### GET /api/report/log

获取报告生成日志。

**响应示例：**
```json
{
  "success": true,
  "log_lines": [
    "[10:30:15] [INFO] 开始生成报告...",
    "[10:30:20] [INFO] 正在调用 LLM..."
  ]
}
```

---

### POST /api/report/log/clear

清空报告日志。

**响应示例：**
```json
{
  "success": true,
  "message": "日志已清空"
}
```

---

### GET /api/report/export/md/{task_id}

导出报告为 Markdown 格式。

**Content-Type:** `text/markdown`
**Content-Disposition:** `attachment; filename="report_xxx.md"`

---

### GET /api/report/export/pdf/{task_id}

导出报告为 PDF 格式。

**查询参数：**
- `optimize`: 是否启用布局优化（默认 `true`）

**Content-Type:** `application/pdf`
**Content-Disposition:** `attachment; filename="report_xxx.pdf"`

**注意：** 需要安装 Pango 系统依赖，否则返回 503 错误。

---

### POST /api/report/export/pdf-from-ir

从 IR JSON 直接导出 PDF（无需任务 ID）。

**请求体：**
```json
{
  "document_ir": { ... },
  "optimize": true
}
```

**Content-Type:** `application/pdf`

---

## 7. 知识图谱 API

### GET /api/graph/{report_id}

获取指定报告的知识图谱数据。

**响应示例：**
```json
{
  "success": true,
  "graph": {
    "nodes": [
      {
        "id": "node_1",
        "label": "舆情分析",
        "group": "section",
        "title": "<b>舆情分析</b><br>类型: section",
        "properties": { "summary": "..." }
      }
    ],
    "edges": [
      {
        "from": "node_1",
        "to": "node_2",
        "label": "contains",
        "arrows": "to"
      }
    ],
    "stats": {
      "node_count": 15,
      "edge_count": 20
    }
  }
}
```

---

### GET /api/graph/latest

获取最近一次生成的知识图谱。

**响应示例：**
```json
{
  "success": true,
  "report_id": "report_1705632000",
  "graph": { ... }
}
```

---

### POST /api/graph/query

查询知识图谱。

**请求体：**
```json
{
  "report_id": "report_1705632000",
  "keywords": ["舆情", "分析"],
  "node_types": ["section", "source"],
  "engine_filter": "insight",
  "depth": 2
}
```

**响应示例：**
```json
{
  "success": true,
  "result": {
    "matched_sections": [...],
    "matched_queries": [...],
    "matched_sources": [...],
    "total_nodes": 15,
    "query_params": { ... },
    "summary": "找到 3 个章节、5 个查询、7 个来源"
  }
}
```

---

## 8. 异步任务 API (v2)

异步任务 API 提供"提交任务 + 轮询查询"模式，适用于长时间运行的分析任务。所有接口前缀为 `/api/v2`。

### GET /api/v2/health

健康检查端点，检查 Redis 连接和任务统计。

**响应示例：**
```json
{
  "status": "healthy",
  "service": "BettaFish API v2",
  "components": {
    "redis": "healthy"
  },
  "task_stats": {
    "pending": 2,
    "running": 1,
    "generating_report": 0,
    "completed": 15,
    "failed": 0,
    "total": 18
  }
}
```

**status 可能的值：** `healthy` | `degraded`（Redis 连接失败时）

---

### POST /api/v2/analyze

提交分析任务，立即返回任务 ID，不阻塞等待结果。

**请求体：**
```json
{
  "query": "武汉大学舆情分析",
  "options": {
    "mode": "phased",
    "priority": "normal"
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 分析查询内容（最大 500 字符） |
| `options.mode` | string | 否 | 执行模式：`phased`（默认，Orchestrator 模式）或 `standard`（直接并行模式） |
| `options.priority` | string | 否 | 预留扩展字段 |

**执行模式说明：**

| 模式 | 说明 |
|------|------|
| `phased` | **Orchestrator 模式**（默认）：三阶段执行（Plan → Research → Report），每阶段由 Orchestrator 进行 LLM 决策评审，支持 guidance 指导和补充研究 |
| `standard` | **标准模式**：三个 Agent 直接并行执行研究，完成后生成报告 |

**响应示例：**
```json
{
  "success": true,
  "task_id": "task_1706123456789",
  "status": "pending",
  "mode": "phased",
  "message": "任务已提交（Orchestrator 模式）",
  "poll_url": "/api/v2/task/task_1706123456789"
}
```

**错误响应：**
```json
{
  "success": false,
  "error": "查询内容不能为空"
}
```

---

### GET /api/v2/task/{task_id}

查询任务状态和进度。

**路径参数：**
- `task_id`: 任务 ID

**响应示例（进行中）：**
```json
{
  "task_id": "task_1706123456789_1",
  "query": "武汉大学舆情分析",
  "status": "running",
  "progress": 45,
  "created_at": "2026-01-24T10:00:00",
  "updated_at": "2026-01-24T10:05:00",
  "message": "Agent 正在执行研究..."
}
```

**响应示例（已完成）：**
```json
{
  "task_id": "task_1706123456789_1",
  "query": "武汉大学舆情分析",
  "status": "completed",
  "progress": 100,
  "created_at": "2026-01-24T10:00:00",
  "updated_at": "2026-01-24T10:25:00",
  "completed_at": "2026-01-24T10:25:00",
  "message": "分析完成",
  "result": {
    "title": "武汉大学舆情分析分析报告",
    "summary": ["发现 3 个主要舆情热点", "整体情感倾向偏正面"],
    "available_formats": ["json", "html", "pdf", "md"]
  },
  "result_url": "/api/v2/task/task_1706123456789_1/result"
}
```

**status 可能的值：**

| 状态 | 说明 |
|------|------|
| `pending` | 任务已提交，等待执行 |
| `running` | Agent 正在执行研究（标准模式） |
| `phase1_plan` | Phase 1: Agent 正在生成研究计划（Orchestrator 模式） |
| `orchestrating_plan` | Orchestrator 正在评审 Plan（Orchestrator 模式） |
| `phase2_research` | Phase 2: Agent 正在执行研究（Orchestrator 模式） |
| `orchestrating_research` | Orchestrator 正在评审 Research（Orchestrator 模式） |
| `phase2_supplement` | Phase 2: 补充研究中（Orchestrator 模式，最多 1 轮） |
| `phase3_report` | Phase 3: Agent 正在生成报告（Orchestrator 模式） |
| `generating_report` | 正在生成最终报告（标准模式） |
| `generating_final_report` | 正在生成最终报告（Orchestrator 模式） |
| `completed` | 分析完成 |
| `failed` | 任务执行失败 |

---

### GET /api/v2/task/{task_id}/progress

获取任务各 Agent 的详细进度。

**路径参数：**
- `task_id`: 任务 ID

**响应示例：**
```json
{
  "success": true,
  "task_id": "task_1706123456789_1",
  "status": "running",
  "overall_progress": 45,
  "agents": {
    "query": {
      "status": "completed",
      "progress": 100,
      "updated_at": "2026-01-24T10:05:00"
    },
    "media": {
      "status": "running",
      "progress": 50,
      "updated_at": "2026-01-24T10:06:00"
    },
    "insight": {
      "status": "pending",
      "progress": 0
    }
  }
}
```

---

### GET /api/v2/task/{task_id}/phases

获取任务的阶段性进度详情（仅适用于 Orchestrator 模式）。

返回每个 Agent 的当前阶段、各阶段结果、Orchestrator 决策、Forum 讨论日志等。

**路径参数：**
- `task_id`: 任务 ID

**响应示例：**
```json
{
  "success": true,
  "task_id": "task_1706123456789",
  "phases": {
    "query": "research",
    "media": "research",
    "insight": "plan"
  },
  "plans": {
    "query": {
      "keywords": ["武汉大学", "舆情"],
      "search_strategy": "broad",
      "report_structure": ["introduction", "findings", "conclusion"]
    },
    "media": {
      "media_types": ["video", "image"],
      "keywords": ["武汉大学"]
    },
    "insight": {
      "analysis_aspects": ["trends", "insights"],
      "keywords": ["武汉大学"]
    }
  },
  "research": {
    "query": {
      "result": "...",
      "plan": {...},
      "guidance_applied": true
    }
  },
  "reports": {},
  "supplement_round": 0,
  "guidance": {
    "plan": "建议增加时间维度的分析",
    "research": null
  },
  "forum_log": [
    {
      "speaker": "system",
      "content": "开始阶段性分析: 武汉大学舆情分析",
      "timestamp": "2026-01-24T10:00:00"
    },
    {
      "speaker": "query",
      "content": "开始 Plan 阶段",
      "timestamp": "2026-01-24T10:00:01"
    },
    {
      "speaker": "orchestrator",
      "content": "Plan 评审：approve",
      "timestamp": "2026-01-24T10:01:00"
    }
  ]
}
```

**响应字段说明：**

| 字段 | 说明 |
|------|------|
| `phases` | 各 Agent 当前所在阶段（plan/research/report） |
| `plans` | 各 Agent 的 Plan 阶段输出（研究计划） |
| `research` | 各 Agent 的 Research 阶段输出（研究结果） |
| `reports` | 各 Agent 的 Report 阶段输出（报告内容） |
| `supplement_round` | 补充研究轮次（0 表示未补充，最大 1） |
| `guidance.plan` | Orchestrator 对 Plan 阶段的指导意见 |
| `guidance.research` | Orchestrator 对 Research 阶段的指导意见 |
| `forum_log` | 完整的 Forum 讨论日志（Blackboard 模式下替代 forum.log 文件） |

---

### GET /api/v2/task/{task_id}/result

获取任务完整结果，支持多种输出格式。

**路径参数：**
- `task_id`: 任务 ID

**查询参数：**
- `format`: 输出格式，可选值：`json` | `html` | `md` | `pdf`（默认 `json`）

#### format=json

返回完整的 IR JSON 结构。

**Content-Type:** `application/json`

**响应示例：**
```json
{
  "success": true,
  "data": {
    "reportId": "task_1706123456789_1",
    "metadata": {
      "query": "武汉大学舆情分析",
      "title": "武汉大学舆情分析分析报告",
      "subtitle": "基于多源数据的综合分析",
      "generatedAt": "2026-01-24T10:25:00"
    },
    "summary": {
      "highlights": [
        "发现 3 个主要舆情热点",
        "整体情感倾向偏正面 (62%)",
        "主要传播平台为微博和抖音"
      ],
      "kpis": [
        {"label": "舆情热度", "value": "8.5/10", "trend": "up"},
        {"label": "讨论量", "value": "12.3万", "trend": "up"},
        {"label": "正面占比", "value": "62%", "trend": "stable"}
      ]
    },
    "chapters": [
      {
        "chapterId": "S1",
        "title": "报告摘要",
        "blocks": [
          {"type": "paragraph", "content": "本报告针对..."}
        ]
      }
    ],
    "sources": [
      {"engine": "QueryEngine", "source": "综合网络搜索", "count": 15},
      {"engine": "MediaEngine", "source": "社交媒体分析", "count": 20},
      {"engine": "InsightEngine", "source": "深度洞察分析", "count": 8}
    ]
  }
}
```

#### format=html

返回渲染后的 HTML 报告。

**Content-Type:** `text/html`

**Content-Disposition:** `inline; filename="report_task_xxx.html"`

#### format=md

返回 Markdown 格式报告。

**Content-Type:** `text/markdown`

**Content-Disposition:** `attachment; filename="report_task_xxx.md"`

#### format=pdf

返回 PDF 格式报告（暂未实现）。

**响应（501）：**
```json
{
  "success": false,
  "error": "PDF 格式暂未实现，请使用 json/html/md 格式"
}
```

**错误响应（任务未完成）：**
```json
{
  "success": false,
  "error": "任务未完成，当前状态: running",
  "status": "running",
  "progress": 45
}
```

---

### GET /api/v2/tasks

列出所有任务。

**查询参数：**
- `limit`: 返回数量限制（默认 50，最大 100）
- `offset`: 偏移量（默认 0）

**响应示例：**
```json
{
  "success": true,
  "tasks": [
    {
      "task_id": "task_1706123456789_1",
      "query": "武汉大学舆情分析",
      "status": "completed",
      "progress": 100,
      "created_at": "2026-01-24T10:00:00",
      "completed_at": "2026-01-24T10:25:00",
      "message": "分析完成"
    },
    {
      "task_id": "task_1706123456000_1",
      "query": "新能源汽车市场分析",
      "status": "running",
      "progress": 30,
      "created_at": "2026-01-24T09:50:00",
      "message": "Agent 正在执行研究..."
    }
  ],
  "total": 18,
  "stats": {
    "pending": 2,
    "running": 1,
    "completed": 15,
    "failed": 0,
    "total": 18
  }
}
```

---

### 轮询最佳实践

建议使用指数退避策略轮询任务状态：

```javascript
async function pollTask(taskId) {
  const baseUrl = '/api/v2/task';
  let delay = 1000; // 初始延迟 1 秒
  const maxDelay = 10000; // 最大延迟 10 秒

  while (true) {
    const response = await fetch(`${baseUrl}/${taskId}`);
    const data = await response.json();

    if (data.status === 'completed') {
      return data;
    }
    if (data.status === 'failed') {
      throw new Error(data.error_message);
    }

    // 等待后重试，逐步增加延迟
    await new Promise(resolve => setTimeout(resolve, delay));
    delay = Math.min(delay * 1.5, maxDelay);
  }
}
```

---

## 9. WebSocket 事件

使用 Socket.IO 协议，连接地址与 HTTP 服务相同。

### 客户端 → 服务器

| 事件名 | 说明 | 数据格式 |
|-------|------|---------|
| `connect` | 建立连接 | - |
| `request_status` | 请求状态更新 | - |

### 服务器 → 客户端

| 事件名 | 说明 | 数据格式 |
|-------|------|---------|
| `status` | 连接确认 | `"Connected to Flask server"` |
| `status_update` | 应用状态推送 | `{ "insight": { "status": "running", "port": 8501 }, ... }` |
| `console_output` | 控制台日志推送 | `{ "app": "insight", "line": "[10:30:15] ..." }` |
| `forum_message` | 论坛消息推送 | `{ "type": "agent", "sender": "Query Engine", "content": "...", "timestamp": "10:30:15" }` |

**连接示例（JavaScript）：**
```javascript
import { io } from 'socket.io-client';

const socket = io('http://localhost:5000');

socket.on('connect', () => {
  console.log('Connected');
  socket.emit('request_status');
});

socket.on('status_update', (data) => {
  console.log('Status:', data);
});

socket.on('console_output', (data) => {
  console.log(`[${data.app}] ${data.line}`);
});

socket.on('forum_message', (msg) => {
  console.log(`[${msg.sender}] ${msg.content}`);
});
```

---

## 通用响应格式

所有 JSON API 遵循统一响应格式：

**成功响应：**
```json
{
  "success": true,
  ...
}
```

**错误响应：**
```json
{
  "success": false,
  "error": "错误信息",
  "message": "详细说明（可选）"
}
```

**HTTP 状态码：**
| 状态码 | 说明 |
|-------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用（如缺少依赖） |

---

## 配置项列表

可通过 `/api/config` 管理的配置项：

| 配置项 | 说明 |
|-------|------|
| `HOST` | 服务器主机地址 |
| `PORT` | 服务器端口 |
| `DB_DIALECT` | 数据库类型 |
| `DB_HOST` | 数据库主机 |
| `DB_PORT` | 数据库端口 |
| `DB_USER` | 数据库用户名 |
| `DB_PASSWORD` | 数据库密码 |
| `DB_NAME` | 数据库名称 |
| `DB_CHARSET` | 数据库字符集 |
| `INSIGHT_ENGINE_API_KEY` | Insight 引擎 API Key |
| `INSIGHT_ENGINE_BASE_URL` | Insight 引擎 API 地址 |
| `INSIGHT_ENGINE_MODEL_NAME` | Insight 引擎模型名 |
| `MEDIA_ENGINE_API_KEY` | Media 引擎 API Key |
| `MEDIA_ENGINE_BASE_URL` | Media 引擎 API 地址 |
| `MEDIA_ENGINE_MODEL_NAME` | Media 引擎模型名 |
| `QUERY_ENGINE_API_KEY` | Query 引擎 API Key |
| `QUERY_ENGINE_BASE_URL` | Query 引擎 API 地址 |
| `QUERY_ENGINE_MODEL_NAME` | Query 引擎模型名 |
| `REPORT_ENGINE_API_KEY` | Report 引擎 API Key |
| `REPORT_ENGINE_BASE_URL` | Report 引擎 API 地址 |
| `REPORT_ENGINE_MODEL_NAME` | Report 引擎模型名 |
| `FORUM_HOST_API_KEY` | 论坛主持人 API Key |
| `FORUM_HOST_BASE_URL` | 论坛主持人 API 地址 |
| `FORUM_HOST_MODEL_NAME` | 论坛主持人模型名 |
| `KEYWORD_OPTIMIZER_API_KEY` | 关键词优化 API Key |
| `KEYWORD_OPTIMIZER_BASE_URL` | 关键词优化 API 地址 |
| `KEYWORD_OPTIMIZER_MODEL_NAME` | 关键词优化模型名 |
| `TAVILY_API_KEY` | Tavily 搜索 API Key |
| `SEARCH_TOOL_TYPE` | 搜索工具类型 |
| `BOCHA_WEB_SEARCH_API_KEY` | Bocha 搜索 API Key |
| `ANSPIRE_API_KEY` | Anspire API Key |
| `GRAPHRAG_ENABLED` | 是否启用知识图谱 |
| `GRAPHRAG_MAX_QUERIES` | 图谱查询最大数量 |
| `REDIS_HOST` | Redis 服务器地址（默认 127.0.0.1） |
| `REDIS_PORT` | Redis 端口号（默认 6379） |
| `REDIS_DB` | Redis 数据库编号（默认 10） |
| `REDIS_PASSWORD` | Redis 密码（可选） |

---

## 备注

1. **异步任务 API (v2)**：`/api/v2/*` 接口使用 Celery + Redis 实现真正的异步任务处理，支持两种执行模式：

   **标准模式 (standard)**：
   - 3 个 Agent（QueryEngine, MediaEngine, InsightEngine）直接并行执行
   - 完成后自动触发报告生成

   **Orchestrator 模式 (phased)**（默认）：
   - 三阶段执行：Plan → Research → Report
   - 每阶段由 Orchestrator 进行 LLM 决策评审
   - 使用 Blackboard (Redis) 共享 Agent 间状态
   - 支持 guidance 指导机制和补充研究（最多 1 轮）
   - 通过 `/api/v2/task/{id}/phases` 获取详细阶段进度

2. **Celery 服务启动**：需要先启动 Redis 和 Celery Worker：
   ```bash
   # 开发环境（推荐，高并发）
   PYTHONPATH=/path/to/BettaFish celery -A celery_app worker --loglevel=info -Q celery,agents,orchestrator,report --pool=gevent --concurrency=30

   # 或使用 prefork（默认）
   PYTHONPATH=/path/to/BettaFish celery -A celery_app worker --loglevel=info -Q celery,agents,orchestrator,report --concurrency=4

   # 使用 Docker Compose（生产环境）
   docker-compose up -d

   # 定时任务（可选）
   celery -A celery_app beat --loglevel=info
   ```

   **队列说明：**
   | 队列 | 任务类型 |
   |------|---------|
   | `celery` | 主编排任务 |
   | `agents` | Agent 研究任务（plan/research/report） |
   | `orchestrator` | Orchestrator LLM 决策任务 |
   | `report` | 报告生成任务 |

3. **Flower 监控面板**：访问 `http://localhost:5555` 查看 Celery 任务监控。

4. **清除 Celery 残留任务**：开发调试时清除所有任务数据（队列、结果、Blackboard 状态、缓存）：
   ```bash
   # Python 版本（推荐）
   python clear_celery_tasks.py              # 交互模式（会询问是否清除缓存）
   python clear_celery_tasks.py --all        # 清除所有（包括缓存）
   python clear_celery_tasks.py --cache-only # 仅清除查询缓存
   python clear_celery_tasks.py --yes        # 跳过确认提示

   # Bash 版本
   ./clear_celery_tasks.sh                   # 交互模式
   ```

   **清除内容：**
   - Celery 任务队列（celery, agents, orchestrator, report）
   - Celery 任务结果（celery-task-meta-*）
   - 自定义任务数据（task:* 包括 Blackboard 状态）
   - 任务列表（tasks:all）
   - 查询缓存（cache:query:* 可选）

5. **三引擎独立 API 尚未实现**：QueryEngine、InsightEngine、MediaEngine 目前仅通过 Streamlit 应用间接调用，尚无直接的 Flask API。如需独立对接，需后续开发。

5. **默认端口**：
   - Flask 主服务：5000
   - Insight Engine：8501
   - Media Engine：8502
   - Query Engine：8503
   - Redis：6379
   - Flower：5555

6. **跨域支持**：Socket.IO 已配置 `cors_allowed_origins="*"`，HTTP API 可能需要额外配置 CORS。

7. **Redis 数据结构（Blackboard 模式）**：
   | Key Pattern | 说明 | TTL |
   |-------------|------|-----|
   | `task:{id}:agent:{name}:phase` | Agent 当前阶段 | 7 天 |
   | `task:{id}:agent:{name}:plan` | Plan 阶段输出 | 7 天 |
   | `task:{id}:agent:{name}:research` | Research 阶段输出 | 7 天 |
   | `task:{id}:agent:{name}:report` | Report 阶段输出 | 7 天 |
   | `task:{id}:guidance:plan` | Plan 阶段 guidance | 7 天 |
   | `task:{id}:guidance:research` | Research 阶段 guidance | 7 天 |
   | `task:{id}:supplement:round` | 补充轮次计数 | 7 天 |
   | `task:{id}:forum:log` | Forum 讨论记录 (List) | 7 天 |