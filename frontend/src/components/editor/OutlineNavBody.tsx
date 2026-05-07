import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Pencil, RefreshCw, Settings, Trash2 } from "lucide-react";
import type { CSSProperties } from "react";
import { useState } from "react";

import type { OutlineChapter } from "@/types/outline";

export type OutlineSelection =
  | { type: "setup" }
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
};

function chapterStatusLabel(status: OutlineChapter["status"]): string {
  if (status === "done") return "正文已完成";
  if (status === "generating") return "生成中";
  return "待撰写";
}

function ChapterRowInner({
  chapter,
  active,
  onSelect,
  onRename,
  onRegenerate,
  onDelete,
  dragHandleProps,
  style,
}: {
  chapter: OutlineChapter;
  active: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onRegenerate: () => void;
  onDelete: () => void;
  dragHandleProps?: Record<string, unknown>;
  style?: CSSProperties;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(chapter.title);

  const statusClass =
    chapter.status === "done"
      ? "outline-status-done"
      : chapter.status === "generating"
        ? "outline-status-generating"
        : "outline-status-pending";

  return (
    <div style={style} className={`outline-item ${active ? "outline-item-active" : ""} ${statusClass}`}>
      {dragHandleProps ? (
        <button type="button" className="outline-drag" aria-label="拖拽排序" {...dragHandleProps}>
          <GripVertical className="h-4 w-4 text-slate-400" />
        </button>
      ) : (
        <span className="outline-drag cursor-default opacity-40" aria-hidden>
          <GripVertical className="h-4 w-4 text-slate-400" />
        </span>
      )}
      <button type="button" className="outline-item-main" onClick={onSelect}>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1 text-left">
            {editing ? (
              <input
                className="input py-0.5 text-sm"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => {
                  setEditing(false);
                  if (draft.trim() && draft !== chapter.title) onRename(draft.trim());
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                }}
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <p className="truncate text-sm font-medium text-ink">{chapter.title}</p>
            )}
            <p className="mt-0.5 text-[11px] text-slate-500">
              {chapter.word_count ?? 0} 字 · {chapterStatusLabel(chapter.status)}
            </p>
          </div>
          <span className="shrink-0 text-xs tabular-nums text-slate-400">{chapter.index}</span>
        </div>
      </button>
      <div className="outline-item-actions">
        <button
          type="button"
          className="icon-button h-8 w-8 border-0 bg-transparent shadow-none"
          title="重命名"
          onClick={(e) => {
            e.stopPropagation();
            setDraft(chapter.title);
            setEditing(true);
          }}
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          className="icon-button h-8 w-8 border-0 bg-transparent shadow-none"
          title="重新生成"
          onClick={(e) => {
            e.stopPropagation();
            onRegenerate();
          }}
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          className="icon-button h-8 w-8 border-0 bg-transparent text-rose-600 shadow-none hover:text-rose-700"
          title="删除"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function SortableRow(
  props: Omit<Parameters<typeof ChapterRowInner>[0], "dragHandleProps" | "style">,
) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: props.chapter.id,
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.7 : 1,
  };
  return (
    <div ref={setNodeRef}>
      <ChapterRowInner
        {...props}
        dragHandleProps={{ ...attributes, ...listeners }}
        style={style}
      />
    </div>
  );
}

/** 目录列表主体（弹层与旧侧栏共用） */
export default function OutlineNavBody({
  chapters,
  selection,
  onSelect,
  onReorder,
  onRename,
  onRegenerate,
  onDelete,
  onAddChapter,
  dragDisabled,
}: OutlineNavBodyProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = chapters.findIndex((c) => c.id === active.id);
    const newIndex = chapters.findIndex((c) => c.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(chapters, oldIndex, newIndex);
    const items = reordered.map((c, i) => ({ chapter_id: c.id, new_index: i + 1 }));
    onReorder(items);
  }

  const setupActive = selection.type === "setup";

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <button
        type="button"
        className={`outline-setup-row shrink-0 ${setupActive ? "outline-item-active" : ""}`}
        onClick={() => onSelect({ type: "setup" })}
      >
        <span className="text-sm font-medium">书稿设定</span>
        <Settings className="h-4 w-4 text-slate-400" aria-hidden />
      </button>

      <p className="outline-divider shrink-0">── 大纲与章节 ──</p>

      <div className="outline-panel-scroll min-h-0">
        {chapters.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-slate-400">暂无章节，请先生成大纲。</p>
        ) : dragDisabled ? (
          <div className="space-y-2">
            {chapters.map((ch) => (
              <ChapterRowInner
                key={ch.id}
                chapter={ch}
                active={selection.type === "chapter" && selection.index === ch.index}
                onSelect={() => onSelect({ type: "chapter", index: ch.index })}
                onRename={(t) => onRename(ch.index, t)}
                onRegenerate={() => onRegenerate(ch.index)}
                onDelete={() => onDelete(ch.index)}
              />
            ))}
          </div>
        ) : (
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={chapters.map((c) => c.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {chapters.map((ch) => (
                  <SortableRow
                    key={ch.id}
                    chapter={ch}
                    active={selection.type === "chapter" && selection.index === ch.index}
                    onSelect={() => onSelect({ type: "chapter", index: ch.index })}
                    onRename={(t) => onRename(ch.index, t)}
                    onRegenerate={() => onRegenerate(ch.index)}
                    onDelete={() => onDelete(ch.index)}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        )}
      </div>

      <button type="button" className="btn-secondary mt-2 w-full shrink-0 text-sm" onClick={onAddChapter}>
        ＋ 添加章节
      </button>
    </div>
  );
}
