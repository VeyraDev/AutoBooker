import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import toast from "react-hot-toast";

import { getPreface, openPrefaceGenerateStream, putPreface, type PrefaceData } from "@/api/preface";

type Props = {
  bookId: string;
  /** 由目录栏/父级统一驱动流式生成时使用 */
  generating?: boolean;
  streamMd?: string | null;
  onGenerate?: () => void;
};

export default function PrefaceWritingPanel({
  bookId,
  generating: generatingProp,
  streamMd: streamMdProp,
  onGenerate,
}: Props) {
  const [pf, setPf] = useState<PrefaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [localGenerating, setLocalGenerating] = useState(false);
  const [localStreamMd, setLocalStreamMd] = useState("");

  const generating = generatingProp ?? localGenerating;
  const streamMd = streamMdProp ?? localStreamMd;

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getPreface(bookId);
      setPf(data);
    } catch {
      toast.error("加载前言失败");
    } finally {
      setLoading(false);
    }
  }, [bookId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleGenerateInternal() {
    setLocalGenerating(true);
    setLocalStreamMd("");
    try {
      const res = await openPrefaceGenerateStream(bookId);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let full = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const payload = JSON.parse(line.slice(5).trim()) as {
            token?: string;
            done?: boolean;
            markdown?: string;
            partial?: boolean;
            error?: string;
          };
          if (payload.token) {
            full += payload.token;
            setLocalStreamMd(full);
          }
          if (payload.done) {
            const md = typeof payload.markdown === "string" ? payload.markdown : full;
            if (md.trim()) {
              const wc = md.replace(/\n/g, "").replace(/ /g, "").length;
              const data = await putPreface(bookId, {
                text: md,
                summary: md.slice(0, 500),
                word_count: wc,
                status: "done",
              });
              setPf(data);
            } else {
              await reload();
            }
            toast.success(payload.partial ? "前言已保存（生成未完全结束）" : "前言已生成");
          }
          if (payload.error) throw new Error(payload.error);
        }
      }
      if (!full.trim()) return;
      const wc = full.replace(/\n/g, "").replace(/ /g, "").length;
      const data = await putPreface(bookId, {
        text: full,
        summary: full.slice(0, 500),
        word_count: wc,
        status: "done",
      });
      setPf(data);
      toast.success("前言内容已保存");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "前言生成失败");
    } finally {
      setLocalGenerating(false);
    }
  }

  function handleGenerate() {
    if (onGenerate) onGenerate();
    else void handleGenerateInternal();
  }

  async function handleSaveBrief(brief: string) {
    try {
      const data = await putPreface(bookId, { brief });
      setPf(data);
    } catch {
      toast.error("保存失败");
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-500">加载前言…</p>;
  }

  if (!pf?.enabled) {
    return (
      <div className="rounded-lg border border-slate-100 bg-white/80 p-6 text-sm text-slate-600">
        <p>本书未启用前言。可在大纲页「前言」卡片中开启。</p>
      </div>
    );
  }

  const displayMd =
    generating && streamMd
      ? streamMd
      : pf.text?.trim() || pf.summary?.trim() || null;
  const hasBody = Boolean(pf.tiptap_json) || Boolean(displayMd) || (pf.word_count ?? 0) > 0;

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-lg font-semibold text-ink">前言</h2>
        <p className="mt-1 text-xs text-slate-500">
          目标约 {pf.target_words?.toLocaleString() ?? "3,000"} 字
          {pf.word_count ? ` · 当前 ${pf.word_count.toLocaleString()} 字` : ""}
        </p>
      </header>

      <label className="block text-sm">
        <span className="text-slate-600">写作要点</span>
        <textarea
          className="input mt-1 min-h-[80px] text-sm"
          defaultValue={pf.brief}
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v !== (pf.brief || "").trim()) void handleSaveBrief(v);
          }}
        />
      </label>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn-primary text-sm"
          disabled={generating}
          onClick={handleGenerate}
        >
          {generating ? (
            <>
              <Loader2 className="mr-1.5 inline h-4 w-4 animate-spin" aria-hidden />
              生成中…
            </>
          ) : hasBody ? (
            "重新生成前言"
          ) : (
            "生成前言"
          )}
        </button>
      </div>

      {displayMd ? (
        <article className="prose prose-sm max-w-none rounded-lg border border-slate-100 bg-white/90 p-4">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayMd}</ReactMarkdown>
        </article>
      ) : (
        <p className="text-sm text-slate-500">暂无前言正文，点击侧栏或上方按钮生成。</p>
      )}
    </div>
  );
}
