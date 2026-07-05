# 变更日志（CHANGELOG）

记录 **AutoBooker（前端品牌 AutoBook）** 每次迭代的用户可见变更。**按日期倒序排列**（最新在上）。

---

## 书写规范

1. **每次更新**在下方新增或续写 `## YYYY-MM-DD` 小节；若当天已有小节，只在当日下追加 bullet，不要另建重复日期。
2. 每条写清 **用户可感知的结果**；涉及实现位置时用括号注明路径（如 `backend/app/llm/`、`frontend/src/pages/`）。
3. 发版日可在日期后标注版本：`## YYYY-MM-DD · vx.y.z`。
4. 破坏性变更在条目前加 **`BREAKING:`**。
5. **不要**使用 `[Unreleased]` 或按 Added/Changed/Fixed 分类堆叠；一切变更归属到具体日期。

---

## 2026-07-04

- **表格内公式渲染**：Markdown 转 TipTap 时表格单元格支持 `$…$` 行内公式；加载旧章节时不再跳过表格内段落迁移（`markdown_to_tiptap.py`、`migrateMathInTiptapDoc.ts`）。
- **全书图片按钮状态**：顶栏「生成全书图片」在单章自动图片批次运行时也会显示「暂停生成图片」；点击全书按钮时若已有进行中的批次则复用该批次，不再误报「暂无待生成图片」（`figures.py`、`figure_batch_service.py`、`chapters.py`）。
- **引用编号规则统一**：正式序号只表示书末参考文献位置。GB/T 7714 按正文首次出现顺序编号，同一文献重复引用保持同一编号；未使用文献不编号，引用次数、外部被引量和 GitHub 星标不参与编号。
- **非顺序格式修正**：APA、MLA、Chicago 正文不再显示 `[n]`，改为对应作者/年份样式；书末参考文献按作者、年份、标题规则排序，不再套用正文首次出现顺序。
- **引用管理合并**：文献模块只保留“文献搜索”和“引用管理”。引用管理按文献分组，集中显示元数据完整性、正文引用处数、所有章节位置、上下文、跳转和单次删除；未使用文献排在已使用文献之后并标记“尚未引用”。
- **移除危险与重复操作**：删除“替换来源”“修改来源”和手动“同步参考文献章”入口；搜索结果统一为“加入本书”，引用关联错误时采用删除后重新插入的明确流程。
- **独立书后参考文献**：参考文献从普通 `Chapter` 迁移到 `Book.bibliography`，不再计入章节数、目标字数、章节生成或审校。目录单列“书后内容”，Markdown、DOCX、PDF 在正文之后自动追加同一份参考文献。
- **引用持久化修复**：引用节点刷新改用 JSON 深拷贝，确保格式切换和重新编号真正写入 PostgreSQL；图表正文重建前将结构化引用还原为内部 UUID 标记，避免丢失文献关联。
- **数据库与验证**：新增迁移 `q4r5s6t7u8v9` 并完成旧参考文献章节搬迁；后端 307 项测试、前端 8 项测试、TypeScript 检查、生产构建及 PostgreSQL 格式切换事务验收通过。

## 2026-07-03 · v0.5.0

- **统一资料处理**：上传文件统一支持大纲、写作要求、参考资料、参考文献和原始书稿五种用途；新增解析中、待确认、已生效、已停用和失败状态，并展示解析产物与冲突确认（`reference.py`、`material.py`、`material_parse_service.py`、`SetupView.tsx`）。
- **主大纲约束**：主大纲参与生成时强制保留章数、顺序、锁定标题和锁定小节；多主大纲、结构、字数和术语冲突进入用户确认，不再让生成结果静默覆盖原结构（`outline.py`、`outline_agent.py`）。
- **安全删除与旧数据兼容**：删除资料会移除物理文件、停用派生产物并标记相关写作规则过期，不重写已有正文；新上传不再写入旧 `user_material`，历史书稿继续只读兼容（`references.py`、`book.py`）。
- **优化已有书稿**：新建书稿可选择“优化已有书稿”，上传 DOCX、PDF 或 TXT 后完成章节识别、映射确认、不可变基线、全书诊断、优化方案和逐章优化（`optimization.py`、`optimization_service.py`、`OptimizationPage.tsx`）。
- **候选修订闭环**：优化结果保存为候选版本，可查看原稿/优化稿对比、接受、放弃或恢复原稿；默认禁止删除、合并和重排章节，批量优化任务持久化进度并支持失败后重试。
- **结构化引用**：TipTap 新增内联引用节点，正文保存时同步引用位置、证据、章节和上下文；支持单次删除、来源替换、正文跳转、完整性提示以及未匹配来源清单（`CitationNode.ts`、`citation_nodes.py`、`LiteraturePanel.tsx`）。
- **引用与导出一致**：引用格式变化后按正文首次出现顺序重新编号并刷新书末参考文献；Markdown、DOCX、PDF 统一识别引用节点，GB/T 7714 同一来源只列一次。
- **图片批次**：新增全书和单章图片批次及持久化进度；跳过截图、已上传和已成功图片，通过数据库锁避免并发重复生成。一键成书每章完成后自动提交该章图片，图片失败不影响正文成功状态（`figure_batch.py`、`figure_batch_service.py`、`FigureQuickPanel.tsx`）。
- **写作规则与术语**：术语表只收录专业术语、理论、专名和用户指定表达；普通题材允许空术语表，不再强制英文名或首次解释（`memory_extract.py`、`publication_standards.py`）。
- **主要路径文案**：新建、资料、策划、自动进度、写作、图片、引用和审校页面统一为用户语言，隐藏内部实现术语与原始服务端异常；一键成书创建后直接进入进度页，普通创作与书稿优化按工作流分流。
- **生成大纲修复**：修复首次保存引用格式时的枚举类型错误；点击后立即显示保存/生成状态，使用刚保存的最新设定发起请求；设定保存失败不再静默，大纲服务异常只显示可操作的用户提示。
- **一键成书跳转修复**：新建时通过单个接口原子创建书稿与任务并直接进入进度页；运行中书稿从首页或列表打开仍进入进度页，任务缺失可原地重启，离开进度页后返回也能从持久化检查点恢复自动写作。
- **文献跨来源选择修复**：“全选本页”改为叠加当前页结果，切换论文、GitHub、百科或官方资料来源后不会清空此前勾选；只有开始新检索、主动清空或成功加入引用库时才重置选择。
- **写作入口精简**：删除设定页重复的“开始一键成书”按钮，一键成书只从新建书稿流程启动。
- **全书图片暂停**：全书图片任务运行时顶栏按钮切换为“暂停生成图片”；服务端持久化 `paused` 状态，停止尚未开始的项目，允许已进入生成调用的项目收尾，并可从剩余图片继续。
- **引用识别与编号修复**：统一识别 `[[CITE:文献UUID|引用方式]]`，将模型同时输出的作者年份括注合并为单个引用节点；图表同步后再次归一化引用，按全书首次出现顺序显示 `[1]` 等特殊节点，并同步“本书引用”位置。已有内部标记在章节读取或打开本书引用时自动修复。
- **数据库与测试**：新增 0.5 核心迁移 `p3q4r5s6t7u8`；后端 303 项测试、前端 6 项组件/序列化测试、TypeScript 检查、真实 Chrome 端到端烟测、API 冒烟及生产构建通过（`backend/migrations/versions/p3q4r5s6t7u8_autobooker_05_core.py`、`backend/tests/test_autobooker_05_core.py`、`backend/tests/test_workflow_regressions.py`）。
- **依赖安全**：前端升级到 Vite 8、Vitest 4 及兼容依赖，完整 `npm audit` 无已知漏洞。
- **架构文档**：README 新增总体架构、两种工作流、资料/引用/图片管线、数据模型、路由、前端状态、部署边界和测试说明（`README.md`）。

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
