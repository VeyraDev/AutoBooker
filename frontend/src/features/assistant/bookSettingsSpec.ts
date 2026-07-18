/**
 * 唯一正式书稿设定：启动助手 / 项目要点 / 高级编辑 / 大纲入参 共用。
 * WritingBasis 不再作为第二套 UI 表单（仅下游静默兼容）。
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

export const BOOK_TYPE_LABEL: Record<string, string> = {
  nonfiction: "大众非虚构",
  academic: "学术专著",
};
