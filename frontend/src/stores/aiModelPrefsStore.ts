import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AiScene = "outline" | "constitution" | "writing";

export type AiModelPrefs = Record<AiScene, string | null>;

interface AiModelPrefsState {
  prefs: AiModelPrefs;
  setSceneModel: (scene: AiScene, model: string) => void;
}

const DEFAULT_PREFS: AiModelPrefs = {
  outline: null,
  constitution: null,
  writing: null,
};

export const useAiModelPrefsStore = create<AiModelPrefsState>()(
  persist(
    (set) => ({
      prefs: DEFAULT_PREFS,
      setSceneModel: (scene, model) =>
        set((state) => ({
          prefs: { ...state.prefs, [scene]: model },
        })),
    }),
    { name: "autoBookerAiModelPrefs" },
  ),
);
