import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
    <section className="border-b border-slate-100 px-3 py-3">
      <p className="text-xs font-medium text-slate-600">
        {book ? "本书模型" : "默认模型"}
      </p>
      <p className="pt-1.5 text-[10px] leading-snug text-slate-400">
        {book ? "分别作用于大纲、叙事宪法与写作。" : "新建书稿时将作为各场景默认模型。"}
      </p>
      <div className="mt-2.5 space-y-2.5">
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
    </section>
  );
}
