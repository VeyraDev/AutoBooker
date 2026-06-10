"""Analyze exported DOCX for figure export quality."""
from __future__ import annotations

import io
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


def analyze(docx_path: Path) -> None:
    if not docx_path.is_file():
        print(f"FILE NOT FOUND: {docx_path}")
        sys.exit(1)

    z = zipfile.ZipFile(docx_path)
    media = sorted(n for n in z.namelist() if n.startswith("word/media/"))
    print("=== 媒体文件 ===")
    print("count:", len(media))
    sizes: list[tuple[int, int]] = []
    for m in media:
        data = z.read(m)
        try:
            img = Image.open(io.BytesIO(data))
            sizes.append(img.size)
            print(f"  {m}: {img.size[0]}x{img.size[1]} {img.mode} {img.format}")
        except Exception as exc:
            print(f"  {m}: ERROR {exc}")

    if sizes:
        ws, hs = zip(*sizes)
        print(
            f"尺寸范围: 宽 {min(ws)}-{max(ws)}px, 高 {min(hs)}-{max(hs)}px, "
            f"平均 {sum(ws)//len(ws)}x{sum(hs)//len(hs)}"
        )
        square = sum(1 for w, h in sizes if 0.85 <= w / h <= 1.18)
        wide = sum(1 for w, h in sizes if w / h > 1.5)
        tall = sum(1 for w, h in sizes if h / w > 1.5)
        print(f"长宽比: 近方形 {square}, 偏宽 {wide}, 偏高 {tall}")

    xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    root = ET.fromstring(xml)
    body = root.find(f"{{{W_NS}}}body")
    paras: list[tuple[int, str, bool]] = []
    for i, p in enumerate(body.findall(f"{{{W_NS}}}p")):
        texts: list[str] = []
        for t in p.iter(f"{{{W_NS}}}t"):
            if t.text:
                texts.append(t.text)
            if t.tail:
                texts.append(t.tail)
        text = "".join(texts).strip()
        has_img = bool(
            p.findall(f".//{{{WP_NS}}}inline") or p.findall(f".//{{{WP_NS}}}anchor")
        )
        paras.append((i, text, has_img))

    pending = [p for p in paras if "待生成" in p[1]]
    fig_caps = [p for p in paras if re.match(r"^图\s*\d", p[1])]
    imgs = [p for p in paras if p[2]]
    nonempty = [p for p in paras if p[1]]

    print("\n=== 段落统计 ===")
    print("总段落:", len(paras))
    print("非空段落:", len(nonempty))
    print("含图片段落:", len(imgs))
    print("待生成段落:", len(pending))
    print("图题注段落:", len(fig_caps))
    if imgs or pending:
        print(f"插图成功率: {len(imgs)}/{len(imgs)+len(pending)} = {100*len(imgs)/(len(imgs)+len(pending)):.1f}%")

    print("\n=== 章节标题(抽样) ===")
    for i, t, _ in paras:
        if t and ("章" in t[:20] or t.startswith("第")) and len(t) < 60:
            print(f"  [{i}] {t}")

    print("\n=== 待生成列表 ===")
    for i, t, _ in pending:
        print(f"  [{i}] {t}")

    print("\n=== 图文序列(前50个相关段) ===")
    shown = 0
    for i, t, has_img in paras:
        if has_img or "待生成" in t or re.match(r"^图\s*\d", t):
            kind = "IMG" if has_img else ("PEND" if "待生成" in t else "CAP")
            print(f"  [{i:4d}] {kind:4s} {t[:100]}")
            shown += 1
            if shown >= 50:
                break

    # image display size in docx (EMU)
    print("\n=== DOCX 中图片显示尺寸(英寸近似) ===")
    emu_per_inch = 914400
    shown = 0
    for p in body.findall(f"{{{W_NS}}}p"):
        for ext in p.findall(f".//{{{WP_NS}}}extent"):
            cx = int(ext.get("cx", 0))
            cy = int(ext.get("cy", 0))
            if cx and cy:
                w_in = cx / emu_per_inch
                h_in = cy / emu_per_inch
                print(f"  display ~{w_in:.2f}\" x {h_in:.2f}\" (ratio {w_in/h_in:.2f})")
                shown += 1
                if shown >= 15:
                    break
        if shown >= 15:
            break


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"c:\Users\h'p\Downloads\图测试.docx")
    analyze(path)
