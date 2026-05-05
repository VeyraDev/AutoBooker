import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import axios from "axios";

import { createBook } from "@/api/books";
import type { BookType } from "@/types/book";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function NewBookDialog({ open, onClose }: Props) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [bookType, setBookType] = useState<BookType>("nonfiction");
  const [discipline, setDiscipline] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      createBook({
        title: title.trim(),
        book_type: bookType,
        discipline: bookType === "academic" && discipline ? discipline : null,
      }),
    onSuccess: () => {
      toast.success("已创建");
      qc.invalidateQueries({ queryKey: ["books"] });
      setTitle("");
      setDiscipline("");
      setBookType("nonfiction");
      onClose();
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
            <label className="block text-sm text-slate-600 mb-1">书类</label>
            <select
              value={bookType}
              onChange={(e) => setBookType(e.target.value as BookType)}
              className="input"
            >
              <option value="nonfiction">大众非虚构</option>
              <option value="academic">学术专著</option>
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
            <button
              type="submit"
              disabled={mutation.isPending}
              className="btn-primary"
            >
              {mutation.isPending ? "创建中..." : "创建"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
