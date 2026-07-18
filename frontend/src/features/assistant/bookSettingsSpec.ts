/**
 * 书稿设定统一结构：项目要点 / 高级编辑 / 大纲入参 共用同一套字段语义。
 *
 * Book 字段 = 可持久化到 books 表的核心设定
 * WritingBasis 扩展字段 = 助手沉淀的策划细节（同步展示，确认时写入 WritingRequirement）
 */

export const BOOK_SETUP_FIELDS = [
  { key: "title", label: "书名", source: "book" as const },
  { key: "book_type", label: "一级分类", source: "book" as const },
  { key: "style_type", label: "二级体裁", source: "book" as const },
  { key: "target_audience", label: "目标读者", source: "book" as const },
  { key: "disciplines", label: "学科领域", source: "book" as const },
  { key: "target_words", label: "目标字数", source: "book" as const },
  { key: "topic_tags", label: "话题标签", source: "book" as const },
  { key: "topic_brief", label: "主题要点", source: "book" as const },
  { key: "citation_style", label: "引用格式", source: "book" as const },
] as const;

export const BASIS_SETUP_FIELDS = [
  { key: "book_promise", label: "书稿承诺" },
  { key: "reader_outcome", label: "读者收获" },
  { key: "scope", label: "内容范围" },
  { key: "depth", label: "专业深度" },
  { key: "voice", label: "语言风格" },
  { key: "must_avoid", label: "禁止事项", list: true },
  { key: "must_keep", label: "必须保留", list: true },
] as const;

export const BOOK_TYPE_LABEL: Record<string, string> = {
  nonfiction: "大众非虚构",
  academic: "学术专著",
};
