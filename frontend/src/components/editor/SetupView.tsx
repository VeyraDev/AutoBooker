import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import { setupRecommend, updateBook } from "@/api/books";
import { startAutoGenerateForBook } from "@/api/bookJobs";
import { deleteReference, listReferences, uploadReference } from "@/api/references";
import LiteraturePanel from "@/components/editor/LiteraturePanel";
import { styleOptionsFor } from "@/lib/styleTypes";
import type { Book, BookType, CitationStyle, StyleType } from "@/types/book";
import type { FilePurpose, ReferenceFile } from "@/types/reference";

const CITATION_OPTIONS: { value: CitationStyle; label: string }[] = [
  { value: "apa", label: "APA" },
  { value: "mla", label: "MLA" },
  { value: "chicago", label: "Chicago" },
  { value: "gb_t7714", label: "GB/T 7714" },
];

const BOOK_TYPE_LABEL: Record<BookType, string> = {
  nonfiction: "大众非虚构",
  academic: "学术专著",
};

const PURPOSE_LABELS: Record<FilePurpose, string> = {
  outline: "大纲",
  writing_requirements: "写作要求",
  reference: "参考资料",
};

function defaultCitationFor(bookType: BookType): CitationStyle | "" {
  return bookType === "academic" ? "gb_t7714" : "apa";
}

export const TOPIC_INSPIRATION_PRESETS: { id: string; label: string; text: string }[] = [
  {
    id: "tech",
    label: "技术专著",
    text:
      "面向具备一定基础的开发者；侧重原理阐述与工程实践结合；每章包含架构示意图与可运行示例；语气严谨、条理清晰；适当引用官方文档与开源实现。",
  },
  {
    id: "science",
    label: "科普文风",
    text:
      "面向大众读者；避免堆砌术语，用类比与故事引入概念；章节短小精炼；配图建议；保持好奇与启发式语气；结尾给出延伸阅读。",
  },
  {
    id: "business",
    label: "商业读物",
    text:
      "面向管理者与创业者；强调案例与可落地方法论；每章有关键框架图或清单；数据与趋势支撑观点；语气务实、结论先行。",
  },
];

/** @deprecated 迁移至 API topic_brief */
export const topicKey = (bookId: string) => `autobooker_topic_brief_${bookId}`;
/** @deprecated 迁移至 API target_audience */
export const audienceKey = (bookId: string) => `autobooker_target_audience_${bookId}`;

export type SetupViewActions = {
  saveMeta: () => Promise<void>;
};

type Props = {
  book: Book;
  onBookPatched: (b: Book) => void;
  onRegisterActions?: (actions: SetupViewActions) => void;
  /** 从新建对话框带入：进入设定页后提示一键生成 */
  pendingAutoGenerate?: boolean;
};

const FILE_ACCEPT =
  ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

const TARGET_WORDS_STEP = 5000;
const TARGET_WORDS_MIN = 1000;

type TouchedFields = {
  targetAudience: boolean;
  disciplines: boolean;
  topicBrief: boolean;
  topicTags: boolean;
  citation: boolean;
};

export default function SetupView({
  book,
  onBookPatched,
  onRegisterActions,
  pendingAutoGenerate,
}: Props) {
  const qc = useQueryClient();
  const [targetAudience, setTargetAudience] = useState("");
  const [disciplines, setDisciplines] = useState<string[]>([]);
  const [disciplineInput, setDisciplineInput] = useState("");
  const [citation, setCitation] = useState<CitationStyle | "">("");
  const [targetWords, setTargetWords] = useState(String(book.target_words ?? 80000));
  const [topicBrief, setTopicBrief] = useState("");
  const [styleType, setStyleType] = useState<StyleType>("popular_science");
  const [topicTags, setTopicTags] = useState<string[]>([]);
  const [customTagInput, setCustomTagInput] = useState("");
  const [allowTitleOptimization, setAllowTitleOptimization] = useState(false);
  const [shareToLibrary, setShareToLibrary] = useState(false);

  const [recommendedTags, setRecommendedTags] = useState<string[]>([]);
  const [recommendLoading, setRecommendLoading] = useState(false);
  const [recommendStale, setRecommendStale] = useState(false);
  const [recommendCacheKey, setRecommendCacheKey] = useState<string | null>(null);

  const touchedRef = useRef<TouchedFields>({
    targetAudience: false,
    disciplines: false,
    topicBrief: false,
    topicTags: false,
    citation: false,
  });

  const styleOpts = styleOptionsFor(book.book_type);
  const recommendInputKey = `${book.title}|${book.book_type}|${styleType}`;

  useEffect(() => {
    const discs =
      book.disciplines?.length ? [...book.disciplines] : book.discipline ? [book.discipline] : [];
    setDisciplines(discs);
    setCitation(book.citation_style ?? defaultCitationFor(book.book_type));
    setTargetWords(String(book.target_words ?? 80000));
    setStyleType(
      (book.style_type as StyleType) ||
        (book.book_type === "academic" ? "textbook" : "popular_science"),
    );
    setTopicTags(book.topic_tags?.length ? [...book.topic_tags] : []);
    setTopicBrief(book.topic_brief?.trim() ?? "");
    setAllowTitleOptimization(Boolean(book.allow_title_optimization));
    setTargetAudience(book.target_audience?.trim() ?? "");

    const storedBrief = window.localStorage.getItem(topicKey(book.id));
    const storedAud = window.localStorage.getItem(audienceKey(book.id));
    if (!book.topic_brief?.trim() && storedBrief) {
      setTopicBrief(storedBrief);
      void updateBook(book.id, { topic_brief: storedBrief }).then((b) => {
        onBookPatched(b);
        window.localStorage.removeItem(topicKey(book.id));
      });
    }
    if (!book.target_audience?.trim() && storedAud) {
      setTargetAudience(storedAud);
      void updateBook(book.id, { target_audience: storedAud }).then((b) => {
        onBookPatched(b);
        window.localStorage.removeItem(audienceKey(book.id));
      });
    }
  }, [book.id]);

  useEffect(() => {
    if (recommendCacheKey && recommendCacheKey !== recommendInputKey) {
      setRecommendStale(true);
    }
  }, [recommendInputKey, recommendCacheKey]);

  const applyRecommendation = useCallback(
    (rec: {
      recommended_tags: string[];
      target_audience: string;
      disciplines: string[];
      topic_brief: string;
      cache_key: string;
    }) => {
      setRecommendedTags(rec.recommended_tags);
      setRecommendCacheKey(rec.cache_key);
      setRecommendStale(false);
      const t = touchedRef.current;
      if (!t.targetAudience && rec.target_audience) setTargetAudience(rec.target_audience);
      if (!t.disciplines && rec.disciplines.length) setDisciplines(rec.disciplines);
      if (!t.topicBrief && rec.topic_brief) setTopicBrief(rec.topic_brief);
    },
    [],
  );

  const fetchRecommend = useCallback(
    async (force: boolean) => {
      setRecommendLoading(true);
      try {
        const rec = await setupRecommend(book.id, { force });
        applyRecommendation(rec);
      } catch {
        toast.error("推荐生成失败，可手动填写后继续");
      } finally {
        setRecommendLoading(false);
      }
    },
    [applyRecommendation, book.id],
  );

  useEffect(() => {
    void fetchRecommend(false);
  }, [book.id]);

  function addRecommendedTag(tag: string) {
    if (topicTags.includes(tag)) return;
    touchedRef.current.topicTags = true;
    setTopicTags((prev) => [...prev, tag]);
  }

  function removeTag(tag: string) {
    touchedRef.current.topicTags = true;
    setTopicTags((prev) => prev.filter((t) => t !== tag));
  }

  function addCustomTag() {
    const tag = customTagInput.trim().slice(0, 80);
    if (!tag) return;
    if (topicTags.includes(tag)) {
      toast.error("该标签已存在");
      return;
    }
    touchedRef.current.topicTags = true;
    setTopicTags((prev) => [...prev, tag]);
    setCustomTagInput("");
  }

  function addDiscipline() {
    const d = disciplineInput.trim().slice(0, 100);
    if (!d) return;
    if (disciplines.includes(d)) {
      toast.error("该学科已存在");
      return;
    }
    touchedRef.current.disciplines = true;
    setDisciplines((prev) => [...prev, d]);
    setDisciplineInput("");
  }

  function removeDiscipline(d: string) {
    touchedRef.current.disciplines = true;
    setDisciplines((prev) => prev.filter((x) => x !== d));
  }

  function bumpTargetWords(delta: number) {
    const current = parseInt(targetWords, 10);
    const base = Number.isNaN(current) ? book.target_words ?? 80000 : current;
    setTargetWords(String(Math.max(TARGET_WORDS_MIN, base + delta)));
  }

  async function saveMeta() {
    const tw = parseInt(targetWords, 10);
    if (Number.isNaN(tw) || tw < 1000) {
      toast.error("目标字数需为 ≥1000 的数字");
      throw new Error("invalid_target_words");
    }
    const next = await updateBook(book.id, {
      disciplines: disciplines.length ? disciplines : null,
      discipline: disciplines[0]?.trim() || null,
      target_audience: targetAudience.trim() || null,
      citation_style: citation || null,
      target_words: tw,
      style_type: styleType,
      topic_tags: topicTags.length ? topicTags : null,
      topic_brief: topicBrief.trim() || null,
      allow_title_optimization: allowTitleOptimization,
    });
    onBookPatched(next);
    toast.success("书稿设定已保存");
  }

  const saveMetaRef = useRef(saveMeta);
  saveMetaRef.current = saveMeta;
  useEffect(() => {
    onRegisterActions?.({
      saveMeta: async () => {
        await saveMetaRef.current();
      },
    });
  }, [book.id, onRegisterActions]);

  const [files, setFiles] = useState<ReferenceFile[]>([]);
  const [uploadPurposes, setUploadPurposes] = useState<FilePurpose[]>(["reference"]);
  const [uploadOutlineUsage, setUploadOutlineUsage] = useState<"primary" | "reference">("reference");
  const [uploadNote, setUploadNote] = useState("");
  const [autoJobStarting, setAutoJobStarting] = useState(false);

  async function refreshRefs() {
    const list = await listReferences(book.id);
    setFiles(list);
    return list;
  }

  useEffect(() => {
    void refreshRefs().catch(() => {});
  }, [book.id]);

  const parsingActive = files.some((f) => f.parse_status === "pending" || f.parse_status === "processing");

  useEffect(() => {
    if (!parsingActive) return;
    const id = window.setInterval(() => {
      void refreshRefs().catch(() => {});
    }, 3000);
    return () => window.clearInterval(id);
  }, [book.id, parsingActive]);

  async function onUploadFiles(fileList: FileList | null) {
    if (!fileList?.length) return;
    if (uploadPurposes.length === 0) {
      toast.error("请至少选择一种文件用途");
      return;
    }
    for (const f of Array.from(fileList)) {
      try {
        await uploadReference(book.id, f, {
          filePurposes: uploadPurposes,
          outlineUsage: uploadPurposes.includes("outline") ? uploadOutlineUsage : undefined,
          userNote: uploadNote.trim() || undefined,
          shareToLibrary,
        });
        toast.success(`已上传 ${f.name}`);
      } catch {
        toast.error(`上传失败：${f.name}`);
      }
    }
    await refreshRefs();
    void qc.invalidateQueries({ queryKey: ["book", book.id] });
  }

  async function onDeleteFile(file: ReferenceFile) {
    if (!window.confirm(`确定删除「${file.filename}」？相关解析结果将一并失效。`)) return;
    try {
      await deleteReference(book.id, file.id);
      toast.success("已删除");
      await refreshRefs();
      void qc.invalidateQueries({ queryKey: ["book", book.id] });
    } catch {
      toast.error("删除失败");
    }
  }

  function applyPreset(text: string) {
    touchedRef.current.topicBrief = true;
    setTopicBrief((prev) => (prev.trim() ? `${prev.trim()}\n\n${text}` : text));
  }

  async function handleStartAutoGenerate() {
    setAutoJobStarting(true);
    try {
      await saveMeta();
      await startAutoGenerateForBook(book.id);
      toast.success("已开始一键生成，完成后将通知您");
      void qc.invalidateQueries({ queryKey: ["book", book.id] });
      void qc.invalidateQueries({ queryKey: ["bookJob", book.id] });
    } catch {
      toast.error("启动一键生成失败");
    } finally {
      setAutoJobStarting(false);
    }
  }

  useEffect(() => {
    if (pendingAutoGenerate && book.status === "setup") {
      toast("可在保存设定后点击「开始一键生成」", { icon: "ℹ️" });
    }
  }, [pendingAutoGenerate, book.status]);

  const availableRecommended = recommendedTags.filter((t) => !topicTags.includes(t));

  return (
    <div className="setup-view">
      <div className="card divide-y divide-slate-200/80 border border-slate-200/80 bg-white/70 shadow-sm">
        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">基础信息</h3>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="text-sm md:col-span-2">
              <span className="text-slate-600">书名</span>
              <p className="mt-1 font-medium text-ink">{book.title || "未命名"}</p>
              <label className="mt-2 flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={allowTitleOptimization}
                  onChange={(e) => setAllowTitleOptimization(e.target.checked)}
                />
                允许系统优化书名
              </label>
              <p className="mt-1 text-[11px] text-slate-400">
                不勾选时，大纲与写作流程将锁定您输入的书名。
                {book.original_title && book.original_title !== book.title
                  ? ` 原始书名：${book.original_title}`
                  : null}
              </p>
            </div>
            <div className="text-sm">
              <span className="text-slate-600">一级分类</span>
              <p className="mt-1 font-medium text-ink">{BOOK_TYPE_LABEL[book.book_type]}</p>
            </div>
          </div>
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">体例风格</h3>
          <p className="mt-1 text-xs text-slate-500">二级体裁决定大纲与章节专用 prompt；三级标签写入全书上下文。</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <label className="block text-sm md:col-span-2">
              <span className="text-slate-600">二级体裁</span>
              <select
                className="input mt-1"
                value={styleType}
                onChange={(e) => setStyleType(e.target.value as StyleType)}
              >
                {styleOpts.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm md:col-span-2">
              <span className="text-slate-600">引用格式</span>
              <select
                className="input mt-1"
                value={citation}
                onChange={(e) => {
                  touchedRef.current.citation = true;
                  setCitation(e.target.value as CitationStyle | "");
                }}
              >
                <option value="">无需引用</option>
                {CITATION_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="text-sm md:col-span-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-slate-600">三级话题标签</span>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-xs text-brand-700 hover:underline disabled:opacity-50"
                  disabled={recommendLoading}
                  onClick={() => void fetchRecommend(true)}
                >
                  {recommendLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
                  重新推荐
                </button>
              </div>
              {recommendStale ? (
                <p className="mt-1 text-[11px] text-amber-700">书名或分类已变更，推荐可能已过期。</p>
              ) : null}
              <p className="mt-1 text-[11px] text-slate-400">自动生成，不满意可手动调整。</p>

              <p className="mt-3 text-xs font-medium text-slate-500">系统推荐标签（根据书名与分类自动生成）</p>
              <div className="mt-2 flex min-h-[2rem] flex-wrap gap-2">
                {recommendLoading && availableRecommended.length === 0 ? (
                  <span className="inline-flex items-center gap-1 text-xs text-slate-400">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> 生成中…
                  </span>
                ) : availableRecommended.length === 0 ? (
                  <span className="text-xs text-slate-400">暂无新推荐，可手动添加</span>
                ) : (
                  availableRecommended.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => addRecommendedTag(tag)}
                      className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-violet-300 hover:bg-violet-50"
                    >
                      + {tag}
                    </button>
                  ))
                )}
              </div>

              <p className="mt-3 text-xs font-medium text-slate-500">已选标签</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {topicTags.length === 0 ? (
                  <span className="text-xs text-slate-400">尚未添加</span>
                ) : (
                  topicTags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="rounded-full border border-violet-400 bg-violet-50 px-3 py-1 text-xs text-violet-900"
                      title="点击移除"
                    >
                      {tag} ×
                    </button>
                  ))
                )}
              </div>

              <p className="mt-3 text-xs font-medium text-slate-500">自定义标签</p>
              <div className="mt-2 flex gap-2">
                <input
                  className="input h-9 flex-1 text-sm"
                  value={customTagInput}
                  onChange={(e) => setCustomTagInput(e.target.value)}
                  placeholder="输入自定义标签…"
                  maxLength={80}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCustomTag();
                    }
                  }}
                />
                <button type="button" className="btn-secondary h-9 shrink-0 px-3 text-xs" onClick={addCustomTag}>
                  添加
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">写作定位</h3>
          <div className="mt-4 grid gap-4">
            <label className="block text-sm">
              <span className="text-slate-600">目标读者</span>
              <textarea
                className="input mt-1 min-h-[88px]"
                value={targetAudience}
                onChange={(e) => {
                  touchedRef.current.targetAudience = true;
                  setTargetAudience(e.target.value);
                }}
                placeholder="例如：企业管理者、研究生、对 AI 产品落地感兴趣的工程师…"
              />
            </label>
            <div className="text-sm">
              <span className="text-slate-600">学科领域</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {disciplines.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => removeDiscipline(d)}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700"
                  >
                    {d} ×
                  </button>
                ))}
              </div>
              <div className="mt-2 flex gap-2">
                <input
                  className="input h-9 flex-1 text-sm"
                  value={disciplineInput}
                  onChange={(e) => setDisciplineInput(e.target.value)}
                  placeholder="添加学科领域…"
                  maxLength={100}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addDiscipline();
                    }
                  }}
                />
                <button type="button" className="btn-secondary h-9 shrink-0 px-3 text-xs" onClick={addDiscipline}>
                  添加
                </button>
              </div>
            </div>
            <label className="block text-sm md:max-w-md">
              <span className="text-slate-600">全书目标字数</span>
              <div className="mt-1 flex gap-2">
                <button
                  type="button"
                  className="btn-secondary h-10 w-10 shrink-0 px-0 text-lg leading-none"
                  aria-label={`减少 ${TARGET_WORDS_STEP} 字`}
                  onClick={() => bumpTargetWords(-TARGET_WORDS_STEP)}
                >
                  −
                </button>
                <input
                  className="input min-w-0 flex-1 text-center"
                  type="number"
                  min={TARGET_WORDS_MIN}
                  step={TARGET_WORDS_STEP}
                  value={targetWords}
                  onChange={(e) => setTargetWords(e.target.value)}
                />
                <button
                  type="button"
                  className="btn-secondary h-10 w-10 shrink-0 px-0 text-lg leading-none"
                  aria-label={`增加 ${TARGET_WORDS_STEP} 字`}
                  onClick={() => bumpTargetWords(TARGET_WORDS_STEP)}
                >
                  +
                </button>
              </div>
            </label>
          </div>
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">文献检索</h3>
          <p className="mt-1 text-xs text-slate-500">检索词生成较慢，仅在您点击「生成检索词」时调用，不阻塞本页加载。</p>
          <div className="mt-4">
            <LiteraturePanel
              bookId={book.id}
              citationStyle={citation || book.citation_style || null}
              defaultQuery=""
              mode="setup"
              embedded
            />
          </div>
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">主题说明</h3>
          <p className="mt-1 text-xs text-slate-500">将用于生成大纲；可先保存设定再生成。</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {TOPIC_INSPIRATION_PRESETS.map((p) => (
              <button key={p.id} type="button" className="btn-secondary h-8 px-3 text-xs" onClick={() => applyPreset(p.text)}>
                {p.label}
              </button>
            ))}
          </div>
          <textarea
            className="input mt-3 min-h-[140px]"
            value={topicBrief}
            onChange={(e) => {
              touchedRef.current.topicBrief = true;
              setTopicBrief(e.target.value);
            }}
            placeholder="希望全书覆盖哪些论点、案例类型、语气风格等…"
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className="btn-secondary" onClick={() => void saveMeta()}>
              保存设定
            </button>
            {(pendingAutoGenerate || book.status === "setup") && (
              <button
                type="button"
                className="btn-primary"
                disabled={autoJobStarting}
                onClick={() => void handleStartAutoGenerate()}
              >
                {autoJobStarting ? "启动中…" : "开始一键生成"}
              </button>
            )}
          </div>
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">
            资料上传 <span className="font-normal text-slate-500">（{files.length} 个）</span>
          </h3>
          <p className="mt-2 text-xs text-slate-500">选择文件用途（可多选），可选备注说明特殊要求。支持 PDF、DOCX、TXT。</p>

          <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50/60 p-4">
            <p className="text-xs font-medium text-slate-600">文件用途（多选）</p>
            <div className="mt-2 flex flex-wrap gap-3 text-xs">
              {(Object.keys(PURPOSE_LABELS) as FilePurpose[]).map((p) => (
                <label key={p} className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    checked={uploadPurposes.includes(p)}
                    onChange={(e) => {
                      setUploadPurposes((prev) =>
                        e.target.checked ? [...prev, p] : prev.filter((x) => x !== p),
                      );
                    }}
                  />
                  {PURPOSE_LABELS[p]}
                </label>
              ))}
            </div>
            {uploadPurposes.includes("outline") ? (
              <div className="mt-3 text-xs">
                <p className="font-medium text-slate-600">如何使用这份大纲</p>
                <label className="mt-1 flex items-center gap-2">
                  <input
                    type="radio"
                    name="outline_usage"
                    checked={uploadOutlineUsage === "primary"}
                    onChange={() => setUploadOutlineUsage("primary")}
                  />
                  作为本书主大纲
                </label>
                <label className="mt-1 flex items-center gap-2">
                  <input
                    type="radio"
                    name="outline_usage"
                    checked={uploadOutlineUsage === "reference"}
                    onChange={() => setUploadOutlineUsage("reference")}
                  />
                  仅作为生成参考
                </label>
              </div>
            ) : null}
            <label className="mt-3 block text-xs">
              <span className="text-slate-600">文件备注（可选）</span>
              <textarea
                className="input mt-1 min-h-[60px] text-xs"
                value={uploadNote}
                onChange={(e) => setUploadNote(e.target.value)}
                placeholder="例如：一级和二级标题不能修改…"
              />
            </label>
            <label className="btn-secondary mt-3 inline-flex cursor-pointer text-xs">
              选择文件上传
              <input
                type="file"
                accept={FILE_ACCEPT}
                className="hidden"
                multiple
                onChange={(e) => void onUploadFiles(e.target.files)}
              />
            </label>
          </div>

          <label className="mt-3 flex items-start gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={shareToLibrary}
              onChange={(e) => setShareToLibrary(e.target.checked)}
            />
            <span>同意将该文献元数据及摘要加入 AutoBooker 公共书库（默认不勾选）</span>
          </label>

          <ul className="mt-4 space-y-2 text-left text-sm">
            {files.length === 0 ? (
              <li className="text-slate-400">暂无文件</li>
            ) : (
              files.map((f) => (
                <li
                  key={f.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 bg-white/80 px-3 py-2"
                >
                  <div className="min-w-0">
                    <span className="block truncate font-medium text-slate-800">{f.filename}</span>
                    {f.file_purposes?.length ? (
                      <span className="text-[11px] text-slate-500">
                        {f.file_purposes.map((p) => PURPOSE_LABELS[p] ?? p).join(" · ")}
                        {f.outline_usage === "primary" ? " · 主大纲" : ""}
                      </span>
                    ) : null}
                  </div>
                  <span className="flex shrink-0 flex-wrap items-center gap-2 text-xs">
                    {f.parse_status === "pending" || f.parse_status === "processing" ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-500" aria-hidden />
                        <span className="text-slate-600">解析中…</span>
                      </>
                    ) : f.parse_status === "done" ? (
                      <span className="text-emerald-600">✓ 已解析</span>
                    ) : f.parse_status === "failed" ? (
                      <span className="text-red-600" title={f.error_message ?? ""}>
                        ✗ 解析失败
                      </span>
                    ) : null}
                    <button
                      type="button"
                      className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                      title="删除"
                      aria-label={`删除 ${f.filename}`}
                      onClick={() => void onDeleteFile(f)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </span>
                </li>
              ))
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
