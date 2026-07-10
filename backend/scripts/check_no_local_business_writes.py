#!/usr/bin/env python3
"""CI guard: fail if new business local file writes are introduced."""

from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = [
    re.compile(r"settings\.upload_path.*write_bytes"),
    re.compile(r"settings\.figures_path.*write_bytes"),
    re.compile(r"\.export-cache\.png['\"]?\s*\)"),
]

ALLOWLIST = {
    "scripts/inventory_local_file_writes.py",
    "scripts/check_no_local_business_writes.py",
    "tests/",
}


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "app"
    violations: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root.parent).as_posix()
        if any(a in rel for a in ALLOWLIST):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in FORBIDDEN:
            if pat.search(text):
                violations.append(f"{rel}: {pat.pattern}")
    if violations:
        print("Forbidden local business write patterns found:")
        for v in violations:
            print(" ", v)
        return 1
    print("OK: no forbidden local business write patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
