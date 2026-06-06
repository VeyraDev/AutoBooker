"""SVG 基础图元。"""

from __future__ import annotations

import html


def rect(x: float, y: float, w: float, h: float, *, fill: str, stroke: str, rx: int = 8, shadow: bool = False) -> str:
    filt = ' filter="url(#shadow)"' if shadow else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{filt}/>'


def diamond(cx: float, cy: float, w: float, h: float, *, fill: str, stroke: str, shadow: bool = False) -> str:
    x, y = cx - w / 2, cy - h / 2
    pts = f"{cx:.1f},{y:.1f} {x+w:.1f},{cy:.1f} {cx:.1f},{y+h:.1f} {x:.1f},{cy:.1f}"
    filt = ' filter="url(#shadow)"' if shadow else ""
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"{filt}/>'


def database(cx: float, cy: float, w: float, h: float, *, fill: str, stroke: str) -> str:
    x, y = cx - w / 2, cy - h / 2
    ry = min(10.0, h * 0.15)
    return (
        f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="{w/2:.1f}" ry="{ry:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="none"/>'
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x+w:.1f}" y2="{y:.1f}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<ellipse cx="{cx:.1f}" cy="{y+h:.1f}" rx="{w/2:.1f}" ry="{ry:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y+h:.1f}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<line x1="{x+w:.1f}" y1="{y:.1f}" x2="{x+w:.1f}" y2="{y+h:.1f}" stroke="{stroke}" stroke-width="1.5"/>'
    )


def queue_rail(x: float, y: float, w: float, h: float, *, fill: str, stroke: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h/2:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" filter="url(#shadow)"/>'
        f'<line x1="{x+12:.1f}" y1="{y+h/2:.1f}" x2="{x+w-12:.1f}" y2="{y+h/2:.1f}" stroke="{stroke}" stroke-width="1" stroke-dasharray="4 3"/>'
    )


def group_container(x: float, y: float, w: float, h: float, label: str, *, fill: str, stroke: str, text_fill: str) -> str:
    safe = html.escape(label)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1" opacity="0.92"/>'
        f'<text x="{x+10:.1f}" y="{y+16:.1f}" fill="{text_fill}" font-size="11" font-weight="bold">{safe}</text>'
    )


def icon_badge(cx: float, cy: float, icon: str, *, bg: str, fg: str, r: float = 10) -> str:
    safe = html.escape(icon)
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{bg}" stroke="{fg}" stroke-width="0.5"/>'
        f'<text x="{cx:.1f}" y="{cy+1:.1f}" fill="{fg}" font-size="{r:.0f}" text-anchor="middle" dominant-baseline="middle">{safe}</text>'
    )


def label_background(cx: float, cy: float, text_w: float, *, fill: str = "#FFFFFFCC") -> str:
    return f'<rect x="{cx-text_w/2:.1f}" y="{cy-9:.1f}" width="{text_w:.1f}" height="16" rx="3" fill="{fill}" stroke="none"/>'


def polyline(points: list[tuple[float, float]], *, stroke: str, width: float = 1.5, dashed: bool = False, marker_end: str = "") -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    marker = f' marker-end="url(#{marker_end})"' if marker_end else ""
    return f'<polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="{width}"{dash}{marker}/>'


def shadow_filter_def() -> str:
    return (
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#0F172A" flood-opacity="0.12"/>'
        '</filter>'
    )
