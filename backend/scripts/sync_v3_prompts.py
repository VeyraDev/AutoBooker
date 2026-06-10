"""Sync docs/图像生成prompt汇总/*.md → app/services/figures/prompts/*.txt"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "docs" / "图像生成prompt汇总"
DST = Path(__file__).resolve().parents[1] / "app" / "services" / "figures" / "prompts"

PLACEHOLDERS = {
    "{{USER_INPUT}}": "{text}",
    "{{CONTEXT}}": "{context}",
    "{{INTENT_RESULT}}": "{intent_result}",
    "{{BROKEN_BRIEF}}": "{broken_brief}",
    "{{ERRORS}}": "{errors}",
    "{{ILLUSTRATION_BRIEF}}": "{illustration_brief}",
}


def main() -> None:
    for md in sorted(SRC.glob("*.md")):
        content = md.read_text(encoding="utf-8")
        for old, new in PLACEHOLDERS.items():
            content = content.replace(old, new)
        out = DST / f"{md.stem}.txt"
        out.write_text(content, encoding="utf-8")
        print(f"synced {md.name} -> {out.name}")


if __name__ == "__main__":
    main()
