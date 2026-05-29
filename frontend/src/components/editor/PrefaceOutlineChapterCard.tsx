import { useQuery, useQueryClient } from "@tanstack/react-query";

import { useEffect, useState } from "react";

import toast from "react-hot-toast";



import { getPreface, putPreface, type PrefaceData } from "@/api/preface";



type Props = {

  bookId: string;

};



/** 与 OutlineChapterListEditor 章节卡片同款的紧凑前言行 */

export default function PrefaceOutlineChapterCard({ bookId }: Props) {

  const qc = useQueryClient();

  const prefaceQuery = useQuery({

    queryKey: ["preface", bookId],

    queryFn: () => getPreface(bookId),

  });

  const pf = prefaceQuery.data ?? null;

  const [collapsed, setCollapsed] = useState(false);

  const [briefOpen, setBriefOpen] = useState(true);

  const [brief, setBrief] = useState("");

  const [targetWords, setTargetWords] = useState("3000");



  useEffect(() => {

    if (!pf) return;

    setBrief(pf.brief || "");

    setTargetWords(String(pf.target_words || 3000));

  }, [pf?.brief, pf?.target_words]);



  async function savePatch(patch: Partial<PrefaceData>) {

    const data = await putPreface(bookId, patch);

    qc.setQueryData(["preface", bookId], data);

  }



  async function disablePreface() {

    const data = await putPreface(bookId, { enabled: false });

    qc.setQueryData(["preface", bookId], data);

    toast.success("已关闭本书前言");

  }



  if (prefaceQuery.isPending) return null;

  if (!pf) return null;



  if (!pf.enabled) {

    return (

      <div className="outline-chapter-card outline-chapter-card-dense">

        <div className="outline-chapter-title-row outline-chapter-title-row-tight outline-chapter-title-row-only">

          <span className="outline-collapse-btn opacity-30" aria-hidden>

            ▶

          </span>

          <span className="outline-chapter-title-input cursor-default bg-transparent font-medium text-ink">前言</span>

          <div className="outline-chapter-actions">

            <button

              type="button"

              className="outline-chip-btn outline-chip-btn-muted"

              onClick={() => void putPreface(bookId, { enabled: true }).then((data) => qc.setQueryData(["preface", bookId], data))}

            >

              启用前言

            </button>

          </div>

        </div>

      </div>

    );

  }



  return (

    <div className="outline-chapter-card outline-chapter-card-dense group">

      <div

        className={`outline-chapter-title-row outline-chapter-title-row-tight ${collapsed ? "outline-chapter-title-row-only" : ""}`}

      >

        <button

          type="button"

          className="outline-collapse-btn"

          onClick={() => setCollapsed((v) => !v)}

          aria-label={collapsed ? "展开" : "折叠"}

        >

          {collapsed ? "▶" : "▼"}

        </button>

        <span className="outline-chapter-title-input cursor-default bg-transparent font-medium text-ink">前言</span>

        <div className="flex shrink-0 flex-col items-end gap-0.5">

          <span className="text-[10px] text-slate-400">目标字数</span>

          <input

            type="number"

            min={500}

            step={500}

            className="w-14 rounded border border-slate-200 px-1 py-0.5 text-[11px]"

            value={targetWords}

            onChange={(e) => setTargetWords(e.target.value)}

            onBlur={() =>

              void savePatch({

                enabled: true,

                brief,

                target_words: parseInt(targetWords, 10) || 3000,

              })

            }

          />

        </div>

        <div className="outline-chapter-actions">

          <button type="button" className="outline-chip-btn outline-chip-btn-muted" onClick={() => setBriefOpen((v) => !v)}>

            {briefOpen ? "完成编辑" : "编辑要点"}

          </button>

          <button

            type="button"

            className="outline-chip-btn outline-chip-btn-danger opacity-0 transition-opacity group-hover:opacity-100"

            onClick={() => void disablePreface()}

            title="不写前言"

          >

            关闭

          </button>

        </div>

      </div>



      {!collapsed && (

        <div className="outline-chapter-body-stack">

          {!briefOpen ? (

            <button type="button" className="outline-meta-expand-bar outline-meta-expand-bar-flush" onClick={() => setBriefOpen(true)}>

              展开前言要点 ▼

            </button>

          ) : (

            <div className="outline-meta-vertical">

              <div className="outline-inline-stack outline-inline-stack-tight">

                <span className="outline-inline-label">前言要点</span>

                <textarea

                  className="outline-plain-textarea"

                  rows={3}

                  value={brief}

                  onChange={(e) => setBrief(e.target.value)}

                  placeholder="生成大纲后自动填入 2-4 句写作要点"

                  onBlur={() => {

                    const v = brief.trim();

                    if (v !== (pf.brief || "").trim()) {

                      void savePatch({ brief: v });

                    }

                  }}

                />

              </div>

              <button type="button" className="outline-meta-collapse-link" onClick={() => setBriefOpen(false)}>

                收起前言要点 ▲

              </button>

            </div>

          )}

          {pf.summary ? (

            <div className="outline-sections-plain">

              <span className="outline-inline-label">已生成摘要</span>

              <p className="outline-sections-merged-summary whitespace-pre-wrap text-xs leading-relaxed text-slate-600">

                {pf.summary}

              </p>

            </div>

          ) : null}

        </div>

      )}

    </div>

  );

}


