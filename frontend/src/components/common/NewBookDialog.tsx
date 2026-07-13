import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import axios from "axios";
import { useNavigate } from "react-router-dom";

import { createBook } from "@/api/books";
import { bootstrapProjectStart } from "@/features/intake/api/intakeApi";
import { startAutoGenerateForBook } from "@/api/bookJobs";
import { autoBookProgressPath } from "@/lib/bookRoutes";
import { DEFAULT_TARGET_WORDS } from "@/lib/styleTypes";

interface Props {
  open: boolean;
  onClose: () => void;
}

async function createProjectBook(brief: string) {
  const book = await createBook({
    book_type: "nonfiction",
    target_words: DEFAULT_TARGET_WORDS.nonfiction,
    style_type: "popular_science",
    workflow_mode: "from_scratch",
    creation_origin: "idea_only",
  });
  await bootstrapProjectStart(book.id, {
    creation_origin: "idea_only",
    raw_goal_text: brief,
  });
  return book;
}

export default function NewBookDialog({ open, onClose }: Props) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [brief, setBrief] = useState("");

  const refineMutation = useMutation({
    mutationFn: async () => createProjectBook(brief.trim()),
    onSuccess: (book) => {
      qc.invalidateQueries({ queryKey: ["books"] });
      setBrief("");
      onClose();
      toast.success("已创建书稿，可在助手中继续完善");
      navigate(`/app/books/${book.id}`);
    },
    onError: (err) => {
      toast.error(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "创建失败，请重试",
      );
    },
  });

  const autoMutation = useMutation({
    mutationFn: async () => {
      const book = await createProjectBook(brief.trim());
      await startAutoGenerateForBook(book.id);
      return book;
    },
    onSuccess: (book) => {
      qc.invalidateQueries({ queryKey: ["books"] });
      setBrief("");
      onClose();
      toast.success("一键生成已开始");
      navigate(autoBookProgressPath(book.id));
    },
    onError: (err) => {
      toast.error(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "未能启动一键生成，请重试",
      );
    },
  });

  if (!open) return null;

  const busy = refineMutation.isPending || autoMutation.isPending;

  function handleRefine() {
    if (!brief.trim()) {
      toast.error("请先说说你想写什么");
      return;
    }
    refineMutation.mutate();
  }

  function handleAuto() {
    if (!brief.trim()) {
      toast.error("请先说说你想写什么");
      return;
    }
    autoMutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-lg">
        <h2 className="text-lg font-medium text-ink mb-1">新建书稿</h2>
        <p className="mb-4 text-sm text-slate-500">一句话、一段想法、大纲片段或资料说明都可以。</p>
        <label className="block">
          <span className="mb-1 block text-sm text-slate-600">先说说你想写什么</span>
          <textarea
            autoFocus
            rows={5}
            maxLength={8000}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            className="input min-h-[120px] resize-y"
            placeholder="例如：一本面向产品经理的 AI 应用实战书，侧重落地案例，不要趋势综述…"
          />
        </label>
        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={busy} className="btn-secondary order-3 sm:order-1">
            取消
          </button>
          <button type="button" onClick={handleRefine} disabled={busy} className="btn-secondary order-1 sm:order-2">
            {refineMutation.isPending ? "创建中…" : "继续完善"}
          </button>
          <button type="button" onClick={handleAuto} disabled={busy} className="btn-primary order-2 sm:order-3">
            {autoMutation.isPending ? "启动中…" : "一键生成"}
          </button>
        </div>
      </div>
    </div>
  );
}
