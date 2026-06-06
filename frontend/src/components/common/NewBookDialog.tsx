import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import axios from "axios";
import { useNavigate } from "react-router-dom";

import { startAutoGenerate } from "@/api/bookJobs";
import { createBook } from "@/api/books";
import { fetchLlmModels } from "@/api/config";
import { effectiveSceneModel } from "@/lib/bookAiModels";
import { DEFAULT_TARGET_WORDS, styleOptionsFor } from "@/lib/styleTypes";
import { useAiModelPrefsStore } from "@/stores/aiModelPrefsStore";
import type { BookType, StyleType } from "@/types/book";

interface Props {
  open: boolean;
  onClose: () => void;
}

type Mode = "manual" | "auto";

export default function NewBookDialog({ open, onClose }: Props) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [bookType, setBookType] = useState<BookType>("nonfiction");
  const [styleType, setStyleType] = useState<StyleType>("popular_science");
  const [discipline, setDiscipline] = useState("");
  const [mode, setMode] = useState<Mode>("manual");

  const styleOpts = styleOptionsFor(bookType);
  const { prefs } = useAiModelPrefsStore();

  const mutation = useMutation({
    mutationFn: async () => {
      if (mode === "auto") {
        return startAutoGenerate({
          title: title.trim(),
          book_type: bookType,
          style_type: styleType,
          discipline: bookType === "academic" && discipline ? discipline : null,
        });
      }
      const catalog = await fetchLlmModels().catch(() => undefined);
      const writing = effectiveSceneModel("writing", { prefs, catalog });
      const book = await createBook({
        title: title.trim(),
        book_type: bookType,
        discipline: bookType === "academic" && discipline ? discipline : null,
        target_words: DEFAULT_TARGET_WORDS[bookType],
        style_type: styleType,
        ai_model: writing,
        outline_ai_model: effectiveSceneModel("outline", { prefs, catalog }),
        constitution_ai_model: effectiveSceneModel("constitution", { prefs, catalog }),
        writing_ai_model: writing,
      });
      return { book_id: book.id, id: "", status: "setup", current_step: null, progress_pct: 0, error_message: null };
    },
    onSuccess: (result) => {
      toast.success(mode === "auto" ? "已开始一键生成，完成后将通知您" : "已创建");
      qc.invalidateQueries({ queryKey: ["books"] });
      setTitle("");
      setDiscipline("");
      setBookType("nonfiction");
      setStyleType("popular_science");
      setMode("manual");
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
        <h2 className="text-lg font-medium text-ink mb-4">新建书稿</h2>
        <div className="mb-4 flex gap-2">
          <button
            type="button"
            className={`flex-1 rounded-lg border px-3 py-2 text-xs ${mode === "manual" ? "border-indigo-500 bg-indigo-50 text-indigo-800" : "border-slate-200 text-slate-600"}`}
            onClick={() => setMode("manual")}
          >
            手动创建
          </button>
          <button
            type="button"
            className={`flex-1 rounded-lg border px-3 py-2 text-xs ${mode === "auto" ? "border-indigo-500 bg-indigo-50 text-indigo-800" : "border-slate-200 text-slate-600"}`}
            onClick={() => setMode("auto")}
          >
            一键生成
          </button>
        </div>
        {mode === "auto" ? (
          <p className="mb-3 text-[11px] leading-relaxed text-slate-500">
            自动完成：基础设定 → 文献检索 → 大纲 → 前言 → 逐章写作。不含自动配图、降 AI 率与审校修复。
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
              <option value="nonfiction">大众非虚构（默认目标约 8 万字）</option>
              <option value="academic">学术专著（默认目标约 20 万字）</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">二级体裁</label>
            <select value={styleType} onChange={(e) => setStyleType(e.target.value as StyleType)} className="input">
              {styleOpts.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          {bookType === "academic" && (
            <div>
              <label className="block text-sm text-slate-600 mb-1">学科（可选）</label>
              <input
                maxLength={100}
                value={discipline}
                onChange={(e) => setDiscipline(e.target.value)}
                className="input"
                placeholder="例如：社会学 / 计算机科学"
              />
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              取消
            </button>
            <button type="submit" disabled={mutation.isPending} className="btn-primary">
              {mutation.isPending
                ? mode === "auto"
                  ? "启动中..."
                  : "创建中..."
                : mode === "auto"
                  ? "开始一键生成"
                  : "创建"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
