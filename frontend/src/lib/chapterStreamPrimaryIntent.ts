import type { ChapterGenMode } from "@/lib/chapterGenMode";
import type { OutlineChapter } from "@/types/outline";

/** 与正文区「生成本章 / 重新生成」一致：正文为空时走生成 */
export type ChapterStreamPrimaryIntent = "generate" | "regenerate" | "busy" | "waiting";

export function chapterStreamPrimaryIntent(
  meta: OutlineChapter,
  opts: {
    streamingChapterIndex: number | null;
    chapterGenMode: ChapterGenMode;
    autoGenerating: boolean;
    hasBody: boolean;
  },
): ChapterStreamPrimaryIntent {
  const streamingHere = opts.streamingChapterIndex !== null && opts.streamingChapterIndex === meta.index;
  if (streamingHere || meta.status === "generating") return "busy";
  if (meta.status === "done") {
    return opts.hasBody ? "regenerate" : "generate";
  }
  if (meta.status === "pending") {
    if (
      opts.chapterGenMode === "auto" &&
      opts.autoGenerating &&
      opts.streamingChapterIndex != null &&
      opts.streamingChapterIndex !== meta.index
    ) {
      return "waiting";
    }
    return "generate";
  }
  return opts.hasBody ? "regenerate" : "generate";
}
