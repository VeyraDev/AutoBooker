import { useState } from "react";

type Props = {
  text: string;
  unclearQuestions?: string[] | null;
  onCorrect: (correction: string) => Promise<void>;
  onConfirm: () => void;
  loading?: boolean;
};

export default function UnderstandingReview({ text, unclearQuestions, onCorrect, onConfirm, loading }: Props) {
  const [correction, setCorrection] = useState("");

  return (
    <div className="space-y-4">
      <div className="rounded border bg-slate-50 p-4 text-sm whitespace-pre-wrap">{text || "正在理解…"}</div>
      {unclearQuestions?.length ? (
        <ul className="list-disc pl-5 text-sm text-amber-800">
          {unclearQuestions.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ul>
      ) : null}
      <label className="block text-sm">
        自然语言修正
        <textarea
          className="mt-1 w-full rounded border p-2"
          rows={3}
          value={correction}
          onChange={(e) => setCorrection(e.target.value)}
          placeholder="例如：目标读者是大学生，不是大众…"
        />
      </label>
      <div className="flex gap-2">
        {correction.trim() ? (
          <button
            type="button"
            className="rounded border px-4 py-2 text-sm"
            disabled={loading}
            onClick={() => void onCorrect(correction.trim())}
          >
            提交修正
          </button>
        ) : null}
        <button type="button" className="rounded bg-brand px-4 py-2 text-sm text-white" disabled={loading} onClick={onConfirm}>
          确认理解并生成写作方案
        </button>
      </div>
    </div>
  );
}
