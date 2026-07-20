"""Publication cover / copyright metadata for formal book export."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


PUBLICATION_INFO_KEYS = (
    "title",
    "subtitle",
    "author",
    "publisher",
    "publish_year",
    "isbn",
    "edition",
    "series",
    "cip_text",
    "price",
    "editor",
    "proofreader",
    "address",
    "postal_code",
    "print_count",
    "word_count_label",
    "format_label",
    "page_format_id",
    "binding_type",
    "cover_bg_asset_id",
)

# 封面元素在封面上的默认位置（百分比，相对封面宽高；文字水平居中锚定于 x）
DEFAULT_COVER_LAYOUT: dict[str, dict[str, float]] = {
    "series": {"x": 50, "y": 8},
    "title": {"x": 50, "y": 32},
    "subtitle": {"x": 50, "y": 44},
    "author": {"x": 50, "y": 62},
    "publisher": {"x": 50, "y": 88},
}


class PublicationInfo(BaseModel):
    title: str = ""
    subtitle: str = ""
    author: str = ""
    publisher: str = ""
    publish_year: str = ""
    isbn: str = ""
    edition: str = ""
    series: str = ""
    cip_text: str = Field(default="", description="CIP / 图书在版编目数据")
    price: str = ""
    editor: str = ""
    proofreader: str = ""
    address: str = ""
    postal_code: str = ""
    print_count: str = ""
    word_count_label: str = ""
    format_label: str = "大 32 开"
    page_format_id: str = "da32_dade"
    binding_type: str = "paperback"  # paperback=平装 | hardcover=精装
    cover_layout: dict[str, Any] = Field(default_factory=dict)
    cover_theme: str = ""
    cover_bg_seed: str = ""
    cover_bg_asset_id: str = ""


def default_cover_layout() -> dict[str, dict[str, float]]:
    return {k: dict(v) for k, v in DEFAULT_COVER_LAYOUT.items()}


def normalize_cover_layout(raw: Any) -> dict[str, dict[str, float]]:
    base = default_cover_layout()
    if not isinstance(raw, dict):
        return base
    for key in base:
        item = raw.get(key)
        if not isinstance(item, dict):
            continue
        try:
            x = float(item.get("x", base[key]["x"]))
            y = float(item.get("y", base[key]["y"]))
        except (TypeError, ValueError):
            continue
        base[key] = {"x": max(0.0, min(100.0, x)), "y": max(0.0, min(100.0, y))}
    return base


def default_publication_info(book_title: str | None = None) -> dict[str, Any]:
    from app.services.publication.page_formats import DEFAULT_PAGE_FORMAT_ID, get_page_format

    spec = get_page_format(DEFAULT_PAGE_FORMAT_ID)
    data = PublicationInfo(
        title=(book_title or "").strip() or "未命名",
        format_label=spec.short_label,
        page_format_id=spec.id,
    ).model_dump()
    data["cover_layout"] = default_cover_layout()
    return data


def normalize_publication_info(
    raw: dict[str, Any] | None,
    *,
    fallback_title: str | None = None,
) -> dict[str, Any]:
    from app.services.publication.page_formats import get_page_format, resolve_page_format_id

    base = default_publication_info(fallback_title)
    if isinstance(raw, dict):
        for key in PUBLICATION_INFO_KEYS:
            if key in raw and raw[key] is not None:
                base[key] = str(raw[key]).strip()
        if "cover_layout" in raw:
            base["cover_layout"] = normalize_cover_layout(raw.get("cover_layout"))
        if raw.get("cover_theme") is not None:
            base["cover_theme"] = str(raw.get("cover_theme") or "").strip()
        if raw.get("cover_bg_seed") is not None:
            base["cover_bg_seed"] = str(raw.get("cover_bg_seed") or "").strip()
        if raw.get("cover_bg_asset_id") is not None:
            base["cover_bg_asset_id"] = str(raw.get("cover_bg_asset_id") or "").strip()
    if not base.get("title"):
        base["title"] = (fallback_title or "").strip() or "未命名"

    fmt_id = resolve_page_format_id(base.get("page_format_id") or base.get("format_label"))
    from app.services.publication.page_formats import resolve_binding_type

    binding = resolve_binding_type(base.get("binding_type"))
    base["binding_type"] = binding
    spec = get_page_format(fmt_id, binding=binding)
    base["page_format_id"] = spec.id
    base["format_label"] = spec.short_label

    if not isinstance(base.get("cover_layout"), dict) or not base["cover_layout"]:
        base["cover_layout"] = default_cover_layout()
    else:
        base["cover_layout"] = normalize_cover_layout(base["cover_layout"])
    return base


def build_colophon_lines(pub: dict[str, Any] | None) -> list[str]:
    """
    版权页完整行（与导出预览一致）。
    返回已排好的文本行；空可选字段不输出。
    """
    from app.services.publication.page_formats import get_page_format_from_publication

    pub = pub if isinstance(pub, dict) else {}
    spec = get_page_format_from_publication(pub)
    title = (pub.get("title") or "").strip() or "未命名"
    subtitle = (pub.get("subtitle") or "").strip()
    author = (pub.get("author") or "").strip()
    publisher = (pub.get("publisher") or "").strip()
    year = (pub.get("publish_year") or "").strip()
    edition = (pub.get("edition") or "").strip() or "第1版"
    isbn = (pub.get("isbn") or "").strip()
    cip = (pub.get("cip_text") or "").strip()
    price = (pub.get("price") or "").strip()
    editor = (pub.get("editor") or "").strip()
    proofreader = (pub.get("proofreader") or "").strip()
    address = (pub.get("address") or "").strip()
    postal = (pub.get("postal_code") or "").strip()
    print_count = (pub.get("print_count") or "").strip()
    words = (pub.get("word_count_label") or "").strip()
    fmt = (pub.get("format_label") or spec.short_label).strip() or spec.short_label
    size_note = f"{fmt}（{spec.width_mm:.0f}×{spec.height_mm:.0f}mm）"

    lines: list[str] = []
    if cip:
        lines.append("图书在版编目（CIP）数据")
        lines.append(cip)

    rows: list[tuple[str, str]] = [
        ("书　　名", title),
        ("副 书 名", subtitle),
        ("著　　者", f"{author}　著" if author else "（待填）"),
        ("责任编辑", editor or "（待填）"),
        ("责任校对", proofreader),
        ("出版发行", publisher or "（待填）"),
        ("地　　址", address),
        ("邮政编码", postal),
        ("开　　本", size_note),
        ("字　　数", words),
        ("版　　次", f"{year}年　{edition}" if year else edition),
        ("印　　数", print_count),
        ("定　　价", price),
        ("ISBN", isbn),
    ]
    for label, value in rows:
        if not value:
            continue
        lines.append(f"{label}　{value}")
    return lines
