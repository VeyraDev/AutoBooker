# 变更日志（CHANGELOG）

本文件记录 AutoBooker 的功能变更、缺陷修复与重要配置调整。**每次合并/发布前请追加条目**。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)（尚未发版时可写在 `[Unreleased]` 下）。

---

## 如何书写新条目

1. 在 **`[Unreleased]`** 下按类型追加 bullet（发版时将 `[Unreleased]` 改为 `[x.y.z] - YYYY-MM-DD` 并新建空的 `[Unreleased]`）。
2. 类型（按需选用）：
   - **Added**：新功能
   - **Changed**：既有行为变更
   - **Fixed**：缺陷修复
   - **Removed**：删除的能力
   - **Deprecated**：即将废弃
   - **Security**：安全相关
3. 每条写清 **用户可感知的结果**，必要时注明模块路径（如 `backend/app/llm/`、`frontend/src/lib/`）。
4. 破坏性变更标注 **`BREAKING:`** 前缀。

---

## [Unreleased]

### Changed

- **品牌与导航**：产品标识 `AutoBooker` → `AutoBook`；「图书管理」→「图书生成」；系统书库标注「待开发」；移除个人主页与数据统计入口（`frontend/`）。
- **新建书稿**：分为「生成新书」（含手动/一键出书）与「优化新书」（占位待开发）（`frontend/src/components/common/NewBookDialog.tsx`）。
- **导出**：DOCX / PDF 页脚新增居中页码（`backend/app/services/publication/page_numbers.py`）。

### Removed

- **页面**：个人主页、数据统计（`ProfilePage`、`StatsPage` 及对应路由）。

### Fixed

- **插图生成**：OpenAI/智灵图像 API 因 billing、配额、欠费失败时，若已配置 DashScope，自动回退通义万相（`backend/app/services/figures/render/image_api/pipeline.py`）。
- **大纲生成**：加长 JSON completion 预算（按章数动态计算，最高 32768）；增强截断 JSON 修复与 salvage；重试时要求紧凑 JSON（`backend/app/utils/json_llm.py`、`backend/app/agents/outline_agent.py`）。
- **章节公式渲染**：修复 Markdown→TipTap 时行内 `$...$` 被丢弃的问题（`tokenize` 不再拆散 inline segment）；合并被空行拆开的行内公式；含公式时前端优先走 `plainTextMarkdownToTiptapDoc`；无 `[DIAGRAM:…]` 时不再用 `sync_figures_to_tiptap` 覆盖已组装的章节结构（`backend/app/services/math_tokenizer.py`、`backend/app/services/repair_inline_math.py`、`frontend/src/lib/repairInlineMath.ts` 等）。

### Added

- **测试**：插图 billing 回退（`backend/tests/test_figure_image_fallback.py`）、截断 JSON 解析（`backend/tests/test_json_llm.py`）、行内公式修复（`backend/tests/test_repair_inline_math.py`）。
- **文档**：本变更日志（`CHANGELOG.md`）。

---

## [0.1.0] - 2026-06-29

### Added

- 初始能力：书稿 CRUD、大纲 JSON 生成、章节 SSE 流式写作、TipTap 编辑、多 LLM 服务商路由、向量 RAG、配图管道（智灵/OpenAI/万相）、叙事宪法、文献引用等（详见 `backend/PHASE2_NOTES.md`）。

[Unreleased]: https://github.com/your-org/AutoBooker/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/AutoBooker/releases/tag/v0.1.0
