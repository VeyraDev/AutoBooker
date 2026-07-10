#!/usr/bin/env python3
"""Inventory local business file read/write call sites for refactor tracking."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = [
    ("storage_path", re.compile(r"\bstorage_path\b")),
    ("file_path", re.compile(r"\bfile_path\b")),
    ("file_url", re.compile(r"\bfile_url\b")),
    ("svg_url", re.compile(r"\bsvg_url\b")),
    ("write_bytes", re.compile(r"\.write_bytes\s*\(")),
    ("/static/figures", re.compile(r"/static/figures")),
    (".export-cache", re.compile(r"\.export-cache")),
    (".candidate-", re.compile(r"\.candidate-")),
    ("upload_path", re.compile(r"\bupload_path\b")),
    ("figures_path", re.compile(r"\bfigures_path\b")),
]

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build"}
SKIP_SUFFIXES = {".pyc", ".png", ".svg", ".pdf", ".docx", ".zip"}


def scan(root: Path) -> dict[str, list[tuple[str, int, str]]]:
    hits: dict[str, list[tuple[str, int, str]]] = {name: [] for name, _ in PATTERNS}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS:
                if pattern.search(line):
                    rel = path.relative_to(root).as_posix()
                    hits[name].append((rel, line_no, line.strip()[:120]))
    return hits


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    hits = scan(root)
    total = sum(len(v) for v in hits.values())
    print(f"Local file inventory under {root}")
    print(f"Total matches: {total}\n")
    for name, rows in hits.items():
        if not rows:
            continue
        print(f"## {name} ({len(rows)})")
        for rel, line_no, snippet in rows[:50]:
            print(f"  {rel}:{line_no}: {snippet}")
        if len(rows) > 50:
            print(f"  ... and {len(rows) - 50} more")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
