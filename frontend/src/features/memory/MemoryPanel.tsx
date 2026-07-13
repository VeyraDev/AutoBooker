import { Pencil, Trash2, Check, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import toast from "react-hot-toast";

import {
  deleteMemory,
  listMemories,
  MEMORY_TYPE_LABELS,
  patchMemory,
  STRENGTH_LABELS,
  type ProjectMemory,
} from "@/features/memory/memoryApi";

type Props = {
  bookId: string;
  refreshKey?: number;
};

export default function MemoryPanel({ bookId, refreshKey = 0 }: Props) {
  const [rows, setRows] = useState<ProjectMemory[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listMemories(bookId);
      setRows(data);
    } catch {
      toast.error("加载项目记忆失败");
    } finally {
      setLoading(false);
    }
  }, [bookId]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const startEdit = (row: ProjectMemory) => {
    setEditingId(row.id);
    setEditContent(row.content);
  };

  const saveEdit = async (row: ProjectMemory) => {
    const content = editContent.trim();
    if (!content) {
      toast.error("内容不能为空");
      return;
    }
    try {
      const updated = await patchMemory(bookId, row.id, { content });
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)));
      setEditingId(null);
      toast.success("已保存");
    } catch {
      toast.error("保存失败");
    }
  };

  const toggleConfirmed = async (row: ProjectMemory) => {
    try {
      const updated = await patchMemory(bookId, row.id, { confirmed: !row.confirmed });
      setRows((prev) => prev.map((r) => (r.id === row.id ? updated : r)));
    } catch {
      toast.error("更新失败");
    }
  };

  const remove = async (row: ProjectMemory) => {
    if (!window.confirm("确定删除这条记忆？")) return;
    try {
      await deleteMemory(bookId, row.id);
      setRows((prev) => prev.filter((r) => r.id !== row.id));
      toast.success("已删除");
    } catch {
      toast.error("删除失败");
    }
  };

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">加载记忆…</div>;
  }

  if (!rows.length) {
    return (
      <div className="p-4 text-sm text-gray-500">
        暂无项目记忆。与助手多轮对话后，关键决策与禁令会沉淀在这里。
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 p-3 overflow-y-auto max-h-full">
      {rows.map((row) => (
        <div key={row.id} className="rounded-lg border border-gray-200 bg-white p-3 text-sm shadow-sm">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
              {MEMORY_TYPE_LABELS[row.memory_type] ?? row.memory_type}
            </span>
            <span className="rounded bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
              {STRENGTH_LABELS[row.strength] ?? row.strength}
            </span>
            {row.confirmed ? (
              <span className="rounded bg-green-50 px-2 py-0.5 text-xs text-green-700">已确认</span>
            ) : (
              <span className="rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">待确认</span>
            )}
          </div>
          {editingId === row.id ? (
            <textarea
              className="mb-2 w-full rounded border border-gray-300 p-2 text-sm"
              rows={3}
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
            />
          ) : (
            <p className="mb-2 whitespace-pre-wrap text-gray-800">{row.content}</p>
          )}
          <div className="flex gap-2">
            {editingId === row.id ? (
              <>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs text-white"
                  onClick={() => void saveEdit(row)}
                >
                  <Check className="h-3 w-3" />
                  保存
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs"
                  onClick={() => setEditingId(null)}
                >
                  <X className="h-3 w-3" />
                  取消
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs"
                  onClick={() => startEdit(row)}
                >
                  <Pencil className="h-3 w-3" />
                  编辑
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border px-2 py-1 text-xs"
                  onClick={() => void toggleConfirmed(row)}
                >
                  {row.confirmed ? "取消确认" : "确认"}
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded border border-red-200 px-2 py-1 text-xs text-red-600"
                  onClick={() => void remove(row)}
                >
                  <Trash2 className="h-3 w-3" />
                  删除
                </button>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
