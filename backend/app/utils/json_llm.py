"""Parse JSON from LLM output (strip markdown fences, tolerate common LLM mistakes)."""

from __future__ import annotations

import json
import re


def _strip_markdown_fence(s: str) -> str:
    s = s.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _extract_json_object(s: str) -> str:
    start = s.find("{")
    if start < 0:
        return s
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    end = s.rfind("}")
    if end > start:
        return s[start : end + 1]
    return s[start:]


def _remove_trailing_commas(s: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", s)


def _normalize_smart_quotes(s: str) -> str:
    return (
        s.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _escape_raw_newlines_in_strings(s: str) -> str:
    """LLM 常在 JSON 字符串值里直接换行，导致 json.loads 失败。"""
    out: list[str] = []
    in_string = False
    escape = False
    for i, ch in enumerate(s):
        if in_string:
            if escape:
                out.append(ch)
                escape = False
            elif ch == "\\":
                out.append(ch)
                escape = True
            elif ch == '"':
                out.append(ch)
                in_string = False
            elif ch == "\r":
                if i + 1 < len(s) and s[i + 1] == "\n":
                    continue
                out.append("\\n")
            elif ch == "\n":
                out.append("\\n")
            else:
                out.append(ch)
            continue
        out.append(ch)
        if ch == '"':
            in_string = True
    return "".join(out)


def _loads_with_repairs(s: str) -> dict:
    candidates = [
        s,
        _remove_trailing_commas(s),
        _normalize_smart_quotes(s),
        _escape_raw_newlines_in_strings(s),
        _escape_raw_newlines_in_strings(_remove_trailing_commas(_normalize_smart_quotes(s))),
    ]
    seen: set[str] = set()
    last_err: json.JSONDecodeError | None = None
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_err = exc
            continue
        if isinstance(data, dict):
            return data
        raise ValueError(f"expected JSON object, got {type(data).__name__}")
    if last_err is not None:
        raise last_err
    raise json.JSONDecodeError("empty JSON input", s, 0)


def parse_llm_json(raw: str) -> dict:
    s = _extract_json_object(_strip_markdown_fence(raw))
    return _loads_with_repairs(s)
