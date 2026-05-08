import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";

import { listReferences, uploadReference } from "@/api/references";
import { updateBook } from "@/api/books";
import type { Book, BookType, CitationStyle } from "@/types/book";
import type { ReferenceFile } from "@/types/reference";

const CITATION_OPTIONS: { value: CitationStyle; label: string }[] = [
  { value: "apa", label: "APA" },
  { value: "mla", label: "MLA" },
  { value: "chicago", label: "Chicago" },
  { value: "gb_t7714", label: "GB/T 7714" },
];

const BOOK_TYPE_LABEL: Record<BookType, string> = {
  nonfiction: "非虚构",
  academic: "学术",
};

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

export const topicKey = (bookId: string) => `autobooker_topic_brief_${bookId}`;
export const audienceKey = (bookId: string) => `autobooker_target_audience_${bookId}`;

export type SetupViewActions = {
  saveMeta: () => Promise<void>;
};

type Props = {
  book: Book;
  onBookPatched: (b: Book) => void;
  /** 供策划向导 FAB 在生成大纲前调用保存 */
  onRegisterActions?: (actions: SetupViewActions) => void;
};

export default function SetupView({ book, onBookPatched, onRegisterActions }: Props) {
  const [targetAudience, setTargetAudience] = useState("");
  const [discipline, setDiscipline] = useState(book.discipline ?? "");
  const [citation, setCitation] = useState<CitationStyle | "">(book.citation_style ?? "");
  const [targetWords, setTargetWords] = useState(String(book.target_words ?? 80000));
  const [topicBrief, setTopicBrief] = useState("");

  useEffect(() => {
    setDiscipline(book.discipline ?? "");
    setCitation(book.citation_style ?? "");
    setTargetWords(String(book.target_words ?? 80000));
    const stored = window.localStorage.getItem(topicKey(book.id));
    if (stored) setTopicBrief(stored);
    const fromApi = book.target_audience?.trim();
    if (fromApi) {
      setTargetAudience(fromApi);
    } else {
      const aud = window.localStorage.getItem(audienceKey(book.id));
      setTargetAudience(aud ?? "");
    }
  }, [book]);

  useEffect(() => {
    window.localStorage.setItem(topicKey(book.id), topicBrief);
  }, [book.id, topicBrief]);

  useEffect(() => {
    window.localStorage.setItem(audienceKey(book.id), targetAudience);
  }, [book.id, targetAudience]);

  async function saveMeta() {
    const tw = parseInt(targetWords, 10);
    if (Number.isNaN(tw) || tw < 1000) {
      toast.error("目标字数需为 ≥1000 的数字");
      throw new Error("invalid_target_words");
    }
    const next = await updateBook(book.id, {
      discipline: discipline.trim() || null,
      target_audience: targetAudience.trim() || null,
      citation_style: citation || null,
      target_words: tw,
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

  async function refreshRefs() {
    const list = await listReferences(book.id);
    setFiles(list);
  }

  useEffect(() => {
    refreshRefs().catch(() => {});
    const id = window.setInterval(() => {
      refreshRefs().catch(() => {});
    }, 4000);
    return () => window.clearInterval(id);
  }, [book.id]);

  async function onDropUpload(fileList: FileList | null) {
    if (!fileList?.length) return;
    for (const f of Array.from(fileList)) {
      try {
        await uploadReference(book.id, f);
        toast.success(`已上传 ${f.name}`);
      } catch {
        toast.error(`上传失败：${f.name}`);
      }
    }
    await refreshRefs();
  }

  function applyPreset(text: string) {
    setTopicBrief((prev) => (prev.trim() ? `${prev.trim()}\n\n${text}` : text));
  }

  const parsingCount = files.filter((f) => f.parse_status === "processing" || f.parse_status === "pending").length;

  return (
    <div className="setup-view flex flex-col gap-8">
      <section className="card border border-slate-200/80 bg-white/70 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-ink">基础信息</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="text-sm">
            <span className="text-slate-600">书名</span>
            <p className="mt-1 font-medium text-ink">{book.title || "未命名"}</p>
          </div>
          <div className="text-sm">
            <span className="text-slate-600">类型</span>
            <p className="mt-1 font-medium text-ink">{BOOK_TYPE_LABEL[book.book_type]}</p>
          </div>
        </div>
      </section>

      <section className="card border border-slate-200/80 bg-white/70 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-ink">写作参数</h3>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block text-sm">
            <span className="text-slate-600">目标读者</span>
            <input
              className="input mt-1"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="例如：企业管理者、研究生…"
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">学科领域</span>
            <input className="input mt-1" value={discipline} onChange={(e) => setDiscipline(e.target.value)} />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">引用格式</span>
            <select
              className="input mt-1"
              value={citation}
              onChange={(e) => setCitation(e.target.value as CitationStyle | "")}
            >
              <option value="">无需引用</option>
              {CITATION_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">目标字数</span>
            <input className="input mt-1" type="number" min={1000} value={targetWords} onChange={(e) => setTargetWords(e.target.value)} />
          </label>
        </div>
      </section>

      <section className="card border border-slate-200/80 bg-white/70 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-ink">主题要点</h3>
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
          onChange={(e) => setTopicBrief(e.target.value)}
          placeholder="希望全书覆盖哪些论点、案例类型、语气风格等…"
        />
      </section>

      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={() => void saveMeta()}>
          保存设定
        </button>
      </div>

      <details className="card group border border-slate-200/80 bg-white/70 p-5 shadow-sm">
        <summary className="cursor-pointer list-none text-sm font-semibold text-ink [&::-webkit-details-marker]:hidden">
          参考文献 <span className="font-normal text-slate-500">（{files.length} 个文件）</span>
        </summary>
        <p className="mt-2 text-xs text-slate-500">上传 PDF / DOCX，解析完成后可用于写作检索。</p>
        <div
          className="mt-4 rounded-xl border border-dashed border-slate-300 bg-white/70 p-6 text-center"
          onDragOver={(e) => {
            e.preventDefault();
          }}
          onDrop={(e) => {
            e.preventDefault();
            onDropUpload(e.dataTransfer.files);
          }}
        >
          <p className="text-sm text-slate-600">拖拽 PDF / DOCX 到此处，或</p>
          <label className="btn-secondary mt-3 inline-flex cursor-pointer">
            选择文件
            <input
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              multiple
              onChange={(e) => onDropUpload(e.target.files)}
            />
          </label>
        </div>
        <ul className="mt-4 space-y-2 text-left text-sm">
          {files.length === 0 ? (
            <li className="text-slate-400">暂无参考资料</li>
          ) : (
            files.map((f) => (
              <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 bg-white/80 px-3 py-2">
                <span className="min-w-0 truncate font-medium text-slate-800">{f.filename}</span>
                <span className="shrink-0 text-xs text-slate-500">
                  {f.parse_status === "done"
                    ? "已解析"
                    : f.parse_status === "failed"
                      ? "解析失败"
                      : parsingCount > 0 && (f.parse_status === "processing" || f.parse_status === "pending")
                        ? "解析中…"
                        : f.parse_status}
                </span>
              </li>
            ))
          )}
        </ul>
      </details>
    </div>
  );
}
