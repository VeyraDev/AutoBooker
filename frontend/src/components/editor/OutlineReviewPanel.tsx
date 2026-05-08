import { Trash2 } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";

import { putOutline } from "@/api/outline";
import type { OutlineBookResponse, OutlineChapter } from "@/types/outline";

type Props = {
  bookId: string;
  targetAudience: string | null | undefined;
  outline: OutlineBookResponse;
  generating: boolean;
  onOutlinePatched: () => void;
  onStartWriting: () => void;
  onRegenerateOutline: (payload: {
    topic_override?: string | null;
    target_audience?: string | null;
  }) => Promise<void>;
  onDeleteChapter?: (chapterIndex: number) => void;
};

export default function OutlineReviewPanel({
  bookId,
  targetAudience,
  outline,
  generating,
  onOutlinePatched,
  onStartWriting,
  onRegenerateOutline,
  onDeleteChapter,
}: Props) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [metaExpanded, setMetaExpanded] = useState<Set<number>>(new Set());
  /** 本章小节是否按标题+内容分条编辑（默认合并一块展示） */
  const [sectionsDetailOpen, setSectionsDetailOpen] = useState<Set<number>>(new Set());

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

  async function updateSection(
    ch: OutlineChapter,
    sectionIndex: number,
    patch: { title?: string; summary?: string },
  ) {
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

  function handleRegenerateClick() {
    const stored = window.localStorage.getItem(`autobooker_topic_brief_${bookId}`) ?? "";
    void onRegenerateOutline({
      topic_override: stored.trim() || null,
      target_audience: targetAudience?.trim() || null,
    });
  }

  return (
    <div className="outline-review-root">
      <div className="outline-review-body outline-review-body-single">
        <div className="outline-review-main">
          <div className="outline-review-header outline-review-header-tight">
            <div>
              <h2 className="text-base font-semibold text-ink">大纲预览</h2>
              <span className="mt-0.5 block text-xs text-slate-500">
                共 {outline.chapters.length} 章 · 预估 {(totalEstWords / 10000).toFixed(1)} 万字
              </span>
            </div>
            <button
              type="button"
              className="btn-secondary shrink-0 text-sm"
              disabled={generating}
              onClick={handleRegenerateClick}
            >
              {generating ? "生成中…" : "重新生成大纲"}
            </button>
          </div>

          <div className="outline-chapter-list outline-chapter-list-tight">
            {outline.chapters.map((ch) => {
              const isCollapsed = collapsed.has(ch.index);
              const metaOpen = metaExpanded.has(ch.index);
              const detailOpen = sectionsDetailOpen.has(ch.index);

              return (
                <div key={ch.id} className="outline-chapter-card outline-chapter-card-dense">
                  <div
                    className={`outline-chapter-title-row outline-chapter-title-row-tight ${isCollapsed ? "outline-chapter-title-row-only" : ""}`}
                  >
                    <button
                      type="button"
                      className="outline-collapse-btn"
                      onClick={() => toggleCollapse(ch.index)}
                      aria-label={isCollapsed ? "展开" : "折叠"}
                    >
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
                    <span className="outline-chapter-words text-[11px] text-slate-400">
                      ~{((ch.estimated_words ?? 3000) / 1000).toFixed(0)}k
                    </span>
                    <div className="outline-chapter-actions">
                      <button
                        type="button"
                        className="outline-chip-btn outline-chip-btn-muted"
                        onClick={() => toggleSectionsDetail(ch.index)}
                      >
                        {detailOpen ? "完成编辑" : "本章编辑"}
                      </button>
                      {onDeleteChapter ? (
                        <button
                          type="button"
                          className="outline-chip-btn outline-chip-btn-danger"
                          onClick={() => onDeleteChapter(ch.index)}
                        >
                          删除章
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {!isCollapsed && (
                    <div className="outline-chapter-body-stack">
                      {!metaOpen ? (
                        <button
                          type="button"
                          className="outline-meta-expand-bar outline-meta-expand-bar-flush"
                          onClick={() => toggleMetaExpand(ch.index)}
                        >
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
                          <button
                            type="button"
                            className="outline-meta-collapse-link"
                            onClick={() => toggleMetaExpand(ch.index)}
                          >
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
                                    i > 0 &&
                                    ch.sections.slice(0, i).some((x) => (x.title ?? "").trim() || (x.summary ?? "").trim());
                                  return (
                                    <span key={`${ch.id}-merged-${i}`}>
                                      {showSep ? "\n" : null}
                                      {t ? (
                                        <span className="outline-sections-merged-title">{t}</span>
                                      ) : null}
                                      {t && u ? "\n" : null}
                                      {u ? (
                                        <span className="outline-sections-merged-summary">{u}</span>
                                      ) : null}
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
                            <button
                              type="button"
                              className="outline-add-section-bottom"
                              onClick={() => void addSection(ch)}
                            >
                              + 小节
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="outline-review-footer outline-review-footer-actions outline-review-footer-tight">
        <button
          type="button"
          className="btn-primary px-6 py-2 text-sm"
          disabled={generating || outline.chapters.length === 0}
          onClick={() => onStartWriting()}
        >
          确认大纲，开始生成全书 →
        </button>
        <span className="text-xs text-slate-500">
          {outline.chapters.length} 章 · 预估 {(totalEstWords / 10000).toFixed(1)} 万字
        </span>
      </div>
    </div>
  );
}
