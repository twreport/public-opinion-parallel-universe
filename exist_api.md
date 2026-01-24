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
- [8. WebSocket 事件](#8-websocket-事件)

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

## 8. WebSocket 事件

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

---

## 备注

1. **三引擎独立 API 尚未实现**：QueryEngine、InsightEngine、MediaEngine 目前仅通过 Streamlit 应用间接调用，尚无直接的 Flask API。如需独立对接，需后续开发。

2. **默认端口**：
   - Flask 主服务：5000
   - Insight Engine：8501
   - Media Engine：8502
   - Query Engine：8503

3. **跨域支持**：Socket.IO 已配置 `cors_allowed_origins="*"`，HTTP API 可能需要额外配置 CORS。