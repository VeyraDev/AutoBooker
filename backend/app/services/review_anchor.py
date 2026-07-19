"""正文快照、段落锚点与审校 issue 定位。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

_PID_RE = re.compile(r"^\s*<!--\s*pid:([A-Za-z0-9_.:-]+)\s*-->\s*$")


@dataclass(frozen=True)
class ParagraphAnchor:
    paragraph_id: str
    paragraph_index: int
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class LocatedAnchor:
    paragraph_id: str | None
    paragraph_index: int | None
    char_start: int | None
    char_end: int | None
    quote: str
    strategy: str
    confidence: float
    anchor_hash: str | None


def canonical_markdown(md: str) -> str:
    text = (md or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines).strip()
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text


def snapshot_hash(md: str) -> str:
    return hashlib.sha256(canonical_markdown(md).encode("utf-8")).hexdigest()


def short_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def parse_paragraphs(md: str) -> list[ParagraphAnchor]:
    text = canonical_markdown(md)
    if not text:
        return []
    blocks: list[ParagraphAnchor] = []
    pos = 0
    pending_pid: str | None = None
    raw_blocks = re.split(r"\n{2,}", text)
    for raw in raw_blocks:
        block = raw.strip()
        if not block:
            pos += len(raw) + 2
            continue
        m = _PID_RE.match(block)
        if m:
            pending_pid = m.group(1)
            pos = text.find(raw, pos) + len(raw)
            continue
        block_pid = pending_pid
        first_line = block.split("\n", 1)[0]
        first_match = _PID_RE.match(first_line)
        if first_match:
            block_pid = first_match.group(1)
        start = text.find(raw, pos)
        if start < 0:
            start = pos
        clean = _strip_pid_lines(raw).strip()
        if not clean:
            pos = start + len(raw)
            continue
        local_start = raw.find(clean)
        char_start = start + max(local_start, 0)
        char_end = char_start + len(clean)
        index = len(blocks)
        pid = block_pid or f"p_{index + 1:04d}_{short_hash(clean)[:8]}"
        blocks.append(
            ParagraphAnchor(
                paragraph_id=pid,
                paragraph_index=index,
                text=clean,
                char_start=char_start,
                char_end=char_end,
            )
        )
        pending_pid = None
        pos = start + len(raw)
    return blocks


def locate_issue_anchor(
    md: str,
    *,
    quote: str = "",
    paragraph_id: str | None = None,
    paragraph_index: int | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
) -> LocatedAnchor:
    text = canonical_markdown(md)
    quote = (quote or "").strip()
    paragraphs = parse_paragraphs(text)

    if quote and char_start is not None and char_end is not None:
        if 0 <= char_start <= char_end <= len(text):
            slice_text = text[char_start:char_end]
            if _norm(slice_text) == _norm(quote):
                para = _paragraph_for_range(paragraphs, char_start, char_end)
                return _located(para, char_start, char_end, quote, "offset", 1.0)

    if paragraph_id:
        para = next((p for p in paragraphs if p.paragraph_id == paragraph_id), None)
        if para:
            if quote:
                idx = para.text.find(quote)
                if idx >= 0:
                    start = para.char_start + idx
                    return _located(para, start, start + len(quote), quote, "paragraph_id_quote", 0.95)
                fuzzy = _best_window(para.text, quote)
                if fuzzy and fuzzy[2] >= 0.72:
                    start = para.char_start + fuzzy[0]
                    return _located(para, start, start + fuzzy[1], para.text[fuzzy[0] : fuzzy[0] + fuzzy[1]], "paragraph_id_fuzzy", fuzzy[2])
            return _located(para, para.char_start, para.char_start, quote, "paragraph_id", 0.65)

    if paragraph_index is not None and 0 <= paragraph_index < len(paragraphs):
        window = paragraphs[max(0, paragraph_index - 2) : min(len(paragraphs), paragraph_index + 3)]
        found = _find_in_paragraphs(window, quote)
        if found:
            return found

    if quote:
        idx = text.find(quote)
        if idx >= 0:
            para = _paragraph_for_range(paragraphs, idx, idx + len(quote))
            return _located(para, idx, idx + len(quote), quote, "full_quote", 0.88)
        found = _find_in_paragraphs(paragraphs, quote, fuzzy=True)
        if found:
            return found

    if paragraphs:
        para = paragraphs[0]
        return _located(para, para.char_start, para.char_start, quote, "fallback_first_paragraph", 0.25)

    return LocatedAnchor(None, None, None, None, quote, "not_found", 0.0, None)


def enrich_issue_anchor(md: str, issue: dict) -> dict:
    located = locate_issue_anchor(
        md,
        quote=str(issue.get("quote") or ""),
        paragraph_id=issue.get("paragraph_id"),
        paragraph_index=issue.get("paragraph_index"),
        char_start=issue.get("char_start"),
        char_end=issue.get("char_end"),
    )
    out = dict(issue)
    out.update(
        {
            "paragraph_id": located.paragraph_id,
            "paragraph_index": located.paragraph_index,
            "char_start": located.char_start,
            "char_end": located.char_end,
            "anchor_hash": located.anchor_hash,
            "locator_strategy": located.strategy,
            "locator_confidence": located.confidence,
        }
    )
    if located.quote and not out.get("quote"):
        out["quote"] = located.quote
    return out


def apply_text_edit(md: str, *, start: int, end: int, replacement: str, action: str) -> str:
    text = canonical_markdown(md)
    start = max(0, min(len(text), int(start)))
    end = max(start, min(len(text), int(end)))
    if action == "delete":
        replacement = ""
    if action == "insert":
        end = start
    return text[:start] + (replacement or "") + text[end:]


def build_text_diff(before: str, after: str, *, start: int | None = None, end: int | None = None) -> dict:
    if start is None or end is None:
        start = _common_prefix_len(before, after)
        suffix = _common_suffix_len(before, after, start)
        end = len(before) - suffix
        after_end = len(after) - suffix
    else:
        after_end = start + max(0, len(after) - (len(before) - (end - start)))
    return {
        "before": before[start:end],
        "after": after[start:after_end],
        "char_start": start,
        "char_end": end,
    }


def _strip_pid_lines(block: str) -> str:
    return "\n".join(line for line in block.split("\n") if not _PID_RE.match(line))


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or ""))


def _paragraph_for_range(paragraphs: list[ParagraphAnchor], start: int, end: int) -> ParagraphAnchor | None:
    for p in paragraphs:
        if p.char_start <= start <= p.char_end or p.char_start <= end <= p.char_end:
            return p
    return None


def _located(
    para: ParagraphAnchor | None,
    start: int | None,
    end: int | None,
    quote: str,
    strategy: str,
    confidence: float,
) -> LocatedAnchor:
    anchor_text = f"{para.paragraph_id if para else ''}:{start}:{end}:{quote[:160]}"
    return LocatedAnchor(
        paragraph_id=para.paragraph_id if para else None,
        paragraph_index=para.paragraph_index if para else None,
        char_start=start,
        char_end=end,
        quote=quote,
        strategy=strategy,
        confidence=round(max(0.0, min(1.0, confidence)), 3),
        anchor_hash=short_hash(anchor_text) if start is not None else None,
    )


def _find_in_paragraphs(paragraphs: list[ParagraphAnchor], quote: str, *, fuzzy: bool = False) -> LocatedAnchor | None:
    if not quote:
        return None
    for para in paragraphs:
        idx = para.text.find(quote)
        if idx >= 0:
            start = para.char_start + idx
            return _located(para, start, start + len(quote), quote, "paragraph_window_quote", 0.84)
    if not fuzzy:
        return None
    best: tuple[ParagraphAnchor, int, int, float] | None = None
    for para in paragraphs:
        got = _best_window(para.text, quote)
        if got and (best is None or got[2] > best[3]):
            best = (para, got[0], got[1], got[2])
    if best and best[3] >= 0.58:
        para, offset, length, score = best
        start = para.char_start + offset
        return _located(para, start, start + length, para.text[offset : offset + length], "full_fuzzy", score)
    return None


def _best_window(text: str, quote: str) -> tuple[int, int, float] | None:
    q = quote.strip()
    if not text or not q:
        return None
    if len(q) > len(text):
        score = SequenceMatcher(None, _norm(text), _norm(q)).ratio()
        return (0, len(text), score)
    win = max(8, min(len(text), len(q)))
    step = max(1, win // 5)
    best: tuple[int, int, float] | None = None
    for start in range(0, max(1, len(text) - win + 1), step):
        cand = text[start : start + win]
        score = SequenceMatcher(None, _norm(cand), _norm(q)).ratio()
        if best is None or score > best[2]:
            best = (start, len(cand), score)
    return best


def _common_prefix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return i


def _common_suffix_len(a: str, b: str, prefix_len: int) -> int:
    limit = min(len(a), len(b)) - prefix_len
    i = 0
    while i < limit and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1
    return i
