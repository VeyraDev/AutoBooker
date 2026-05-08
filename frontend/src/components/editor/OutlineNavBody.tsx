import { ListTree, Plus, Settings } from "lucide-react";
import { useState, type MouseEvent } from "react";

import type { OutlineChapter } from "@/types/outline";

export type OutlineSelection =
  | { type: "setup" }
  | { type: "outline_preview" }
  | { type: "chapter"; index: number };

export type OutlineNavBodyProps = {
  chapters: OutlineChapter[];
  selection: OutlineSelection;
  onSelect: (s: OutlineSelection) => void;
  onReorder: (items: { chapter_id: string; new_index: number }[]) => void;
  onRename: (chapterIndex: number, title: string) => void;
  onRegenerate: (chapterIndex: number) => void;
  onDelete: (chapterIndex: number) => void;
  onAddChapter: () => void;
  dragDisabled?: boolean;
  /** SETUP 且已有章节时显示「大纲展示」入口 */
  showOutlinePreviewNav?: boolean;
};

export default function OutlineNavBody({
  chapters,
  selection,
  onSelect,
  onAddChapter,
  showOutlinePreviewNav,
}: OutlineNavBodyProps) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  function toggleCollapse(idx: number, e: MouseEvent) {
    e.stopPropagation();
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  const setupActive = selection.type === "setup";
  const outlinePreviewActive = selection.type === "outline_preview";

  return (
    <div className="toc-root">
      <button
        type="button"
        className={`toc-setup-row ${setupActive ? "toc-active" : ""}`}
        onClick={() => onSelect({ type: "setup" })}
      >
        <Settings className="h-3.5 w-3.5 shrink-0 text-slate-400" />
        <span>书稿设定</span>
      </button>

      {showOutlinePreviewNav ? (
        <button
          type="button"
          className={`toc-setup-row ${outlinePreviewActive ? "toc-active" : ""}`}
          onClick={() => onSelect({ type: "outline_preview" })}
        >
          <ListTree className="h-3.5 w-3.5 shrink-0 text-slate-400" />
          <span>大纲展示</span>
        </button>
      ) : null}

      <div className="toc-divider">── 大纲与章节 ──</div>

      <div className="toc-list">
        {chapters.length === 0 ? (
          <p className="toc-empty">暂无章节，请先生成大纲</p>
        ) : (
          chapters.map((ch) => {
            const isCollapsed = collapsed.has(ch.index);
            const chapterActive = selection.type === "chapter" && selection.index === ch.index;
            const hasSections = ch.sections && ch.sections.length > 0;

            const statusClass =
              ch.status === "done"
                ? "toc-ch-done"
                : ch.status === "generating"
                  ? "toc-ch-generating"
                  : "toc-ch-pending";

            return (
              <div key={ch.id} className={`toc-chapter-group ${statusClass}`}>
                <div
                  className={`toc-chapter-row ${chapterActive ? "toc-active" : ""}`}
                  onClick={() => onSelect({ type: "chapter", index: ch.index })}
                >
                  <button
                    type="button"
                    className="toc-toggle"
                    onClick={(e) => hasSections && toggleCollapse(ch.index, e)}
                    aria-label={isCollapsed ? "展开" : "折叠"}
                    style={{ visibility: hasSections ? "visible" : "hidden" }}
                  >
                    {isCollapsed ? "▶" : "▼"}
                  </button>
                  <span className="toc-chapter-title">{ch.title}</span>
                  {ch.status === "generating" && <span className="toc-generating-dot" title="生成中" />}
                </div>

                {!isCollapsed &&
                  hasSections &&
                  ch.sections.map((sec, i) => (
                    <div
                      key={i}
                      className="toc-section-row"
                      onClick={() => onSelect({ type: "chapter", index: ch.index })}
                      title={sec.summary || sec.title}
                    >
                      <span className="toc-section-title">{sec.title || `${i + 1}、小节`}</span>
                    </div>
                  ))}
              </div>
            );
          })
        )}
      </div>

      <button type="button" className="toc-add-btn" onClick={onAddChapter}>
        <Plus className="h-3.5 w-3.5" />
        添加章节
      </button>
    </div>
  );
}
