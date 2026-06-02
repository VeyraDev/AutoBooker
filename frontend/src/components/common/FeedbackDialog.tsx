import { useMutation } from "@tanstack/react-query";
import { MessageSquarePlus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import toast from "react-hot-toast";

import { submitFeedback } from "@/api/feedback";
import { fetchCommunityQrUrl } from "@/api/notifications";

type Props = {
  open: boolean;
  onClose: () => void;
  bookId?: string;
};

export default function FeedbackDialog({ open, onClose, bookId }: Props) {
  const [type, setType] = useState("feature");
  const [content, setContent] = useState("");
  const [qrUrl, setQrUrl] = useState("");

  useEffect(() => {
    if (!open) return;
    void fetchCommunityQrUrl().then(setQrUrl).catch(() => setQrUrl(""));
  }, [open]);

  const mutation = useMutation({
    mutationFn: () =>
      submitFeedback({
        type,
        content: content.trim(),
        page_url: typeof window !== "undefined" ? window.location.href : undefined,
        book_id: bookId,
      }),
    onSuccess: () => {
      toast.success("感谢反馈，我们已收到");
      setContent("");
      onClose();
    },
    onError: () => toast.error("提交失败"),
  });

  if (!open) return null;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (content.trim().length < 5) {
      toast.error("请至少输入 5 个字");
      return;
    }
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/40 px-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
        <div className="mb-4 flex items-center gap-2">
          <MessageSquarePlus className="h-5 w-5 text-indigo-600" />
          <h2 className="text-lg font-medium text-ink">意见反馈</h2>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-600 mb-1">类型</label>
            <select className="input" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="bug">Bug</option>
              <option value="feature">功能建议</option>
              <option value="experience">体验问题</option>
              <option value="other">其他</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">描述</label>
            <textarea
              className="input min-h-[120px]"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="请描述问题或建议…"
            />
          </div>
          {qrUrl ? (
            <div className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-center">
              <p className="text-xs text-slate-500 mb-2">扫码加入读者群</p>
              <img src={qrUrl} alt="社群二维码" className="mx-auto h-28 w-28 object-contain" />
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>
              取消
            </button>
            <button type="submit" className="btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? "提交中…" : "提交"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
