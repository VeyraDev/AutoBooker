#!/usr/bin/env python3
"""Migrate local reference files and figure images into binary_assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.binary_asset import AssetDomain, AssetRole, BinaryAsset, FigureAsset, FigureAssetRole
from app.models.book import Book
from app.models.figure import Figure
from app.models.reference import ReferenceFile
from app.services.figures.storage.manager import figure_storage


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def migrate_references(db, *, dry_run: bool) -> dict:
    report = {"migrated": 0, "skipped": 0, "missing": []}
    refs = db.query(ReferenceFile).filter(ReferenceFile.asset_id.is_(None)).all()
    for ref in refs:
        path = Path(ref.storage_path or "")
        if not path.is_file() or str(ref.storage_path or "").startswith("db://"):
            report["missing"].append({"ref_id": str(ref.id), "path": ref.storage_path})
            report["skipped"] += 1
            continue
        content = path.read_bytes()
        book = db.query(Book).filter_by(id=ref.book_id).first()
        if not book:
            report["skipped"] += 1
            continue
        if dry_run:
            report["migrated"] += 1
            continue
        asset = BinaryAsset(
            book_id=ref.book_id,
            owner_user_id=book.user_id,
            asset_domain=AssetDomain.reference,
            asset_role=AssetRole.original_upload,
            filename=ref.filename,
            mime_type="application/octet-stream",
            extension=path.suffix.lstrip("."),
            content=content,
            size_bytes=len(content),
            sha256=_sha256(content),
        )
        db.add(asset)
        db.flush()
        ref.asset_id = asset.id
        ref.storage_path = f"db://binary_assets/{asset.id}"
        report["migrated"] += 1
    return report


def _load_json_sidecar(fig_dir: Path, name: str) -> dict | None:
    p = fig_dir / name
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def migrate_figures(db, *, dry_run: bool) -> dict:
    report = {"migrated": 0, "skipped": 0, "dsl_migrated": 0, "missing": [], "files": []}
    figures = db.query(Figure).all()
    for fig in figures:
        if fig.file_path and str(fig.file_path).startswith("db://"):
            report["skipped"] += 1
            continue
        paths: list[Path] = []
        if fig.file_path:
            p = Path(fig.file_path)
            if p.is_file():
                paths.append(p)
        for candidate in figure_storage.png_path(fig.book_id, fig.chapter_index, fig.id), figure_storage.svg_path(
            fig.book_id, fig.chapter_index, fig.id
        ):
            if candidate.is_file():
                paths.append(candidate)
        if not paths:
            report["missing"].append({"figure_id": str(fig.id), "file_path": fig.file_path})
            report["skipped"] += 1
            continue
        book = db.query(Book).filter_by(id=fig.book_id).first()
        if not book:
            report["skipped"] += 1
            continue
        fig_dir = figure_storage.png_path(fig.book_id, fig.chapter_index, fig.id).parent
        dsl = _load_json_sidecar(fig_dir, "figure.dsl.json")
        meta = _load_json_sidecar(fig_dir, "figure.meta.json")
        for path in paths:
            content = path.read_bytes()
            report["files"].append({"figure_id": str(fig.id), "path": str(path), "sha256": _sha256(content)})
            if dry_run:
                report["migrated"] += 1
                continue
            asset = BinaryAsset(
                book_id=fig.book_id,
                owner_user_id=book.user_id,
                asset_domain=AssetDomain.figure,
                asset_role=AssetRole.figure_png if path.suffix.lower() != ".svg" else AssetRole.figure_svg,
                filename=path.name,
                mime_type="image/png" if path.suffix.lower() != ".svg" else "image/svg+xml",
                extension=path.suffix.lstrip("."),
                content=content,
                size_bytes=len(content),
                sha256=_sha256(content),
            )
            db.add(asset)
            db.flush()
            role = FigureAssetRole.png if path.suffix.lower() == ".png" else FigureAssetRole.svg
            db.add(FigureAsset(figure_id=fig.id, asset_id=asset.id, role=role, active=True))
            if path.suffix.lower() == ".png" or not fig.file_url:
                fig.file_path = f"db://binary_assets/{asset.id}"
                fig.file_url = f"/api/books/{fig.book_id}/assets/{asset.id}/content"
            if path.suffix.lower() == ".svg":
                fig.svg_url = f"/api/books/{fig.book_id}/assets/{asset.id}/content"
            report["migrated"] += 1
        if dsl or meta:
            clf = dict(fig.classification_json) if isinstance(fig.classification_json, dict) else {}
            if dsl:
                clf["dsl_json"] = dsl
            if meta:
                clf["render_meta"] = meta
            if not dry_run:
                fig.classification_json = clf
            report["dsl_migrated"] += 1
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        ref_report = migrate_references(db, dry_run=args.dry_run)
        fig_report = migrate_figures(db, dry_run=args.dry_run)
        if not args.dry_run:
            db.commit()
        print(json.dumps({"references": ref_report, "figures": fig_report}, ensure_ascii=False, indent=2))
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
