import type { ReviewDimension, ReviewDimensionKey } from "@/types/review";
import { REVIEW_DIMENSION_LABEL } from "@/types/review";

const ORDER: ReviewDimensionKey[] = [
  "logic_structure",
  "language_grammar",
  "style_consistency",
  "citation_sources",
  "factual_support",
  "figure_quality",
  "ai_signature",
];

type Props = {
  dimensions: Record<string, ReviewDimension> | ReviewDimension[];
  size?: number;
  activeKey?: string | null;
  onSelect?: (key: string | null) => void;
};

export default function ReviewRadarChart({ dimensions, size = 210, activeKey, onSelect }: Props) {
  const rows = normalizeRows(dimensions);
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.34;
  const levels = [0.25, 0.5, 0.75, 1];

  function point(i: number, val: number) {
    const angle = (Math.PI * 2 * i) / rows.length - Math.PI / 2;
    const dist = r * (val / 100);
    return [cx + dist * Math.cos(angle), cy + dist * Math.sin(angle)];
  }

  const dataPoints = rows
    .map((row, i) => point(i, scoreOf(row)))
    .map(([x, y]) => `${x},${y}`)
    .join(" ");

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="text-slate-300">
        {levels.map((lv) => (
          <polygon
            key={lv}
            points={rows
              .map((_, i) => {
                const [x, y] = point(i, lv * 100);
                return `${x},${y}`;
              })
              .join(" ")}
            fill="none"
            stroke="currentColor"
            strokeWidth={0.5}
          />
        ))}
        {rows.map((row, i) => {
          const key = row.key || row.dimension || ORDER[i];
          const [x, y] = point(i, 100);
          const [lx, ly] = point(i, scoreOf(row));
          const labelAngle = (Math.PI * 2 * i) / rows.length - Math.PI / 2;
          const tx = cx + (r + 24) * Math.cos(labelAngle);
          const ty = cy + (r + 24) * Math.sin(labelAngle);
          const active = activeKey === key;
          return (
            <g key={key}>
              <line x1={cx} y1={cy} x2={x} y2={y} stroke="currentColor" strokeWidth={0.5} />
              <line x1={cx} y1={cy} x2={lx} y2={ly} stroke="#0f766e" strokeWidth={1} opacity={0.45} />
              <circle
                cx={lx}
                cy={ly}
                r={active ? 4 : 3}
                fill={active ? "#0f766e" : "#14b8a6"}
                className={onSelect ? "cursor-pointer" : ""}
                onClick={() => onSelect?.(active ? null : key)}
              />
              <text
                x={tx}
                y={ty}
                textAnchor="middle"
                dominantBaseline="middle"
                className={`cursor-pointer fill-slate-600 text-[9px] ${active ? "font-semibold" : ""}`}
                onClick={() => onSelect?.(active ? null : key)}
              >
                {row.label || REVIEW_DIMENSION_LABEL[key as ReviewDimensionKey] || key}
              </text>
            </g>
          );
        })}
        <polygon points={dataPoints} fill="rgba(20,184,166,0.22)" stroke="#0f766e" strokeWidth={1.5} />
      </svg>
      <div className="grid w-full grid-cols-2 gap-1 text-[10px] text-slate-600">
        {rows.map((row) => {
          const key = row.key || row.dimension || "";
          const active = activeKey === key;
          return (
            <button
              type="button"
              key={key}
              className={`rounded border px-2 py-1 text-left ${
                active ? "border-teal-300 bg-teal-50 text-teal-900" : "border-slate-100 bg-white hover:bg-slate-50"
              }`}
              onClick={() => onSelect?.(active ? null : key)}
            >
              <span className="font-medium">{row.label || REVIEW_DIMENSION_LABEL[key as ReviewDimensionKey] || key}</span>
              <span className="ml-1">{scoreOf(row)}</span>
              <span className="ml-1 text-slate-400">w{row.weight ?? 0}</span>
              {(row.issue_count ?? 0) > 0 ? <span className="ml-1 text-amber-700">{row.issue_count}项</span> : null}
              {row.status && row.status !== "completed" ? <span className="ml-1 text-slate-400">{row.status}</span> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function normalizeRows(input: Record<string, ReviewDimension> | ReviewDimension[]): ReviewDimension[] {
  const map = Array.isArray(input)
    ? Object.fromEntries(input.map((row) => [row.key || row.dimension || "", row]))
    : input;
  return ORDER.map((key) => ({
    ...map[key],
    key,
    label: map[key]?.label ?? REVIEW_DIMENSION_LABEL[key],
    score: map[key]?.score ?? map[key]?.effective_score ?? map[key]?.raw_score ?? 0,
  }));
}

function scoreOf(row: ReviewDimension): number {
  return Math.max(0, Math.min(100, Math.round(row.effective_score ?? row.score ?? row.raw_score ?? 0)));
}
