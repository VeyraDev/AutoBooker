import json
from uuid import uuid4

from app.services.figures.storage.manager import figure_storage


def test_storage_paths_and_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("FIGURES_DIR", str(tmp_path))
    from app.config import Settings

    settings = Settings()
    book_id = uuid4()
    figure_id = uuid4()
    chapter_id = 2

    monkeypatch.setattr("app.services.figures.storage.manager.settings", settings)
    from app.services.figures.storage.manager import FigureStorageManager

    storage = FigureStorageManager()
    png = storage.png_path(book_id, chapter_id, figure_id)
    assert png.name == "figure.png"
    assert str(chapter_id) in str(png)

    storage.save_assets(
        book_id=book_id,
        chapter_id=chapter_id,
        figure_id=figure_id,
        dsl={"diagram_type": "flowchart", "title": "测试", "nodes": [], "edges": []},
        meta={"figure_id": str(figure_id), "diagram_type": "flowchart", "renderer": "structured.flowchart"},
    )

    meta_path = storage.meta_path(book_id, chapter_id, figure_id)
    assert meta_path.is_file()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["diagram_type"] == "flowchart"
    assert "created_at" in meta

    url = storage.public_url(book_id, chapter_id, figure_id)
    resolved = storage.resolve_local_path(url)
    assert resolved is None  # png not written yet
