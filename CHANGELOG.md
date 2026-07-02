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

- **一键成书流程简化**：后台 Job 仅负责设定/文献/大纲/叙事宪法；叙事宪法完成后进入写作页，自动调用与正常流程相同的 `handleStartWriting('auto')`（前言 SSE + 全书章节流式生成）；写作页不再显示成书进度/后台 Job 相关 UI（`auto_book_job.py`、`BookEditorPage.tsx`、`autoBookWrite.ts`）。
- **修复自动写作未启动**：进度页跳转标记在大纲未加载完前被提前消费，导致前言不生成、流式与「暂停生成」失效；改为 `peekPendingAutoWrite` 待数据就绪后再 `consume`（`autoBookWrite.ts`、`BookEditorPage.tsx`）。
- **一键成书进度页**：新增固定路由 `/app/books/:bookId/auto-progress`，仅展示设定、文献、大纲、叙事宪法四阶段（`AutoBookProgressPage.tsx`、`autoBookProgress.ts`）。
- **一键成书跳转**：点击「一键出书」后创建书稿、启动前置 Job 并进入进度页；前置 Job 未完成时写作页自动重定向至进度页（`NewBookDialog.tsx`、`BookEditorPage.tsx`、`SetupView.tsx`）。

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
