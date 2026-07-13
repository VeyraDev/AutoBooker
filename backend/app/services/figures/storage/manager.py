"""StorageManager — 配图分层目录与元数据。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from app.config import settings
from app.services.storage_policy import local_business_storage_allowed


class FigureStorageManager:
    def figure_dir(self, book_id: UUID, chapter_id: int | str, figure_id: UUID) -> Path:
        base = settings.figures_path / str(book_id) / str(chapter_id) / str(figure_id)
        if local_business_storage_allowed():
            base.mkdir(parents=True, exist_ok=True)
        return base

    def legacy_dir(self, book_id: UUID) -> Path:
        base = settings.figures_path / str(book_id)
        if local_business_storage_allowed():
            base.mkdir(parents=True, exist_ok=True)
        return base

    def png_path(self, book_id: UUID, chapter_id: int | str, figure_id: UUID) -> Path:
        return self.figure_dir(book_id, chapter_id, figure_id) / "figure.png"

    def svg_path(self, book_id: UUID, chapter_id: int | str, figure_id: UUID) -> Path:
        return self.figure_dir(book_id, chapter_id, figure_id) / "figure.svg"

    def dsl_path(self, book_id: UUID, chapter_id: int | str, figure_id: UUID) -> Path:
        return self.figure_dir(book_id, chapter_id, figure_id) / "figure.dsl.json"

    def meta_path(self, book_id: UUID, chapter_id: int | str, figure_id: UUID) -> Path:
        return self.figure_dir(book_id, chapter_id, figure_id) / "figure.meta.json"

    def resolve_output_paths(
        self,
        book_id: UUID,
        chapter_id: int | str,
        figure_id: UUID,
        *,
        prefer_legacy: bool = False,
    ) -> tuple[Path, Path]:
        if prefer_legacy:
            legacy = self.legacy_dir(book_id) / f"{figure_id.hex}.png"
            return legacy, legacy.with_suffix(".svg")
        return self.png_path(book_id, chapter_id, figure_id), self.svg_path(book_id, chapter_id, figure_id)

    def public_url(self, book_id: UUID, chapter_id: int | str, figure_id: UUID, *, ext: str = "png") -> str:
        return f"/static/figures/{book_id}/{chapter_id}/{figure_id}/figure.{ext}"

    def legacy_public_url(self, book_id: UUID, filename: str) -> str:
        return f"/static/figures/{book_id}/{filename}"

    def save_assets(
        self,
        *,
        book_id: UUID,
        chapter_id: int | str,
        figure_id: UUID,
        dsl: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Path:
        if not local_business_storage_allowed():
            raise RuntimeError("Local figure asset writes are disabled; use BinaryAssetService")
        ddir = self.figure_dir(book_id, chapter_id, figure_id)
        if dsl is not None:
            self.dsl_path(book_id, chapter_id, figure_id).write_text(
                json.dumps(dsl, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if meta is not None:
            meta.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            meta.setdefault("version", 1)
            self.meta_path(book_id, chapter_id, figure_id).write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return ddir

    def resolve_local_path(self, url_or_path: str) -> Path | None:
        raw = str(url_or_path or "").strip().split("?", 1)[0].split("#", 1)[0].strip()
        if not raw:
            return None
        if raw.startswith("/static/figures/"):
            rel = raw.replace("/static/figures/", "", 1).replace("\\", "/")
            parts = [p for p in rel.split("/") if p]
            if parts:
                candidate = settings.figures_path.joinpath(*parts)
                if candidate.is_file():
                    return candidate
            if len(parts) == 2:
                legacy = settings.figures_path / parts[0] / parts[1]
                if legacy.is_file():
                    return legacy
        p = Path(raw)
        return p if p.is_file() else None


figure_storage = FigureStorageManager()
