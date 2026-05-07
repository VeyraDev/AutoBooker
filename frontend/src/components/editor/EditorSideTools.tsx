import { LayoutList, Pencil, ShieldCheck, Sparkles, Wand2 } from "lucide-react";

export type EditorTool = "edit" | "ai" | "review" | "rewrite";

type Props = {
  active: EditorTool;
  onChange: (t: EditorTool) => void;
  outlineOpen: boolean;
  onOutlineToggle: () => void;
  outlineChapterCount?: number;
};

const items: { id: EditorTool; label: string; icon: typeof Pencil }[] = [
  { id: "edit", label: "编辑", icon: Pencil },
  { id: "ai", label: "AI助手", icon: Sparkles },
  { id: "review", label: "审校", icon: ShieldCheck },
  { id: "rewrite", label: "降重", icon: Wand2 },
];

export default function EditorSideTools({
  active,
  onChange,
  outlineOpen,
  onOutlineToggle,
  outlineChapterCount = 0,
}: Props) {
  return (
    <aside className="editor-side-tools" aria-label="左侧工具栏">
      <div className="flex flex-col items-center gap-0.5">
        <button
          type="button"
          title="目录"
          aria-label="打开目录"
          aria-expanded={outlineOpen}
          aria-pressed={outlineOpen}
          className={`editor-side-tool-btn relative ${outlineOpen ? "editor-side-tool-btn-active" : ""}`}
          onClick={onOutlineToggle}
        >
          <LayoutList className="h-5 w-5" aria-hidden />
          {outlineChapterCount > 0 ? (
            <span className="pointer-events-none absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-violet-600 px-1 text-[10px] font-semibold leading-none text-white">
              {outlineChapterCount > 99 ? "99+" : outlineChapterCount}
            </span>
          ) : null}
        </button>
        <div className="my-1 h-px w-8 bg-slate-200/90" aria-hidden />
      </div>
      {items.map((it) => {
        const Icon = it.icon;
        const isOn = active === it.id;
        return (
          <button
            key={it.id}
            type="button"
            title={it.label}
            aria-label={it.label}
            aria-pressed={isOn}
            className={`editor-side-tool-btn ${isOn ? "editor-side-tool-btn-active" : ""}`}
            onClick={() => onChange(it.id)}
          >
            <Icon className="h-5 w-5" />
          </button>
        );
      })}
    </aside>
  );
}
