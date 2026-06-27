"""LaTeX 源码规范化（与前端 latexNormalize 对齐）。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class NormalizedLatex:
    latex: str
    kind: str  # inline | block
    numbered: bool = False
    equation_number: str = ""
    label: str = ""
    stripped: list[str] | None = None


def _strip_tag_label(src: str) -> tuple[str, bool, str, str, list[str]]:
    latex = src
    numbered = False
    equation_number = ""
    label = ""
    stripped: list[str] = []

    for m in re.finditer(r"\\label\s*\{([^{}]+)\}", latex):
        label = m.group(1).strip()
        stripped.append("\\label{…}")
    latex = re.sub(r"\\label\s*\{[^{}]+\}", "", latex).strip()

    tag = re.search(r"\\tag\s*\{([^{}]+)\}\s*$", latex)
    if tag:
        numbered = True
        equation_number = tag.group(1).strip()
        latex = re.sub(r"\\tag\s*\{[^{}]+\}\s*$", "", latex).strip()
        stripped.append("\\tag{…}")

    return latex, numbered, equation_number, label, stripped


def normalize_latex_input(
    raw: str,
    *,
    prefer_kind: str = "inline",
) -> NormalizedLatex:
    s = (raw or "").replace("\r\n", "\n").strip()
    stripped: list[str] = []
    kind = prefer_kind if prefer_kind in ("inline", "block") else "inline"

    m = re.match(r"^\s*\$\$([\s\S]*?)\$\$\s*$", s)
    if m:
        s = m.group(1)
        kind = "block"
        stripped.append("$$…$$")
    else:
        m = re.match(r"^\s*\\\[([\s\S]*?)\\\]\s*$", s)
        if m:
            s = m.group(1)
            kind = "block"
            stripped.append("\\[…\\]")
        else:
            m = re.match(r"^\s*\\\(([\s\S]*?)\\\)\s*$", s)
            if m:
                s = m.group(1)
                kind = "inline"
                stripped.append("\\(…\\)")
            else:
                m = re.match(r"^\s*(?<!\$)\$(?!\$)([\s\S]*?)(?<!\$)\$(?!\$)\s*$", s)
                if m:
                    s = m.group(1)
                    kind = "inline"
                    stripped.append("$…$")

    latex, numbered, eq_num, label, meta_strip = _strip_tag_label(s.strip())
    if kind == "inline":
        latex = re.sub(r"\s*\n+\s*", "", latex)
    stripped.extend(meta_strip)
    return NormalizedLatex(
        latex=latex,
        kind=kind,
        numbered=numbered,
        equation_number=eq_num,
        label=label,
        stripped=stripped,
    )
