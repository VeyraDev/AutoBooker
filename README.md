# AutoBooker

这是 AutoBooker 项目的根目录，包含后端 FastAPI 服务和前端 Vite + React 应用。

## 目录结构

- `backend/`：FastAPI 后端服务
- `frontend/`：React + Vite 前端应用

## 环境需求

- Node.js 18+ / npm
- Python 3.11+（推荐）
- **PostgreSQL + pgvector 扩展**（本地推荐 Docker 镜像 `pgvector/pgvector:pg16`）
- `.env` 文件来自 `backend/.env.example`
- 可选：Graphviz（用于流程图/图形渲染，Windows 上默认会自动探测 `C:\Program Files\Graphviz\bin`）

### 后端配置

复制 `backend/.env.example` 为 `backend/.env`，并根据实际环境设置：

- `DATABASE_URL`
- `JWT_SECRET`
- `CORS_ORIGINS`
- `UPLOAD_DIR`
- `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `KIMI_API_KEY` / `DOUBAO_API_KEY` / `BAIDU_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `GROK_API_KEY`
- `FIGURE_IMAGE_PROVIDER`

当前后端配置文件为 `backend/app/config.py`，默认使用 `.env` 中的设置。

### 后端主要路由

当前后端包含以下主要路由组：

- `auth`
- `books`
- `references`
- `literature`
- `citations`
- `review`
- `outline`
- `chapters`
- `figures`
- `assistant`

此外提供健康检查接口：

- `GET /health`

更多说明见 `backend/PHASE2_NOTES.md`。

## 后端启动

1. 进入后端目录：

```powershell
cd backend
```

2. 建议创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. 安装依赖：

```powershell
pip install -r requirements.txt
```

4. 复制 `.env.example` 为 `.env`，并根据实际情况填写所需环境变量：

```powershell
copy .env.example .env
```

5. 运行数据库迁移：

```powershell
alembic upgrade head
```

6. 启动后端服务：

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

后端默认运行在 `http://localhost:8001`。

## 前端启动

1. 进入前端目录：

```powershell
cd frontend
```

2. 安装依赖：

```powershell
npm install
```

3. 启动开发服务器：

```powershell
npm run dev
```

默认会在 `http://localhost:5173` 启动前端应用。

## 访问方式

- 前端：`http://localhost:5173`
- 后端健康检查：`http://localhost:8001/health`

## 备注

- 后端配置文件：`backend/app/config.py`
- 前端配置文件：`frontend/vite.config.ts`
- 若前端与后端不在同一主机或端口，请确保 `CORS_ORIGINS` 设置包含前端地址。
- 若使用不同数据库连接，请修改 `DATABASE_URL` 为实际 PostgreSQL 地址。
