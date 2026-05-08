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
import { GripVertical, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";

import { putOutline } from "@/api/outline";
import type { OutlineBookResponse, OutlineChapter } from "@/types/outline";

type Props = {
  bookId: string;
  outline: OutlineBookResponse;
  onOutlinePatched: () => void;
  onDeleteChapter?: (chapterIndex: number) => void;
  onReorder: (items: { chapter_id: string; new_index: number }[]) => void | Promise<void>;
  dragDisabled?: boolean;
};

function SortableChapterCard({
  ch,
  onDeleteChapter,
  dragDisabled,
  collapsed,
  metaExpanded,
  sectionsDetailOpen,
  toggleCollapse,
  toggleMetaExpand,
  toggleSectionsDetail,
  saveChapterInline,
  saveKeyPointsFromText,
  addSection,
  updateSection,
  removeSection,
}: {
  ch: OutlineChapter;
  onDeleteChapter?: (chapterIndex: number) => void;
  dragDisabled: boolean;
  collapsed: Set<number>;
  metaExpanded: Set<number>;
  sectionsDetailOpen: Set<number>;
  toggleCollapse: (idx: number) => void;
  toggleMetaExpand: (idx: number) => void;
  toggleSectionsDetail: (idx: number) => void;
  saveChapterInline: (ch: OutlineChapter, patch: Partial<OutlineChapter>) => Promise<void>;
  saveKeyPointsFromText: (ch: OutlineChapter, text: string) => Promise<void>;
  addSection: (ch: OutlineChapter) => Promise<void>;
  updateSection: (ch: OutlineChapter, sectionIndex: number, patch: { title?: string; summary?: string }) => Promise<void>;
  removeSection: (ch: OutlineChapter, sectionIndex: number) => Promise<void>;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: ch.id, disabled: dragDisabled });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.85 : 1,
  };

  const isCollapsed = collapsed.has(ch.index);
  const metaOpen = metaExpanded.has(ch.index);
  const detailOpen = sectionsDetailOpen.has(ch.index);

  const [estDraft, setEstDraft] = useState(String(ch.estimated_words ?? 3000));

  useEffect(() => {
    setEstDraft(String(ch.estimated_words ?? 3000));
  }, [ch.id, ch.estimated_words]);

  return (
    <div ref={setNodeRef} style={style} className="outline-chapter-card outline-chapter-card-dense group">
      <div
        className={`outline-chapter-title-row outline-chapter-title-row-tight ${isCollapsed ? "outline-chapter-title-row-only" : ""}`}
      >
        {!dragDisabled ? (
          <button
            type="button"
            className="outline-drag mr-0.5 shrink-0 cursor-grab touch-none active:cursor-grabbing"
            aria-label="拖拽排序"
            {...attributes}
            {...listeners}
          >
            <GripVertical className="h-4 w-4" />
          </button>
        ) : null}
        <button type="button" className="outline-collapse-btn" onClick={() => toggleCollapse(ch.index)} aria-label={isCollapsed ? "展开" : "折叠"}>
          {isCollapsed ? "▶" : "▼"}
        </button>
        <input
          className="outline-chapter-title-input"
          defaultValue={ch.title}
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== ch.title) void saveChapterInline(ch, { title: v });
          }}
        />
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          <span className="text-[10px] text-slate-400">预估字数</span>
          <div className="flex items-center gap-1">
            <input
              type="range"
              min={500}
              max={30000}
              step={100}
              className="h-1 w-20 cursor-pointer accent-violet-600"
              value={Number(estDraft) || 3000}
              onChange={(e) => setEstDraft(e.target.value)}
              onMouseUp={() => {
                const n = parseInt(estDraft, 10);
                if (!Number.isNaN(n) && n >= 100 && n !== (ch.estimated_words ?? 3000)) {
                  void saveChapterInline(ch, { estimated_words: n });
                }
              }}
            />
            <input
              type="number"
              min={100}
              step={100}
              className="w-14 rounded border border-slate-200 px-1 py-0.5 text-[11px]"
              value={estDraft}
              onChange={(e) => setEstDraft(e.target.value)}
              onBlur={() => {
                const n = parseInt(estDraft, 10);
                if (!Number.isNaN(n) && n >= 100 && n !== (ch.estimated_words ?? 3000)) {
                  void saveChapterInline(ch, { estimated_words: n });
                }
              }}
            />
          </div>
        </div>
        <div className="outline-chapter-actions">
          <button type="button" className="outline-chip-btn outline-chip-btn-muted" onClick={() => toggleSectionsDetail(ch.index)}>
            {detailOpen ? "完成编辑" : "本章编辑"}
          </button>
          {onDeleteChapter ? (
            <button
              type="button"
              className="outline-chip-btn outline-chip-btn-danger opacity-0 transition-opacity group-hover:opacity-100"
              onClick={() => {
                if (!window.confirm(`确定删除「${ch.title}」？此操作不可撤销。`)) return;
                onDeleteChapter(ch.index);
              }}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>

      {!isCollapsed && (
        <div className="outline-chapter-body-stack">
          {!metaOpen ? (
            <button type="button" className="outline-meta-expand-bar outline-meta-expand-bar-flush" onClick={() => toggleMetaExpand(ch.index)}>
              展开摘要与论点 ▼
            </button>
          ) : (
            <div className="outline-meta-vertical">
              <div className="outline-inline-stack outline-inline-stack-tight">
                <span className="outline-inline-label">摘要</span>
                <textarea
                  key={`sum-${ch.id}-${(ch.summary ?? "").slice(0, 24)}`}
                  className="outline-plain-textarea"
                  rows={3}
                  defaultValue={ch.summary ?? ""}
                  placeholder="本章摘要，失焦保存"
                  onBlur={(e) => {
                    const v = e.target.value.trim();
                    if (v !== (ch.summary ?? "")) void saveChapterInline(ch, { summary: v });
                  }}
                />
              </div>
              <div className="outline-inline-stack outline-inline-stack-tight">
                <span className="outline-inline-label">核心论点（每行一条）</span>
                <textarea
                  key={`kp-${ch.id}-${(ch.key_points ?? []).length}`}
                  className="outline-plain-textarea"
                  rows={4}
                  defaultValue={(ch.key_points ?? []).join("\n")}
                  placeholder={"每行一条论点"}
                  onBlur={(e) => void saveKeyPointsFromText(ch, e.target.value)}
                />
              </div>
              <button type="button" className="outline-meta-collapse-link" onClick={() => toggleMetaExpand(ch.index)}>
                收起摘要与论点 ▲
              </button>
            </div>
          )}

          <div className="outline-sections-plain">
            <span className="outline-inline-label">小节</span>

            {!detailOpen ? (
              <div className="outline-sections-merged">
                {ch.sections.some((s) => (s.title ?? "").trim() || (s.summary ?? "").trim()) ? (
                  <div className="outline-sections-merged-body">
                    {ch.sections.map((sec, i) => {
                      const t = (sec.title ?? "").trim();
                      const u = (sec.summary ?? "").trim();
                      if (!t && !u) return null;
                      const showSep =
                        i > 0 && ch.sections.slice(0, i).some((x) => (x.title ?? "").trim() || (x.summary ?? "").trim());
                      return (
                        <span key={`${ch.id}-merged-${i}`}>
                          {showSep ? "\n" : null}
                          {t ? <span className="outline-sections-merged-title">{t}</span> : null}
                          {t && u ? "\n" : null}
                          {u ? <span className="outline-sections-merged-summary">{u}</span> : null}
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <p className="outline-section-empty-plain">暂无小节</p>
                )}
              </div>
            ) : (
              <>
                {ch.sections.length === 0 ? (
                  <p className="outline-section-empty-plain">暂无小节，可在下方添加</p>
                ) : (
                  <ul className="outline-section-plain-list">
                    {ch.sections.map((sec, i) => (
                      <li key={`${ch.id}-sec-${i}`} className="outline-section-plain-item outline-section-plain-item-row">
                        <div className="outline-section-inline-fields">
                          <input
                            className="outline-section-title-input"
                            defaultValue={sec.title}
                            placeholder="小节标题"
                            onBlur={(e) => {
                              const v = e.target.value.trim();
                              if (v !== sec.title) void updateSection(ch, i, { title: v });
                            }}
                          />
                          <textarea
                            className="outline-plain-textarea outline-plain-textarea-compact"
                            rows={2}
                            defaultValue={sec.summary ?? ""}
                            placeholder="小节说明（可选）"
                            onBlur={(e) => {
                              const v = e.target.value.trim();
                              if (v !== (sec.summary ?? "")) void updateSection(ch, i, { summary: v });
                            }}
                          />
                        </div>
                        <button
                          type="button"
                          className="outline-section-delete-btn"
                          title="删除小节"
                          aria-label="删除小节"
                          onClick={() => void removeSection(ch, i)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <button type="button" className="outline-add-section-bottom" onClick={() => void addSection(ch)}>
                  + 小节
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function OutlineChapterListEditor({
  bookId,
  outline,
  onOutlinePatched,
  onDeleteChapter,
  onReorder,
  dragDisabled = false,
}: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [metaExpanded, setMetaExpanded] = useState<Set<number>>(new Set());
  const [sectionsDetailOpen, setSectionsDetailOpen] = useState<Set<number>>(new Set());

  const ordered = useMemo(
    () => [...outline.chapters].sort((a, b) => a.index - b.index),
    [outline.chapters],
  );

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function toggleCollapse(idx: number) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  function toggleMetaExpand(idx: number) {
    setMetaExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  function toggleSectionsDetail(idx: number) {
    setSectionsDetailOpen((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  async function saveChapterInline(ch: OutlineChapter, patch: Partial<OutlineChapter>) {
    await putOutline(bookId, {
      chapters: [{ index: ch.index, ...patch }],
    });
    onOutlinePatched();
  }

  async function addSection(ch: OutlineChapter) {
    const nextSections = [...ch.sections, { title: "新小节", summary: "" }];
    await saveChapterInline(ch, { sections: nextSections });
    toast.success("已添加小节");
  }

  async function updateSection(ch: OutlineChapter, sectionIndex: number, patch: { title?: string; summary?: string }) {
    const nextSections = ch.sections.map((s, i) => (i === sectionIndex ? { ...s, ...patch } : s));
    await saveChapterInline(ch, { sections: nextSections });
  }

  async function removeSection(ch: OutlineChapter, sectionIndex: number) {
    if (!window.confirm("确定删除该小节？")) return;
    const nextSections = ch.sections.filter((_, i) => i !== sectionIndex);
    await saveChapterInline(ch, { sections: nextSections });
    toast.success("已删除小节");
  }

  async function saveKeyPointsFromText(ch: OutlineChapter, text: string) {
    const key_points = text
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const same = JSON.stringify(key_points) === JSON.stringify(ch.key_points ?? []);
    if (same) return;
    await saveChapterInline(ch, { key_points });
  }

  const totalEstWords = outline.chapters.reduce((s, c) => s + (c.estimated_words ?? 0), 0);

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = ordered.findIndex((c) => c.id === active.id);
    const newIndex = ordered.findIndex((c) => c.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const nextOrder = arrayMove(ordered, oldIndex, newIndex);
    const items = nextOrder.map((c, i) => ({ chapter_id: c.id, new_index: i + 1 }));
    await onReorder(items);
  }

  return (
    <div className="outline-chapter-list-editor">
      <p className="mb-3 text-xs text-slate-500">
        共 {outline.chapters.length} 章 · 预估全书 {totalEstWords.toLocaleString()} 字（约 {(totalEstWords / 10000).toFixed(1)} 万字）
      </p>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleDragEnd(e)}>
        <SortableContext items={ordered.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          <div className="outline-chapter-list outline-chapter-list-tight space-y-2">
            {ordered.map((ch) => (
              <SortableChapterCard
                key={ch.id}
                ch={ch}
                onDeleteChapter={onDeleteChapter}
                dragDisabled={dragDisabled}
                collapsed={collapsed}
                metaExpanded={metaExpanded}
                sectionsDetailOpen={sectionsDetailOpen}
                toggleCollapse={toggleCollapse}
                toggleMetaExpand={toggleMetaExpand}
                toggleSectionsDetail={toggleSectionsDetail}
                saveChapterInline={saveChapterInline}
                saveKeyPointsFromText={saveKeyPointsFromText}
                addSection={addSection}
                updateSection={updateSection}
                removeSection={removeSection}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
