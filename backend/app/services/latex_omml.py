"""LaTeX → OMML（DOCX 导出时转换，不写入章节正文）。"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_GROUPCHR_PR_CLOSE = re.compile(
    r"(<m:groupChrPr\b[^>]*>.*?</m:groupChr>)(\s*<m:e>)",
    re.DOTALL,
)


def _repair_omml_xml(omml: str) -> str:
    """修复 mathml2omml 将 groupChrPr 误闭合为 groupChr 的已知问题。"""
    fixed = omml
    while True:
        next_fixed = _GROUPCHR_PR_CLOSE.sub(
            lambda m: m.group(1).replace("</m:groupChr>", "</m:groupChrPr>", 1) + m.group(2),
            fixed,
        )
        if next_fixed == fixed:
            break
        fixed = next_fixed
    return fixed


def _validate_omml_xml(omml: str) -> bool:
    from docx.oxml.parser import parse_xml

    try:
        parse_xml(omml)
        return True
    except Exception:
        return False


from app.services.latex_normalize import normalize_latex_input


def latex_to_omml(latex: str) -> dict[str, Any]:
    """将 LaTeX 转为 OMML XML 字符串；失败时返回 status=failed。"""
    norm = normalize_latex_input(latex or "")
    src = norm.latex.strip()
    if not src:
        return {"status": "failed", "latex": src, "error": "empty_latex", "omml": None}
    try:
        from latex2mathml.converter import convert as latex2mathml
        from mathml2omml import convert as mathml2omml

        mathml = latex2mathml(src)
        omml = mathml2omml(mathml)
        if not omml or "<m:oMath" not in omml:
            raise ValueError("empty_omml")
        if 'xmlns:m="' not in omml:
            omml = omml.replace("<m:oMath>", f'<m:oMath xmlns:m="{MATH_NS}">', 1)
        omml = _repair_omml_xml(omml)
        if not _validate_omml_xml(omml):
            raise ValueError("invalid_omml_xml")
        return {"status": "ok", "latex": src, "error": None, "omml": omml}
    except Exception as exc:
        logger.warning("latex_to_omml failed latex=%r err=%s", src[:120], exc)
        return {"status": "failed", "latex": src, "error": str(exc), "omml": None}


def omml_block_xml(omml: str) -> str:
    """独立公式：oMathPara 居中。"""
    inner = omml.strip()
    if inner.startswith("<m:oMathPara"):
        return inner
    if not inner.startswith("<m:oMath"):
        inner = f'<m:oMath xmlns:m="{MATH_NS}">{inner}</m:oMath>'
    return (
        f'<m:oMathPara xmlns:m="{MATH_NS}">'
        f"<m:oMathParaPr><m:jc m:val=\"center\"/></m:oMathParaPr>{inner}</m:oMathPara>"
    )


def omml_numbered_table_xml(omml: str, number: str) -> str:
    """带编号独立公式：三列无边框表格（左空 | 公式 | 编号）。"""
    num = re.sub(r"[^\d().\-]", "", str(number or "").strip()) or "?"
    block = omml_block_xml(omml)
    return (
        f'<w:tbl xmlns:w="{W_NS}" xmlns:m="{MATH_NS}">'
        "<w:tblPr><w:tblW w:w=\"5000\" w:type=\"pct\"/><w:tblBorders>"
        "<w:top w:val=\"nil\"/><w:left w:val=\"nil\"/><w:bottom w:val=\"nil\"/>"
        "<w:right w:val=\"nil\"/><w:insideH w:val=\"nil\"/><w:insideV w:val=\"nil\"/>"
        "</w:tblBorders></w:tblPr>"
        "<w:tr>"
        f'<w:tc><w:tcPr><w:tcW w:w=\"800\" w:type=\"dxa\"/></w:tcPr><w:p/></w:tc>'
        f"<w:tc><w:tcPr><w:tcW w:w=\"7200\" w:type=\"dxa\"/></w:tcPr><w:p>{block}</w:p></w:tc>"
        f'<w:tc><w:tcPr><w:tcW w:w=\"800\" w:type=\"dxa\"/></w:tcPr>'
        f'<w:p><w:pPr><w:jc w:val=\"right\"/></w:pPr>'
        f"<w:r><w:t>({num})</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
    )
