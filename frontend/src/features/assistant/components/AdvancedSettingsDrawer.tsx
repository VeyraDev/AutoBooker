import { X } from "lucide-react";
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import SetupView from "@/components/editor/SetupView";
import type { Book } from "@/types/book";

type Props = {
  open: boolean;
  book: Book;
  onClose: () => void;
};

export default function AdvancedSettingsDrawer({ open, book, onClose }: Props) {
  const qc = useQueryClient();

  useEffect(() => {
    if (!open) return;
    // 打开时拉取助手刚同步的 Book / WritingBasis，避免高级编辑仍是旧设定
    void qc.invalidateQueries({ queryKey: ["book", book.id] });
    void qc.invalidateQueries({ queryKey: ["writingBasis", book.id] });
  }, [open, book.id, qc]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30">
      <button type="button" className="flex-1" aria-label="关闭" onClick={onClose} />
      <aside className="flex h-full w-full max-w-xl flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <h2 className="text-base font-medium text-ink">高级编辑</h2>
            <p className="text-xs text-slate-500">与项目要点同一套书稿设定；含书名、读者、体裁、策划细节与资料</p>
          </div>
          <button
            type="button"
            onClick={() => {
              void qc.invalidateQueries({ queryKey: ["book", book.id] });
              void qc.invalidateQueries({ queryKey: ["writingBasis", book.id] });
              onClose();
            }}
            className="rounded p-1 text-slate-500 hover:bg-slate-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <SetupView
            book={book}
            onBookPatched={(b) => {
              qc.setQueryData(["book", book.id], b);
            }}
          />
        </div>
      </aside>
    </div>
  );
}
