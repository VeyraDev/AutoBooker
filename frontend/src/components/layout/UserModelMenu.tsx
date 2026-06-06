import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cpu } from "lucide-react";
import { useMemo } from "react";
import { useMatch } from "react-router-dom";

import { getBook, updateBook } from "@/api/books";
import { fetchLlmModels } from "@/api/config";
import ModelSelector from "@/components/editor/ModelSelector";
import { effectiveSceneModel } from "@/lib/bookAiModels";
import { useAiModelPrefsStore, type AiScene } from "@/stores/aiModelPrefsStore";
import type { BookUpdatePayload } from "@/types/book";

const SCENES: { key: AiScene; label: string }[] = [
  { key: "outline", label: "大纲" },
  { key: "constitution", label: "叙事宪法" },
  { key: "writing", label: "写作" },
];

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function UserModelMenu({ open, onClose }: Props) {
  const qc = useQueryClient();
  const bookMatch = useMatch("/app/books/:bookId/*");
  const bookId = bookMatch?.params.bookId;
  const { prefs, setSceneModel } = useAiModelPrefsStore();

  const llmQuery = useQuery({
    queryKey: ["llm-models"],
    queryFn: fetchLlmModels,
    staleTime: 5 * 60_000,
  });

  const bookQuery = useQuery({
    queryKey: ["book", bookId],
    queryFn: () => getBook(bookId!),
    enabled: Boolean(bookId),
  });

  const book = bookQuery.data;

  const sceneModels = useMemo(
    () =>
      Object.fromEntries(
        SCENES.map(({ key }) => [key, effectiveSceneModel(key, { book, prefs, catalog: llmQuery.data })]),
      ) as Record<AiScene, string>,
    [book, prefs, llmQuery.data],
  );

  const updateMutation = useMutation({
    mutationFn: (payload: BookUpdatePayload) => updateBook(bookId!, payload),
    onSuccess: (b) => {
      qc.setQueryData(["book", bookId], b);
    },
  });

  function onSceneChange(scene: AiScene, model: string) {
    if (bookId && book) {
      const payload: BookUpdatePayload =
        scene === "outline"
          ? { outline_ai_model: model }
          : scene === "constitution"
            ? { constitution_ai_model: model }
            : { writing_ai_model: model, ai_model: model };
      updateMutation.mutate(payload);
      return;
    }
    setSceneModel(scene, model);
    onClose();
  }

  if (!open) return null;

  return (
    <div
      role="menu"
      className="user-model-menu absolute right-0 top-[calc(100%+6px)] z-50 w-72 rounded-xl border border-slate-200 bg-white py-3 shadow-xl"
    >
      <p className="border-b border-slate-100 px-3 pb-2 text-xs font-medium text-slate-600">
        {book ? "本书模型" : "默认模型"}
      </p>
      <p className="px-3 pt-2 text-[10px] leading-snug text-slate-400">
        {book ? "仅影响当前书稿的大纲、叙事宪法与写作。" : "新建书稿时将作为默认模型。"}
      </p>
      <div className="mt-2 space-y-2.5 px-3">
        {SCENES.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-2">
            <span className="w-14 shrink-0 text-[11px] text-slate-500">{label}</span>
            <ModelSelector
              aiModel={sceneModels[key]}
              catalog={llmQuery.data}
              loading={llmQuery.isLoading}
              onModelChange={(m) => onSceneChange(key, m)}
              className="relative min-w-0 flex-1"
              triggerClassName="input flex h-8 w-full min-w-0 cursor-pointer items-center justify-between gap-1 py-1 pl-2 pr-2 text-[11px]"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export function UserModelTrigger({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      className={`user-model-trigger ${open ? "user-model-trigger-active" : ""}`}
      aria-expanded={open}
      aria-haspopup="menu"
      aria-label="模型设置"
      title="模型设置"
      onClick={onToggle}
    >
      <Cpu className="h-3 w-3 shrink-0" aria-hidden />
      <span>模型</span>
    </button>
  );
}
