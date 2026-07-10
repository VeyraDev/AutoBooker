"""Reference asset materialization must be request-scoped and DB-first."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.services.assets.reference_asset_service import ReferenceAssetService


class _Query:
    def __init__(self, row):
        self._row = row

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._row


class _Db:
    def __init__(self, asset=None):
        self.asset = asset

    def query(self, *_args, **_kwargs):
        return _Query(self.asset)


def test_materialize_db_reference_cleans_temp_file():
    asset_id = uuid4()
    asset = SimpleNamespace(id=asset_id, extension="txt", content=b"hello from db")
    ref = SimpleNamespace(asset_id=asset_id, storage_path=f"db://binary_assets/{asset_id}", file_type="txt")

    with ReferenceAssetService(_Db(asset)).materialize(ref) as path:
        assert path.exists()
        assert path.suffix == ".txt"
        assert path.read_bytes() == b"hello from db"
        captured = path

    assert not captured.exists()


def test_materialize_legacy_reference_keeps_source_file(tmp_path):
    legacy = tmp_path / "legacy.txt"
    legacy.write_text("legacy text", encoding="utf-8")
    ref = SimpleNamespace(asset_id=None, storage_path=str(legacy), file_type="txt")

    with ReferenceAssetService(_Db()).materialize(ref) as path:
        assert path == legacy
        assert path.read_text(encoding="utf-8") == "legacy text"

    assert legacy.exists()


def test_reference_and_optimization_uploads_do_not_write_upload_dir():
    backend_root = Path(__file__).resolve().parents[1]
    for rel in ("app/routers/references.py", "app/routers/optimization.py"):
        source = (backend_root / rel).read_text(encoding="utf-8")
        assert "ReferenceAssetService(db).attach_upload" in source
        assert "settings.upload_path" not in source
        assert ".write_bytes(" not in source
