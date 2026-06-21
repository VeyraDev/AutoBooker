"""FLOWCHART pipeline: LLM → DOT → Graphviz PNG."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from app.config import settings
from app.llm.client import LLMClient
from app.prompts.flowchart import FLOWCHART_PROMPT

_TOPOLOGY_KEYWORDS = ("拓扑", "网络", "节点", "松散", "neato", "fdp", "集群")

_DEFAULT_GRAPHVIZ_BIN_DIRS = (
    Path(r"C:\Program Files\Graphviz\bin"),
    Path(r"C:\Program Files (x86)\Graphviz\bin"),
)


def _ensure_graphviz_on_path() -> None:
    """Cursor/旧终端可能未继承安装后的 PATH，此处补全 dot 所在目录。"""
    if shutil.which("dot"):
        return
    candidates: list[Path] = []
    custom = settings.GRAPHVIZ_BIN_DIR.strip()
    if custom:
        candidates.append(Path(custom))
    candidates.extend(_DEFAULT_GRAPHVIZ_BIN_DIRS)
    for bin_dir in candidates:
        dot_exe = bin_dir / ("dot.exe" if os.name == "nt" else "dot")
        if dot_exe.is_file():
            bin_str = str(bin_dir.resolve())
            path = os.environ.get("PATH", "")
            if bin_str.casefold() not in path.casefold():
                os.environ["PATH"] = bin_str + os.pathsep + path
            if os.name == "nt":
                win_fonts = str(Path(r"C:\Windows\Fonts").resolve())
                os.environ.setdefault("GDFONTPATH", win_fonts)
            return


def _pick_cjk_font() -> str:
    """选取本机可用的中文 TrueType 字体名（供 Graphviz/Pango 使用）。"""
    if os.name == "nt":
        fonts = Path(r"C:\Windows\Fonts")
        if (fonts / "msyh.ttc").is_file() or (fonts / "msyhbd.ttc").is_file():
            return "Microsoft YaHei"
        if (fonts / "simhei.ttf").is_file():
            return "SimHei"
        if (fonts / "simsun.ttc").is_file():
            return "SimSun"
    return "Noto Sans CJK SC"


def _inject_cjk_fonts(dot_source: str) -> str:
    """在 DOT 图级注入 UTF-8 与中文字体，避免渲染出方框/乱码。"""
    dot = dot_source.strip()
    if not dot:
        return dot
    font = _pick_cjk_font()
    defaults = (
        f'graph [fontname="{font}", fontsize=12, charset="UTF-8", ranksep=0.85, nodesep=0.58, splines=ortho, overlap=false, bgcolor="white", pad=0.25];\n'
        f'node [fontname="{font}", fontsize=11, charset="UTF-8", shape=box, style="rounded,filled", fillcolor="#EFF6FF", color="#2563EB", penwidth=1.35, margin="0.14,0.08"];\n'
        f'edge [fontname="{font}", fontsize=10, charset="UTF-8", color="#64748B", arrowsize=0.72, penwidth=1.15];\n'
    )
    m = re.match(
        r"(?is)^(\s*(?:strict\s+)?(?:di)?graph\s+(?:\"[^\"]+\"|\w+)?\s*\{)",
        dot,
    )
    if m:
        pos = m.end()
        return f"{dot[:pos]}\n  {defaults.replace(chr(10), chr(10) + '  ')}{dot[pos:]}"
    return f"{defaults}\n{dot}"


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    m = re.search(r"```(?:dot|graphviz)?\s*([\s\S]*?)```", t, re.I)
    if m:
        return m.group(1).strip()
    if t.lower().startswith("digraph") or t.lower().startswith("graph "):
        return t
    return t


def llm_to_dot(description: str, *, model: str, book_type: str = "") -> str:
    client = LLMClient()
    ctx = f"书型：{book_type}\n" if book_type else ""
    user_msg = f"{ctx}{FLOWCHART_PROMPT.format(description=description)}"
    out = client.chat_completion(
        [
            {"role": "system", "content": "只输出 Graphviz DOT 代码，不要 Markdown 或解释。"},
            {"role": "user", "content": user_msg},
        ],
        model=model,
        max_tokens=4096,
        temperature=0.45,
    )
    return _strip_code_fence(out)


def _pick_engine(description: str) -> str:
    low = description.lower()
    if any(k in description or k in low for k in _TOPOLOGY_KEYWORDS):
        return "neato"
    return "dot"


def _resolve_rendered_png(base_path: Path, expected: Path) -> Path:
    """Graphviz 使用 renderer=cairo 时可能输出 .cairo.png，统一落到 expected。

    必须先检查本次 render 产物，不能把已存在的 expected 旧文件当成成功结果。
    """
    rendered_first = [
        Path(str(base_path) + ".cairo.png"),
        Path(str(base_path) + ".png"),
        base_path.with_name(base_path.name + ".cairo.png"),
        base_path.with_suffix(".png"),
    ]
    seen: set[Path] = set()
    for path in rendered_first:
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            continue
        expected.parent.mkdir(parents=True, exist_ok=True)
        if expected.is_file() and path.resolve() != expected.resolve():
            expected.unlink()
        if path.resolve() != expected.resolve():
            path.replace(expected)
        return expected
    if expected.is_file():
        return expected
    raise RuntimeError(f"Graphviz 未生成 PNG（已检查: {', '.join(str(p) for p in seen)}）")


def render_flowchart(dot_source: str, output_path: Path, *, description: str = "") -> Path:
    import graphviz
    from graphviz.backend.execute import ExecutableNotFound

    _ensure_graphviz_on_path()
    engine = _pick_engine(description)
    src = graphviz.Source(dot_source, encoding="utf-8")
    base_path = output_path.with_suffix("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # 清理上次渲染残留，避免误用旧 PNG
    for stale in (
        output_path,
        Path(str(base_path) + ".png"),
        Path(str(base_path) + ".cairo.png"),
        base_path.with_suffix(".png"),
    ):
        if stale.is_file():
            stale.unlink()
    try:
        src.render(
            str(base_path),
            format="png",
            engine=engine,
            renderer="cairo",
            cleanup=True,
        )
    except ExecutableNotFound as e:
        raise RuntimeError(
            "未找到 Graphviz 可执行文件 dot。请安装 Graphviz 并将 bin 目录加入 PATH，"
            "安装后重启终端与后端。Windows: winget install Graphviz.Graphviz"
        ) from e
    return _resolve_rendered_png(base_path, output_path)


def generate_flowchart(
    description: str,
    output_path: Path,
    *,
    model: str,
    book_type: str = "",
    image_type: str = "process_flow",
) -> tuple[str, Path]:
    from app.services.figures.render.legacy_svg.figure_validate import merge_validation_report

    dot = _inject_cjk_fonts(llm_to_dot(description, model=model, book_type=book_type))
    report = merge_validation_report(dot, description, image_type)
    if not report["ok"] and image_type != "process_flow":
        dot = _inject_cjk_fonts(llm_to_dot(
            description + "\n\n请修正：节点对齐、避免重叠、控制节点文字长度。",
            model=model,
            book_type=book_type,
        ))
    png = render_flowchart(dot, output_path, description=description)
    return dot, png
