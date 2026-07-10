import { useEffect, useState } from "react";

type Props = {
  text: string;
  onConfirm: (text: string) => void;
  loading?: boolean;
};

export default function WritingPlanReview({ text, onConfirm, loading }: Props) {
  const [edited, setEdited] = useState(text);

  useEffect(() => {
    setEdited(text);
  }, [text]);

  return (
    <div className="space-y-4">
      <label className="block text-sm">
        给后续写作系统的说明（可编辑）
        <textarea className="mt-1 w-full rounded border p-2 text-sm" rows={8} value={edited} onChange={(e) => setEdited(e.target.value)} />
      </label>
      <button type="button" className="rounded bg-brand px-4 py-2 text-sm text-white" disabled={loading} onClick={() => onConfirm(edited)}>
        确认并用于后续写作
      </button>
    </div>
  );
}
