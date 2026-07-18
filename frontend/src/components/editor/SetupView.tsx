import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import { setupRecommend, updateBook } from "@/api/books";
import { confirmReference, deleteReference, listReferences, uploadReference } from "@/api/references";
import LiteraturePanel from "@/components/editor/LiteraturePanel";
import {
  usePatchWritingBasis,
  useWritingBasis,
} from "@/features/assistant/hooks/useWritingBasis";
import { BASIS_SETUP_FIELDS } from "@/features/assistant/bookSettingsSpec";
import type { WritingBasis } from "@/features/assistant/api/assistantApi";
import { styleOptionsFor } from "@/lib/styleTypes";
import type { Book, BookType, CitationStyle, SetupRecommendResult, StyleType } from "@/types/book";
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
  reference_material: "参考资料",
  bibliography: "参考文献",
  source_manuscript: "原始书稿",
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
  saveMeta: () => Promise<Book>;
};

type Props = {
  book: Book;
  onBookPatched: (b: Book) => void;
  onRegisterActions?: (actions: SetupViewActions) => void;
};

const FILE_ACCEPT =
  ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

const TARGET_WORDS_STEP = 5000;
const TARGET_WORDS_MIN = 1000;
type DisciplineCandidate = NonNullable<SetupRecommendResult["discipline_candidates"]>[number];

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
}: Props) {
  const qc = useQueryClient();
  const basisQuery = useWritingBasis(book.id);
  const patchBasis = usePatchWritingBasis(book.id);
  const [titleDraft, setTitleDraft] = useState(book.title ?? "");
  const [targetAudience, setTargetAudience] = useState("");
  const [disciplines, setDisciplines] = useState<string[]>([]);
  const [disciplineInput, setDisciplineInput] = useState("");
  const [citation, setCitation] = useState<CitationStyle | "">("");
  const [targetWords, setTargetWords] = useState(String(book.target_words ?? 80000));
  const [topicBrief, setTopicBrief] = useState("");
  const [bookType, setBookType] = useState<BookType>(book.book_type);
  const [styleType, setStyleType] = useState<StyleType>("popular_science");
  const [topicTags, setTopicTags] = useState<string[]>([]);
  const [customTagInput, setCustomTagInput] = useState("");
  const [allowTitleOptimization, setAllowTitleOptimization] = useState(false);
  const [shareToLibrary, setShareToLibrary] = useState(false);
  const [savingMeta, setSavingMeta] = useState(false);
  const [basisDraft, setBasisDraft] = useState<Partial<WritingBasis>>({});

  const [recommendedTags, setRecommendedTags] = useState<string[]>([]);
  const [disciplineCandidates, setDisciplineCandidates] = useState<DisciplineCandidate[]>([]);
  const [disciplineConfirmationNote, setDisciplineConfirmationNote] = useState("");
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

  const styleOpts = styleOptionsFor(bookType);
  const recommendInputKey = `${book.title}|${bookType}|${styleType}`;

  useEffect(() => {
    const discs =
      book.disciplines?.length ? [...book.disciplines].slice(0, 3) : book.discipline ? [book.discipline] : [];
    setTitleDraft(book.title ?? "");
    setDisciplines(discs);
    setBookType(book.book_type);
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
  }, [
    book.id,
    book.title,
    book.target_audience,
    book.discipline,
    JSON.stringify(book.disciplines ?? null),
    book.target_words,
    book.book_type,
    book.style_type,
    JSON.stringify(book.topic_tags ?? null),
    book.topic_brief,
    book.citation_style,
    book.allow_title_optimization,
  ]);

  useEffect(() => {
    const b = basisQuery.data;
    if (!b) return;
    setBasisDraft({
      book_promise: b.book_promise ?? "",
      reader_outcome: b.reader_outcome ?? "",
      scope: b.scope ?? "",
      depth: b.depth ?? "",
      voice: b.voice ?? "",
      must_avoid: b.must_avoid ?? [],
      must_keep: b.must_keep ?? [],
    });
  }, [basisQuery.data]);

  useEffect(() => {
    if (recommendCacheKey && recommendCacheKey !== recommendInputKey) {
      setRecommendStale(true);
    }
  }, [recommendInputKey, recommendCacheKey]);

  const applyRecommendation = useCallback(
    (rec: SetupRecommendResult) => {
      setRecommendedTags(rec.recommended_tags);
      setDisciplineCandidates(rec.discipline_candidates ?? []);
      setDisciplineConfirmationNote(rec.discipline_confirmation_note ?? "");
      setRecommendCacheKey(rec.cache_key);
      setRecommendStale(false);
      // 仅用户点击「智能推荐」时写入；不覆盖已手动改过的字段
      const t = touchedRef.current;
      if (!t.targetAudience && rec.target_audience) setTargetAudience(rec.target_audience);
      if (!t.disciplines && rec.disciplines.length) setDisciplines(rec.disciplines.slice(0, 3));
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
        toast.success("已生成推荐标签与要点，可点选标签并保存设定");
      } catch {
        toast.error("推荐生成失败，可手动填写后继续");
      } finally {
        setRecommendLoading(false);
      }
    },
    [applyRecommendation, book.id],
  );

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
    if (disciplines.length >= 3) {
      toast.error("学科领域最多保留 3 个");
      return;
    }
    touchedRef.current.disciplines = true;
    setDisciplines((prev) => [...prev, d]);
    setDisciplineInput("");
  }

  function selectDisciplineCandidate(name: string) {
    const d = name.trim().slice(0, 100);
    if (!d || disciplines.includes(d)) return;
    if (disciplines.length >= 3) {
      toast.error("学科领域最多保留 3 个");
      return;
    }
    touchedRef.current.disciplines = true;
    setDisciplines((prev) => [...prev, d]);
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

  async function saveMeta(): Promise<Book> {
    const tw = parseInt(targetWords, 10);
    if (Number.isNaN(tw) || tw < 1000) {
      toast.error("目标字数需为 ≥1000 的数字");
      throw new Error("invalid_target_words");
    }
    setSavingMeta(true);
    try {
      const next = await updateBook(book.id, {
        title: titleDraft.trim() || book.title,
        book_type: bookType,
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
      const basisPatch: Partial<WritingBasis> = {
        book_promise: String(basisDraft.book_promise ?? "").trim() || null,
        reader_outcome: String(basisDraft.reader_outcome ?? "").trim() || null,
        scope: String(basisDraft.scope ?? "").trim() || null,
        depth: String(basisDraft.depth ?? "").trim() || null,
        voice: String(basisDraft.voice ?? "").trim() || null,
        must_avoid: Array.isArray(basisDraft.must_avoid) ? basisDraft.must_avoid : [],
        must_keep: Array.isArray(basisDraft.must_keep) ? basisDraft.must_keep : [],
        target_readers: targetAudience.trim() || null,
        direction: topicBrief.trim() || null,
      };
      try {
        await patchBasis.mutateAsync(basisPatch);
        await qc.invalidateQueries({ queryKey: ["writingBasis", book.id] });
      } catch {
        /* Book 已保存；依据补丁失败不阻断 */
      }
      toast.success("书稿设定已保存");
      return next;
    } catch (error) {
      toast.error("书稿设定保存失败，请检查网络后重试");
      throw error;
    } finally {
      setSavingMeta(false);
    }
  }

  const saveMetaRef = useRef(saveMeta);
  saveMetaRef.current = saveMeta;
  useEffect(() => {
    onRegisterActions?.({
      saveMeta: async () => {
        return saveMetaRef.current();
      },
    });
  }, [book.id, onRegisterActions]);

  const [files, setFiles] = useState<ReferenceFile[]>([]);
  const [uploadPurposes, setUploadPurposes] = useState<FilePurpose[]>(["reference_material"]);
  const [uploadOutlineUsage, setUploadOutlineUsage] = useState<"primary" | "reference">("reference");
  const [uploadNote, setUploadNote] = useState("");

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
    if (!window.confirm(`确定删除「${file.filename}」？该文件提供的大纲、要求和资料也将停用。`)) return;
    try {
      await deleteReference(book.id, file.id);
      toast.success("已删除");
      await refreshRefs();
      void qc.invalidateQueries({ queryKey: ["book", book.id] });
    } catch {
      toast.error("删除失败");
    }
  }

  async function onConfirmFile(file: ReferenceFile) {
    try {
      await confirmReference(book.id, file.id, {
        purposes: file.file_purposes ?? undefined,
        primary_outline: file.outline_usage === "primary",
        conflict_resolutions: Object.fromEntries(
          (file.conflicts ?? []).map((conflict) => [
            conflict.id,
            conflict.type === "multiple_primary_outlines" ? file.id : "accept_current",
          ]),
        ),
      });
      toast.success("文件内容已确认并生效");
      await refreshRefs();
    } catch {
      toast.error("未能确认文件，请检查待处理问题");
    }
  }

  function applyPreset(text: string) {
    touchedRef.current.topicBrief = true;
    setTopicBrief((prev) => (prev.trim() ? `${prev.trim()}\n\n${text}` : text));
  }

  const availableRecommended = recommendedTags.filter((t) => !topicTags.includes(t));

  return (
    <div className="setup-view">
      <div className="card divide-y divide-slate-200/80 border border-slate-200/80 bg-white/70 shadow-sm">
        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">基础信息</h3>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="text-sm md:col-span-2">
              <label className="block">
                <span className="text-slate-600">书名</span>
                <input
                  className="input mt-1"
                  value={titleDraft}
                  onChange={(e) => setTitleDraft(e.target.value)}
                  maxLength={500}
                  placeholder="书稿正式名称"
                />
              </label>
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
            <label className="block text-sm">
              <span className="text-slate-600">一级分类</span>
              <select
                className="input mt-1"
                value={bookType}
                onChange={(e) => {
                  const next = e.target.value as BookType;
                  setBookType(next);
                  const opts = styleOptionsFor(next);
                  if (!opts.some((o) => o.value === styleType)) {
                    setStyleType(opts[0]?.value ?? (next === "academic" ? "textbook" : "popular_science"));
                  }
                }}
              >
                <option value="nonfiction">{BOOK_TYPE_LABEL.nonfiction}</option>
                <option value="academic">{BOOK_TYPE_LABEL.academic}</option>
              </select>
              <p className="mt-1 text-[11px] text-slate-400">
                新建时的「大众非虚构」只是占位；请按创作意图选择，或用项目要点「智能补齐设定」。
              </p>
            </label>
          </div>
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">体例风格</h3>
          <p className="mt-1 text-xs text-slate-500">体裁决定全书的结构与表达方式；话题标签用于限定主题范围。</p>
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
                  {recommendedTags.length ? "重新推荐" : "智能推荐标签与要点"}
                </button>
              </div>
              {recommendStale ? (
                <p className="mt-1 text-[11px] text-amber-700">书名或分类已变更，推荐可能已过期。</p>
              ) : null}
              <p className="mt-1 text-[11px] text-slate-400">
                点击上方按钮才会根据书名与分类推断标签、读者与主题要点；不会在进入页面时自动填充。
              </p>

              <p className="mt-3 text-xs font-medium text-slate-500">推荐标签</p>
              <div className="mt-2 flex min-h-[2rem] flex-wrap gap-2">
                {recommendLoading && availableRecommended.length === 0 ? (
                  <span className="inline-flex items-center gap-1 text-xs text-slate-400">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> 生成中…
                  </span>
                ) : availableRecommended.length === 0 ? (
                  <span className="text-xs text-slate-400">暂无推荐，可直接添加标签</span>
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
              {disciplineCandidates.length ? (
                <div className="mt-3 space-y-2">
                  <div className="text-xs text-slate-500">
                    {disciplineConfirmationNote || "学科领域用于约束术语解释、证据标准和论证方式。"}
                  </div>
                  <div className="space-y-2">
                    {disciplineCandidates.map((candidate) => {
                      const selected = disciplines.includes(candidate.name);
                      return (
                        <button
                          key={candidate.name}
                          type="button"
                          className={`w-full rounded-md border px-3 py-2 text-left text-xs ${
                            selected
                              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                              : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                          }`}
                          onClick={() => selectDisciplineCandidate(candidate.name)}
                          disabled={selected}
                        >
                          <span className="font-medium">{candidate.name}</span>
                          {candidate.reason ? (
                            <span className="mt-1 block leading-relaxed text-slate-500">{candidate.reason}</span>
                          ) : null}
                          {candidate.ambiguity_note ? (
                            <span className="mt-1 block leading-relaxed text-amber-700">{candidate.ambiguity_note}</span>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : null}
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
              <p className="mt-1 text-xs text-slate-500">需要时先生成检索词，再选择文献加入本书。</p>
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
          <p className="mt-1 text-xs text-slate-500">将作为大纲和写作的主要依据。</p>
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
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">策划细节</h3>
          <p className="mt-1 text-xs text-slate-500">
            与项目启动助手「项目要点」同一结构；助手对话会自动同步到这里。
          </p>
          <div className="mt-4 space-y-3">
            {BASIS_SETUP_FIELDS.map((f) => {
              const isList = "list" in f && f.list;
              const value = isList
                ? ((basisDraft[f.key as keyof WritingBasis] as string[] | undefined) ?? []).join("\n")
                : String(basisDraft[f.key as keyof WritingBasis] ?? "");
              return (
                <label key={f.key} className="block text-sm">
                  <span className="text-slate-600">{f.label}</span>
                  <textarea
                    className="input mt-1 min-h-[64px]"
                    value={value}
                    onChange={(e) => {
                      const raw = e.target.value;
                      setBasisDraft((prev) => ({
                        ...prev,
                        [f.key]: isList
                          ? raw
                              .split("\n")
                              .map((x) => x.trim())
                              .filter(Boolean)
                          : raw,
                      }));
                    }}
                    placeholder={isList ? "每行一条" : undefined}
                  />
                </label>
              );
            })}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-secondary"
              disabled={savingMeta}
              onClick={() => void saveMeta()}
            >
              {savingMeta ? "保存中…" : "保存设定"}
            </button>
          </div>
        </section>

        <section className="p-5">
          <h3 className="text-sm font-semibold text-ink">
            资料上传 <span className="font-normal text-slate-500">（{files.length} 个）</span>
          </h3>
          <p className="mt-2 text-xs text-slate-500">上传后系统会解析内容；同一文件可以用于多个环节。</p>

          <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50/60 p-4">
            <p className="text-xs font-medium text-slate-600">这份文件用于</p>
            <div className="mt-2 flex flex-wrap gap-3 text-xs">
              {(Object.keys(PURPOSE_LABELS) as FilePurpose[]).filter((p) => p !== "source_manuscript").map((p) => (
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
                  作为主大纲
                </label>
                <label className="mt-1 flex items-center gap-2">
                  <input
                    type="radio"
                    name="outline_usage"
                    checked={uploadOutlineUsage === "reference"}
                    onChange={() => setUploadOutlineUsage("reference")}
                  />
                  仅供大纲生成参考
                </label>
              </div>
            ) : null}
            <label className="mt-3 block text-xs">
              <span className="text-slate-600">补充说明（可选）</span>
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

          {uploadPurposes.includes("bibliography") ? <label className="mt-3 flex items-start gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={shareToLibrary}
              onChange={(e) => setShareToLibrary(e.target.checked)}
            />
            <span>允许将该文献的题录和摘要用于公共书库</span>
          </label> : null}

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
                        <span className="text-slate-600">正在解析…</span>
                      </>
                    ) : f.parse_status === "done" ? (
                      <span className={f.lifecycle_status === "pending_confirmation" ? "text-amber-700" : "text-emerald-600"}>
                        {f.lifecycle_status === "pending_confirmation" ? "待确认" : "✓ 已生效"}
                      </span>
                    ) : f.parse_status === "failed" ? (
                      <span className="text-red-600" title={f.error_message ?? ""}>
                        ✗ 解析失败，请重新上传
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
                  {f.parse_artifacts ? (
                    <div className="w-full rounded bg-slate-50 p-2 text-[11px] text-slate-500">
                      大纲 {f.parse_artifacts.outline_candidate?.length ?? 0} 章 ·
                      写作要求 {f.parse_artifacts.writing_rules?.length ?? 0} 条 ·
                      术语 {f.parse_artifacts.terminology?.length ?? 0} 条 ·
                      资料分块 {f.parse_artifacts.reference_chunk_count ?? f.chunk_count ?? 0} 个
                      {f.conflicts?.length ? ` · 待确认 ${f.conflicts.length} 项` : ""}
                    </div>
                  ) : null}
                  {f.lifecycle_status === "pending_confirmation" ? (
                    <div className="w-full rounded border border-amber-100 bg-amber-50 p-2 text-[11px] text-amber-800">
                      {(f.conflicts ?? []).map((conflict) => (
                        <p key={conflict.id}>{conflict.message}</p>
                      ))}
                      <button
                        type="button"
                        className="mt-2 rounded bg-amber-700 px-2 py-1 text-white"
                        onClick={() => void onConfirmFile(f)}
                      >
                        确认并生效
                      </button>
                    </div>
                  ) : null}
                </li>
              ))
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
