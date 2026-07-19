"""Regression tests for the retired book-column feature."""

from pathlib import Path

from app.models.generation_context_snapshot import GenerationContextSnapshot
from app.models.intake import ProjectIntake
from app.prompts.chapter_voice import _CHAPTER_VOICE
from app.prompts.chapter_writer import WRITER_SYSTEM_PROMPT
from app.prompts.narrative_prompts import (
    NARRATIVE_SYSTEM_A,
    NARRATIVE_SYSTEM_B,
    NARRATIVE_SYSTEM_C,
)
from app.prompts.outline import OUTLINE_JSON_INSTRUCTION


COLUMN_WORD = "\u680f\u76ee"


def test_generation_prompts_do_not_define_or_discuss_columns():
    prompts = [
        OUTLINE_JSON_INSTRUCTION,
        NARRATIVE_SYSTEM_A,
        NARRATIVE_SYSTEM_B,
        NARRATIVE_SYSTEM_C,
        WRITER_SYSTEM_PROMPT,
        *_CHAPTER_VOICE.values(),
    ]

    assert all(COLUMN_WORD not in prompt for prompt in prompts)
    assert "column_labels" not in OUTLINE_JSON_INSTRUCTION
    assert "chapter_format_strategy_block" not in WRITER_SYSTEM_PROMPT


def test_column_feature_modules_and_database_fields_are_removed():
    app_root = Path(__file__).parents[1] / "app"
    retired_paths = [
        app_root / "models" / "book_format_strategy.py",
        app_root / "routers" / "format_strategy.py",
        app_root / "schemas" / "format_strategy.py",
        app_root / "services" / "writing" / "format_strategy_service.py",
        app_root / "prompts" / "format_strategy" / "generate.py",
    ]

    assert all(not path.exists() for path in retired_paths)
    assert not hasattr(ProjectIntake, "confirmed_format_strategy_id")
    assert not hasattr(GenerationContextSnapshot, "format_strategy_id")
