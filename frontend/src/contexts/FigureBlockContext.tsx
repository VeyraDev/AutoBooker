import type { FigureOut } from "@/api/figures";
import { createContext, useContext } from "react";
import type { Editor } from "@tiptap/core";

export type FigureBlockContextValue = {
  bookId: string;
  chapterIndex: number;
  editor: Editor | null;
  /** 文档修订序号，figureBlock 增删/移动后递增，用于刷新图号 */
  figureDocRevision: number;
  /** 本章 TipTap 中该 figureBlock 的序号（从 1 起），未找到返回 0 */
  getFigureOrdinal: (figureId: string) => number;
  onFigureUpdated: (figureId: string, patch: Record<string, unknown>) => void;
  /** 按当前编辑器文档重算后端图号并写回 attrs；返回本章图表列表 */
  refreshFigureNumbers: () => Promise<FigureOut[]>;
  onQuoteFigure?: (figureId: string, annotation: string) => void;
};

export const FigureBlockContext = createContext<FigureBlockContextValue | null>(null);

export function useFigureBlockContext(): FigureBlockContextValue {
  const ctx = useContext(FigureBlockContext);
  if (!ctx) {
    return {
      bookId: "",
      chapterIndex: 0,
      editor: null,
      figureDocRevision: 0,
      getFigureOrdinal: () => 0,
      onFigureUpdated: () => {},
      refreshFigureNumbers: async () => [],
    };
  }
  return ctx;
}
