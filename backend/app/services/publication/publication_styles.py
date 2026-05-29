"""Shared publication style constants (DOCX pt / PDF CSS)."""

BODY_PT = 12
CHAPTER_TITLE_PT = 16
SECTION_TITLE_PT = 14
SUBSECTION_TITLE_PT = 13
CAPTION_PT = 10.5
LINE_SPACING = 1.5
FIRST_LINE_INDENT_PT = 24  # ~2 Chinese chars at 12pt
PDF_PAGE_MARGIN_PT = 56
# A4 可排版区域宽度（与 render_ast_to_pdf 页边距一致）
PDF_CONTENT_WIDTH_PT = 595.28 - 2 * PDF_PAGE_MARGIN_PT
PDF_CONTENT_HEIGHT_PT = 841.89 - 2 * PDF_PAGE_MARGIN_PT
# Story 对 CSS pt 支持差，按 96dpi 换算为像素宽度并预缩放位图
PDF_FIGURE_WIDTH_PX = int(PDF_CONTENT_WIDTH_PT / 72 * 96)
PDF_FIGURE_MAX_HEIGHT_PX = int(PDF_CONTENT_HEIGHT_PT / 72 * 96)

PUBLICATION_CSS = """
body {
  font-family: "Noto Serif SC", "SimSun", serif;
  font-size: 12pt;
  line-height: 1.5;
  color: #000000;
}
p.body {
  text-indent: 2em;
  margin: 0 0 8pt 0;
}
h1.book-title { font-size: 22pt; text-align: center; font-weight: bold; margin: 0 0 24pt 0; color: #000; }
h1.preface-title { font-size: 18pt; text-align: center; font-weight: bold; margin: 24pt 0 12pt 0; color: #000; }
h1.chapter-title { font-size: 16pt; text-align: center; font-weight: bold; margin: 24pt 0 12pt 0; color: #000; }
h2.section-title { font-size: 14pt; text-align: left; font-weight: bold; margin: 16pt 0 8pt 0; color: #000; }
h3, h4, h5, h6 { font-size: 13pt; text-align: left; font-weight: bold; margin: 12pt 0 6pt 0; color: #000; }
.caption { font-size: 10.5pt; color: #000; text-align: center; margin: 6pt 0 12pt 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; }
td, th { border: 1pt solid #333; padding: 4pt 6pt; font-size: 11pt; color: #000; }
blockquote { margin: 8pt 0 8pt 18pt; color: #000; }
pre { background: #f5f5f5; padding: 8pt; font-size: 10pt; }
.figure-group { page-break-inside: avoid; margin: 12pt 0 8pt 0; }
.figure-group img { border: none; }
"""
