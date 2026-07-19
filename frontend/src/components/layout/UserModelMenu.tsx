import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useMatch } from "react-router-dom";

import { patchUserAiModels } from "@/api/auth";
import { fetchLlmModels } from "@/api/config";
import ModelSelector from "@/components/editor/ModelSelector";
import { resolveUserSceneModel, type UserAiScene } from "@/lib/bookAiModels";
import { phaseOf } from "@/lib/bookStatus";
import { useAuthStore } from "@/stores/authStore";
import { getBook } from "@/api/books";

const SCENES: { key: UserAiScene; label: string }[] = [
  { key: "outline", label: "大纲" },
  { key: "constitution", label: "写作规则" },
  { key: "writing", label: "写作" },
  { key: "assistant", label: "AI 助手" },
];

type Props = {
  open: boolean;
  onClose: () => void;
};

export default function UserModelMenu({ open, onClose }: Props) {
  const bookMatch = useMatch("/app/books/:bookId/*");
  const bookId = bookMatch?.params.bookId;
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

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
  const catalog = llmQuery.data;
  const userModels = user?.ai_models;

  const visibleScenes = useMemo(() => {
    if (!book) return SCENES;
    const phase = phaseOf(book);
    if (phase === "WRITING" || phase === "COMPLETED") {
      return SCENES.filter((s) => s.key === "writing" || s.key === "assistant");
    }
    return SCENES;
  }, [book]);

  const sceneModels = useMemo(
    () =>
      Object.fromEntries(
        visibleScenes.map(({ key }) => [key, resolveUserSceneModel(key, userModels, catalog)]),
      ) as Record<UserAiScene, string>,
    [visibleScenes, userModels, catalog],
  );

  const updateUserMutation = useMutation({
    mutationFn: patchUserAiModels,
    onSuccess: (u) => setUser(u),
  });

  function onSceneChange(scene: UserAiScene, model: string) {
    const patch =
      scene === "outline"
        ? { outline_ai_model: model }
        : scene === "constitution"
          ? { constitution_ai_model: model }
          : scene === "writing"
            ? { writing_ai_model: model }
            : { assistant_ai_model: model };
    updateUserMutation.mutate(patch);
    onClose();
  }

  const menuTitle = book
    ? visibleScenes.length <= 2
      ? "写作与助手模型"
      : "模型偏好"
    : "模型偏好";
  const menuHint = book
    ? visibleScenes.length <= 2
      ? "与写作页顶栏一致；各场景独立生效，改哪项只影响哪项。"
      : "大纲与写作规则用于本书生成流程；写作与助手见对应入口。"
    : "未单独设置时使用系统默认。新建书稿与每次生成均按当前选择调用。";

  if (!open) return null;

  return (
    <section className="border-b border-slate-100 px-3 py-3">
      <p className="text-xs font-medium text-slate-600">{menuTitle}</p>
      <p className="pt-1.5 text-[10px] leading-snug text-slate-400">{menuHint}</p>
      <div className="mt-2.5 space-y-2.5">
        {visibleScenes.map(({ key, label }) => (
          <div key={key} className="flex items-center gap-2">
            <span className="w-14 shrink-0 text-[11px] text-slate-500">{label}</span>
            <ModelSelector
              aiModel={sceneModels[key]}
              catalog={catalog}
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
