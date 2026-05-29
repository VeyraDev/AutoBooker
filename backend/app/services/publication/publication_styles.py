"""Shared publication style constants (DOCX pt / PDF CSS)."""

BODY_PT = 12
CHAPTER_TITLE_PT = 16
SECTION_TITLE_PT = 14
SUBSECTION_TITLE_PT = 13
CAPTION_PT = 10.5
LINE_SPACING = 1.5
FIRST_LINE_INDENT_PT = 24  # ~2 Chinese chars at 12pt

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
"""
