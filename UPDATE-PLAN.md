# BettaFish 架构改造计划

## 项目背景

本项目 Fork 自 [666ghj/BettaFish](https://github.com/666ghj/BettaFish)，原项目采用 Flask + Streamlit 子进程 + iframe 的架构，前端通过刷新 iframe URL 参数触发各 Agent 的搜索功能。

## 改造目标

将项目改造为纯 API 服务，支持异步任务处理，满足多用户并发访问和热点预分析缓存的需求。

---

## 核心需求一：API 化改造

### 改造原因

1. **分析耗时长**：单次完整分析需要 15-30 分钟，不适合同步请求-响应模式
2. **前端解耦**：放弃 Streamlit + iframe 的前端，允许任意客户端通过 API 调用
3. **灵活集成**：API 方式更便于与其他系统集成，或构建自定义前端

### 改造思路

1. **提交任务接口**：`POST /api/analyze`
   - 接收用户输入的分析问题
   - 立即返回 `task_id`，不阻塞等待结果

2. **查询任务接口**：`GET /api/task/{task_id}`
   - 用户使用 `task_id` 轮询任务状态
   - 返回状态：`pending` → `running` → `completed` / `failed`
   - 任务完成后返回报告内容或报告路径

### 技术可行性

经代码分析确认，三个 Agent 的核心类**完全独立于 Streamlit**：

| Agent | 核心类位置 | 统一接口 |
|-------|-----------|----------|
| QueryEngine | `QueryEngine/agent.py:DeepSearchAgent` | `research(query) → str` |
| MediaEngine | `MediaEngine/agent.py:DeepSearchAgent` | `research(query) → str` |
| InsightEngine | `InsightEngine/agent.py:DeepSearchAgent` | `research(query) → str` |
| ReportEngine | `ReportEngine/agent.py:ReportAgent` | 从文件读取 → 生成报告 |

Streamlit 应用（`SingleEngineApp/*.py`）只是包装层，核心逻辑可直接调用。

---

## 核心需求二：Celery 任务队列

### 改造原因

1. **并发访问**：预计 10 个以下并发用户，每个请求触发 3 个 Agent 并行执行
2. **资源控制**：10 并发 × 3 Agent × 30 分钟 = 同时 30 个长任务，需要排队控制
3. **缓存需求**：热点资讯需要预分析缓存，提升用户体验和产品演示效果
4. **后台调度**：需要定时预热热门话题的分析结果

### 为什么选择 Celery

| 能力 | 必要性 | Celery 支持 |
|------|--------|-------------|
| 任务排队 | 必须 | ✅ |
| Worker 池控制（限制并发数） | 必须 | ✅ |
| 任务持久化（服务重启不丢任务） | 必须 | ✅ |
| 结果缓存 | 必须 | ✅ 配合 Redis |
| 定时调度（预热热点） | 必须 | ✅ Celery Beat |
| 任务重试 | 需要 | ✅ |
| 分布式扩展 | 未来 | ✅ |

### 架构设计

```
Flask API
    │
    ▼
Redis（任务队列 + 结果缓存）
    │
    ▼
Celery Workers（并发数可控）
    ├── Query Agent
    ├── Media Agent
    └── Insight Agent
           │
           ▼
    ReportEngine（汇总报告）

Celery Beat（定时任务）
    └── 热点预热、缓存清理
```

### 关键设计点

1. **并发控制**：Worker 并发数设为 3，避免资源爆炸
2. **任务编排**：3 个 Agent 并行执行，全部完成后触发 ReportEngine
3. **结果缓存**：相同查询复用缓存结果（TTL 24 小时）
4. **任务去重**：相同查询正在执行时，新请求等待现有任务
5. **定时预热**：每日凌晨自动分析热门话题

---

## 核心需求三：输出格式（后端统一渲染）

### 当前数据结构

系统生成的数据分为多个层次：

| 数据层 | 位置 | 说明 |
|--------|------|------|
| IR JSON | `final_reports/ir/*.json` | 结构化中间表示，核心数据源 |
| Chapter JSON | `final_reports/chapters/*/chapter.json` | 各章节内容（blocks 数组） |
| HTML | `final_reports/final_report_*.html` | 渲染后的完整报告（~2MB） |
| State JSON | `final_reports/report_state_*.json` | 任务状态信息 |

IR JSON 包含完整的报告元数据（标题、摘要、KPI、目录）和章节内容（heading、paragraph、list、chart、kpiGrid、engineQuote 等 block 类型）。

### 设计决策

- **所有格式在后端渲染**，一体化交付
- 用户通过 API 参数选择返回格式
- 现有渲染器均可复用

### API 设计

```
GET /api/task/{task_id}                     # 返回任务状态 + 精简摘要
GET /api/task/{task_id}/result?format=json  # 完整 IR JSON
GET /api/task/{task_id}/result?format=html  # HTML 报告
GET /api/task/{task_id}/result?format=pdf   # PDF 下载
GET /api/task/{task_id}/result?format=md    # Markdown
```

### 现有渲染器

| 格式 | 渲染器 | 位置 |
|------|--------|------|
| HTML | `HTMLRenderer` | `ReportEngine/renderers/html_renderer.py` |
| PDF | `PDFRenderer` | `ReportEngine/renderers/pdf_renderer.py` |
| Markdown | 已有脚本 | `regenerate_latest_md.py` |
| JSON | IR 直接输出 | 无需额外渲染 |

---

## 核心需求四：Agent 扩展与 ForumEngine 改造

### 扩展计划

计划新增 2 个 Agent：

| Agent | 类型 | 数据源 |
|-------|------|--------|
| 新 Insight Agent | 类似 InsightEngine | 另一个本地爬虫数据库 |
| 新 Query Agent | 类似 QueryEngine | 另一个搜索 API |

### ForumEngine 现状分析

ForumEngine 当前**硬编码了 3 个 Agent**，扩展性差：

| 硬编码位置 | 内容 |
|-----------|------|
| `monitor.py:33-37` | 监控文件列表固定为 insight/media/query |
| `monitor.py:58-67` | 节点匹配模式硬编码 3 个 Engine 路径 |
| `monitor.py:362` | `app_names = ['INSIGHT', 'MEDIA', 'QUERY']` |
| `llm_host.py:120` | Speaker 识别只认 3 个名字 |
| `llm_host.py:147-149` | Agent 介绍硬编码 |

### ReportEngine 现状分析

ReportEngine 核心接口 `generate_report(query, reports: List[Any])` 天然支持任意数量输入，但周边方法有硬编码：

| 硬编码位置 | 内容 |
|-----------|------|
| `agent.py:343-347` | 文件基准目录固定 3 个 |
| `agent.py:1102` | `_normalize_reports` 固定 3 个 key |
| `agent.py:1602` | `check_input_files` 固定参数签名 |
| `agent.py:1683` | `load_input_files` 固定 3 个 engine |

### 改造决策

| 组件 | 决策 | 理由 |
|------|------|------|
| ForumEngine | **重新设计为 Orchestrator** | 原有日志监控模式不适合 Celery 架构 |
| ReportEngine 核心 | 保持不变 | `reports: List[Any]` 已支持 N 个 Agent |
| ReportEngine 辅助方法 | 改为配置驱动 | Celery 模式下直接传字符串，绕过文件系统 |

---

## 核心需求五：多 Agent 协调架构

### 需求描述

- Agent 间需要通信和共享中间结果
- ForumEngine 作为"主持人"分析各 Agent 输出并下发指导意见
- ForumEngine 可以干预 Agent 行为（如更换关键词、补充搜索）
- 每个 Agent 的执行拆分为多个阶段，阶段间可被 ForumEngine 干预

### 架构模式选择：Blackboard + Orchestrator

经过对业界方案（LangGraph、AutoGen、CrewAI、MetaGPT）的分析，选择 **Blackboard + Orchestrator 混合模式**，理由：

1. 不需要引入新框架，Celery + Redis 天然支持
2. Blackboard（Redis）提供共享状态，Orchestrator（ForumEngine）提供决策能力
3. 适合分布式长任务场景
4. Agent 数量固定（5 个），不需要动态发现

### 架构设计

```
┌─────────────────────────────────────────────────────┐
│                   Flask API                          │
│  POST /api/analyze → 创建任务                        │
│  GET /api/task/{id} → 查询状态/结果                  │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│               Celery Workers                         │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ...   │
│  │Agent 1 │ │Agent 2 │ │Agent 3 │ │Agent 4 │       │
│  └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘       │
└───────┼──────────┼──────────┼──────────┼────────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
┌─────────────────────────────────────────────────────┐
│            Redis (Blackboard)                        │
│  agent:{id}:state     → 各 Agent 的中间状态          │
│  agent:{id}:result    → 各阶段的输出结果             │
│  forum:guidance:{id}  → ForumEngine 的指导意见       │
│  task:{id}:status     → 全局任务进度                 │
└─────────────────────────────────────────────────────┘
        ▲                                    │
        │                                    ▼
┌─────────────────────────────────────────────────────┐
│          ForumEngine (Orchestrator)                   │
│  1. 监听所有 Agent 的阶段完成事件                     │
│  2. 读取 Blackboard 上的中间结果                      │
│  3. LLM 分析 → 决策（继续/换关键词/补充/停止）        │
│  4. 写入 guidance 到 Blackboard                      │
│  5. 触发下一阶段的 Celery 任务                        │
└─────────────────────────────────────────────────────┘
```

### Agent 任务粒度

每个 Agent 拆分为 3-4 个阶段性 Celery 任务（不是每步 LLM 调用一个任务）：

| 阶段 | 任务内容 | ForumEngine 介入 |
|------|---------|-----------------|
| Phase 1: Plan | 生成报告结构 | ✅ 评审规划，可调整 |
| Phase 2: Research | 逐段落搜索+总结+反思 | ✅ 评审结果，可要求补充 |
| Phase 3: Report | 生成最终报告 | ❌ 直接执行 |

### 执行流程

```
1. Flask 接收请求 → 创建全局任务 → 通知 ForumEngine

2. ForumEngine 启动 Phase 1:
   - 并行触发所有 Agent 的 plan 任务
   - 等待所有 Agent 完成规划
   - 读取 Blackboard，LLM 分析各规划的互补性
   - 决策：确认/调整

3. ForumEngine 启动 Phase 2:
   - 并行触发所有 Agent 的 research 任务（附带 guidance）
   - 等待所有 Agent 完成研究
   - 读取 Blackboard，LLM 评审研究结果
   - 决策：通过 / 要求某些 Agent 补充研究

4. ForumEngine 启动 Phase 3:
   - 并行触发所有 Agent 的 report 任务
   - 收集所有报告

5. ForumEngine 触发 ReportEngine:
   - 传入所有 Agent 报告 + ForumEngine 讨论记录
   - 生成最终综合报告
```

### 关键设计点

1. **Agent 无状态**：状态存在 Redis，Agent 任务从 Redis 恢复状态执行
2. **ForumEngine 有全局视野**：可以读取所有 Agent 的中间结果
3. **最多补充 1 轮**：避免无限循环，ForumEngine 最多要求补充研究 1 次
4. **超时保护**：每个阶段设置 soft_time_limit，超时自动进入下一阶段
5. **降级策略**：ForumEngine 失败时，Agent 直接推进不等待指导

### 不引入新框架的理由

| 需求 | 框架方案 | 自建方案（Celery + Redis） |
|------|---------|--------------------------|
| 状态共享 | LangGraph State | Redis Hash |
| Agent 调度 | AutoGen GroupChat | ForumEngine + Celery |
| 条件路由 | LangGraph Edges | Python if/else |
| 消息传递 | AutoGen Messages | Redis Pub/Sub |
| 任务编排 | CrewAI Process | Celery chain/group/chord |

LangGraph/AutoGen 是单进程框架，不适合分布式长任务场景。Celery + Redis 已具备所有需要的能力。

---

## 改造范围（更新）

### 需要新增

- `celery_app.py`：Celery 应用配置
- `tasks.py`：Celery 任务定义（各 Agent 的阶段性任务）
- `orchestrator.py`：ForumEngine 编排逻辑（Blackboard 读写 + 决策）
- `docker-compose.yml`：Redis + Celery Worker + Celery Beat

### 需要改造

- `app.py`：精简为纯 API 服务
- `ForumEngine/`：从日志监控模式改造为 Orchestrator 模式
- `ReportEngine/agent.py`：`_normalize_reports` 等方法改为配置驱动

### 保持不变

- `QueryEngine/agent.py`：核心逻辑不变
- `MediaEngine/agent.py`：核心逻辑不变
- `InsightEngine/agent.py`：核心逻辑不变
- `ReportEngine/` 核心渲染逻辑：不变

### 可移除

- `templates/index.html`：前端页面
- `templates/graph_viewer.html`：图谱查看器
- `SingleEngineApp/`：Streamlit 包装应用

---

## 实施阶段

### 第一期：基础 API + Celery

- [ ] API 化改造（POST 提交 + 轮询查询）
- [ ] Celery 任务定义（每个 Agent 整体作为一个任务）
- [ ] 结果缓存 + 任务去重
- [ ] 多格式输出（JSON/HTML/PDF/MD）
- [ ] 5 个 Agent 并行执行 → ReportEngine 汇总

### 第二期：ForumEngine 编排

- [ ] Blackboard 状态管理（Redis）
- [ ] Agent 任务拆分为阶段性任务
- [ ] ForumEngine Orchestrator 实现
- [ ] 阶段间 guidance 机制
- [ ] 补充研究轮次

### 第三期：高级功能

- [ ] Celery Beat 定时预热
- [ ] 任务优先级队列
- [ ] 分布式 Worker 部署
- [ ] 监控面板（Flower）
