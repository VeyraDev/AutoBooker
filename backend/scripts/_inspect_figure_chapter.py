"""Inspect / repair 图测试 chapter content in DB."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

eng = create_engine(os.environ.get("DATABASE_URL", ""))

with eng.connect() as c:
    rows = c.execute(
        text(
            """
            SELECT b.id, b.title, ch.index, ch.title AS ch_title, ch.word_count,
                   octet_length(ch.content::text) AS content_len
            FROM chapters ch
            JOIN books b ON b.id = ch.book_id
            WHERE ch.title LIKE '%图测试%' OR b.title LIKE '%图测试%'
            ORDER BY ch.index
            """
        )
    ).fetchall()
    print("chapters:", len(rows))
    for r in rows:
        print(dict(r._mapping))

    if not rows:
        rows = c.execute(
            text(
                """
                SELECT b.id, b.title, ch.index, ch.title AS ch_title
                FROM chapters ch
                JOIN books b ON b.id = ch.book_id
                WHERE ch.content::text LIKE '%figureBlock%'
                ORDER BY ch.updated_at DESC NULLS LAST
                LIMIT 5
                """
            )
        ).fetchall()
        print("fallback figure chapters:", len(rows))
        for r in rows:
            print(dict(r._mapping))

    if rows:
        bid, idx = rows[0][0], rows[0][2]
        content = c.execute(
            text("SELECT content FROM chapters WHERE book_id = :bid AND index = :idx"),
            {"bid": bid, "idx": idx},
        ).scalar()
        if isinstance(content, dict):
            print("keys:", list(content.keys()))
            textv = content.get("text") or ""
            print("text_len:", len(textv))
            print("text_repr:", repr(textv[:200]))
            tj = content.get("tiptap_json")
            if isinstance(tj, dict):
                s = json.dumps(tj, ensure_ascii=False)
                print("tiptap_json_len:", len(s))
                print("has figureBlock:", "figureBlock" in s)
                print("content nodes:", len(tj.get("content") or []))
                print("tiptap_json:", s)
            ov = content.get("figure_table_overview")
            if isinstance(ov, list):
                print("overview_len:", len(ov))
                if ov:
                    print("overview_sample:", json.dumps(ov[:2], ensure_ascii=False)[:600])
            sections = content.get("sections")
            if isinstance(sections, list):
                print("sections:", len(sections))

        figs = c.execute(
            text(
                "SELECT id, figure_number, status, caption FROM figures WHERE book_id = :bid AND chapter_index = :idx"
            ),
            {"bid": bid, "idx": idx},
        ).fetchall()
        print("figures:", len(figs))
        for f in figs[:5]:
            print(dict(f._mapping))

        if "--repair" in sys.argv:
            print("Run repair via API: POST /books/{id}/chapters/{idx}/figures/rebuild-body")
