"""Title length benchmarks derived from local sample book documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class TitleBenchmark:
    sample_count: int
    source_dir: str | None
    median_len: int
    p10_len: int
    p90_len: int
    soft_min: int
    soft_max: int
    hard_max: int
    examples: tuple[str, ...]

    def evidence(self) -> dict[str, object]:
        return {
            "source": "data/document" if self.source_dir else "fallback",
            "sample_count": self.sample_count,
            "median_len": self.median_len,
            "p10_len": self.p10_len,
            "p90_len": self.p90_len,
            "soft_min": self.soft_min,
            "soft_max": self.soft_max,
            "hard_max": self.hard_max,
            "examples": list(self.examples),
        }

    def note(self) -> str:
        if self.sample_count <= 0:
            return f"当前采用兜底书类规则，建议区间约 {self.soft_min}-{self.soft_max} 个中文字符。"
        examples = "、".join(f"《{item}》" for item in self.examples[:3])
        return (
            f"参考 data/document 中 {self.sample_count} 个可识别标题，常见区间约 "
            f"{self.soft_min}-{self.soft_max} 个中文字符，中位数约 {self.median_len}"
            + (f"，样例：{examples}。" if examples else "。")
        )


_FALLBACK_LIMITS = {
    "popular_science": (4, 14, 36),
    "opinion_commentary": (4, 14, 36),
    "practical_guide": (6, 18, 42),
    "technical_deep_dive": (6, 22, 48),
    "academic_monograph": (10, 30, 56),
    "textbook": (4, 20, 42),
    "reference_tool": (4, 20, 42),
    "business_management": (6, 18, 42),
}
_SUPPORTED_SUFFIXES = {".txt", ".pdf"}
_DESCRIPTOR_RE = re.compile(
    r"(文字版|PDF电子书|电子书|雅书|下载|扫描版|高清版|完整版|第?\s*\d+\s*册)",
    re.IGNORECASE,
)
_VERSION_RE = re.compile(r"^(?:v?\d+(?:\.\d+)*|zh|cn|中文版)$", re.IGNORECASE)
_LONG_BRACKET_RE = re.compile(r"[（(][^）)]{1,120}[）)]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_TECH_KEYWORDS = (
    "AI",
    "人工智能",
    "大模型",
    "生成式",
    "深度学习",
    "机器学习",
    "Claude",
    "Code",
    "Agent",
    "OpenClaw",
    "工程",
    "开发",
    "算法",
    "模型",
)
_GUIDE_KEYWORDS = ("指南", "入门", "实战", "玩转", "构建", "Complete Guide", "Guide")
_ACADEMIC_KEYWORDS = ("理论", "方法", "研究", "文明史", "前史", "专著", "计算", "科学")


def title_benchmark_for_style(
    book_style: str,
    *,
    source_dir: str | Path | None = None,
) -> TitleBenchmark:
    source_key = str(Path(source_dir)) if source_dir is not None else ""
    return _title_benchmark_for_style_cached(book_style or "", source_key)


def extract_title_from_document_name(name: str) -> str | None:
    stem = Path(name).stem.strip()
    if not stem or stem.startswith("_"):
        return None
    angle = re.search(r"《([^》]{1,120})》", stem)
    if angle:
        return _clean_title(angle.group(1))
    stem = re.sub(r"^\d{6,}[-_\s]+", "", stem)
    stem = re.sub(r"【[^】]*】", "", stem)
    stem = _drop_descriptor_tail(stem)
    if "-" in stem or "_" in stem:
        stem = _title_from_chunks(stem)
    return _clean_title(stem)


def title_limits_from_benchmark(book_style: str, benchmark: TitleBenchmark) -> tuple[int, int, int]:
    fallback = _fallback_limits(book_style)
    if benchmark.sample_count <= 0:
        return fallback
    return benchmark.soft_min, benchmark.soft_max, benchmark.hard_max


@lru_cache(maxsize=64)
def _title_benchmark_for_style_cached(book_style: str, source_key: str) -> TitleBenchmark:
    source_dir = Path(source_key) if source_key else _find_data_document_dir()
    fallback_min, fallback_max, fallback_hard = _fallback_limits(book_style)
    titles = _load_titles(source_dir)
    selected = [title for title in titles if _title_matches_style(title, book_style)]
    if len(selected) < 8:
        selected = titles
    lengths = sorted(_cjk_len(title) for title in selected if _cjk_len(title) > 0)
    if not lengths:
        return TitleBenchmark(
            sample_count=0,
            source_dir=None,
            median_len=0,
            p10_len=fallback_min,
            p90_len=fallback_max,
            soft_min=fallback_min,
            soft_max=fallback_max,
            hard_max=fallback_hard,
            examples=(),
        )
    p10 = _percentile(lengths, 0.1)
    median = _percentile(lengths, 0.5)
    p90 = _percentile(lengths, 0.9)
    soft_min = max(4, min(fallback_min, max(3, p10 - 2)))
    soft_max = max(fallback_max, min(36, p90 + 4))
    hard_max = max(fallback_hard, min(64, p90 + 18))
    examples = tuple(selected[:5])
    return TitleBenchmark(
        sample_count=len(selected),
        source_dir=str(source_dir) if source_dir else None,
        median_len=median,
        p10_len=p10,
        p90_len=p90,
        soft_min=soft_min,
        soft_max=soft_max,
        hard_max=hard_max,
        examples=examples,
    )


def _find_data_document_dir() -> Path | None:
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in here.parents:
        candidates.append(parent / "data" / "document")
        candidates.append(parent.parent / "data" / "document")
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _load_titles(source_dir: Path | None) -> list[str]:
    if not source_dir or not source_dir.exists():
        return []
    titles: list[str] = []
    seen: set[str] = set()
    for path in sorted(source_dir.iterdir(), key=lambda p: p.name):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        title = extract_title_from_document_name(path.name)
        if not title or title in seen:
            continue
        seen.add(title)
        titles.append(title)
    return titles


def _title_from_chunks(stem: str) -> str:
    chunks = [part.strip() for part in re.split(r"[-_]+", stem) if part.strip()]
    kept: list[str] = []
    for chunk in chunks:
        if _DESCRIPTOR_RE.search(chunk) or _VERSION_RE.match(chunk):
            break
        if kept and _looks_like_author_chunk(chunk):
            break
        kept.append(chunk)
        if len(kept) >= 4:
            break
    return " ".join(kept) if kept else stem


def _clean_title(text: str | None) -> str | None:
    if not text:
        return None
    title = str(text).strip()
    title = re.sub(r"【[^】]*】", "", title)
    title = _LONG_BRACKET_RE.sub("", title)
    title = _drop_descriptor_tail(title)
    title = re.sub(r"\s+", " ", title)
    title = title.strip(" -_·:：,，。[]【】")
    if len(title) < 2:
        return None
    return title


def _drop_descriptor_tail(text: str) -> str:
    title = text
    for _ in range(4):
        title = re.sub(r"[-_\s]*" + _DESCRIPTOR_RE.pattern + r".*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def _looks_like_author_chunk(chunk: str) -> bool:
    cleaned = re.sub(r"\s+", "", chunk)
    if _VERSION_RE.match(cleaned) or _DESCRIPTOR_RE.search(cleaned):
        return True
    if re.fullmatch(r"[\u4e00-\u9fff]{1,4}", cleaned):
        return True
    return False


def _title_matches_style(title: str, book_style: str) -> bool:
    style = (book_style or "").lower()
    blob = title.lower()
    if style in {"technical_deep_dive", "textbook", "reference_tool"}:
        return any(keyword.lower() in blob for keyword in _TECH_KEYWORDS)
    if style in {"practical_guide", "business_management"}:
        return any(keyword.lower() in blob for keyword in (*_TECH_KEYWORDS, *_GUIDE_KEYWORDS))
    if style == "academic_monograph":
        return any(keyword.lower() in blob for keyword in (*_ACADEMIC_KEYWORDS, *_TECH_KEYWORDS))
    if style in {"popular_science", "opinion_commentary"}:
        return not any(keyword.lower() in blob for keyword in _GUIDE_KEYWORDS)
    return True


def _fallback_limits(book_style: str) -> tuple[int, int, int]:
    return _FALLBACK_LIMITS.get(book_style, (6, 20, 42))


def _percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    index = round((len(values) - 1) * ratio)
    return values[max(0, min(len(values) - 1, index))]


def _cjk_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def benchmark_title_lengths(titles: Iterable[str], book_style: str = "practical_guide") -> TitleBenchmark:
    fallback_min, fallback_max, fallback_hard = _fallback_limits(book_style)
    cleaned = [title for title in (_clean_title(t) for t in titles) if title]
    lengths = sorted(_cjk_len(title) for title in cleaned)
    if not lengths:
        return TitleBenchmark(0, None, 0, fallback_min, fallback_max, fallback_min, fallback_max, fallback_hard, ())
    p10 = _percentile(lengths, 0.1)
    median = _percentile(lengths, 0.5)
    p90 = _percentile(lengths, 0.9)
    soft_min = max(4, min(fallback_min, max(3, p10 - 2)))
    soft_max = max(fallback_max, min(36, p90 + 4))
    hard_max = max(fallback_hard, min(64, p90 + 18))
    return TitleBenchmark(len(cleaned), "memory", median, p10, p90, soft_min, soft_max, hard_max, tuple(cleaned[:5]))
