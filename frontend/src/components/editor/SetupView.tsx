import { useEffect, useState } from "react";
import toast from "react-hot-toast";

import { listReferences, uploadReference } from "@/api/references";
import { updateBook } from "@/api/books";
import type { Book, CitationStyle } from "@/types/book";
import type { ReferenceFile } from "@/types/reference";

const CITATION_OPTIONS: { value: CitationStyle; label: string }[] = [
  { value: "apa", label: "APA" },
  { value: "mla", label: "MLA" },
  { value: "chicago", label: "Chicago" },
  { value: "gb_t7714", label: "GB/T 7714" },
];

const topicKey = (bookId: string) => `autobooker_topic_brief_${bookId}`;
const audienceKey = (bookId: string) => `autobooker_target_audience_${bookId}`;

type Props = {
  book: Book;
  onBookPatched: (b: Book) => void;
  onGenerateOutline: (payload: { topic_override?: string | null; target_audience?: string | null }) => Promise<void>;
  generating: boolean;
  outlineLocked: boolean;
};

export default function SetupView({
  book,
  onBookPatched,
  onGenerateOutline,
  generating,
  outlineLocked,
}: Props) {
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
      return;
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

  return (
    <div className="setup-view space-y-6">
      <div>
        <h2 className="text-lg font-medium text-ink">书稿设定</h2>
        <p className="mt-1 text-sm text-slate-500">
          补充写作参数与参考资料；已进入写作阶段后仍可在此保存「目标读者」等字段。
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
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

      <label className="block text-sm">
        <span className="text-slate-600">写作需求 / 主题要点（可选，提交到大纲生成）</span>
        <textarea
          className="input mt-1 min-h-[120px]"
          value={topicBrief}
          onChange={(e) => setTopicBrief(e.target.value)}
          placeholder="希望全书覆盖哪些论点、案例类型、语气风格等…"
        />
      </label>

      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-secondary" onClick={() => saveMeta()}>
          保存设定
        </button>
      </div>

      <div
        className="rounded-xl border border-dashed border-slate-300 bg-white/70 p-6 text-center"
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
        <ul className="mt-4 space-y-1 text-left text-xs text-slate-500">
          {files.map((f) => (
            <li key={f.id} className="flex justify-between gap-2">
              <span className="truncate">{f.filename}</span>
              <span className="shrink-0">{f.parse_status}</span>
            </li>
          ))}
          {files.length === 0 ? <li>暂无参考资料</li> : null}
        </ul>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-primary"
            disabled={generating || outlineLocked}
            onClick={() =>
              onGenerateOutline({
                topic_override: topicBrief.trim() || null,
                target_audience: targetAudience.trim() || null,
              })
            }
          >
            {generating ? "大纲生成中…" : outlineLocked ? "已定稿 · 不可重新生成大纲" : "生成大纲"}
          </button>
        </div>
        {outlineLocked ? (
          <p className="text-xs leading-relaxed text-slate-500">
            已进入写作阶段：左侧目录可切换章节；点「书稿设定」仍可查看本页。大纲生成按钮已锁定（后端状态）；章节正文进度请以大目录旁的状态为准（待撰写 / 生成中 /
            正文已完成）。
          </p>
        ) : (
          <p className="text-xs text-slate-400">生成大纲会使用上方的主题要点与目标读者（请先保存设定）。</p>
        )}
      </div>
    </div>
  );
}
