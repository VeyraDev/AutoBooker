"""Cross-analyze DOCX export with DB figure metadata."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from app.database import SessionLocal
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.figure import Figure
from app.services.publication.book_ast_builder import build_book_ast
from app.config import settings
from PIL import Image

BOOK_ID = "c22dc3ec-a9b6-4895-9550-aa00fdbcc6c0"


def main() -> None:
    db = SessionLocal()
    book = db.query(Book).filter(Book.id == BOOK_ID).first()
    chapters = db.query(Chapter).filter(Chapter.book_id == BOOK_ID).order_by(Chapter.index).all()
    ast = build_book_ast(book, chapters, db)

    fig_blocks = [b for b in ast.blocks if b.role == "figure" and b.attrs.get("chapter_index") == 1]
    caps = []
    for i, b in enumerate(ast.blocks):
        if b.role == "figure_caption" and b.text.startswith("图1-"):
            caps.append(b.text)

    print("=== 第1章配图块 vs 题注 ===")
    print(f"figure块: {len(fig_blocks)}, 题注: {len(caps)}")

    fig_by_id = {str(f.id): f for f in db.query(Figure).filter(Figure.book_id == BOOK_ID).all()}

    rows = []
    for idx, block in enumerate(fig_blocks):
        fid = str(block.attrs.get("figureId") or "")
        fig = fig_by_id.get(fid)
        cap = caps[idx] if idx < len(caps) else ""
        cap_short = cap.split("：", 1)[-1][:60] if cap else ""

        clf = {}
        renderer = sub_kind = intent = ""
        quality_status = ""
        warnings: list[str] = []
        if fig and isinstance(fig.classification_json, dict):
            clf = fig.classification_json
            renderer = str(clf.get("renderer") or "")
            sub_kind = str(clf.get("sub_kind") or clf.get("subtype") or "")
            intent = str(clf.get("intent") or "")
            qr = clf.get("quality_report") or {}
            if isinstance(qr, dict):
                quality_status = str(qr.get("status") or "")
                warnings = [str(w) for w in (qr.get("warnings") or [])[:3]]

        raw = (fig.raw_annotation or "")[:80] if fig else ""
        ftype = str(fig.figure_type) if fig else "?"
        status = str(fig.status) if fig else "?"

        # disk size
        px = ""
        svg_p = png_p = None
        if fig:
            from app.services.figures.storage.manager import figure_storage
            svg_p = figure_storage.svg_path(fig.book_id, fig.chapter_index, fig.id)
            png_p = figure_storage.png_path(fig.book_id, fig.chapter_index, fig.id)
            p = png_p if png_p.is_file() else (svg_p if svg_p.is_file() else None)
            if p and p.is_file():
                try:
                    with Image.open(p) as im:
                        px = f"{im.size[0]}x{im.size[1]}"
                        ratio = im.size[0] / im.size[1] if im.size[1] else 0
                except Exception:
                    ratio = 0
            else:
                ratio = 0
        else:
            ratio = 0

        rows.append({
            "num": block.attrs.get("figureNumber") or f"1-{idx+1}",
            "ftype": ftype.replace("FigureType.", ""),
            "renderer": renderer,
            "sub_kind": sub_kind,
            "intent": intent,
            "status": status.replace("FigureStatus.", ""),
            "px": px,
            "ratio": round(ratio, 2),
            "quality": quality_status,
            "warnings": warnings,
            "cap": cap_short,
            "raw": raw,
        })

    # classification stats
    from collections import Counter
    print("\n=== 分类统计(第1章) ===")
    print("figure_type:", dict(Counter(r["ftype"] for r in rows)))
    print("renderer:", dict(Counter(r["renderer"] for r in rows)))
    print("sub_kind:", dict(Counter(r["sub_kind"] for r in rows if r["sub_kind"])))
    print("status:", dict(Counter(r["status"] for r in rows)))

    print("\n=== 逐图明细 ===")
    print(f"{'图号':<6} {'类型':<10} {'渲染器':<12} {'子类':<14} {'像素':<12} {'宽高比':<6} {'质量':<8} 题注/标注")
    for r in rows:
        warn = f" [!]{','.join(r['warnings'][:2])}" if r["warnings"] else ""
        print(
            f"{r['num']:<6} {r['ftype']:<10} {r['renderer']:<12} {r['sub_kind']:<14} "
            f"{r['px']:<12} {r['ratio']:<6} {r['quality']:<8} {r['cap'][:40]}{warn}"
        )

  # mismatch heuristics
    print("\n=== 疑似分类/布局问题 ===")
    issues = []
    for r in rows:
        cap = r["cap"].lower()
        if "柱状" in r["cap"] or "折线" in r["cap"] or "饼图" in r["cap"] or "份额" in r["cap"]:
            if r["renderer"] not in ("chart", "") and r["ftype"] != "chart":
                issues.append(f"{r['num']}: 题注像数据图表但渲染为 {r['renderer']}/{r['ftype']}")
            if r["sub_kind"] and "chart" not in r["sub_kind"] and r["ftype"] != "chart":
                issues.append(f"{r['num']}: 题注描述统计图但 sub_kind={r['sub_kind']}")
        if "插画" in r["cap"] or "场景" in r["cap"] or "工程师" in r["cap"]:
            if r["renderer"] == "layout_svg" or r["ftype"] == "flowchart":
                issues.append(f"{r['num']}: 题注像场景插画却走流程/布局渲染")
        if r["ratio"] > 2.5:
            issues.append(f"{r['num']}: 画布过宽({r['px']}, ratio={r['ratio']})，导出会被拉成横幅")
        if r["ratio"] < 0.5 and r["ratio"] > 0:
            issues.append(f"{r['num']}: 画布过高({r['px']}, ratio={r['ratio']})")
        if r["px"] and int(r["px"].split("x")[0]) > 1800:
            issues.append(f"{r['num']}: 源图超宽 {r['px']}，可能布局未收敛")
        if r["status"] == "pending":
            issues.append(f"{r['num']}: 未生成")
        if r["quality"] == "warning" and r["warnings"]:
            issues.append(f"{r['num']}: 质量警告 — {'; '.join(r['warnings'][:2])}")

    if not issues:
        print("  (未命中规则，见下方布局维度分析)")
    for item in issues:
        print(f"  - {item}")

    # layout dimension clusters
    ratios = [r["ratio"] for r in rows if r["ratio"]]
    if ratios:
        banner = sum(1 for x in ratios if x > 2.0)
        square = sum(1 for x in ratios if 0.85 <= x <= 1.18)
        portrait = sum(1 for x in ratios if x < 0.85)
        landscape = sum(1 for x in ratios if 1.18 < x <= 2.0)
        print("\n=== 画布长宽比分布 ===")
        print(f"  横幅型(>2.0): {banner}  横向(1.18-2.0): {landscape}  近方: {square}  竖向(<0.85): {portrait}")

    db.close()


if __name__ == "__main__":
    main()
