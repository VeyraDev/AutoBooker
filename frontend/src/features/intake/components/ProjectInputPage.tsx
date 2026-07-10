import { useEffect, useRef, useState } from "react";
import OriginPicker from "@/features/intake/components/OriginPicker";
import UnderstandingReview from "@/features/intake/components/UnderstandingReview";
import WritingPlanReview from "@/features/intake/components/WritingPlanReview";
import { useIntakeFlow } from "@/features/intake/hooks/useIntakeFlow";
import type { CreationOrigin } from "@/features/intake/api/intakeApi";

type Props = {
  bookId: string;
  onComplete?: () => void | Promise<void>;
};

export default function ProjectInputPage({ bookId, onComplete }: Props) {
  const flow = useIntakeFlow(bookId);
  const fileRef = useRef<HTMLInputElement>(null);
  const [origin, setOrigin] = useState<CreationOrigin | null>(null);
  const [goal, setGoal] = useState("");
  const [negative, setNegative] = useState("");
  const selectedOrigin = origin ?? flow.origin;

  useEffect(() => {
    if (!goal && flow.intake?.raw_goal_text) {
      setGoal(flow.intake.raw_goal_text);
    }
  }, [flow.intake?.raw_goal_text, goal]);

  useEffect(() => {
    if (!negative && flow.intake?.negative_constraints_text) {
      setNegative(flow.intake.negative_constraints_text);
    }
  }, [flow.intake?.negative_constraints_text, negative]);

  if (flow.loading && !selectedOrigin) {
    return <div className="mx-auto max-w-2xl p-4 text-sm text-slate-500">正在读取项目输入…</div>;
  }

  if (!selectedOrigin) {
    return (
      <div className="mx-auto max-w-lg p-4">
        <h2 className="mb-3 text-lg font-semibold">选择创作起点</h2>
        <OriginPicker
          onSelect={(nextOrigin) => {
            setOrigin(nextOrigin);
            void flow.initializeOrigin(nextOrigin);
          }}
        />
      </div>
    );
  }

  if (flow.step === "input") {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-4">
        <h2 className="text-lg font-semibold">项目输入</h2>
        <p className="text-sm text-slate-500">{flow.originLabels[selectedOrigin]}</p>
        <label className="block text-sm">
          我想写什么
          <textarea className="mt-1 w-full rounded border p-2" rows={4} value={goal} onChange={(e) => setGoal(e.target.value)} />
        </label>
        <label className="block text-sm">
          我不想要什么
          <textarea className="mt-1 w-full rounded border p-2" rows={2} value={negative} onChange={(e) => setNegative(e.target.value)} />
        </label>
        <div>
          <input ref={fileRef} type="file" className="hidden" onChange={(e) => void flow.uploadFile(e.target.files?.[0])} />
          <button
            type="button"
            className="rounded border px-3 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!flow.canUpload || flow.loading}
            onClick={() => fileRef.current?.click()}
          >
            上传资料文件
          </button>
        </div>
        <button
          type="button"
          className="rounded bg-brand px-4 py-2 text-white"
          disabled={flow.loading}
          onClick={async () => {
            await flow.start(selectedOrigin, goal, negative);
            await flow.runUnderstanding();
          }}
        >
          {flow.loading ? "处理中…" : "生成当前理解"}
        </button>
      </div>
    );
  }

  if (flow.step === "understanding") {
    return (
      <div className="mx-auto max-w-2xl space-y-4 p-4">
        <h2 className="text-lg font-semibold">确认输入如何被使用</h2>
        <UnderstandingReview
          text={flow.intake?.understanding?.user_facing_text || ""}
          unclearQuestions={flow.intake?.understanding?.unclear_questions}
          loading={flow.loading}
          onCorrect={(c) => flow.applyCorrection(c)}
          onConfirm={() => void flow.confirmU()}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4">
      <h2 className="text-lg font-semibold">确认后续写作方向</h2>
      <WritingPlanReview
        text={flow.intake?.writing_plan?.user_facing_text || ""}
        loading={flow.loading}
        onConfirm={async (editedText) => {
          await flow.confirmP(editedText);
          await onComplete?.();
        }}
      />
    </div>
  );
}
