import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ListTree, Loader2, Play, Plus, RotateCcw, Settings } from "lucide-react";

import type { ChapterGenMode } from "@/lib/chapterGenMode";
import { chapterStreamPrimaryIntent } from "@/lib/chapterStreamPrimaryIntent";
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
  /** 正文条同源逻辑：本章主生成按钮 */
  onChapterStreamPrimary: (chapterIndex: number) => void;
  chapterBodyByIndex?: Record<number, boolean>;
  onDelete: (chapterIndex: number) => void;
  onAddChapter: () => void;
  dragDisabled?: boolean;
  showOutlinePreviewNav?: boolean;
  writingMode?: boolean;
  streamingChapterIndex?: number | null;
  /** 写作：打开全屏大纲 */
  onOpenGlobalOutline?: () => void;
  chapterGenMode?: ChapterGenMode;
  /** 全书批量是否在跑（与顶栏批量按钮一致） */
  autoGenerating?: boolean;
};

function SortableChapterBlock({
  ch,
  isCollapsed,
  hasSections,
  chapterActive,
  streamingHere,
  toggleCollapse,
  onSelect,
  onRename,
  onChapterStreamPrimary,
  streamingChapterIndex,
  hasChapterBody,
  chapterGenMode,
  autoGenerating,
  onDelete,
  dragDisabled,
  editingIndex,
  setEditingIndex,
  draftTitle,
  setDraftTitle,
}: {
  ch: OutlineChapter;
  isCollapsed: boolean;
  hasSections: boolean;
  chapterActive: boolean;
  streamingHere: boolean;
  toggleCollapse: (idx: number, e: MouseEvent) => void;
  onSelect: (s: OutlineSelection) => void;
  onRename: (chapterIndex: number, title: string) => void;
  onChapterStreamPrimary: (chapterIndex: number) => void;
  streamingChapterIndex: number | null;
  hasChapterBody: boolean;
  chapterGenMode: ChapterGenMode;
  autoGenerating: boolean;
  onDelete: (chapterIndex: number) => void;
  dragDisabled: boolean;
  editingIndex: number | null;
  setEditingIndex: (i: number | null) => void;
  draftTitle: string;
  setDraftTitle: (s: string) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: ch.id, disabled: dragDisabled });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.85 : 1,
  };

  const statusClass =
    ch.status === "done"
      ? "toc-ch-done"
      : ch.status === "generating" || streamingHere
        ? "toc-ch-generating"
        : "toc-ch-pending";

  const editing = editingIndex === ch.index;

  const streamIntent = chapterStreamPrimaryIntent(ch, {
    streamingChapterIndex,
    chapterGenMode,
    autoGenerating,
    hasBody: hasChapterBody,
  });

  return (
    <div ref={setNodeRef} style={style} className={`toc-chapter-group ${statusClass}`}>
      <div
        className={`toc-chapter-row group/row ${chapterActive ? "toc-active" : ""}`}
        onClick={() => !editing && onSelect({ type: "chapter", index: ch.index })}
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

        {editing ? (
          <input
            className="toc-title-input"
            value={draftTitle}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setDraftTitle(e.target.value)}
            onBlur={() => {
              const t = draftTitle.trim();
              if (t && t !== ch.title) onRename(ch.index, t);
              setEditingIndex(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") {
                setDraftTitle(ch.title);
                setEditingIndex(null);
              }
            }}
            autoFocus
          />
        ) : (
          <span className="toc-chapter-title">{ch.title}</span>
        )}

        {(ch.status === "generating" || streamingHere) && (
          <span className="toc-generating-dot" title="生成中" />
        )}

        <div className="toc-row-actions">
          <button
            type="button"
            className="toc-row-icon"
            title="拖拽排序"
            {...attributes}
            {...listeners}
            onClick={(e) => e.stopPropagation()}
          >
            ⠿
          </button>
          <button
            type="button"
            className="toc-row-icon"
            title="重命名"
            onClick={(e) => {
              e.stopPropagation();
              setDraftTitle(ch.title);
              setEditingIndex(ch.index);
            }}
          >
            ✎
          </button>
          <button
            type="button"
            className="toc-row-icon toc-row-icon--stream"
            title={
              streamIntent === "generate"
                ? "生成本章"
                : streamIntent === "regenerate"
                  ? "重新生成"
                  : streamIntent === "busy"
                    ? "生成中…"
                    : "等待中"
            }
            aria-label={
              streamIntent === "generate"
                ? "生成本章"
                : streamIntent === "regenerate"
                  ? "重新生成"
                  : streamIntent === "busy"
                    ? "生成中"
                    : "等待生成"
            }
            disabled={streamIntent === "busy" || streamIntent === "waiting"}
            onClick={(e) => {
              e.stopPropagation();
              if (streamIntent === "busy" || streamIntent === "waiting") return;
              onChapterStreamPrimary(ch.index);
            }}
          >
            {streamIntent === "busy" ? (
              <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-violet-500" aria-hidden />
            ) : streamIntent === "waiting" ? (
              <span className="text-xs font-semibold tracking-tight text-slate-400" aria-hidden>
                ⋯
              </span>
            ) : streamIntent === "generate" ? (
              <Play className="h-3.5 w-3.5 shrink-0 fill-current text-emerald-600" aria-hidden />
            ) : (
              <RotateCcw className="h-3.5 w-3.5 shrink-0 text-slate-600" aria-hidden />
            )}
          </button>
          <button
            type="button"
            className="toc-row-icon text-red-600 hover:text-red-700"
            title="删除章节"
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm("确定删除该章节？")) onDelete(ch.index);
            }}
          >
            🗑
          </button>
        </div>
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
}

export default function OutlineNavBody({
  chapters,
  selection,
  onSelect,
  onReorder,
  onRename,
  onChapterStreamPrimary,
  chapterBodyByIndex = {},
  onDelete,
  onAddChapter,
  showOutlinePreviewNav,
  writingMode,
  streamingChapterIndex = null,
  onOpenGlobalOutline,
  chapterGenMode = "auto",
  autoGenerating = false,
  dragDisabled = false,
}: OutlineNavBodyProps) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draftTitle, setDraftTitle] = useState("");

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function toggleCollapse(idx: number, e: MouseEvent) {
    e.stopPropagation();
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  function handleDragEnd(e: DragEndEvent) {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const ids = chapters.map((c) => c.id);
    const oldIndex = ids.indexOf(String(active.id));
    const newIndex = ids.indexOf(String(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const newOrder = arrayMove(chapters, oldIndex, newIndex);
    const items = newOrder.map((c, i) => ({ chapter_id: c.id, new_index: i + 1 }));
    void onReorder(items);
  }

  const setupActive = selection.type === "setup";
  const outlinePreviewActive = selection.type === "outline_preview";

  const chapterIds = chapters.map((c) => c.id);

  const writingStickyTop =
    writingMode && onOpenGlobalOutline ? (
      <div className="toc-writing-strip -mx-1 border-b border-slate-200/35 bg-[var(--bg-page)] px-1 pb-2 pt-0">
        <div className="toc-writing-header">
          <button type="button" className="toc-writing-header-btn" onClick={() => onOpenGlobalOutline()}>
            <ListTree className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden />
            返回全局大纲
          </button>
          <button type="button" className="toc-writing-header-btn toc-writing-header-btn-primary" onClick={onAddChapter}>
            <Plus className="h-3.5 w-3.5" aria-hidden />
            添加章节
          </button>
        </div>
        <div className="toc-divider toc-divider-tight mt-1">章节</div>

        <div className="toc-divider toc-divider-line mt-2" aria-hidden />
      </div>
    ) : null;

  const chapterListInner =
    chapters.length === 0 ? (
      <p className="toc-empty">暂无章节</p>
    ) : writingMode ? (
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={chapterIds} strategy={verticalListSortingStrategy}>
          {chapters.map((ch) => {
            const isCollapsed = collapsed.has(ch.index);
            const chapterActive = selection.type === "chapter" && selection.index === ch.index;
            const hasSections = ch.sections && ch.sections.length > 0;
            const streamingHere = streamingChapterIndex != null && streamingChapterIndex === ch.index;
            return (
              <SortableChapterBlock
                key={ch.id}
                ch={ch}
                isCollapsed={isCollapsed}
                hasSections={!!hasSections}
                chapterActive={chapterActive}
                streamingHere={streamingHere}
                toggleCollapse={toggleCollapse}
                onSelect={onSelect}
                onRename={onRename}
                onChapterStreamPrimary={onChapterStreamPrimary}
                streamingChapterIndex={streamingChapterIndex}
                hasChapterBody={chapterBodyByIndex[ch.index] ?? false}
                chapterGenMode={chapterGenMode}
                autoGenerating={autoGenerating}
                onDelete={onDelete}
                dragDisabled={dragDisabled}
                editingIndex={editingIndex}
                setEditingIndex={setEditingIndex}
                draftTitle={draftTitle}
                setDraftTitle={setDraftTitle}
              />
            );
          })}
        </SortableContext>
      </DndContext>
    ) : (
      chapters.map((ch) => {
        const isCollapsed = collapsed.has(ch.index);
        const chapterActive = selection.type === "chapter" && selection.index === ch.index;
        const hasSections = ch.sections && ch.sections.length > 0;
        const streamingHere = streamingChapterIndex != null && streamingChapterIndex === ch.index;
        const statusClass =
          ch.status === "done"
            ? "toc-ch-done"
            : ch.status === "generating" || streamingHere
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
              {(ch.status === "generating" || streamingHere) && (
                <span className="toc-generating-dot" title="生成中" />
              )}
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
    );

  return (
    <div className={`toc-root ${writingMode ? "toc-root-writing-layout" : ""}`}>
      {writingStickyTop}

      {!writingMode ? (
        <>
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
        </>
      ) : null}

      {!writingMode ? <div className="toc-divider toc-divider-line my-1" aria-hidden /> : null}

      {writingMode ? (
        <div className="toc-scroll-writing">
          <div className="toc-list">{chapterListInner}</div>
        </div>
      ) : (
        <div className="toc-list">{chapterListInner}</div>
      )}

      {!writingMode || !onOpenGlobalOutline ? (
        <button type="button" className="toc-add-btn" onClick={onAddChapter}>
          <Plus className="h-3.5 w-3.5" />
          添加章节
        </button>
      ) : null}
    </div>
  );
}
