"""Shared publication style constants — 国内正规图书字号层级（Word/PDF 共用）。

字号对照：五号=10.5pt，小四=12pt，四号=14pt，小三=15pt，三号=16pt，六号=9pt，小五=9pt。
大32开正文五号；大16开正文小四。标题：一级三号、二级小三黑体、三级四号黑体…
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.publication.page_formats import (
    DEFAULT_PAGE_FORMAT_ID,
    PageFormatSpec,
    get_page_format,
)

_DEFAULT = get_page_format(DEFAULT_PAGE_FORMAT_ID)

PAGE_WIDTH_MM = _DEFAULT.width_mm
PAGE_HEIGHT_MM = _DEFAULT.height_mm
PAGE_WIDTH_PT = _DEFAULT.width_pt
PAGE_HEIGHT_PT = _DEFAULT.height_pt
MARGIN_INNER_MM = _DEFAULT.margin_inner_mm
MARGIN_OUTER_MM = _DEFAULT.margin_outer_mm
MARGIN_TOP_MM = _DEFAULT.margin_top_mm
MARGIN_BOTTOM_MM = _DEFAULT.margin_bottom_mm
MARGIN_INNER_PT = _DEFAULT.margin_inner_pt
MARGIN_OUTER_PT = _DEFAULT.margin_outer_pt
MARGIN_TOP_PT = _DEFAULT.margin_top_pt
MARGIN_BOTTOM_PT = _DEFAULT.margin_bottom_pt
FORMAT_LABEL = _DEFAULT.short_label

COVER_DPI = 150
COVER_WIDTH_PX = int(PAGE_WIDTH_MM / 25.4 * COVER_DPI)
COVER_HEIGHT_PX = int(PAGE_HEIGHT_MM / 25.4 * COVER_DPI)

# —— 字号标准（pt）——
HAO_WU = 10.5  # 五号 · 大32正文
HAO_XIAOSI = 12.0  # 小四 · 大16正文 / 目录标题
HAO_SI = 14.0  # 四号 · 三级标题
HAO_XIAOSAN = 15.0  # 小三 · 二级标题
HAO_SAN = 16.0  # 三号 · 章标题
HAO_LIU = 9.0  # 六号 · 图注页码脚注
HAO_XIAOWU = 9.0  # 小五

BODY_PT = HAO_WU
BOOK_TITLE_PT = 22
CHAPTER_TITLE_PT = HAO_SAN
SECTION_TITLE_PT = HAO_XIAOSAN
SUBSECTION_TITLE_PT = HAO_SI
FOURTH_TITLE_PT = HAO_XIAOSI
FIFTH_TITLE_PT = HAO_WU
SIXTH_TITLE_PT = HAO_WU
CAPTION_PT = HAO_LIU
LINE_SPACING = 1.5
FIRST_LINE_INDENT_PT = 21  # 五号约 2 字宽
PDF_PAGE_MARGIN_PT = MARGIN_OUTER_PT
PDF_CONTENT_WIDTH_PT = PAGE_WIDTH_PT - MARGIN_INNER_PT - MARGIN_OUTER_PT
PDF_CONTENT_HEIGHT_PT = PAGE_HEIGHT_PT - MARGIN_TOP_PT - MARGIN_BOTTOM_PT
PDF_FIGURE_WIDTH_PX = int(PDF_CONTENT_WIDTH_PT / 72 * 96)
PDF_FIGURE_MAX_HEIGHT_PX = int(PDF_CONTENT_HEIGHT_PT / 72 * 96)

DOC_BODY_FONT = "宋体"
DOC_HEADING_FONT = "黑体"
DOC_PREFACE_FONT = "楷体"
DOC_LATIN_FONT = "Times New Roman"

AST_WORD_HEADING_LEVEL: dict[str, int | None] = {
    "book_title": None,
    "preface_title": 1,
    "chapter_title": 1,
    "chapter_flyleaf": None,
    "section_title": 2,
    "section_flyleaf": 2,
    "subsection_title": 3,
}


@dataclass(frozen=True)
class TypeScale:
    body_pt: float
    chapter_pt: float
    section_pt: float
    subsection_pt: float
    fourth_pt: float
    fifth_pt: float
    caption_pt: float
    toc_title_pt: float
    toc_entry_pt: float
    page_num_pt: float
    line_spacing: float
    first_indent_pt: float


def type_scale_for_format(spec: PageFormatSpec | None = None) -> TypeScale:
    """按开本返回正文字号：大32→五号；大16及更大→小四（可用 spec.body_pt 覆盖）。"""
    spec = spec or get_page_format(DEFAULT_PAGE_FORMAT_ID)
    large = spec.width_mm >= 180  # 大16 / B5 / 24开 / 8开
    body = float(spec.body_pt) if spec.body_pt else (HAO_XIAOSI if large else HAO_WU)
    indent = 24.0 if large else 21.0
    return TypeScale(
        body_pt=body,
        chapter_pt=HAO_SAN,
        section_pt=HAO_XIAOSAN,
        subsection_pt=HAO_SI,
        fourth_pt=HAO_XIAOSI,
        fifth_pt=HAO_WU,
        caption_pt=HAO_LIU,
        toc_title_pt=HAO_XIAOSI,
        toc_entry_pt=HAO_WU if not large else HAO_XIAOSI,
        page_num_pt=HAO_WU,
        line_spacing=1.5 if not large else 1.6,
        first_indent_pt=indent,
    )


def subsection_word_heading_level(tiptap_level: int) -> int:
    return max(3, min(6, int(tiptap_level or 3)))


def publication_css_for_body_pt(body_pt: float = BODY_PT) -> str:
    scale = type_scale_for_format()
    # 若传入 body_pt 与默认不同，覆盖正文
    b = body_pt
    return f"""
body {{
  font-family: "{DOC_BODY_FONT}", "Noto Serif SC", "SimSun", serif;
  font-size: {b}pt;
  line-height: {scale.line_spacing};
  color: #000000;
}}
p.body {{
  text-indent: 2em;
  margin: 0;
}}
h1.book-title {{ font-size: {BOOK_TITLE_PT}pt; text-align: center; font-weight: bold; margin: 0 0 24pt 0; color: #000; }}
h1.preface-title {{
  font-family: "{DOC_HEADING_FONT}", "SimHei", sans-serif;
  font-size: {scale.chapter_pt}pt; text-align: center; font-weight: bold; margin: 24pt 0 12pt 0; color: #000;
}}
h1.chapter-title {{
  font-family: "{DOC_HEADING_FONT}", "SimHei", sans-serif;
  font-size: {scale.chapter_pt}pt; text-align: center; font-weight: bold; margin: 24pt 0 12pt 0; color: #000;
}}
h2.section-title {{
  font-family: "{DOC_HEADING_FONT}", "SimHei", sans-serif;
  font-size: {scale.section_pt}pt; text-align: left; font-weight: bold; margin: 14pt 0 8pt 0; color: #000;
}}
h3.subsection-title {{
  font-family: "{DOC_HEADING_FONT}", "SimHei", sans-serif;
  font-size: {scale.subsection_pt}pt; text-align: left; font-weight: bold; margin: 12pt 0 6pt 0; color: #000;
}}
h4.subsection-title {{
  font-family: "{DOC_HEADING_FONT}", "SimHei", sans-serif;
  font-size: {scale.fourth_pt}pt; text-align: left; font-weight: bold; margin: 10pt 0 4pt 0; color: #000;
}}
h5.subsection-title, h6.subsection-title {{
  font-family: "{DOC_HEADING_FONT}", "SimHei", sans-serif;
  font-size: {scale.fifth_pt}pt; text-align: left; font-weight: bold; margin: 8pt 0 4pt 0; color: #000;
}}
.caption {{ font-size: {scale.caption_pt}pt; color: #000; text-align: center; margin: 6pt 0 10pt 0; }}
.flyleaf {{
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  min-height: 70vh; text-align: center; page-break-after: always;
}}
.flyleaf-title {{
  font-family: "{DOC_HEADING_FONT}", "SimHei", sans-serif;
  font-size: {scale.chapter_pt}pt; font-weight: bold; margin: 0 0 18pt 0;
}}
.flyleaf-summary {{
  font-family: "{DOC_PREFACE_FONT}", "KaiTi", serif;
  font-size: {scale.body_pt}pt; max-width: 85%; line-height: 1.7; margin: 0;
}}
table {{ border-collapse: collapse; width: 100%; margin: 8pt 0; }}
td, th {{ border: 1pt solid #333; padding: 4pt 6pt; font-size: {b - 0.5}pt; color: #000; }}
table.toc-row {{
  width: 100%; border-collapse: collapse; margin: 3pt 0; table-layout: fixed;
}}
table.toc-row td {{
  border: none; font-size: {b}pt; vertical-align: bottom;
}}
table.toc-row td.toc-title {{
  border-bottom: 0.7pt dotted #555;
}}
table.toc-row td.toc-page {{
  white-space: nowrap; text-align: right;
}}
blockquote {{
  font-family: "{DOC_PREFACE_FONT}", "KaiTi", serif;
  margin: 8pt 2em; color: #000; font-size: {b}pt;
}}
pre {{ background: #f5f5f5; padding: 8pt; font-size: 9pt; }}
.figure-group {{ page-break-inside: avoid; margin: 12pt 0 8pt 0; }}
.figure-group img {{ border: none; }}
p.colophon-spacer {{
  margin: 0; padding: 0; height: 42%; min-height: 160pt; text-indent: 0;
  color: #fff; font-size: 1pt; line-height: 1;
}}
p.colophon-line {{
  text-indent: 0; margin: 2.5pt 0; font-size: {b - 0.5}pt; line-height: 1.35;
}}
p.colophon-first {{
  border-top: 0.6pt solid #ccc; padding-top: 10pt; margin-top: 0;
}}
"""


PUBLICATION_CSS = publication_css_for_body_pt(BODY_PT)
