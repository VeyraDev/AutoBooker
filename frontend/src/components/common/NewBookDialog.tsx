import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import axios from "axios";
import { useNavigate } from "react-router-dom";

import { createBook } from "@/api/books";
import { DEFAULT_TARGET_WORDS, styleOptionsFor } from "@/lib/styleTypes";
import type { BookType, StyleType } from "@/types/book";

interface Props {
  open: boolean;
  onClose: () => void;
}

type BookKind = "generate" | "optimize";
type GenerateMode = "manual" | "auto";

const PENDING_AUTO_KEY = "autobooker_pending_auto";

export function consumePendingAutoGenerate(bookId: string): boolean {
  try {
    const raw = sessionStorage.getItem(PENDING_AUTO_KEY);
    if (raw === bookId) {
      sessionStorage.removeItem(PENDING_AUTO_KEY);
      return true;
    }
  } catch {
    /* ignore */
  }
  return false;
}

export default function NewBookDialog({ open, onClose }: Props) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [bookType, setBookType] = useState<BookType>("nonfiction");
  const [styleType, setStyleType] = useState<StyleType>("popular_science");
  const [bookKind, setBookKind] = useState<BookKind>("generate");
  const [generateMode, setGenerateMode] = useState<GenerateMode>("manual");

  const styleOpts = styleOptionsFor(bookType);

  const mutation = useMutation({
    mutationFn: async () => {
      const book = await createBook({
        title: title.trim(),
        book_type: bookType,
        target_words: DEFAULT_TARGET_WORDS[bookType],
        style_type: styleType,
      });
      return { book_id: book.id, mode: generateMode };
    },
    onSuccess: (result) => {
      if (result.mode === "auto") {
        try {
          sessionStorage.setItem(PENDING_AUTO_KEY, result.book_id);
        } catch {
          /* ignore */
        }
        toast.success("已创建，请在设定页确认后一键生成");
      } else {
        toast.success("已创建");
      }
      qc.invalidateQueries({ queryKey: ["books"] });
      setTitle("");
      setBookType("nonfiction");
      setStyleType("popular_science");
      setBookKind("generate");
      setGenerateMode("manual");
      onClose();
      navigate(`/app/books/${result.book_id}`);
    },
    onError: (err) => {
      const msg =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "创建失败";
      toast.error(msg);
    },
  });

  if (!open) return null;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      toast.error("请输入书名");
      return;
    }
    mutation.mutate();
  }

  function resetAndClose() {
    setBookKind("generate");
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
        <h2 className="text-lg font-medium text-ink mb-4">新建书稿</h2>
        <div className="mb-4 flex gap-2">
          <button
            type="button"
            className={`flex-1 rounded-lg border px-3 py-2 text-xs ${bookKind === "generate" ? "border-indigo-500 bg-indigo-50 text-indigo-800" : "border-slate-200 text-slate-600"}`}
            onClick={() => setBookKind("generate")}
          >
            生成新书
          </button>
          <button
            type="button"
            className={`flex-1 rounded-lg border px-3 py-2 text-xs ${bookKind === "optimize" ? "border-indigo-500 bg-indigo-50 text-indigo-800" : "border-slate-200 text-slate-600"}`}
            onClick={() => setBookKind("optimize")}
          >
            优化新书
          </button>
        </div>

        {bookKind === "optimize" ? (
          <div className="py-8 text-center">
            <p className="text-sm text-slate-500">优化新书功能开发中，敬请期待。</p>
            <button type="button" onClick={resetAndClose} className="btn-secondary mt-6">
              关闭
            </button>
          </div>
        ) : (
          <>
            <div className="mb-4 flex gap-2">
              <button
                type="button"
                className={`flex-1 rounded-lg border px-3 py-2 text-xs ${generateMode === "manual" ? "border-slate-300 bg-slate-50 text-slate-800" : "border-slate-200 text-slate-600"}`}
                onClick={() => setGenerateMode("manual")}
              >
                手动创建
              </button>
              <button
                type="button"
                className={`flex-1 rounded-lg border px-3 py-2 text-xs ${generateMode === "auto" ? "border-slate-300 bg-slate-50 text-slate-800" : "border-slate-200 text-slate-600"}`}
                onClick={() => setGenerateMode("auto")}
              >
                一键出书
              </button>
            </div>
            {generateMode === "auto" ? (
              <p className="mb-3 text-[11px] leading-relaxed text-slate-500">
                先进入书稿设定页补充或确认设定，再开始自动完成：文献检索 → 大纲 → 叙事宪法 → 逐章写作。
              </p>
            ) : null}
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-slate-600 mb-1">书名</label>
                <input
                  autoFocus
                  maxLength={500}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="input"
                  placeholder="例如：人工智能如何改变商业决策"
                />
              </div>
              <div>
                <label className="block text-sm text-slate-600 mb-1">一级分类</label>
                <select
                  value={bookType}
                  onChange={(e) => {
                    const bt = e.target.value as BookType;
                    setBookType(bt);
                    const opts = styleOptionsFor(bt);
                    setStyleType(opts[0]?.value ?? "popular_science");
                  }}
                  className="input"
                >
                  <option value="nonfiction">大众非虚构</option>
                  <option value="academic">学术专著</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-600 mb-1">二级分类（体裁）</label>
                <select value={styleType} onChange={(e) => setStyleType(e.target.value as StyleType)} className="input">
                  {styleOpts.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={resetAndClose} className="btn-secondary">
                  取消
                </button>
                <button type="submit" disabled={mutation.isPending} className="btn-primary">
                  {mutation.isPending ? "创建中..." : generateMode === "auto" ? "创建并进入设定" : "创建"}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
