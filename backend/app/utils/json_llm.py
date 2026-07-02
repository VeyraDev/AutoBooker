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


def _remove_control_chars_outside_strings(s: str) -> str:
    """Strip ASCII control chars except tab/newline; unescaped newlines in strings handled separately."""
    out: list[str] = []
    in_string = False
    escape = False
    for ch in s:
        if in_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            continue
        if ord(ch) < 32 and ch not in "\t\n\r":
            continue
        out.append(ch)
    return "".join(out)


def _normalize_smart_quotes(s: str) -> str:
    """Curly double quotes → corner brackets (avoid breaking JSON string boundaries)."""
    return (
        s.replace("\u201c", "「")
        .replace("\u201d", "」")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _escape_inner_quotes_in_json_strings(s: str) -> str:
    """Escape bare \" inside JSON string values (common LLM mistake)."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch != '"':
            out.append(ch)
            i += 1
            continue
        out.append('"')
        i += 1
        while i < n:
            ch = s[i]
            if ch == "\\":
                out.append(ch)
                i += 1
                if i < n:
                    out.append(s[i])
                    i += 1
                continue
            if ch == '"':
                j = i + 1
                while j < n and s[j] in " \t\r\n":
                    j += 1
                if j >= n or s[j] in ",}]:":
                    out.append('"')
                    i += 1
                    break
                out.append('\\"')
                i += 1
                continue
            out.append(ch)
            i += 1
    return "".join(out)


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


def _close_truncated_json(s: str) -> str:
    """补全被截断 JSON 的引号与括号（常见于大纲输出触达 max_tokens）。"""
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in s:
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
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()

    out = s.rstrip()
    if in_string:
        out += '"'
    out = re.sub(r',\s*"[^"]*"\s*:\s*$', "", out)
    out = re.sub(r'"[^"]*"\s*:\s*$', "", out)
    out = re.sub(r",\s*$", "", out.rstrip())
    if re.search(r":\s*$", out):
        out += "null"
    out += "".join(reversed(stack))
    return _remove_trailing_commas(out)


def _salvage_json_object(s: str) -> dict | None:
    """从截断/损坏 JSON 中尽量恢复完整对象（回退到最后可闭合的 `}`）。"""
    start = s.find("{")
    if start < 0:
        return None

    fragments: list[str] = []
    seen: set[str] = set()

    def _push(fragment: str) -> None:
        closed = _close_truncated_json(fragment.rstrip().rstrip(","))
        if closed not in seen:
            seen.add(closed)
            fragments.append(closed)

    _push(s)
    brace_positions = [i for i, ch in enumerate(s) if ch == "}"]
    for pos in reversed(brace_positions[-80:]):
        _push(s[: pos + 1])

    for candidate in fragments:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _loads_with_repairs(s: str) -> dict:
    base = _remove_control_chars_outside_strings(_normalize_smart_quotes(s))
    inner_fixed = _escape_inner_quotes_in_json_strings(base)
    newline_fixed = _escape_raw_newlines_in_strings(inner_fixed)
    candidates = [
        s,
        base,
        inner_fixed,
        newline_fixed,
        _remove_trailing_commas(s),
        _remove_trailing_commas(base),
        _remove_trailing_commas(inner_fixed),
        _remove_trailing_commas(newline_fixed),
        _close_truncated_json(s),
        _close_truncated_json(newline_fixed),
        _escape_raw_newlines_in_strings(s),
        _escape_raw_newlines_in_strings(base),
        _escape_raw_newlines_in_strings(_remove_trailing_commas(base)),
        _escape_inner_quotes_in_json_strings(_escape_raw_newlines_in_strings(base)),
        _remove_trailing_commas(_escape_inner_quotes_in_json_strings(_escape_raw_newlines_in_strings(base))),
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

    salvaged = _salvage_json_object(newline_fixed)
    if salvaged is not None:
        return salvaged

    if last_err is not None:
        raise last_err
    raise json.JSONDecodeError("empty JSON input", s, 0)


def parse_llm_json(raw: str) -> dict:
    s = _extract_json_object(_strip_markdown_fence(raw))
    return _loads_with_repairs(s)
