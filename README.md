# AutoBooker

AutoBooker 是一套面向长篇非虚构与学术书稿的 AI 辅助创作系统。当前版本为 0.5，覆盖从零创作、优化已有书稿、资料解析、结构化引用、章节审校、配图生成以及 Markdown、DOCX、PDF 出版导出的完整主路径。

系统采用前后端分离架构：

- 前端：React 18、TypeScript、Vite、TipTap、TanStack Query、Zustand。
- 后端：FastAPI、SQLAlchemy 2、Pydantic 2、Alembic。
- 数据：PostgreSQL、pgvector、JSONB。
- AI：统一 LLM 客户端连接 DeepSeek、千问、Kimi、豆包、百度、智灵网关、OpenAI、Claude、Gemini 与 Grok。
- 存储：PostgreSQL（业务状态 + `binary_assets` 大对象）+ pgvector；进程内缓存与 OS 临时目录仅用于请求级解析/渲染，不作为业务持久化。

## 当前能力

- 从零创作：书稿设定、资料上传、文献检索、大纲生成、前言与章节流式写作、编辑、审校和导出。
- 一键成书：自动完成基础设定、文献、大纲和全书写作规则，再顺序生成前言、章节与章节配图。
- 优化已有书稿：导入 DOCX、PDF 或 TXT，识别章节、保存不可变原稿基线、执行全书诊断，并逐章接受或放弃候选修订。
- 统一资料处理：同一上传入口支持大纲、写作要求、参考资料、参考文献和原始书稿五种用途。
- 结构化引用：TipTap 内联引用节点、来源证据、正文位置、上下文、引用替换、首次出现顺序编号和书末参考文献同步。
- 图片系统：流程图、架构图、数据图表、插画等图片类型，支持本章或全书批量生成及持久化进度。
- 质量控制：章节审校、问题预览与应用、撤销、降重、术语一致性、引用完整性和图片检查。
- 出版输出：Markdown、DOCX、PDF 共用正文、引用与图片语义，DOCX/PDF 支持页码和出版样式。

## 总体架构

```mermaid
flowchart LR
    subgraph Browser["浏览器"]
        Router["React Router 页面"]
        Query["TanStack Query 服务端状态"]
        Store["Zustand 登录状态"]
        Editor["TipTap 章节编辑器"]
        Router --> Query
        Router --> Store
        Router --> Editor
    end

    subgraph API["FastAPI 应用"]
        Routers["路由与权限校验"]
        Schemas["Pydantic 输入输出"]
        Services["领域服务"]
        Agents["写作与解析 Agent"]
        LLM["统一 LLM 客户端"]
        Tasks["后台任务与流式生成"]
        Routers --> Schemas
        Routers --> Services
        Services --> Agents
        Agents --> LLM
        Services --> Tasks
    end

    subgraph Storage["持久化"]
        PG["PostgreSQL"]
        Vector["pgvector 向量块"]
        JSON["JSONB 编辑器与流程状态"]
        Blob["binary_assets 二进制资产"]
        PG --- Vector
        PG --- JSON
        PG --- Blob
    end

    subgraph External["外部能力"]
        Models["文本与视觉模型"]
        Literature["文献与公开资料源"]
        Render["Graphviz / Matplotlib / 图像 API"]
    end

    Browser -->|"HTTP / JSON / SSE"| Routers
    Services --> PG
    LLM --> Models
    Agents --> Literature
    Tasks --> Render
```

### 架构边界

1. PostgreSQL 是业务状态与二进制资产的唯一事实来源。书稿、章节、资料、引用、配图、优化修订、助手对话与图片批次都持久化到数据库；上传原文件与生成图片字节存入 `binary_assets`（URI：`db://binary_assets/{id}`），经 `/api/books/{id}/assets/{asset_id}/content` 交付。
2. `Chapter.content` 是正文内容容器，保留纯文本并以 TipTap JSON 作为编辑器结构；引用、公式、表格和图片等富文本语义由节点表达。书末参考文献保存在 `Book.bibliography`，不占用正文 `Chapter`。
3. **禁止**将业务数据持久化到 `uploads/` 等本地目录。`ALLOW_LOCAL_BUSINESS_STORAGE` 与 `ASSETS_COMPAT_STATIC` 默认均为 `false`，仅用于遗留开发机迁移；生产环境必须保持关闭。
4. 长任务使用 FastAPI `BackgroundTasks`、后台线程和小型线程池，任务状态写入数据库；当前没有独立 Celery/Redis 队列。进程中断后可从持久化状态重新提交，但不会由外部队列自动接管正在执行的线程。
5. 所有新上传资料使用结构化文件表，不再写入 `Book.user_material`。旧字段和旧纯文本引用只用于历史书稿兼容。

## 两种书稿工作流

`Book.workflow_mode` 决定页面和后端流程：

### 从零创作

```mermaid
flowchart LR
    Setup["创建书稿与基础设定"]
    Material["上传并确认资料"]
    Outline["生成或合并大纲"]
    Rules["准备全书写作规则"]
    Write["前言与章节流式写作"]
    Figures["章节图片批次"]
    Review["编辑与审校"]
    Export["Markdown / DOCX / PDF"]

    Setup --> Material --> Outline --> Rules --> Write
    Write --> Figures
    Write --> Review --> Export
```

- 普通创作进入 `/app/books/:bookId`。新书稿经 `project-start/bootstrap` 进入**项目启动助手**（`ProjectAssistantPage`），不再使用旧三步 Intake 向导。
- 一键成书先进入 `/app/books/:bookId/auto-progress`。持久化 `BookJob` 负责设定、文献、大纲和写作规则，完成后由写作页按章调用 SSE 生成接口。
- 章节完成后立即提交该章图片批次；图片失败只记录到图片任务，不回滚已经完成的正文。全书图片任务支持持久化暂停并从剩余图片继续。

### 优化已有书稿

```mermaid
flowchart LR
    Upload["上传原始书稿"]
    Parse["识别章节"]
    Mapping["确认章节映射"]
    Baseline["确认不可变基线"]
    Diagnose["全书诊断与优化方案"]
    Revision["生成候选修订"]
    Decision["接受 / 放弃 / 恢复原稿"]

    Upload --> Parse --> Mapping --> Baseline --> Diagnose --> Revision --> Decision
```

- 优化项目进入 `/app/books/:bookId/optimize`。
- DOCX 优先读取标题样式；PDF 根据字号与位置识别标题；TXT 使用章节标题规则。
- 每章原文写入 `ManuscriptBaselineChapter` 并保存内容哈希。基线确认后，原始书稿文件禁止删除。
- 默认 `allow_structure_changes=false`，服务端保持章节数量、顺序和标题映射。
- AI 输出写入 `ManuscriptRevision` 候选版本，不直接覆盖基线或当前工作稿；只有接受修订才更新工作章节。
- 全书优化任务按章执行并持久化进度，失败后可重新提交。

## 统一资料处理架构

上传入口接受 PDF、DOCX 和 TXT。每个文件可声明一个或多个用途：

| 用途 | 内部值 | 主要产物 |
| --- | --- | --- |
| 大纲 | `outline` | 章节候选、主大纲约束 |
| 写作要求 | `writing_requirements` | 写作规则、术语、验证规则 |
| 参考资料 | `reference_material` | 可检索向量块、页码与标题路径 |
| 参考文献 | `bibliography` | 文献元数据与可追溯证据 |
| 原始书稿 | `source_manuscript` | 优化项目、章节基线和映射 |

文件处理链路如下：

1. `ReferenceFile` 保存原文件位置、解析状态和生命周期。
2. `ReferenceFilePurpose` 保存用途、置信度、用户确认与主大纲标记。
3. `DocumentParserAgent` 从 PDF、DOCX、TXT 提取文本和定位信息。
4. `ReferenceChunk` 保存正文块、1024 维向量、页码、段落序号、标题路径和是否可直接引用。
5. `WritingRequirement`、`MaterialTerm` 与 `OutlineConstraint` 保存写作约束和大纲锁定信息。
6. `MaterialConflict` 记录多主大纲、结构、字数、术语或用途冲突。

生命周期为 `processing`、`pending_confirmation`、`effective`、`disabled`、`failed`。用户明确指定的用途和高置信度结果直接生效；只有确实需要选择的结果进入待确认。

主大纲合并器强制保留章数、顺序、锁定标题和锁定小节，模型仅能补齐缺失信息。删除文件时删除物理文件、停用其派生产物，并将受影响的写作规则标记为过期，不自动重写已经存在的正文。

## 结构化引用架构

引用由三个层次组成：

- `Citation`：题名、作者、年份、期刊、卷期页、DOI、URL、来源等文献元数据。
- `CitationEvidence`：对应资料块、页码、段落、标题路径和可引用原文。
- `CitationOccurrence`：某个 TipTap 引用节点在章节中的实际位置、引用方式、定位、前后缀和上下文。

编辑器中的 `citation` 是内联原子节点，稳定保存：

```json
{
  "type": "citation",
  "attrs": {
    "nodeId": "节点 UUID",
    "citationId": "文献 UUID",
    "evidenceId": "证据 UUID",
    "citeMode": "parenthetical",
    "locator": "p. 12",
    "prefix": "",
    "suffix": "",
    "renderedText": "(Author, 2024)",
    "displayText": "(Author, 2024)"
  }
}
```

章节保存时，后端统一识别带文献 UUID 的内部标记、映射本书文献并同步正文位置和上下文。图表同步从 Markdown 重建正文时会先把引用节点还原为内部标记，再执行同一归一化过程，避免引用身份丢失。无法匹配的标记进入“待补充来源”。

排序与显示由引用格式统一决定：

- GB/T 7714 是顺序编码格式。系统按章节顺序和章内位置计算每篇文献的首次出现位置，同一文献重复使用保持同一编号；增删引用或移动章节后自动重新编号。
- APA、MLA、Chicago 不分配 `[n]`，正文节点显示对应格式的作者、年份或作者信息，书末按各格式的作者、年份、标题规则排序。
- 未在正文使用的文献始终没有正式序号，也不会进入书末参考文献。引用次数、外部被引量和 GitHub 星标均不参与编号。

系统只维护一份 `Book.bibliography` 书后内容，并在每次正文引用变化时自动更新。它不参与目标字数、大纲章节数、章节生成和章节审校；导出时固定追加在所有正文及其他书后内容之后。Markdown、DOCX 和 PDF 都由同一排序与格式化结果生成。历史普通纯文本引用不会被自动改写；带 `[[CITE:...]]` 内部标记的章节会在读取章节或打开引用管理时自动转换。

前端文献模块只保留“文献搜索”和“引用管理”。引用管理按文献分组展示正文引用次数、全部章节位置、上下文、跳转和单次删除；已引用文献的显示顺序就是最终书末顺序，未引用文献排列在后并标记“尚未引用”。

## 图片生成架构

图片系统分为图片记录、生成管线与批次调度：

- `Figure` 保存章节、图片类型、提示、状态、文件路径、图注和排序信息。
- 结构化图先经历语义提取、图类型分类、布局/图形语法编译、约束检查和 SVG/Graphviz/Matplotlib 渲染。
- 插画类图片可调用智灵、OpenAI 或通义万相；OpenAI 类失败时可按配置回退万相。
- `FigureBatchRun` 和 `FigureBatchItem` 保存全书或单章批次进度。
- 批次仅选择 `pending`、非截图且没有成功文件的图片；数据库行锁和活动项目唯一索引防止同一图片并发重复生成。
- 当前批次线程池并发数为 2。单项失败被隔离记录，批次可完成为 `completed_with_errors`。
- 暂停时批次进入 `paused`，尚未开始的项目停止调度，最多两个已进入外部调用的项目允许收尾；再次生成时只选择仍待处理的图片。

图片文件通过 `FigureAsset` 关联 `binary_assets`；渲染管线在 OS 临时目录产出候选图后入库，不写入 `uploads/figures`。

## 后端分层

```text
backend/
├─ app/
│  ├─ agents/          # 大纲、章节、前言、文献、审校、文档解析 Agent
│  ├─ llm/             # 统一模型客户端、服务商注册和模型路由
│  ├─ models/          # SQLAlchemy 模型与数据库枚举
│  ├─ prompts/         # 写作、出版、助手、记忆提取等提示约束
│  ├─ repositories/    # 数据访问辅助
│  ├─ routers/         # FastAPI 路由、鉴权和请求编排
│  ├─ schemas/         # Pydantic 请求与响应模型
│  ├─ services/        # 领域服务、导出、资料、引用、优化、图片、助手与审校
│  │  ├─ assets/       # binary_assets、资料解析临时工作区
│  │  ├─ assistant/    # 项目助手、工具编排、外部检索、长记忆
│  │  └─ figures/      # 配图生成与渲染管线
│  └─ utils/           # JSON 修复、通用工具
├─ migrations/         # Alembic 数据库迁移
├─ scripts/            # 迁移与守卫脚本（migrate_local_assets_to_db 等）
├─ tests/              # pytest 测试
├─ alembic.ini
└─ requirements.txt
```

`uploads/` 仅作本地开发遗留目录，已加入 `.gitignore`，**不得**作为生产持久化层。

主要路由组：

| 路由前缀 | 职责 |
| --- | --- |
| `/auth` | 注册、登录、令牌刷新、当前用户与模型偏好 |
| `/books` | 书稿 CRUD、复制、导出和大部分书稿子资源 |
| `/books/{id}/references` | 文件上传、状态、确认、删除和资料检索 |
| `/books/{id}/outline` | 大纲获取、生成、编辑和开始写作 |
| `/books/{id}/chapters` | 章节 CRUD、排序、SSE 生成和取消 |
| `/books/{id}/citations` | 本书文献、引用节点、证据、正文位置和自动书末参考文献 |
| `/books/{id}/literature` | 查询优化、文献搜索、格式化与加入本书 |
| `/books/{id}/figures` | 图片、上传、生成、审批和图片批次 |
| `/books/{id}/optimization` | 章节映射、诊断、优化任务、对比与修订决策 |
| `/books/{id}/project-assistant` | 项目启动助手与全局助手对话轮次 |
| `/books/{id}/writing-basis` | 写作依据草稿、确认与手动编辑 |
| `/books/{id}/sources` | 资料库上传、分段与确认 |
| `/books/{id}/memories` | 项目长期记忆 |
| `/books/{id}/assets` | 二进制资产内容交付 |
| `/books/{id}/chapters/{index}/review` | 章节审校、问题应用、撤销和复检 |
| `/books/{id}/review-workspace` | 全书审校工作台 |
| `/book-jobs` | 一键成书前置任务和进度 |
| `/library` | 公共文献库 |
| `/notifications`、`/feedback`、`/config` | 通知、反馈和模型目录 |

FastAPI 自动接口文档位于：

- Swagger UI：`http://localhost:8001/docs`
- ReDoc：`http://localhost:8001/redoc`
- 健康检查：`http://localhost:8001/health`

## 数据模型

核心表按领域分组如下：

| 领域 | 主要模型 |
| --- | --- |
| 用户与书稿 | `User`、`Book`、`BookJob`、`Chapter`、`BookMemory` |
| 资料与约束 | `ReferenceFile`、`ReferenceFilePurpose`、`ReferenceChunk`、`WritingRequirement`、`MaterialTerm`、`MaterialConflict`、`OutlineConstraint` |
| 引用 | `Citation`、`CitationEvidence`、`CitationOccurrence` |
| 优化书稿 | `OptimizationProject`、`ManuscriptBaselineChapter`、`ManuscriptChapterMapping`、`ManuscriptRevision`、`OptimizationJob` |
| 图片 | `Figure`、`FigureBatchRun`、`FigureBatchItem` |
| 审校 | `ChapterReview`、`ChapterReviewIssue`、`ReviewApplication` |
| 助手 | `WritingBasis`、`AssistantTurn`、`AssistantTrace`、`ProjectMemory`、`SourceSegment` |
| 其他 | `GlobalLiterature`、`Notification`、`Feedback`、`BinaryAsset` |

结构化正文、流程检查点、诊断和模型缓存使用 JSONB；资料检索向量使用 pgvector。迁移必须通过 Alembic 管理，不使用 `Base.metadata.create_all()` 代替正式迁移。

## 前端架构

```text
frontend/src/
├─ api/          # Axios API 封装和领域请求
├─ components/   # 书稿、编辑器、布局及通用组件
├─ features/     # 助手、资料库、记忆、审校等领域模块
├─ contexts/     # React 上下文
├─ hooks/        # SSE、查询和编辑交互 Hook
├─ lib/          # TipTap 扩展、Markdown 转换、公式、图片与状态工具
├─ pages/        # 页面级路由
├─ stores/       # Zustand 持久化状态
└─ types/        # TypeScript 领域类型
```

主要页面：

- `/`：产品页。
- `/login`、`/register`：身份认证。
- `/app/home`：工作台首页。
- `/app/books`：我的书稿。
- `/app/books/:bookId`：普通创作和编辑工作台。
- `/app/books/:bookId/auto-progress`：一键成书进度。
- `/app/books/:bookId/optimize`：已有书稿优化工作台。
- `/app/library`：公共文献库入口。

前端状态分工：

- TanStack Query 管理书稿、章节、资料、引用、图片和任务等服务端状态。
- Zustand 保存 access token、refresh token 和当前用户，并在 401 时尝试刷新令牌。
- TipTap 保存章节富文本结构，自定义扩展负责引用、公式、表格、图片和段落锚点。
- 章节生成使用 SSE 增量接收文本；普通 JSON API 由 Axios 统一携带 Bearer Token。

## LLM 与检索层

`backend/app/llm/` 提供统一模型选择和调用接口。书稿可分别配置大纲、写作和全书规则模型，未设置时按服务商与默认模型回退。

支持的文本服务商包括：

- 国内：DeepSeek、千问、Kimi、豆包、百度千帆、智灵网关。
- 国际：OpenAI、Claude、Gemini、Grok。

资料向量默认使用 DashScope `text-embedding-v4`，维度固定为 1024，必须与数据库 `ReferenceChunk.embedding` 一致。修改维度需要同时新增数据库迁移，不能只修改环境变量。

## 本地开发

### 环境要求

- Python 3.11+
- Node.js 20.19+ 与 npm（推荐 Node.js 22.12+）
- PostgreSQL 16 和 pgvector 扩展
- 可选：Graphviz，用于部分流程图渲染

推荐使用 Docker 镜像 `pgvector/pgvector:pg16` 提供数据库。

### 1. 配置并启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

至少修改以下配置：

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/autobooker
JWT_SECRET=replace-with-a-long-random-secret
CORS_ORIGINS=http://localhost:5173
DASHSCOPE_API_KEY=
DEEPSEEK_API_KEY=
```

运行迁移并启动：

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

后端配置来源为 `backend/app/config.py` 和 `backend/.env`。完整变量及各模型服务商配置见 `backend/.env.example`。

### 2. 配置并启动前端

```powershell
cd frontend
npm install
```

创建 `frontend/.env`：

```dotenv
VITE_API_BASE=http://localhost:8001
```

启动开发服务器：

```powershell
npm run dev
```

访问：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8001`

Vite 仅自动代理 `/static/figures`；本地 API 地址应通过 `VITE_API_BASE` 指向后端。

## 常用配置

| 配置 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL SQLAlchemy 连接串 |
| `JWT_SECRET` | JWT 签名密钥，生产环境必须替换 |
| `CORS_ORIGINS` | 允许的前端来源，逗号分隔 |
| `UPLOAD_DIR` | 遗留开发目录（生产勿依赖）；业务字节在 `binary_assets` |
| `ASSETS_COMPAT_STATIC` | 是否挂载本地 `uploads/figures`（生产必须为 `false`） |
| `ALLOW_LOCAL_BUSINESS_STORAGE` | 是否允许磁盘 fallback/写入（生产必须为 `false`） |
| `DASHSCOPE_API_KEY` | 千问对话、向量和万相能力 |
| `EMBEDDING_MODEL` | 向量模型，默认 `text-embedding-v4` |
| `FIGURE_IMAGE_PROVIDER` | `auto`、`zeelin`、`openai` 或 `wanx` |
| `GRAPHVIZ_BIN_DIR` | Graphviz 可执行文件目录 |
| `LLM_MAX_RETRIES` | 模型请求最大重试次数 |
| `AI_DETECT_API_URL` | 可选的第三方文本检测接口 |

不要将真实 `.env`、数据库口令、API Key 或上传资料提交到仓库。

## 测试与质量检查

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

前端：

```powershell
cd frontend
npm test
npx tsc -b --pretty false
npm run build
```

数据库迁移状态：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
```

当前 0.5 核心迁移为 `p3q4r5s6t7u8_autobooker_05_core.py`；重构迁移含 `r1s2t3u4v5w6_refactor_core.py` 与 `s7t8u9v0w1x2_writing_context_snapshots.py`。

### 重构部署清单

1. `alembic upgrade head`
2. `python scripts/migrate_local_assets_to_db.py --dry-run` 核对后正式执行
3. 验证旧书稿图片/资料经 `/api/books/{id}/assets/{asset_id}/content` 可访问
4. 设置 `ASSETS_COMPAT_STATIC=false` 与 `ALLOW_LOCAL_BUSINESS_STORAGE=false`（默认）后重启后端
5. CI 工作流 `refactor-guards.yml` 会跑守卫脚本与回归测试子集
6. 确认 `backend/uploads/` 未纳入 git（见根目录 `.gitignore`）

## 兼容与部署注意事项

- 正式数据库只支持 PostgreSQL + pgvector；仓库中可能存在的 SQLite 文件不代表受支持的生产目标。
- 业务二进制资产只存 PostgreSQL `binary_assets`；`uploads/` 不得作为多实例共享卷或对象存储替代方案。
- 旧 `user_material`、历史向量块和纯文本引用不会批量迁移；读取旧书稿时继续兼容。
- 修改引用格式只刷新结构化引用节点，不猜测或重写旧纯文本引用。
- 原稿基线确认后禁止删除源文件；恢复操作从不可变基线生成工作稿。
- 生产环境应关闭 `--reload`，配置强 JWT 密钥、反向代理、HTTPS 和数据库备份。
- 当前后台任务依赖 API 进程。若需要多机调度、自动接管和独立扩缩容，应在后续版本接入外部任务队列（如 Redis + worker）。

版本变化见 [CHANGELOG.md](CHANGELOG.md)。
