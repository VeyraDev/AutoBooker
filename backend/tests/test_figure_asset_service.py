"""DB-backed figure assets must be type-aware and request-scoped."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.models.binary_asset import AssetRole, BinaryAsset, FigureAsset
from app.models.figure import Figure
from app.models.figure_batch import FigureBatchRun
from app.services.assets.asset_resolver import AssetResolver
from app.services.assets.figure_asset_service import FigureAssetService


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *exprs, **_kwargs):
        for expr in exprs:
            left = getattr(expr, "left", None)
            name = getattr(left, "name", None)
            if not name:
                continue
            right = getattr(expr, "right", None)
            value = getattr(right, "value", None)
            if value is None:
                continue
            self._rows = [
                row for row in self._rows if str(getattr(row, name, "")) == str(value)
            ]
        return self

    def join(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, *, assets=None, links=None, figures=None):
        self.assets = list(assets or [])
        self.links = list(links or [])
        self.figures = list(figures or [])

    def query(self, model):
        if model is BinaryAsset:
            return _Query(self.assets)
        if model is FigureAsset:
            return _Query(self.links)
        if model is Figure:
            return _Query(self.figures)
        return _Query([])


def _asset(asset_id, *, content: bytes, mime_type: str, filename: str, role: AssetRole):
    return SimpleNamespace(
        id=asset_id,
        content=content,
        mime_type=mime_type,
        filename=filename,
        extension=filename.rsplit(".", 1)[-1],
        asset_role=role,
    )


def test_figure_asset_service_respects_requested_image_kind():
    figure_id = uuid4()
    png_id = uuid4()
    svg_id = uuid4()
    figure = SimpleNamespace(id=figure_id, file_path=None)
    links = [
        SimpleNamespace(figure_id=figure_id, asset_id=svg_id, active=True),
        SimpleNamespace(figure_id=figure_id, asset_id=png_id, active=True),
    ]
    db = _Db(
        links=links,
        assets=[
            _asset(svg_id, content=b"<svg/>", mime_type="image/svg+xml", filename="figure.svg", role=AssetRole.figure_svg),
            _asset(png_id, content=b"png-bytes", mime_type="image/png", filename="figure.png", role=AssetRole.figure_png),
        ],
    )

    service = FigureAssetService(db)

    assert service.resolve_figure_bytes(figure, prefer_svg=False) == b"png-bytes"
    assert service.resolve_figure_bytes(figure, prefer_svg=True) == b"<svg/>"


def test_materialize_figure_raster_prefers_png_and_cleans_temp_file():
    book_id = uuid4()
    figure_id = uuid4()
    png_id = uuid4()
    svg_id = uuid4()
    figure = SimpleNamespace(id=figure_id, book_id=book_id, chapter_index=1, file_path=None)
    links = [
        SimpleNamespace(figure_id=figure_id, asset_id=svg_id, active=True),
        SimpleNamespace(figure_id=figure_id, asset_id=png_id, active=True),
    ]
    db = _Db(
        links=links,
        assets=[
            _asset(svg_id, content=b"<svg/>", mime_type="image/svg+xml", filename="figure.svg", role=AssetRole.figure_svg),
            _asset(png_id, content=b"png-bytes", mime_type="image/png", filename="figure.png", role=AssetRole.figure_png),
        ],
    )

    with AssetResolver(db).materialize_figure_raster(figure) as path:
        assert path is not None
        assert path.exists()
        assert path.suffix == ".png"
        assert path.read_bytes() == b"png-bytes"
        captured = path

    assert not captured.exists()


def test_materialize_local_path_cleans_db_asset_temp_file():
    asset_id = uuid4()
    db = _Db(
        assets=[
            _asset(asset_id, content=b"db-bytes", mime_type="image/png", filename="figure.png", role=AssetRole.figure_png)
        ]
    )

    with AssetResolver(db).materialize_local_path(f"db://binary_assets/{asset_id}") as path:
        assert path is not None
        assert path.exists()
        assert path.suffix == ".png"
        assert path.read_bytes() == b"db-bytes"
        captured = path

    assert not captured.exists()


def test_asset_content_url_matches_mounted_book_router_and_reads_legacy_url():
    book_id = uuid4()
    asset_id = uuid4()
    figure = SimpleNamespace(
        id=uuid4(),
        file_path=None,
        file_url=f"/api/books/{book_id}/assets/{asset_id}/content",
    )
    resolver = AssetResolver(_Db())

    assert resolver.asset_content_url(book_id, asset_id) == f"/books/{book_id}/assets/{asset_id}/content"
    assert resolver.parse_asset_id_from_figure(figure) == asset_id


def test_figure_batch_model_maps_worker_lease_columns():
    columns = FigureBatchRun.__table__.columns

    assert "lease_owner" in columns
    assert "lease_until" in columns
    assert "heartbeat_at" in columns
