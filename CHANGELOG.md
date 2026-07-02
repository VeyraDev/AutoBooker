# 变更日志（CHANGELOG）

记录 **AutoBook** 每次迭代的用户可见变更。**按日期倒序排列**（最新在上）。

---

## 书写规范

1. **每次更新**在下方新增或续写 `## YYYY-MM-DD` 小节；若当天已有小节，只在当日下追加 bullet，不要另建重复日期。
2. 每条写清 **用户可感知的结果**；涉及实现位置时用括号注明路径（如 `backend/app/llm/`、`frontend/src/pages/`）。
3. 发版日可在日期后标注版本：`## YYYY-MM-DD · vx.y.z`。
4. 破坏性变更在条目前加 **`BREAKING:`**。
5. **不要**使用 `[Unreleased]` 或按 Added/Changed/Fixed 分类堆叠；一切变更归属到具体日期。

---

## 2026-07-02

- **一键成书进度页**：新增固定路由 `/app/books/:bookId/auto-progress`，分阶段展示设定、文献、大纲、叙事宪法、章节写作与配图进度；展示章节/配图计数与已运行时长（`frontend/src/pages/AutoBookProgressPage.tsx`、`frontend/src/lib/autoBookProgress.ts`）。
- **一键成书跳转**：点击「一键出书」后创建书稿、立即启动 Job 并进入进度页，不再要求先到设定页手动确认；写作页在 Job 未就绪时自动重定向至进度页（`NewBookDialog.tsx`、`BookEditorPage.tsx`、`SetupView.tsx`）。
- **进入写作页条件**：大纲与叙事宪法持久化、章节目录已创建、第一章写作启动后（`ready_for_editor`）才自动进入写作页，避免目录为空（`backend/app/services/auto_book_job.py`、`backend/app/services/auto_book_job_progress.py`）。
- **一键成书配图**：章节正文完成后后台并行生成插图（默认 2 并发，不阻塞后续章节；单张失败不回滚正文）（`backend/app/services/auto_book_figure_worker.py`）。
- **Job 状态 API**：`GET /book-jobs/{book_id}` 返回 `detail`（章节/配图进度、阶段文案、`ready_for_editor` 等）（`backend/app/schemas/book_job.py`、`backend/app/routers/book_jobs.py`）。
- **数据库**：`book_job_step` 枚举新增 `figures`（迁移 `migrations/versions/o2p3q4r5s6t7_book_job_figures_step.py`）。

## 2026-06-30

- **品牌**：产品标识 `AutoBooker` → `AutoBook`（顶栏、登录/注册、落地页、`index.html` 等）。
- **导航**：「图书管理」→「图书生成」；系统书库导航与页面标注「待开发」。
- **新建书稿**：分为「生成新书」（手动创建 / 一键出书）与「优化新书」（占位待开发）（`frontend/src/components/common/NewBookDialog.tsx`）。
- **移除页面**：个人主页、数据统计；旧 URL 重定向至主页（`App.tsx`）。
- **导出页码**：DOCX / PDF 页脚居中显示页码（`backend/app/services/publication/page_numbers.py`）。

## 2026-06-29 · v0.1.0

- **初始发布**：书稿 CRUD、大纲 JSON 生成、章节 SSE 流式写作、TipTap 编辑、多 LLM 路由、向量 RAG、配图管道（智灵/OpenAI/万相）、叙事宪法、文献引用等（详见 `backend/PHASE2_NOTES.md`）。
- **插图生成**：OpenAI/智灵 billing/配额/欠费失败时，若已配置 DashScope，自动回退通义万相（`backend/app/services/figures/render/image_api/pipeline.py`）。
- **大纲生成**：按章数动态提高 JSON completion 上限（最高 32768）；增强截断 JSON 修复与 salvage（`backend/app/utils/json_llm.py`、`backend/app/agents/outline_agent.py`）。
- **章节公式渲染**：修复 Markdown→TipTap 时行内 `$...$` 被丢弃等问题（`math_tokenizer.py`、`repair_inline_math.py`、`frontend/src/lib/repairInlineMath.ts` 等）。
- **测试与文档**：补充相关后端测试用例；新增本变更日志（`CHANGELOG.md`）。

## 2026-06-27

- **公式渲染与提示词**：章节内公式显示与写作提示词调整。
