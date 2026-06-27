"""
从 DOCX 中提取含 Office Math (OMML) 的文本，并将 OMML 转为近似 LaTeX。
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _local(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _children(el: ET.Element) -> list[ET.Element]:
    return list(el)


def _text_nodes(el: ET.Element) -> str:
    parts: list[str] = []
    for node in el.iter():
        if _local(node.tag) == "t" and node.text:
            parts.append(node.text)
    return "".join(parts)


def _omml_to_latex(el: ET.Element) -> str:
    """将 OMML 子树转为 LaTeX（覆盖常见结构，失败时回退 m:t 拼接）。"""
    tag = _local(el.tag)

    if tag == "t":
        return el.text or ""

    if tag == "r":
        return _text_nodes(el)

    if tag == "f":
        num = den = ""
        for child in _children(el):
            lt = _local(child.tag)
            if lt == "num":
                num = "".join(_omml_to_latex(c) for c in _children(child))
            elif lt == "den":
                den = "".join(_omml_to_latex(c) for c in _children(child))
        if num or den:
            return f"\\frac{{{num}}}{{{den}}}"
        return ""

    if tag == "rad":
        deg = base = ""
        for child in _children(el):
            lt = _local(child.tag)
            if lt == "deg":
                deg = "".join(_omml_to_latex(c) for c in _children(child))
            elif lt == "e":
                base = "".join(_omml_to_latex(c) for c in _children(child))
        if deg.strip():
            return f"\\sqrt[{deg}]{{{base}}}"
        return f"\\sqrt{{{base}}}"

    if tag in ("sSup", "sSub", "sSubSup"):
        base = sup = sub = ""
        for child in _children(el):
            lt = _local(child.tag)
            if lt == "e":
                base = "".join(_omml_to_latex(c) for c in _children(child))
            elif lt == "sup":
                sup = "".join(_omml_to_latex(c) for c in _children(child))
            elif lt == "sub":
                sub = "".join(_omml_to_latex(c) for c in _children(child))
        out = base
        if sub:
            out += f"_{{{sub}}}"
        if sup:
            out += f"^{{{sup}}}"
        return out

    if tag == "d":
        beg = end = ""
        inner_parts: list[str] = []
        for child in _children(el):
            lt = _local(child.tag)
            if lt == "dPr":
                for p in _children(child):
                    pt = _local(p.tag)
                    if pt == "begChr" and p.get(f"{{{MATH_NS}}}val"):
                        beg = p.get(f"{{{MATH_NS}}}val") or "("
                    if pt == "endChr" and p.get(f"{{{MATH_NS}}}val"):
                        end = p.get(f"{{{MATH_NS}}}val") or ")"
            elif lt == "e":
                inner_parts.append("".join(_omml_to_latex(c) for c in _children(child)))
        inner = "".join(inner_parts)
        if beg == "(" and end == ")":
            return f"\\left({inner}\\right)"
        if beg == "[" and end == "]":
            return f"\\left[{inner}\\right]"
        if beg == "{" and end == "}":
            return f"\\left\\{{{inner}\\right\\}}"
        return f"{beg}{inner}{end}"

    if tag == "nary":
        op = sub = sup = body = ""
        for child in _children(el):
            lt = _local(child.tag)
            if lt == "naryPr":
                for p in _children(child):
                    if _local(p.tag) == "chr":
                        op = p.get(f"{{{MATH_NS}}}val") or ""
            elif lt == "sub":
                sub = "".join(_omml_to_latex(c) for c in _children(child))
            elif lt == "sup":
                sup = "".join(_omml_to_latex(c) for c in _children(child))
            elif lt == "e":
                body = "".join(_omml_to_latex(c) for c in _children(child))
        sym = {"∑": "\\sum", "∫": "\\int", "∏": "\\prod"}.get(op, op or "\\sum")
        out = sym
        if sub:
            out += f"_{{{sub}}}"
        if sup:
            out += f"^{{{sup}}}"
        out += f"{{{body}}}"
        return out

    if tag in ("oMath", "oMathPara"):
        return "".join(_omml_to_latex(c) for c in _children(el))

    # 默认：递归子节点
    parts = [_omml_to_latex(c) for c in _children(el)]
    joined = "".join(parts)
    if joined:
        return joined
    fallback = _text_nodes(el).strip()
    return fallback


def _paragraph_text_with_math(p_el: ET.Element) -> str:
    chunks: list[str] = []
    for child in list(p_el):
        tag = _local(child.tag)
        ns = child.tag.split("}")[0].strip("{") if "}" in child.tag else ""
        if tag == "r" and ns == W_NS:
            for t in child.iter():
                if _local(t.tag) == "t" and t.text:
                    chunks.append(t.text)
        elif tag in ("oMath", "oMathPara") and ns == MATH_NS:
            if tag == "oMathPara":
                for sub in child:
                    if _local(sub.tag) == "oMath":
                        latex = _omml_to_latex(sub).strip()
                        chunks.append(f"$${latex or '[公式]'}$$")
            else:
                latex = _omml_to_latex(child).strip()
                chunks.append(f"${latex or '[公式]'}$")
    return "".join(chunks).strip()


def extract_docx_text_with_math(file_path: str) -> str:
    """读取 DOCX 正文，将 OMML 公式替换为 LaTeX 占位。"""
    path = Path(file_path)
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for p in root.iter():
        if _local(p.tag) == "p" and p.tag.endswith("}p"):
            text = _paragraph_text_with_math(p)
            if text:
                paragraphs.append(text)
    return "\n".join(paragraphs)
