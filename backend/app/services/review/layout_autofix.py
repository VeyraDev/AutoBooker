"""Deterministic layout auto-fixes for review applications."""

from __future__ import annotations

import copy
import re
from typing import Any

from app.services.markdown_to_tiptap import markdown_body_to_tiptap_blocks
from app.services.tiptap_convert import _inline_to_markdown, tiptap_json_to_markdown

FIRST_LINE_INDENT_ATTR = "firstLineIndent"
FIRST_LINE_INDENT_PREFIX = "\u3000\u3000"

_CAPTION_RE = re.compile(r"^\s*(?:图|表)\s*\d+\s*[-–—.]\s*\d+")
_REFERENCE_RE = re.compile(r"^\s*\[\d+\].{6,}")
_URL_RE = re.compile(r"^\s*(?:https?://|doi:)", re.I)


def normalize_first_line_indent(
    markdown: str,
    tiptap_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Set first-line indent metadata on ordinary body paragraphs."""
    if isinstance(tiptap_json, dict) and tiptap_json.get("type") == "doc":
        doc = copy.deepcopy(tiptap_json)
    else:
        doc = {"type": "doc", "content": markdown_body_to_tiptap_blocks(markdown or "")}

    changed = 0
    for node in doc.get("content") or []:
        if not isinstance(node, dict) or node.get("type") != "paragraph":
            continue
        text = _paragraph_text(node)
        if not _is_body_paragraph(text, node.get("attrs")):
            continue
        attrs = dict(node.get("attrs") or {})
        before = dict(attrs)
        attrs[FIRST_LINE_INDENT_ATTR] = True
        node["attrs"] = attrs
        if _strip_manual_indent_from_first_text(node):
            changed += 1
        elif before != attrs:
            changed += 1

    text = tiptap_json_to_markdown(doc).strip("\n\r ")
    return {"tiptap_json": doc, "text": text, "changed_count": changed}


def _paragraph_text(node: dict[str, Any]) -> str:
    return _inline_to_markdown(node.get("content")).strip()


def _is_body_paragraph(text: str, attrs: Any) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return False
    attrs = attrs if isinstance(attrs, dict) else {}
    if attrs.get("textAlign") == "center":
        return False
    if _CAPTION_RE.match(t) or _REFERENCE_RE.match(t) or _URL_RE.match(t):
        return False
    if t.startswith(("#", "|", "```", "$$")):
        return False
    if re.match(r"^\s*[-*+]\s+", t) or re.match(r"^\s*\d+[.)、]\s+", t):
        return False
    return True


def _strip_manual_indent_from_first_text(node: dict[str, Any]) -> bool:
    content = node.get("content")
    if not isinstance(content, list):
        return False
    for child in content:
        if not isinstance(child, dict) or child.get("type") != "text":
            continue
        raw = str(child.get("text") or "")
        stripped = raw.lstrip(" \t\u3000")
        if stripped != raw:
            child["text"] = stripped
            return True
        return False
    return False
