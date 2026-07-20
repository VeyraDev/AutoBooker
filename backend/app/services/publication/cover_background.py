"""Generate a print-ready cover image (大32开) from publication metadata."""

from __future__ import annotations

import colorsys
import hashlib
import io
import logging
import uuid
from typing import Any
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.services.publication.page_formats import cover_pixel_size, get_page_format_from_publication
from app.services.publication.publication_info import normalize_cover_layout, normalize_publication_info

logger = logging.getLogger(__name__)

DEFAULT_POS_FALLBACK = {
    "series": {"x": 50, "y": 8},
    "title": {"x": 50, "y": 32},
    "subtitle": {"x": 50, "y": 44},
    "author": {"x": 50, "y": 62},
    "publisher": {"x": 50, "y": 88},
}


def _hash_seed(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _theme_colors(seed: int, theme: str = "") -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    """Return (bg_top, bg_bottom, accent) from seed / optional theme keyword."""
    theme_map = {
        "academic": (0.58, 0.35, 0.28),
        "science": (0.52, 0.45, 0.32),
        "history": (0.08, 0.42, 0.30),
        "literature": (0.92, 0.28, 0.38),
        "business": (0.62, 0.20, 0.22),
        "warm": (0.06, 0.48, 0.42),
        "cool": (0.55, 0.40, 0.36),
        "ink": (0.0, 0.0, 0.18),
    }
    key = (theme or "").strip().lower()
    if key in theme_map:
        h, s, l = theme_map[key]
    else:
        h = ((seed % 1000) / 1000.0) * 0.85
        s = 0.28 + ((seed >> 8) % 40) / 100.0
        l = 0.28 + ((seed >> 16) % 25) / 100.0
    top = tuple(int(c * 255) for c in colorsys.hls_to_rgb(h, min(0.55, l + 0.12), s))
    bottom = tuple(int(c * 255) for c in colorsys.hls_to_rgb((h + 0.04) % 1.0, max(0.12, l - 0.08), min(0.7, s + 0.08)))
    accent = tuple(int(c * 255) for c in colorsys.hls_to_rgb((h + 0.12) % 1.0, 0.72, 0.35))
    return top, bottom, accent  # type: ignore[return-value]


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _paint_background(img: Image.Image, seed: int, theme: str, title: str) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    top, bottom, accent = _theme_colors(seed, theme)
    for y in range(h):
        t = y / max(1, h - 1)
        color = (
            _lerp(top[0], bottom[0], t),
            _lerp(top[1], bottom[1], t),
            _lerp(top[2], bottom[2], t),
        )
        draw.line([(0, y), (w, y)], fill=color)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    n = 3 + (seed % 4)
    for i in range(n):
        cx = int((0.15 + 0.7 * ((seed >> (i * 3)) % 100) / 100.0) * w)
        cy = int((0.2 + 0.55 * ((seed >> (i * 5)) % 100) / 100.0) * h)
        r = int(w * (0.18 + 0.12 * ((i + len(title)) % 3)))
        alpha = 28 + (i * 10) % 40
        od.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*accent, alpha), width=max(2, w // 180))
    band = max(8, h // 48)
    od.rectangle([0, 0, w, band], fill=(*accent, 90))
    od.rectangle([0, h - band, w, h], fill=(*accent, 90))
    img.alpha_composite(overlay.convert("RGBA") if overlay.mode != "RGBA" else overlay)


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/msyhbd.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/simsun.ttc",
            ]
        )
    candidates.extend(
        [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        ]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines[:6]


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    cx: int,
    cy: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    max_width: int,
) -> None:
    lines = _wrap_text(draw, text, font, max_width)
    if not lines:
        return
    line_heights = []
    widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])
    gap = max(4, int(font.size * 0.25)) if hasattr(font, "size") else 6
    total_h = sum(line_heights) + gap * (len(lines) - 1)
    y = cy - total_h // 2
    for i, line in enumerate(lines):
        x = cx - widths[i] // 2
        draw.text((x + 1, y + 1), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += line_heights[i] + gap


def build_cover_ai_prompt(publication: dict[str, Any] | None, *, fallback_title: str | None = None) -> str:
    pub = normalize_publication_info(publication, fallback_title=fallback_title)
    title = pub.get("title") or "未命名"
    subtitle = (pub.get("subtitle") or "").strip()
    author = (pub.get("author") or "").strip()
    theme = (pub.get("cover_theme") or "").strip()
    seed = (pub.get("cover_bg_seed") or "").strip()
    parts = [
        "设计一本中文正式出版物的竖版书籍封面背景插画。",
        "要求：专业出版级构图，有氛围感与质感，留出中央偏上区域作为书名排版留白。",
        "严禁出现任何文字、字母、数字、水印、Logo、条形码或二维码。",
        f"书籍主题与书名含义：{title}。",
    ]
    if subtitle:
        parts.append(f"副标题意象：{subtitle}。")
    if author:
        parts.append(f"作者气质可参考：{author}。")
    if theme:
        parts.append(f"视觉风格关键词：{theme}。")
    else:
        parts.append("视觉风格：当代人文社科书籍封面，克制、有层次。")
    if seed:
        parts.append(f"变体种子（请据此微调构图与色调，勿输出该字符串）：{seed[:16]}。")
    return "\n".join(parts)


def generate_ai_cover_background(
    publication: dict[str, Any] | None,
    *,
    fallback_title: str | None = None,
) -> bytes:
    """调用智灵网关 gpt-image-2 生成封面背景图。"""
    from app.services.figures.render.image_api.zeelin_provider import generate_image_bytes_zeelin

    prompt = build_cover_ai_prompt(publication, fallback_title=fallback_title)
    return generate_image_bytes_zeelin(prompt, sub_kind="cover")


def save_cover_background_asset(
    db: Session,
    *,
    book_id: UUID,
    owner_user_id: UUID,
    png_or_image_bytes: bytes,
    metadata: dict[str, Any] | None = None,
) -> UUID:
    """将封面背景存入 binary_assets，返回 asset_id。"""
    from app.models.binary_asset import AssetDomain, AssetRole
    from app.services.assets.binary_asset_service import BinaryAssetService

    # 统一转 PNG，便于后续合成
    try:
        with Image.open(io.BytesIO(png_or_image_bytes)) as img:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG", optimize=True)
            content = buf.getvalue()
    except Exception:
        content = png_or_image_bytes

    asset = BinaryAssetService(db).create_asset(
        book_id=book_id,
        owner_user_id=owner_user_id,
        content=content,
        filename="cover-bg.png",
        mime_type="image/png",
        asset_domain=AssetDomain.misc,
        asset_role=AssetRole.export_png,
        metadata=metadata or {"kind": "cover_background"},
    )
    return asset.id


def _load_cover_bg_bytes(
    publication: dict[str, Any],
    *,
    db: Session | None,
    book_id: UUID | None,
    bg_bytes: bytes | None,
) -> bytes | None:
    if bg_bytes:
        return bg_bytes
    raw_id = (publication.get("cover_bg_asset_id") or "").strip()
    if not raw_id or db is None:
        return None
    try:
        asset_id = UUID(str(raw_id))
    except (TypeError, ValueError):
        return None
    from app.models.binary_asset import BinaryAsset

    q = db.query(BinaryAsset).filter(BinaryAsset.id == asset_id, BinaryAsset.deleted_at.is_(None))
    if book_id is not None:
        q = q.filter(BinaryAsset.book_id == book_id)
    asset = q.first()
    if not asset or not asset.content:
        return None
    return bytes(asset.content)


def render_cover_png(
    publication: dict[str, Any] | None,
    *,
    fallback_title: str | None = None,
    bg_bytes: bytes | None = None,
    db: Session | None = None,
    book_id: UUID | None = None,
) -> bytes:
    """Render cover PNG at selected 开本 finished size. Positions follow cover_layout (%)."""
    pub = normalize_publication_info(publication, fallback_title=fallback_title)
    layout = normalize_cover_layout(pub.get("cover_layout"))
    title = pub.get("title") or "未命名"
    seed = _hash_seed(pub.get("cover_bg_seed") or "", title, pub.get("subtitle") or "", pub.get("author") or "")
    theme = pub.get("cover_theme") or ""
    spec = get_page_format_from_publication(pub)
    width_px, height_px = cover_pixel_size(spec)

    img = Image.new("RGBA", (width_px, height_px), (255, 255, 255, 255))
    ai_bg = _load_cover_bg_bytes(pub, db=db, book_id=book_id, bg_bytes=bg_bytes)
    if ai_bg:
        try:
            with Image.open(io.BytesIO(ai_bg)) as raw:
                bg = raw.convert("RGB").resize((width_px, height_px), Image.Resampling.LANCZOS)
            img.paste(bg)
            # 轻微暗化，保证白字可读
            shade = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 56))
            img = Image.alpha_composite(img.convert("RGBA"), shade)
        except Exception:
            logger.exception("failed to apply AI cover background; fallback to procedural")
            _paint_background(img, seed, theme, title)
    else:
        _paint_background(img, seed, theme, title)

    draw = ImageDraw.Draw(img)
    w, h = img.size
    max_text_w = int(w * 0.82)
    text_fill = (252, 250, 245)

    elements = [
        ("series", pub.get("series") or "", _load_font(max(18, w // 28), bold=False), text_fill),
        ("title", title, _load_font(max(36, w // 11), bold=True), text_fill),
        ("subtitle", pub.get("subtitle") or "", _load_font(max(22, w // 22), bold=False), text_fill),
        ("author", (f"{pub['author']}　著" if pub.get("author") else ""), _load_font(max(22, w // 20), bold=False), text_fill),
        (
            "publisher",
            "　".join(x for x in [pub.get("publisher"), pub.get("publish_year")] if x),
            _load_font(max(18, w // 26), bold=False),
            text_fill,
        ),
    ]
    for key, text, font, fill in elements:
        if not text:
            continue
        pos = layout.get(key) or DEFAULT_POS_FALLBACK.get(key, {"x": 50, "y": 50})
        cx = int(w * float(pos["x"]) / 100.0)
        cy = int(h * float(pos["y"]) / 100.0)
        _draw_centered(draw, text, cx=cx, cy=cy, font=font, fill=fill, max_width=max_text_w)

    out = Image.new("RGB", img.size, (255, 255, 255))
    out.paste(img, mask=img.split()[-1])
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def cover_png_data_url(
    publication: dict[str, Any] | None,
    *,
    fallback_title: str | None = None,
    bg_bytes: bytes | None = None,
    db: Session | None = None,
    book_id: UUID | None = None,
) -> str:
    import base64

    raw = render_cover_png(
        publication,
        fallback_title=fallback_title,
        bg_bytes=bg_bytes,
        db=db,
        book_id=book_id,
    )
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def regenerate_cover_background_for_book(
    db: Session,
    *,
    book_id: UUID,
    owner_user_id: UUID,
    publication: dict[str, Any],
    fallback_title: str | None = None,
) -> dict[str, Any]:
    """
    用智灵 gpt-image-2 生成新封面背景，写入 binary_assets，
    并回写 publication_info 中的 cover_bg_asset_id / cover_bg_seed。
    """
    pub = normalize_publication_info(publication, fallback_title=fallback_title)
    seed = uuid.uuid4().hex
    pub["cover_bg_seed"] = seed
    raw = generate_ai_cover_background(pub, fallback_title=fallback_title)
    asset_id = save_cover_background_asset(
        db,
        book_id=book_id,
        owner_user_id=owner_user_id,
        png_or_image_bytes=raw,
        metadata={"kind": "cover_background", "seed": seed, "title": pub.get("title")},
    )
    pub["cover_bg_asset_id"] = str(asset_id)
    return pub
