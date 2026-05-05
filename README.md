# AutoBooker

这是 AutoBooker 项目的根目录，包含后端 FastAPI 服务和前端 Vite + React 应用。

## 目录结构

- `backend/`：FastAPI 后端服务
- `frontend/`：React + Vite 前端应用

## 环境需求

- Node.js 18+ / npm
- Python 3.11+（推荐）
- PostgreSQL 数据库（默认配置可在 `backend/app/config.py` 中修改）

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

4. 选择性创建 `.env` 文件（可选）：

```text
DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/autobooker
JWT_SECRET=your-secret
CORS_ORIGINS=http://localhost:5173
```

5. 启动后端服务：

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
