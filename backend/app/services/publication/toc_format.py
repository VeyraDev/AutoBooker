"""目录行排版：标题 + 点线 + 右端页码（PDF/Word 共用）。"""

from __future__ import annotations

_FONT_CACHE: dict[str, object] = {}


def _font(name: str):
    if name not in _FONT_CACHE:
        import fitz

        try:
            _FONT_CACHE[name] = fitz.Font(name)
        except Exception:
            _FONT_CACHE[name] = None
    return _FONT_CACHE[name]


def _pick_font(*names: str):
    for name in names:
        font = _font(name)
        if font is not None:
            return font
    import fitz

    return fitz.Font("helv")


def measure_width_pt(text: str, font_size_pt: float, *, mono: bool = False) -> float:
    """
    尽量贴近 MuPDF Story 实际字体：
    - 正文/中文：Droid Sans Fallback
    - 点线（ASCII）：Charis SIL
    """
    if mono:
        font = _pick_font("cour", "NimbusMonoPS-Regular", "china-s")
    elif text and all(ch == "." for ch in text):
        font = _pick_font("charis", "CharisSIL", "china-s", "helv")
    else:
        font = _pick_font("droidsansfallback", "Droid Sans Fallback", "china-s", "cjk")
    try:
        return float(font.text_length(text or "", fontsize=float(font_size_pt)))
    except Exception:
        return len(text or "") * float(font_size_pt) * 0.9


def toc_entry_plain_line(
    title: str,
    page: int | None,
    *,
    content_width_pt: float,
    font_size_pt: float,
    indent_pt: float = 0.0,
) -> tuple[str, str]:
    """
    返回 (完整目录行, \"\")。
    点线按「版心宽度 − 标题 − 页码」填充，页码自然贴右；
    不使用前导空格/等宽槽（Story 易裁切只剩末位数字）。
    """
    title = title or ""
    if page is None:
        return title, ""

    page_str = str(int(page))
    fs = float(font_size_pt)
    # Story 字体与测量字体仍可能有偏差，右侧留安全距，避免页码被裁切
    usable = max(40.0, (float(content_width_pt) - float(indent_pt)) * 0.94 - 4.0)
    title_w = measure_width_pt(title, fs)
    page_w = measure_width_pt(page_str, fs)
    dot_w = max(0.8, measure_width_pt(".", fs))
    n = max(2, int((usable - title_w - page_w) / dot_w))
    left = f"{title}{'.' * n}"

    guard = 0
    while measure_width_pt(left, fs) + page_w < usable - 1.5 and guard < 40:
        left += "."
        guard += 1
    while len(left) > len(title) + 2 and measure_width_pt(left, fs) + page_w > usable:
        left = left[:-1]

    return f"{left}{page_str}", ""
