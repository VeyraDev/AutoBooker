# Phase 2 后端实现说明与 Critic 自检

## 已实现能力

- **RAG**：`reference_chunks.embedding` 为 `vector(1024)`，DashScope `text-embedding-v3` 写入，余弦距离检索（`DocumentParserAgent.retrieve`）。
- **上传解析**：`POST /books/{id}/references/upload` 后台任务解析 PDF/DOCX 并入库；`POST .../references/search` 调试用检索。
- **大纲**：`POST /books/{id}/outline` 拉取参考片段 + `OutlineAgent` + jsonschema 校验与最多 3 次重试；`GET/PUT /books/{id}/outline`。
- **章节生成**：`POST /books/{id}/chapters/{n}/generate` **SSE** 流式；完成后合并 `content["text"]` 与记忆提取（`qwen-turbo`）写入 `book_memory`。
- **Prompt 位置**：`app/prompts/`（`outline.py`、`chapter_writer.py`、`memory_extract.py`）。

## 环境要求

1. **PostgreSQL 需含 pgvector 扩展**（标准 PG 镜像无 vector 会无法 `alembic upgrade`）。推荐：`pgvector/pgvector:pg16` 镜像，或自行在库中安装 vector 后 `CREATE EXTENSION vector;`。
2. **`.env`**：至少配置 `DASHSCOPE_API_KEY`；可选 `DASHSCOPE_BASE_URL`（北京/国际端点以控制台为准）、`CHAT_MODEL` / `CHAT_MODEL_FAST` / `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS=1024`。
3. 迁移：`cd backend && alembic upgrade head`

## Critic 自检（至少 3 点）

1. **同步 LLM 阻塞事件循环**：章节生成在 `async` 路由里用同步 `Session` 与 `AsyncOpenAI` 流式混用，高并发下应改为独立 worker 队列或显式 session 范围。
2. **大纲/记忆依赖模型输出 JSON**：虽有 jsonschema + 重试，仍应在生产侧增加原始响应落库与告警（当前仅日志）。
3. **章节 `content` 混用大纲元数据与正文**：`content` 同时存 `sections`/`text`，前端 Tiptap JSON 尚未接入时需约定合并策略，避免后续迁移冲突。

知识库（`vibecoding-workflow/knowledge/`）未自动写入；若需沉淀请在对话中确认后再添加文件。
