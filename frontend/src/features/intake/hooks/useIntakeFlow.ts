import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  addIntakeItem,
  confirmUnderstanding,
  confirmWritingPlan,
  generateWritingPlan,
  initIntake,
  patchUnderstanding,
  patchWritingPlan,
  uploadIntakeFile,
  useGenerateUnderstanding,
  useIntake,
  type CreationOrigin,
} from "@/features/intake/api/intakeApi";

const ORIGIN_LABELS: Record<CreationOrigin, string> = {
  idea_only: "我只有想法，想先确定方向",
  material_first: "我有资料，想整理成书",
  outline_first: "我有明确大纲，想扩写成书",
  manuscript_continue: "我有半成稿，想继续写或优化",
};

export function useIntakeFlow(bookId: string) {
  const { data, refetch, isLoading } = useIntake(bookId);
  const genUnderstanding = useGenerateUnderstanding(bookId);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<"input" | "understanding" | "plan">("input");
  const intake = data?.intake ?? null;
  const origin = intake?.creation_origin ?? null;

  useEffect(() => {
    if (!intake) {
      setStep("input");
      return;
    }
    if (intake.writing_plan) {
      setStep("plan");
      return;
    }
    if (intake.understanding) {
      setStep("understanding");
      return;
    }
    setStep("input");
  }, [intake?.id, intake?.status, intake?.understanding?.id, intake?.writing_plan?.id]);

  const initializeOrigin = async (selectedOrigin: CreationOrigin) => {
    setBusy(true);
    try {
      await initIntake(bookId, { creation_origin: selectedOrigin });
      await refetch();
      setStep("input");
    } finally {
      setBusy(false);
    }
  };

  const start = async (origin: CreationOrigin, goal: string, negative: string) => {
    setBusy(true);
    try {
      await initIntake(bookId, { creation_origin: origin, raw_goal_text: goal, negative_constraints_text: negative });
      if (goal.trim()) {
        await addIntakeItem(bookId, { item_type: "natural_text", text_content: goal.trim() });
      }
      await refetch();
      setStep("understanding");
    } finally {
      setBusy(false);
    }
  };

  const runUnderstanding = async () => {
    await genUnderstanding.mutateAsync();
    await refetch();
    toast.success("已生成当前理解");
    setStep("understanding");
  };

  const confirmU = async () => {
    await confirmUnderstanding(bookId);
    await generateWritingPlan(bookId);
    await refetch();
    setStep("plan");
  };

  const confirmP = async (userFacingText?: string) => {
    const text = userFacingText?.trim();
    if (text) {
      await patchWritingPlan(bookId, text);
      await refetch();
    }
    await confirmWritingPlan(bookId);
    toast.success("写作方案已确认");
  };

  const applyCorrection = async (correction: string) => {
    await patchUnderstanding(bookId, correction);
    await refetch();
    toast.success("已更新理解");
  };

  const uploadFile = async (file: File | undefined) => {
    if (!file) return;
    if (!intake) {
      toast.error("请先选择创作起点");
      return;
    }
    setBusy(true);
    try {
      await uploadIntakeFile(bookId, file);
      await refetch();
      toast.success("文件已上传");
    } finally {
      setBusy(false);
    }
  };

  return {
    step,
    intake,
    origin,
    originLabels: ORIGIN_LABELS,
    initializeOrigin,
    start,
    runUnderstanding,
    confirmU,
    confirmP,
    applyCorrection,
    uploadFile,
    canUpload: Boolean(intake),
    loading: isLoading || busy || genUnderstanding.isPending,
  };
}

export { ORIGIN_LABELS };
