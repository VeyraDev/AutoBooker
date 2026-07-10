import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import axios from "axios";
import { useNavigate } from "react-router-dom";

import { createBook } from "@/api/books";
import OriginPicker from "@/features/intake/components/OriginPicker";
import type { CreationOrigin } from "@/features/intake/api/intakeApi";
import { initIntake } from "@/features/intake/api/intakeApi";
import { createOptimizationProject } from "@/api/optimization";
import { DEFAULT_TARGET_WORDS, styleOptionsFor } from "@/lib/styleTypes";
import type { BookType, StyleType } from "@/types/book";

interface Props {
  open: boolean;
  onClose: () => void;
}

type BookKind = "generate" | "optimize";
type GenerateMode = "manual" | "auto";

const ORIGIN_TO_WORKFLOW: Record<CreationOrigin, BookKind> = {
  idea_only: "generate",
  material_first: "generate",
  outline_first: "generate",
  manuscript_continue: "optimize",
};

export default function NewBookDialog({ open, onClose }: Props) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [bookType, setBookType] = useState<BookType>("nonfiction");
  const [styleType, setStyleType] = useState<StyleType>("popular_science");
  const [selectedOrigin, setSelectedOrigin] = useState<CreationOrigin | null>(null);
  const [bookKind, setBookKind] = useState<BookKind>("generate");
  const [generateMode, setGenerateMode] = useState<GenerateMode>("manual");
  const [sourceManuscript, setSourceManuscript] = useState<File | null>(null);
  const [optimizationGoals, setOptimizationGoals] = useState("");
  const [allowStructureChanges, setAllowStructureChanges] = useState(false);

  const styleOpts = styleOptionsFor(bookType);

  const mutation = useMutation({
    mutationFn: async () => {
      const book = await createBook({
        title: title.trim(),
        book_type: bookType,
        target_words: DEFAULT_TARGET_WORDS[bookType],
        style_type: styleType,
        workflow_mode: selectedOrigin === "manuscript_continue" ? "optimize_existing" : "from_scratch",
        creation_origin: selectedOrigin ?? undefined,
      });
      if (selectedOrigin && selectedOrigin !== "manuscript_continue") {
        await initIntake(book.id, {
          creation_origin: selectedOrigin,
          raw_goal_text: title.trim(),
        });
      }
      return { book_id: book.id, mode: generateMode, intake: selectedOrigin };
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["books"] });
      setTitle("");
      setBookType("nonfiction");
      setStyleType("popular_science");
      setSelectedOrigin(null);
      setBookKind("generate");
      setGenerateMode("manual");
      setSourceManuscript(null);
      setOptimizationGoals("");
      setAllowStructureChanges(false);
      onClose();
      toast.success(result.mode === "auto" ? "书稿已创建，请先确认项目输入" : "书稿已创建");
      if (result.intake) {
        const suffix = result.mode === "auto" ? "?intake=1&auto=1" : "?intake=1";
        navigate(`/app/books/${result.book_id}${suffix}`);
      } else {
        navigate(`/app/books/${result.book_id}`);
      }
    },
    onError: (err) => {
      const msg =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : generateMode === "auto"
            ? "未能开始一键成书，请稍后重试"
            : "创建失败";
      toast.error(msg);
    },
  });

  const optimizeMutation = useMutation({
    mutationFn: async () => {
      if (!sourceManuscript) throw new Error("missing_source");
      return createOptimizationProject(
        sourceManuscript,
        optimizationGoals.split(/\n|；|;/).map((x) => x.trim()).filter(Boolean),
        allowStructureChanges,
      );
    },
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: ["books"] });
      setSourceManuscript(null);
      setOptimizationGoals("");
      setAllowStructureChanges(false);
      setSelectedOrigin(null);
      setBookKind("generate");
      setGenerateMode("manual");
      onClose();
      toast.success("原始书稿已上传，正在分析");
      navigate(`/app/books/${project.book_id}/optimize`);
    },
    onError: (err) => {
      toast.error(err instanceof Error && err.message === "missing_source" ? "请选择原始书稿" : "未能创建优化项目，请稍后重试");
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
    setSelectedOrigin(null);
    setBookKind("generate");
    setGenerateMode("manual");
    setSourceManuscript(null);
    setOptimizationGoals("");
    setAllowStructureChanges(false);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
        <h2 className="text-lg font-medium text-ink mb-4">新建书稿</h2>
        {!selectedOrigin ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">选择创作起点</p>
            <OriginPicker
              onSelect={(origin) => {
                setSelectedOrigin(origin);
                const kind = ORIGIN_TO_WORKFLOW[origin];
                if (kind === "optimize") setBookKind("optimize");
                else setBookKind("generate");
              }}
            />
            <div className="flex justify-end pt-2">
              <button type="button" onClick={resetAndClose} className="btn-secondary">取消</button>
            </div>
          </div>
        ) : (
        <>
        {bookKind === "optimize" ? (
          <div className="space-y-4 py-2">
            <div>
              <label className="block text-sm text-slate-600 mb-1">原始书稿</label>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                className="input text-sm"
                onChange={(e) => setSourceManuscript(e.target.files?.[0] ?? null)}
              />
              <p className="mt-1 text-xs text-slate-500">原稿将保存为不可覆盖的基线版本。</p>
            </div>
            <label className="block text-sm">
              <span className="text-slate-600">优化目标</span>
              <textarea
                className="input mt-1 min-h-[90px]"
                value={optimizationGoals}
                onChange={(e) => setOptimizationGoals(e.target.value)}
                placeholder="例如：改善章节逻辑；减少重复；统一术语"
              />
            </label>
            <label className="flex items-start gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                className="mt-0.5"
                checked={allowStructureChanges}
                onChange={(e) => setAllowStructureChanges(e.target.checked)}
              />
              允许调整章节结构（默认关闭）
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={resetAndClose} className="btn-secondary">取消</button>
              <button
                type="button"
                disabled={optimizeMutation.isPending}
                onClick={() => optimizeMutation.mutate()}
                className="btn-primary"
              >
                {optimizeMutation.isPending ? "正在上传…" : "开始分析"}
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="mb-4 flex gap-2">
              <button
                type="button"
                className={`flex-1 rounded-lg border px-3 py-2 text-xs ${generateMode === "manual" ? "border-slate-300 bg-slate-50 text-slate-800" : "border-slate-200 text-slate-600"}`}
                onClick={() => setGenerateMode("manual")}
              >
                分步创作
              </button>
              <button
                type="button"
                className={`flex-1 rounded-lg border px-3 py-2 text-xs ${generateMode === "auto" ? "border-slate-300 bg-slate-50 text-slate-800" : "border-slate-200 text-slate-600"}`}
                onClick={() => setGenerateMode("auto")}
              >
                一键成书
              </button>
            </div>
            {generateMode === "auto" ? (
              <p className="mb-3 text-[11px] leading-relaxed text-slate-500">
                确认项目输入和写作方案后，系统再自动推进大纲、写作和配图。
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
                  {mutation.isPending ? "创建中..." : generateMode === "auto" ? "创建并确认输入" : "创建书稿"}
                </button>
              </div>
            </form>
          </>
        )}
        </>
        )}
      </div>
    </div>
  );
}
