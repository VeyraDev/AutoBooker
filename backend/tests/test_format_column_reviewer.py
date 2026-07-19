"""Tests for format column reviewer."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.review.format_column_reviewer import run_format_column_review


def test_install_chapter_missing_troubleshoot_column():
    ch = SimpleNamespace(
        id=uuid4(),
        index=3,
        title="安装与配置",
        summary="环境安装步骤",
        content={"text": "本章介绍安装流程与配置步骤。"},
    )
    snap = {
        "format_strategy": {
            "status": "confirmed",
            "chapter_suggestions": {
                "3": [{"column_name": "故障排查", "purpose": "常见问题"}],
            },
        }
    }
    findings = run_format_column_review([ch], snap)
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert "故障排查" in findings[0]["title"]
