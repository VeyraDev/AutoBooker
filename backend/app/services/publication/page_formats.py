"""国内常见图书开本预设（成品尺寸 + 版心留白）。

说明：
- 「开本」名称在业界略有混用；下列尺寸按大众出版常用成品规格对照。
- 大度大 32 开 145×210mm 与 A5 一致；大度大 16 开 210×285mm 略小于 A4(210×297)。
- 页边距由版心反推，订口略大于切口；可选平装/精装微调。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

BindingType = Literal["paperback", "hardcover"]


def _mm_to_pt(mm: float) -> float:
    return mm / 25.4 * 72


@dataclass(frozen=True)
class PageFormatSpec:
    id: str
    label: str
    short_label: str
    width_mm: float
    height_mm: float
    # 版心目标（文字区），四周由此反推页边距
    type_area_width_mm: float
    type_area_height_mm: float
    # 订口略大于切口
    bind_extra_mm: float = 2.0
    body_pt: float = 10.5
    group: str = "common"  # common | extra
    hint: str = ""
    aka: str = ""
    # 精装相对平装：略加宽订口（可选，默认与平装相同视觉）
    hardcover_inner_extra_mm: float = 0.0

    @property
    def margin_h_total_mm(self) -> float:
        return max(0.0, self.width_mm - self.type_area_width_mm)

    @property
    def margin_v_total_mm(self) -> float:
        return max(0.0, self.height_mm - self.type_area_height_mm)

    @property
    def margin_inner_mm(self) -> float:
        base = self.margin_h_total_mm / 2.0
        return base + self.bind_extra_mm / 2.0

    @property
    def margin_outer_mm(self) -> float:
        base = self.margin_h_total_mm / 2.0
        return max(8.0, base - self.bind_extra_mm / 2.0)

    @property
    def margin_top_mm(self) -> float:
        return self.margin_v_total_mm / 2.0

    @property
    def margin_bottom_mm(self) -> float:
        # 底边略宽，留给页码
        return self.margin_v_total_mm / 2.0 + 1.0

    @property
    def width_pt(self) -> float:
        return _mm_to_pt(self.width_mm)

    @property
    def height_pt(self) -> float:
        return _mm_to_pt(self.height_mm)

    @property
    def margin_inner_pt(self) -> float:
        return _mm_to_pt(self.margin_inner_mm)

    @property
    def margin_outer_pt(self) -> float:
        return _mm_to_pt(self.margin_outer_mm)

    @property
    def margin_top_pt(self) -> float:
        return _mm_to_pt(self.margin_top_mm)

    @property
    def margin_bottom_pt(self) -> float:
        return _mm_to_pt(self.margin_bottom_mm)

    @property
    def content_width_pt(self) -> float:
        return self.width_pt - self.margin_inner_pt - self.margin_outer_pt

    @property
    def content_height_pt(self) -> float:
        return self.height_pt - self.margin_top_pt - self.margin_bottom_pt

    def with_binding(self, binding: BindingType | str | None = "paperback") -> PageFormatSpec:
        b = resolve_binding_type(binding)
        if b == "paperback" or self.hardcover_inner_extra_mm <= 0:
            return self
        return replace(self, bind_extra_mm=self.bind_extra_mm + self.hardcover_inner_extra_mm)


# 默认：大度大 32 开（最常见文学/畅销书）
DEFAULT_PAGE_FORMAT_ID = "da32_dade"
DEFAULT_BINDING: BindingType = "paperback"

PAGE_FORMATS: dict[str, PageFormatSpec] = {
    "da32_dade": PageFormatSpec(
        id="da32_dade",
        label="大度大 32 开",
        short_label="大 32 开",
        width_mm=145.0,
        height_mm=210.0,
        type_area_width_mm=115.0,
        type_area_height_mm=175.0,
        body_pt=10.5,
        group="common",
        hint="小说、散文、畅销书首选；成品与 A5 一致",
        aka="A5",
    ),
    "da32_zhengdu": PageFormatSpec(
        id="da32_zhengdu",
        label="正度小 32 开",
        short_label="正度 32 开",
        width_mm=130.0,
        height_mm=184.0,
        type_area_width_mm=105.0,
        type_area_height_mm=155.0,
        body_pt=10.5,
        group="common",
        hint="便携平装、口袋读物",
        aka="",
    ),
    "da16_dade": PageFormatSpec(
        id="da16_dade",
        label="大度大 16 开",
        short_label="大 16 开",
        width_mm=210.0,
        height_mm=285.0,
        type_area_width_mm=168.0,
        type_area_height_mm=248.0,
        body_pt=12.0,
        group="common",
        hint="教材、教辅、学术专著、图文较多",
        aka="≈A4 略矮",
    ),
    "da16_zhengdu": PageFormatSpec(
        id="da16_zhengdu",
        label="正度 16 开",
        short_label="正度 16 开",
        width_mm=185.0,
        height_mm=260.0,
        type_area_width_mm=150.0,
        type_area_height_mm=220.0,
        body_pt=12.0,
        group="common",
        hint="接近 B5，教材/工具书常用",
        aka="≈B5",
    ),
    "b5": PageFormatSpec(
        id="b5",
        label="B5",
        short_label="B5",
        width_mm=169.0,
        height_mm=239.0,
        type_area_width_mm=135.0,
        type_area_height_mm=200.0,
        body_pt=10.5,
        group="extra",
        hint="中小学教材、部分译本常用",
        aka="B5",
    ),
    "kai24": PageFormatSpec(
        id="kai24",
        label="24 开",
        short_label="24 开",
        width_mm=180.0,
        height_mm=210.0,
        type_area_width_mm=145.0,
        type_area_height_mm=175.0,
        body_pt=11.0,
        group="extra",
        hint="绘本、少儿读物、小词典",
        aka="",
    ),
    "kai8": PageFormatSpec(
        id="kai8",
        label="8 开",
        short_label="8 开",
        width_mm=260.0,
        height_mm=370.0,
        type_area_width_mm=220.0,
        type_area_height_mm=320.0,
        body_pt=11.0,
        group="extra",
        hint="大型画册、海报集、美术作品集",
        aka="",
    ),
}

_FORMAT_ALIASES: dict[str, str] = {
    "da32_dade": "da32_dade",
    "大32开": "da32_dade",
    "大 32 开": "da32_dade",
    "大度大32开": "da32_dade",
    "大度大 32 开": "da32_dade",
    "a5": "da32_dade",
    "A5": "da32_dade",
    "da32_zhengdu": "da32_zhengdu",
    "正度32开": "da32_zhengdu",
    "正度小32开": "da32_zhengdu",
    "正度小 32 开": "da32_zhengdu",
    "小32开": "da32_zhengdu",
    "da16_dade": "da16_dade",
    "大16开": "da16_dade",
    "大 16 开": "da16_dade",
    "大度大16开": "da16_dade",
    "大度大 16 开": "da16_dade",
    "da16_zhengdu": "da16_zhengdu",
    "正度16开": "da16_zhengdu",
    "正度 16 开": "da16_zhengdu",
    "小16开": "da16_zhengdu",
    "b5": "b5",
    "B5": "b5",
    "kai24": "kai24",
    "24开": "kai24",
    "24 开": "kai24",
    "kai8": "kai8",
    "8开": "kai8",
    "8 开": "kai8",
}

_BINDING_ALIASES: dict[str, BindingType] = {
    "paperback": "paperback",
    "softcover": "paperback",
    "平装": "paperback",
    "平装书": "paperback",
    "hardcover": "hardcover",
    "hardback": "hardcover",
    "精装": "hardcover",
    "精装书": "hardcover",
}


def resolve_page_format_id(raw: Any) -> str:
    if raw is None:
        return DEFAULT_PAGE_FORMAT_ID
    s = str(raw).strip()
    if not s:
        return DEFAULT_PAGE_FORMAT_ID
    if s in PAGE_FORMATS:
        return s
    return _FORMAT_ALIASES.get(s, DEFAULT_PAGE_FORMAT_ID)


def resolve_binding_type(raw: Any = None) -> BindingType:
    if raw is None:
        return DEFAULT_BINDING
    raw_s = str(raw).strip()
    if raw_s in _BINDING_ALIASES:
        return _BINDING_ALIASES[raw_s]
    return _BINDING_ALIASES.get(raw_s.lower(), DEFAULT_BINDING)


def get_page_format(raw: Any = None, *, binding: Any = None) -> PageFormatSpec:
    spec = PAGE_FORMATS[resolve_page_format_id(raw)]
    return spec.with_binding(binding if binding is not None else DEFAULT_BINDING)


def get_page_format_from_publication(pub: dict[str, Any] | None) -> PageFormatSpec:
    pub = pub if isinstance(pub, dict) else {}
    fmt_id = pub.get("page_format_id") or pub.get("format_id") or pub.get("format_label")
    binding = pub.get("binding_type") or pub.get("binding") or DEFAULT_BINDING
    return get_page_format(fmt_id, binding=binding)


def list_page_formats(*, binding: Any = None) -> list[dict[str, Any]]:
    b = resolve_binding_type(binding)
    out: list[dict[str, Any]] = []
    for base in PAGE_FORMATS.values():
        spec = base.with_binding(b)
        out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "short_label": spec.short_label,
                "width_mm": spec.width_mm,
                "height_mm": spec.height_mm,
                "margin_top_mm": round(spec.margin_top_mm, 1),
                "margin_bottom_mm": round(spec.margin_bottom_mm, 1),
                "margin_inner_mm": round(spec.margin_inner_mm, 1),
                "margin_outer_mm": round(spec.margin_outer_mm, 1),
                "type_area_width_mm": round(spec.type_area_width_mm, 1),
                "type_area_height_mm": round(spec.type_area_height_mm, 1),
                "body_pt": spec.body_pt,
                "group": spec.group,
                "hint": spec.hint,
                "aka": spec.aka,
                "size_text": f"{spec.width_mm:.0f}×{spec.height_mm:.0f}mm",
                "margins_text": (
                    f"上{spec.margin_top_mm:.0f}/下{spec.margin_bottom_mm:.0f}/"
                    f"内{spec.margin_inner_mm:.0f}/外{spec.margin_outer_mm:.0f}mm"
                ),
                "binding_type": b,
            }
        )
    return out


def cover_pixel_size(spec: PageFormatSpec, *, dpi: int = 150) -> tuple[int, int]:
    w = int(spec.width_mm / 25.4 * dpi)
    h = int(spec.height_mm / 25.4 * dpi)
    return max(200, w), max(280, h)
