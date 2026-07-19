# AutoBooker 系统交接文档

> **版本**：0.5（2026-07-13）  
> **产品品牌**：前端显示为 **AutoBook**，代码库与 API 名称为 **AutoBooker**  
> **读者**：接手开发、运维或二次集成的工程师  
> **配套文档**：[README.md](README.md)（架构详解）、[CHANGELOG.md](CHANGELOG.md)（迭代历史）

---

## 如何使用本文档

| 目标 | 建议阅读顺序 |
|------|-------------|
| **30 分钟了解全貌** | [§1 一分钟速览](#1-一分钟速览) → [§2 项目结构](#2-项目结构) → [§4 核心工作流](#4-核心工作流) |
| **接手日常开发** | [§5 后端模块索引](#5-后端模块索引) + [§6 前端模块索引](#6-前端模块索引) + [§9 本地开发](#9-本地开发) |
| **排查线上问题** | [§12 常见问题排查](#12-常见问题排查) + [§11 已知限制](#11-已知限制与历史兼容) |
| **按需检索实现位置** | 直接查 [§13 关键词检索索引](#13-关键词检索索引) 或 `Ctrl+F` 搜索业务词 |

---

## 1. 一分钟速览

AutoBooker 是一套 **AI 辅助长篇非虚构 / 学术书稿创作系统**，前后端分离：

```
浏览器 (React + TipTap)
    │  HTTP/JSON + SSE
    ▼
FastAPI 后端 (路由 → 服务 → Agent → LLM)
    │
    ▼
PostgreSQL 16 + pgvector + binary_assets
    │
    ▼
外部：多 LLM 服务商、文献 API、Graphviz/图像 API
```

**三条主路径：**

1. **从零创作**：创建书稿 → 项目启动助手 → 写作依据确认 → 大纲 → 逐章 SSE 写作 → 配图 → 审校 → 导出 MD/DOCX/PDF
2. **一键成书**：同上，但前置四步（设定/文献/大纲/叙事宪法）由 `BookJob` 后台自动完成，再进入写作页自动流式生成
3. **优化已有书稿**：上传 DOCX/PDF/TXT → 章节映射 → 不可变基线 → 全书诊断 → 候选修订 → 接受/放弃

**必须牢记的 5 条架构边界：**

| # | 规则 |
|---|------|
| 1 | PostgreSQL 是唯一事实来源；业务二进制在 `binary_assets` 表，URI 为 `db://binary_assets/{id}` |
| 2 | 章节正文在 `Chapter.content`（TipTap JSON + text）；书末参考文献在 `Book.bibliography`，不是 Chapter |
| 3 | 生产环境 `ASSETS_COMPAT_STATIC=false`、`ALLOW_LOCAL_BUSINESS_STORAGE=false`，禁止 `uploads/` 持久化 |
| 4 | 无 Celery/Redis；长任务靠进程内 BackgroundTasks + 线程，**进程重启会丢失正在执行的线程** |
| 5 | 向量维度固定 **1024**（`ReferenceChunk.embedding`），改维度必须做 Alembic 迁移 |

---

## 2. 项目结构

```
AutoBooker/                          # Monorepo 根
├── autobooker/                      # ★ 主应用（本文档所在目录）
│   ├── README.md                    # 架构与开发主文档（最详细）
│   ├── CHANGELOG.md                 # 按日期的用户可见变更
│   ├── HANDOVER.md                  # 本文档（交接速查）
│   ├── backend/                     # FastAPI 后端
│   │   ├── app/                     # 应用代码
│   │   ├── migrations/              # Alembic 迁移（38+ 版本）
│   │   ├── scripts/                 # 迁移/守卫/调试脚本
│   │   ├── tests/                   # pytest（约 418 项）
│   │   ├── requirements.txt
│   │   ├── alembic.ini
│   │   └── .env.example
│   ├── frontend/                    # React 前端
│   │   ├── src/
│   │   ├── package.json
│   │   └── vite.config.ts
│   └── .github/workflows/           # CI（refactor-guards）
├── test/                            # 独立 LLM/图片对比实验（非 CI）
└── infographic_renderer_mvp/        # 配图渲染 MVP（独立子项目）
```

---

## 3. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18、TypeScript 5.6、Vite 8、TipTap 2.11、TanStack Query 5、Zustand 4、Tailwind 3、Axios |
| 后端 | FastAPI 0.115、Uvicorn、SQLAlchemy 2、Pydantic 2、Alembic |
| 数据库 | PostgreSQL 16 + **pgvector**（1024 维）+ JSONB |
| 认证 | JWT（access 15min + refresh 7d）+ bcrypt |
| LLM | 统一 `LLMClient`；支持 DeepSeek、千问、Kimi、豆包、百度、智灵、OpenAI、Claude、Gemini、Grok |
| 嵌入 | DashScope `text-embedding-v4` |
| 配图 | Graphviz、Matplotlib、Pillow + 智灵/OpenAI/万相图像 API |
| 导出 | Markdown、DOCX、PDF（共用引用与图片语义） |
| 后台任务 | FastAPI BackgroundTasks + threading + ThreadPoolExecutor(max=2) |

---

## 4. 核心工作流

### 4.1 从零创作（普通路径）

```mermaid
flowchart TD
    A["POST /books 创建书稿"] --> B["POST .../project-start/bootstrap"]
    B --> C["ProjectAssistant 多轮对话<br/>ProjectAssistantPage"]
    C --> D["WritingBasis 确认<br/>POST .../project-start/complete"]
    D --> E["大纲生成/编辑<br/>POST/PUT .../outline"]
    E --> F["叙事宪法<br/>POST .../narrative/ensure"]
    F --> G["资料上传 + 文献检索"]
    G --> H["SSE 逐章生成<br/>POST .../chapters/{i}/generate"]
    H --> I["记忆提取 + 自动配图批次"]
    I --> J["审校 + 导出"]
```

**前端阶段判定**（`frontend/src/lib/bookStatus.ts`）：

| Phase | 条件 | 页面 |
|-------|------|------|
| SETUP | 未完成写作准备 | `ProjectAssistantPage` 或 `PlanningWizard` |
| WRITING | `writing` / `review_ready` | TipTap 编辑器 + 右侧面板 |
| COMPLETED | `completed` | 同 WRITING（收尾） |

**新书默认路径**（2026-07-13 起）：`NewBookDialog` → `bootstrap` → 直接进入 `ProjectAssistantPage`；旧 Intake 三步向导已下线。

### 4.2 一键成书

```mermaid
flowchart LR
    A["NewBookDialog 选一键出书"] --> B["/auto-progress 进度页"]
    B --> C["BookJob: setting→literature→outline→narrative"]
    C --> D["写作页自动前言 SSE + 全书章节 SSE"]
    D --> E["每章完成后自动提交配图批次"]
```

- 启动：`POST /book-jobs/{book_id}/start`（**不是**已废弃的 `POST /book-jobs/auto-generate`）
- 进度查询：`GET /book-jobs/{book_id}`
- Job 使用 DB lease 防并发；进程重启后 lease 过期可重试
- 前端进度映射：`frontend/src/lib/autoBookProgress.ts`

### 4.3 优化已有书稿

- 入口：`/app/books/:bookId/optimize`
- `Book.workflow_mode = optimize_existing`
- 关键表：`OptimizationProject`、`ManuscriptBaselineChapter`、`ManuscriptRevision`、`OptimizationJob`
- 基线确认后 **禁止删除** 原始书稿文件
- 默认 `allow_structure_changes=false`（不改章节结构）

### 4.4 章节生成数据流（实现要点）

```
ChapterWriterAgent (agents/chapter_writer.py)
  ← 系统提示 (prompts/chapter_writer.py)
  ← 写作上下文 (services/writing/writing_context_builder.py)
      ├── BookMemory（章摘要/术语/风格）
      ├── ProjectMemory（长期记忆）
      └── RAG 检索 (agents/document_parser.py → ReferenceChunk)
  → SSE 流式输出
  → process_chapter_generation_result
  → TipTap JSON + 引用归一化 + [DIAGRAM:] → Figure
  → 异步 memory 提取 (prompts/memory_extract.py)
```

---

## 5. 后端模块索引

### 5.1 入口与配置

| 文件 | 职责 |
|------|------|
| `app/main.py` | FastAPI 入口，挂载 26 个 router |
| `app/config.py` | 全部环境变量（Pydantic Settings） |
| `app/database.py` | SQLAlchemy engine / SessionLocal |
| `backend/.env.example` | 环境变量模板 |

### 5.2 路由层（`app/routers/`）

| 路由文件 | 前缀/路径 | 核心职责 |
|----------|-----------|----------|
| `auth.py` | `/auth` | 注册、登录、刷新、用户模型偏好 |
| `books.py` | `/books` | 书稿 CRUD、复制、导出、设定推荐 |
| `intake.py` | `/books/{id}/intake`, `project-start/*` | bootstrap/complete；**写接口 410 Gone** |
| `project_assistant.py` | `/books/{id}/project-assistant` | 项目助手对话轮次与 trace |
| `writing_basis.py` | `/books/{id}/writing-basis` | 写作依据 CRUD/确认 |
| `sources.py` | `/books/{id}/sources` | 资料库上传/分段 |
| `memories.py` | `/books/{id}/memories` | 项目长期记忆 |
| `references.py` | `/books/{id}/references` | 资料上传、向量检索 |
| `outline.py` | `/books/{id}/outline` | 大纲获取/生成/编辑 |
| `chapters.py` | `/books/{id}/chapters` | **SSE 章节生成**、选区编辑、降重 |
| `preface.py` | `/books/{id}/preface` | 前言 SSE 生成 |
| `assistant.py` | `/books/{id}/chapters/{i}/assistant` | **行内 AI 助手**（润色/图表） |
| `literature.py` | `/books/{id}/literature` | 外部文献搜索 |
| `citations.py` | `/books/{id}/citations` | 结构化引用与书末参考文献 |
| `figures.py` | `/books/{id}/figures` | 配图 CRUD、批次生成 |
| `review.py` | `.../chapters/{i}/review` | 章节审校 |
| `review_workspace.py` | `.../review-workspace` | 全书审校工作台 |
| `review_stage.py` | `.../review-stage` | 阶段审校 |
| `book_jobs.py` | `/book-jobs` | 一键成书 Job |
| `optimization.py` | `/books/optimization-*` | 优化书稿全流程 |
| `assets.py` | `/books/{id}/assets/{id}/content` | 二进制资产交付 |
| `config.py` | `/config/llm-models` | 已配置模型目录 |
| `library.py` | `/library` | 公共文献库 |
| `notifications.py` | `/notifications` | 通知 |
| `feedback.py` | `/feedback` | 用户反馈 |

**API 文档**：`http://localhost:8001/docs`（Swagger）

### 5.3 Agent 层（`app/agents/`）

| Agent | 文件 | 用途 |
|-------|------|------|
| 章节写作 | `chapter_writer.py` | SSE 流式章节生成 |
| 大纲 | `outline_agent.py` | 按体裁生成章节树 |
| 叙事宪法 | `narrative_agent.py` | 全书写作规则 |
| 前言 | `preface_writer.py` | 前言生成 |
| 文献 | `literature_agent.py` | 文献查询优化 |
| 文档解析 | `document_parser.py` | PDF/DOCX/TXT 解析 + RAG 检索 |
| 审校 | `review_agent.py` | 章节审校 |

### 5.4 服务层（`app/services/` — 重点子目录）

| 目录/文件 | 职责 |
|-----------|------|
| `book_service.py` | 书稿 CRUD、权限 |
| `auto_book_job.py` | 一键成书前置流水线 |
| `jobs/book_job_dispatch.py` | Job lease + 分发 |
| `memory_service.py` | **章节写作记忆**（BookMemory） |
| `assistant/project_assistant_service.py` | **项目助手**主服务 |
| `assistant/tool_orchestrator.py` | 全局助手工具编排 |
| `assistant/context_compression_service.py` | 对话 >20 轮压缩 |
| `assistant/external_search_service.py` | Semantic Scholar/Crossref/arXiv 等 |
| `writing/writing_context_builder.py` | 章节生成上下文组装 |
| `writing/writing_basis_service.py` | 写作依据 |
| `figure_batch_service.py` | 配图批次（线程池 max=2） |
| `figures/` | 配图全管线（compiler/layout/render…） |
| `export_service.py` | MD/DOCX/PDF 导出 |
| `storage_policy.py` | 禁止本地业务存储守卫 |
| `sources/` | 资料库分段服务 |

### 5.5 提示词（`app/prompts/`）

| 文件/目录 | 用途 |
|-----------|------|
| `chapter_writer.py` | 章节写作系统提示 |
| `outline.py` + `styles/outline_prompt_*.txt` | 7 种体裁大纲 |
| `narrative_prompts.py` | 叙事/体例宪法 |
| `preface_writer.py` | 前言 |
| `memory_extract.py` | 章后记忆 JSON 提取 |
| `assistant/startup_system.py` | 项目启动助手 |
| `assistant/global_system.py` | 全局助手 |
| `figure_types/*.txt` | 各图类型约束 |

### 5.6 数据模型（`app/models/` — 26 个文件）

| 领域 | 模型文件 | 表名（概念） |
|------|----------|-------------|
| 用户 | `user.py` | users |
| 书稿 | `book.py`, `chapter.py`, `book_job.py` | books, chapters, book_jobs |
| 资料 | `reference.py`, `material.py` | reference_files, reference_chunks… |
| 引用 | `citation.py` | citations, citation_evidence, citation_occurrences |
| 记忆 | `memory.py`, `project_memory.py` | book_memories, project_memories |
| 助手 | `writing_basis.py`, `assistant_turn.py`, `intake.py` | writing_basis, assistant_turns… |
| 配图 | `figure.py`, `figure_batch.py`, `binary_asset.py` | figures, figure_batch_runs, binary_assets |
| 审校 | `chapter_review.py`, `review_stage.py`, `review_task.py` | chapter_reviews… |
| 优化 | `optimization.py` | optimization_projects, manuscript_* |

完整 ER 关系见 [README.md §数据模型](README.md#数据模型)。

### 5.7 LLM 层（`app/llm/`）

| 文件 | 职责 |
|------|------|
| `client.py` | 同步/异步 chat、stream、embed；重试逻辑 |
| `providers.py` | 10+ 服务商注册；`parse_ai_model("provider:model")`；按书稿/用户偏好路由 |

模型偏好字段（User 表）：`outline_ai_model`、`constitution_ai_model`、`writing_ai_model`、`assistant_ai_model`。

---

## 6. 前端模块索引

### 6.1 路由（`src/App.tsx`）

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | LandingPage | 产品页 |
| `/login`, `/register` | 认证 | |
| `/app/home` | HomePage | 工作台 |
| `/app/books` | BooksPage | 书稿列表 |
| `/app/books/:bookId` | **BookEditorPage** | ★ 核心编辑页（~2100 行） |
| `/app/books/:bookId/auto-progress` | AutoBookProgressPage | 一键成书进度 |
| `/app/books/:bookId/optimize` | OptimizationPage | 优化书稿 |
| `/app/books/:bookId/review` | ReviewWorkspacePage | 全书审校 |
| `/app/library` | LibraryPage | **占位，待开发** |

路由辅助：`src/lib/bookRoutes.ts`（按 workflow_mode / status 决定跳转目标）

### 6.2 功能模块（`src/features/`）

| 目录 | 职责 | 关键文件 |
|------|------|----------|
| `assistant/` | **项目助手**（启动 + 全局 Dock） | `ProjectAssistantPage.tsx`, `GlobalAssistantDock.tsx`, `toolDispatch.ts` |
| `memory/` | 项目长期记忆面板 | `MemoryPanel.tsx`, `memoryApi.ts` |
| `review/` | 全书审校工作台 | `ReviewWorkspacePage.tsx` |
| `outline/` | 格式策略 | `FormatStrategyPanel.tsx` |
| `intake/` | 项目启动 API | `intakeApi.ts` |

### 6.3 编辑器（`src/components/editor/`）

| 组件 | 职责 |
|------|------|
| `BookEditorPage`（pages/） | 编辑主控制器 |
| `ChapterTiptapEditor.tsx` | TipTap 主编辑器 |
| `RightPanel.tsx` | 六 Tab：细则/图表/文献/AI/审校/记忆 |
| `PlanningWizard.tsx` | 设定→大纲→开写向导 |
| `EditorTopBar.tsx` | 顶栏：导出、审校、模型、配图 |
| `LiteraturePanel.tsx` | 文献搜索 + 引用管理 |
| `AiAssistantPanel.tsx` | **行内 AI**（非项目助手） |
| `ReviewPanel.tsx` | 章节审校 |

### 6.4 状态管理

| 方式 | 用途 |
|------|------|
| TanStack Query | 书稿、章节、大纲、引用、图片、助手轮次等**服务端状态** |
| Zustand `authStore` | JWT 持久化（key=`autobooker-auth`） |
| Zustand `bookStore` | **当前未使用**（遗留） |
| React Context | `FigureBlockContext`（图表块同步） |
| localStorage | 主题、书稿置顶顺序 |

### 6.5 API 客户端

| 层 | 说明 |
|----|------|
| `src/api/client.ts` | Axios 实例 + JWT 拦截器 + 401 刷新 |
| `src/api/*.ts` | 18 个领域 API 模块 |
| `features/*/api/` | 助手、记忆、审校等独立 API |
| `hooks/useChapterStream.ts` | 章节 SSE（fetch，非 Axios） |

**双助手体系（易混淆）：**

| 类型 | API | UI 入口 |
|------|-----|---------|
| 项目助手 | `features/assistant/api/assistantApi.ts` → `/project-assistant/*` | `ProjectAssistantPage`, `GlobalAssistantDock` |
| 行内 AI | `api/assistant.ts` → `/chapters/{i}/assistant` | `AiAssistantPanel`（右侧面板） |

---

## 7. API 速查（高频端点）

> 完整列表见 Swagger `/docs`。以下均为需 JWT 的端点（除注明）。

### 书稿生命周期

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/books` | 创建书稿 |
| POST | `/books/{id}/project-start/bootstrap` | 新书入口 |
| POST | `/books/{id}/project-start/complete` | 完成项目启动 |
| POST | `/books/{id}/outline` | AI 生成大纲 |
| POST | `/books/{id}/narrative/ensure` | 确保叙事宪法 |
| POST | `/books/{id}/chapters/{i}/generate` | **SSE** 章节生成 |
| POST | `/books/{id}/preface/generate` | **SSE** 前言生成 |
| GET | `/books/{id}/export?format=md\|docx\|pdf` | 导出 |

### 助手与记忆

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/books/{id}/project-assistant/turns` | 项目助手对话 |
| GET | `/books/{id}/memories` | 项目记忆列表 |
| PATCH | `/books/{id}/writing-basis` | 编辑写作依据 |

### 一键成书

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/book-jobs/{book_id}/start` | 启动前置 Job |
| GET | `/book-jobs/{book_id}` | 查询进度 |

### 配图

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/books/{id}/figures/batches` | 创建批次 |
| GET | `/books/{id}/figures/batches/{run_id}` | 批次进度 |
| POST | `/books/{id}/figures/batches/{run_id}/pause` | 暂停 |

### 公开/元

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（无需 JWT） |
| GET | `/config/llm-models` | 可用模型目录 |

---

## 8. 配置与环境变量

### 8.1 本地最小配置

```dotenv
# backend/.env
DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/autobooker
JWT_SECRET=<长随机串>
CORS_ORIGINS=http://localhost:5173
DASHSCOPE_API_KEY=<至少一个 LLM 服务商>
```

```dotenv
# frontend/.env
VITE_API_BASE=http://localhost:8001
```

### 8.2 生产必设

```dotenv
ASSETS_COMPAT_STATIC=false
ALLOW_LOCAL_BUSINESS_STORAGE=false
```

### 8.3 关键变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_DIMENSIONS` | 1024 | **不可单独修改**，需迁移 |
| `FIGURE_IMAGE_PROVIDER` | auto | zeelin / openai / wanx / auto |
| `FIGURE_IMAGE_FALLBACK_WANX` | true | OpenAI 失败回退万相 |
| `LLM_MAX_RETRIES` | 3 | LLM 重试次数 |
| `GRAPHVIZ_BIN_DIR` | 自动探测 | 流程图渲染 |

完整列表：`backend/.env.example` + `app/config.py`。

---

## 9. 本地开发

### 9.1 环境要求

- Python 3.11+
- Node.js 20.19+（推荐 22.12+）
- PostgreSQL 16 + pgvector（推荐 Docker：`pgvector/pgvector:pg16`）
- 可选：Graphviz（流程图）

### 9.2 启动步骤

**数据库：**

```powershell
docker run -d --name autobooker-pg -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=autobooker -p 5432:5432 pgvector/pgvector:pg16
```

**后端：**

```powershell
cd autobooker/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# 编辑 .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**前端：**

```powershell
cd autobooker/frontend
npm install
# 创建 .env: VITE_API_BASE=http://localhost:8001
npm run dev
```

**访问：**

- 前端：http://localhost:5173
- 后端：http://localhost:8001
- API 文档：http://localhost:8001/docs

### 9.3 生产部署清单

1. `alembic upgrade head`
2. 可选：`python scripts/migrate_local_assets_to_db.py`（从遗留 uploads 迁移）
3. 设置生产环境变量（JWT、CORS、关闭本地存储）
4. 关闭 `--reload`；配置 HTTPS 反向代理
5. 配置 PostgreSQL 备份
6. **多实例部署需外部队列**（当前架构不支持）

---

## 10. 测试与 CI

### 10.1 后端测试

```powershell
cd autobooker/backend
.\.venv\Scripts\python.exe -m pytest -q          # 全量 ~418 项
.\.venv\Scripts\python.exe -m pytest tests/test_assistant_acceptance.py -q  # 助手验收 14 条
```

**重点测试文件：**

| 文件 | 覆盖 |
|------|------|
| `test_assistant_acceptance.py` | 项目助手全链路 |
| `test_autobooker_05_core.py` | 0.5 核心功能 |
| `test_workflow_regressions.py` | 工作流回归 |
| `test_refactor_acceptance.py` | 存储重构 |
| `test_intake_deprecation.py` | 旧 Intake 410 |
| `test_figure_*` / `test_v3_*` | 配图管线 |

### 10.2 前端测试

```powershell
cd autobooker/frontend
npm test                    # Vitest，12 个测试文件
npx tsc -b --pretty false   # 类型检查
npm run build               # 生产构建
```

### 10.3 CI

`.github/workflows/refactor-guards.yml`：

- `scripts/check_no_local_business_writes.py` — 禁止本地业务写入
- `scripts/inventory_local_file_writes.py` — 本地写入清单
- pytest 重构回归子集

---

## 11. 已知限制与历史兼容

| 项 | 说明 |
|----|------|
| 无独立任务队列 | 长任务绑定 API 进程；重启丢失执行中线程 |
| 旧 Intake 写 API | 返回 410 Gone；只读 GET 保留 6 个月 |
| `POST /book-jobs/auto-generate` | 已废弃（400） |
| 旧 `Book.user_material` | 只读兼容，新上传走 ReferenceFile |
| 纯文本历史引用 | 不自动批量迁移；带 `[[CITE:...]]` 标记会在读取时转换 |
| `/app/library` 前端 | 占位 UI，后端 `/library` 已实现 |
| SQLite 文件 | 非生产目标，仅开发遗留 |
| 向量维度 | 1024 固定，与 pgvector 列绑定 |

---

## 12. 常见问题排查

| 现象 | 可能原因 | 排查方向 |
|------|----------|----------|
| 401 频繁跳转登录 | JWT 过期或 refresh 失败 | `authStore.tryRefresh()`；检查 `JWT_SECRET` 是否变更 |
| 章节生成无输出 | LLM Key 未配或模型不可用 | `GET /config/llm-models`；查后端日志 |
| 资料检索无结果 | embedding 未生成或维度不匹配 | 检查 `DASHSCOPE_API_KEY`；确认迁移已执行 |
| 配图失败但正文成功 | 设计如此，批次独立 | 查 `figure_batch_runs` 状态与 `FigureBatchItem` 错误 |
| 一键成书卡在进度页 | BookJob lease 或步骤失败 | `GET /book-jobs/{id}`；查 `checkpoint_json` |
| 图片 404 | 生产未走 assets API | 确认 `ASSETS_COMPAT_STATIC=false` 时用 `/books/{id}/assets/{id}/content` |
| CORS 错误 | 前端 origin 未允许 | `CORS_ORIGINS` 加入 `http://localhost:5173` |
| 迁移失败 | 数据库版本不一致 | `alembic current` vs `alembic heads` |
| 引用编号错乱 | 格式切换未持久化 | 查 `CitationOccurrence`；GB/T 7714 按首次出现排序 |
| 助手对话过长变慢 | 触发压缩 | `context_compression_service`；>20 轮压缩为记忆 |

**日志位置**：Uvicorn stdout；无独立日志文件配置。

**数据库检查：**

```powershell
cd autobooker/backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
```

---

## 13. 关键词检索索引

> 用 `Ctrl+F` 搜索左列关键词，定位右列文件/模块。

| 关键词 | 定位 |
|--------|------|
| 章节生成 / SSE | `routers/chapters.py`, `agents/chapter_writer.py`, `hooks/useChapterStream.ts` |
| 章节写作提示词 | `prompts/chapter_writer.py` |
| 大纲生成 | `agents/outline_agent.py`, `routers/outline.py`, `prompts/outline.py` |
| 叙事宪法 | `agents/narrative_agent.py`, `prompts/narrative_prompts.py` |
| 前言 | `agents/preface_writer.py`, `routers/preface.py` |
| 项目助手 | `services/assistant/project_assistant_service.py`, `features/assistant/` |
| 全局助手 / 工具编排 | `services/assistant/tool_orchestrator.py`, `GlobalAssistantDock.tsx` |
| 行内 AI / 润色 | `services/assistant/handler.py`, `api/assistant.ts`, `AiAssistantPanel.tsx` |
| 写作依据 | `services/writing/writing_basis_service.py`, `WritingBasisPanel.tsx` |
| 项目记忆 | `models/project_memory.py`, `services/assistant/project_memory_service.py`, `MemoryPanel.tsx` |
| 章节记忆 | `services/memory_service.py`, `prompts/memory_extract.py` |
| 对话压缩 | `services/assistant/context_compression_service.py` |
| 外部文献检索 | `services/assistant/external_search_service.py` |
| 资料上传 / 解析 | `agents/document_parser.py`, `routers/references.py` |
| RAG / 向量检索 | `ReferenceChunk`, `document_parser.py retrieve` |
| 结构化引用 | `models/citation.py`, `lib/tiptap/CitationNode.ts`, `routers/citations.py` |
| 书末参考文献 | `Book.bibliography`, `citations.py` |
| 配图生成 | `services/figures/`, `figure_batch_service.py` |
| 配图批次 | `routers/figures.py`, `FigureQuickPanel.tsx` |
| 一键成书 | `services/auto_book_job.py`, `book_jobs.py`, `AutoBookProgressPage.tsx` |
| 优化书稿 | `services/optimization/`, `OptimizationPage.tsx` |
| 审校 | `services/review/`, `ReviewPanel.tsx`, `ReviewWorkspacePage.tsx` |
| 导出 MD/DOCX/PDF | `services/export_service.py`, `EditorTopBar.tsx` |
| LLM 调用 | `llm/client.py`, `llm/providers.py` |
| 模型路由 | `llm/providers.py` `resolve_book_*_model` |
| 二进制资产 | `models/binary_asset.py`, `services/assets/`, `routers/assets.py` |
| 存储策略 | `services/storage_policy.py` |
| 数据库迁移 | `migrations/versions/`, `alembic.ini` |
| 环境变量 | `config.py`, `.env.example` |
| TipTap 扩展 | `lib/chapterEditorExtensions.ts`, `lib/tiptap/` |
| Markdown 转换 | `lib/tiptapDocToMarkdown.ts`, `lib/markdown_to_tiptap.py`（后端） |
| 公式渲染 | `lib/repairInlineMath.ts`, `math_tokenizer.py` |
| 认证 JWT | `routers/auth.py`, `stores/authStore.ts`, `api/client.ts` |
| 资料库 sources | `routers/sources.py`, `SourceLibraryPanel.tsx` |
| 项目启动 bootstrap | `routers/intake.py`, `features/intake/intakeApi.ts` |
| 旧 Intake 410 | `routers/intake.py`, `test_intake_deprecation.py` |
| 守卫脚本 | `scripts/check_no_local_business_writes.py` |
| 资产迁移 | `scripts/migrate_local_assets_to_db.py` |

---

## 14. 子系统速读（按需深入）

### 14.1 两套记忆体系

| | 章节写作记忆 | 项目长期记忆 |
|---|-------------|-------------|
| 模型 | `BookMemory` | `ProjectMemory` |
| 服务 | `memory_service.py` | `project_memory_service.py` |
| 写入时机 | 章生成后 LLM 提取 | 助手对话沉淀 |
| 读取时机 | 下一章生成上下文 | 助手 + `WritingContextBuilder` |
| 前端 | 无独立面板 | `MemoryPanel`（右侧面板） |

### 14.2 引用三层结构

```
Citation（文献元数据）
  └── CitationEvidence（资料块/页码/原文）
        └── CitationOccurrence（TipTap 节点在正文中的位置）
```

书末列表：`Book.bibliography`（自动同步，不参与章节计数）。

### 14.3 配图管线概要

```
[DIAGRAM:] 占位 / 用户请求
  → 语义解析 → 图类型分类
  → DSL/Graphviz/Matplotlib 编译（结构化图）
  → 或 Image API（插画类）
  → 渲染 → binary_assets 入库
  → Figure 记录关联 FigureAsset
```

批次：`FigureBatchRun` + `FigureBatchItem`；并发 max=2；支持 pause/resume。

### 14.4 资料处理五用途

| 用途 | 内部值 |
|------|--------|
| 大纲 | `outline` |
| 写作要求 | `writing_requirements` |
| 参考资料 | `reference_material` |
| 参考文献 | `bibliography` |
| 原始书稿 | `source_manuscript` |

生命周期：`processing` → `pending_confirmation` → `effective` / `disabled` / `failed`

---

## 15. 近期重要变更（交接关注）

详见 [CHANGELOG.md](CHANGELOG.md)。2026-07-13 核心变更：

- 存储统一入 PostgreSQL `binary_assets`，禁止 uploads 持久化
- 新书统一走项目启动助手，旧 Intake 写接口 410
- 项目长期记忆 + 对话压缩 + 全局助手工具编排
- 外部检索与选题助手（Semantic Scholar 等）
- 助手全链路验收测试 14 条

---

## 16. 文档维护建议

| 变更类型 | 更新位置 |
|----------|----------|
| 用户可见功能 | `CHANGELOG.md`（按日期） |
| 架构/边界/部署 | `README.md` |
| 交接速查/索引 | 本文档 `HANDOVER.md` |
| API 变更 | FastAPI 自动生成 `/docs` + 本文档 §7 |

---

*文档生成日期：2026-07-13。如有疑问，优先查阅 [README.md](README.md) 对应章节，或在代码库中按 §13 关键词索引定位实现。*
