import type { Editor } from "@tiptap/core";

import {
  figureFileVersion,
  type FigureOut,
  type FigureStatus,
  type FigureType,
} from "@/api/figures";

function figureTypeKey(t: string): string {
  const x = t.toLowerCase();
  if (x === "flowchart" || x === "chart" || x === "screenshot") return x;
  return "figure";
}

function str(v: unknown): string {
  return String(v ?? "").trim();
}

function attrsFromFigure(
  current: Record<string, unknown>,
  fig: FigureOut,
): Record<string, unknown> | null {
  const next: Record<string, unknown> = {
    figureId: fig.id,
    fileUrl: fig.file_url ?? "",
    svgUrl: fig.svg_url ?? "",
    figureNumber: fig.figure_number ?? "",
    status: fig.status as FigureStatus,
    caption: fig.caption ?? "",
    figureType: fig.figure_type as FigureType,
    rawAnnotation: fig.raw_annotation ?? "",
  };
  const urlChanged = str(current.fileUrl) !== str(next.fileUrl) || str(current.svgUrl) !== str(next.svgUrl);
  const statusChanged = str(current.status) !== str(next.status);
  const idMissing = !str(current.figureId);
  const currentVersion = Number(current.fileVersion ?? 0) || 0;
  const serverVersion = figureFileVersion(fig.updated_at, Date.now());
  next.fileVersion = Math.max(currentVersion, serverVersion);

  const keys = [
    "figureId",
    "fileUrl",
    "svgUrl",
    "figureNumber",
    "status",
    "caption",
    "figureType",
    "rawAnnotation",
    "fileVersion",
  ] as const;
  for (const k of keys) {
    if (str(current[k]) !== str(next[k])) return next;
  }
  return null;
}

/** 文档中是否存在未绑定 figureId 的 figureBlock */
export function hasUnlinkedFigureBlocks(doc: Record<string, unknown> | null | undefined): boolean {
  if (!doc || doc.type !== "doc") return false;
  let found = false;

  function walk(node: unknown) {
    if (found || !node || typeof node !== "object") return;
    const n = node as Record<string, unknown>;
    if (n.type === "figureBlock") {
      if (!str((n.attrs as Record<string, unknown> | undefined)?.figureId)) {
        found = true;
      }
      return;
    }
    if (Array.isArray(n.content)) {
      for (const child of n.content) walk(child);
    }
  }

  walk(doc);
  return found;
}

/** 将服务端图表列表写回编辑器：按 figureId 更新，并为无 ID 占位块按描述/顺序绑定。 */
export function syncFigureBlocksWithServer(editor: Editor, items: FigureOut[]): number {
  if (!items.length) return 0;

  const byId = new Map(items.map((f) => [f.id, f]));
  const used = new Set<string>();
  const pending: { pos: number; attrs: Record<string, unknown> }[] = [];

  type Orphan = { pos: number; raw: string; typeKey: string; attrs: Record<string, unknown> };
  const orphans: Orphan[] = [];

  editor.state.doc.descendants((node, pos) => {
    if (node.type.name !== "figureBlock") return;
    const current = { ...(node.attrs as Record<string, unknown>) };
    const fid = str(current.figureId);
    if (fid && byId.has(fid)) {
      used.add(fid);
      const patch = attrsFromFigure(current, byId.get(fid)!);
      if (patch) pending.push({ pos, attrs: { ...current, ...patch } });
      return;
    }
    orphans.push({
      pos,
      raw: str(current.rawAnnotation ?? current.caption),
      typeKey: figureTypeKey(String(current.figureType ?? "figure")),
      attrs: current,
    });
  });

  for (const o of orphans) {
    const fig =
      items.find(
        (f) =>
          !used.has(f.id) &&
          figureTypeKey(f.figure_type) === o.typeKey &&
          str(f.raw_annotation) === o.raw,
      ) ??
      items.find((f) => !used.has(f.id) && figureTypeKey(f.figure_type) === o.typeKey);
    if (!fig) continue;
    used.add(fig.id);
    const patch = attrsFromFigure(o.attrs, fig);
    if (patch) pending.push({ pos: o.pos, attrs: { ...o.attrs, ...patch } });
  }

  if (!pending.length) return 0;

  let tr = editor.state.tr;
  for (const { pos, attrs } of pending) {
    tr = tr.setNodeMarkup(pos, undefined, attrs);
  }
  tr.setMeta("addToHistory", false);
  editor.view.dispatch(tr);
  return pending.length;
}
