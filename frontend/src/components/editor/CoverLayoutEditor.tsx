import { useCallback, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

export type CoverLayoutPos = { x: number; y: number };
export type CoverLayout = Record<string, CoverLayoutPos>;

const LABELS: Record<string, string> = {
  series: "丛书",
  title: "书名",
  subtitle: "副标题",
  author: "作者",
  publisher: "出版社",
};

type Props = {
  coverImageUrl: string;
  layout: CoverLayout;
  onChange: (next: CoverLayout) => void;
  disabled?: boolean;
  aspectWidth?: number;
  aspectHeight?: number;
};

export default function CoverLayoutEditor({
  coverImageUrl,
  layout,
  onChange,
  disabled,
  aspectWidth = 145,
  aspectHeight = 210,
}: Props) {
  const frameRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<string | null>(null);

  const onPointerDown = useCallback(
    (key: string, e: ReactPointerEvent) => {
      if (disabled) return;
      e.preventDefault();
      e.stopPropagation();
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
      setDragging(key);
    },
    [disabled],
  );

  const onPointerMove = useCallback(
    (e: ReactPointerEvent) => {
      if (!dragging || !frameRef.current) return;
      const rect = frameRef.current.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      onChange({
        ...layout,
        [dragging]: {
          x: Math.max(5, Math.min(95, x)),
          y: Math.max(4, Math.min(96, y)),
        },
      });
    },
    [dragging, layout, onChange],
  );

  const onPointerUp = useCallback(() => setDragging(null), []);

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-slate-500">拖动手柄调整封面文字位置，再点「刷新预览」生效</p>
      <div
        ref={frameRef}
        className="relative mx-auto w-full max-w-[220px] overflow-hidden rounded-md border border-slate-200 bg-slate-100 shadow-sm"
        style={{ aspectRatio: `${aspectWidth} / ${aspectHeight}` }}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        {coverImageUrl ? (
          <img src={coverImageUrl} alt="封面背景" className="absolute inset-0 h-full w-full object-cover" draggable={false} />
        ) : (
          <div className="absolute inset-0 bg-slate-300" />
        )}
        {Object.keys(LABELS).map((key) => {
          const pos = layout[key] || { x: 50, y: 50 };
          return (
            <button
              key={key}
              type="button"
              className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 rounded-full border px-1.5 py-0.5 text-[10px] shadow ${
                dragging === key
                  ? "border-sky-500 bg-sky-500 text-white"
                  : "border-white/80 bg-black/55 text-white hover:bg-black/70"
              }`}
              style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
              onPointerDown={(e) => onPointerDown(key, e)}
              disabled={disabled}
            >
              {LABELS[key]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
