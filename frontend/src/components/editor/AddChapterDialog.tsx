type Props = {
  open: boolean;
  onClose: () => void;
  onChoose: (mode: "ai" | "manual") => void;
};

export default function AddChapterDialog({ open, onClose, onChoose }: Props) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h3 className="text-lg font-medium text-ink">新增章节</h3>
        <p className="mt-2 text-sm text-slate-600">请选择创作方式：</p>
        <div className="mt-6 flex flex-col gap-3">
          <button type="button" className="btn-primary w-full" onClick={() => onChoose("ai")}>
            AI 协作生成
          </button>
          <button type="button" className="btn-secondary w-full" onClick={() => onChoose("manual")}>
            自由编辑（空白章节）
          </button>
          <button type="button" className="mt-2 text-sm text-slate-500 hover:text-slate-800" onClick={onClose}>
            取消
          </button>
        </div>
      </div>
    </div>
  );
}
