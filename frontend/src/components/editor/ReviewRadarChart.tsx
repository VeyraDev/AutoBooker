const DIMENSION_LABELS: Record<string, string> = {
  logic: "逻辑",
  grammar: "语法",
  style: "风格",
  citation: "引用",
  hallucination: "幻觉",
  figure: "图表",
  ai_feature: "AI特征",
};

type Props = {
  dimensions: Record<string, { score: number; summary?: string }>;
  size?: number;
};

export default function ReviewRadarChart({ dimensions, size = 200 }: Props) {
  const keys = Object.keys(DIMENSION_LABELS).filter((k) => dimensions[k]);
  if (keys.length < 3) return null;
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.36;
  const levels = [0.25, 0.5, 0.75, 1];

  function point(i: number, val: number) {
    const angle = (Math.PI * 2 * i) / keys.length - Math.PI / 2;
    const dist = r * (val / 100);
    return [cx + dist * Math.cos(angle), cy + dist * Math.sin(angle)];
  }

  const dataPoints = keys
    .map((k, i) => point(i, dimensions[k]?.score ?? 0))
    .map(([x, y]) => `${x},${y}`)
    .join(" ");

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="text-slate-300">
        {levels.map((lv) => (
          <polygon
            key={lv}
            points={keys
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
        {keys.map((k, i) => {
          const [x, y] = point(i, 100);
          const [lx, ly] = point(i, dimensions[k]?.score ?? 0);
          const labelAngle = (Math.PI * 2 * i) / keys.length - Math.PI / 2;
          const tx = cx + (r + 18) * Math.cos(labelAngle);
          const ty = cy + (r + 18) * Math.sin(labelAngle);
          return (
            <g key={k}>
              <line x1={cx} y1={cy} x2={x} y2={y} stroke="currentColor" strokeWidth={0.5} />
              <line x1={cx} y1={cy} x2={lx} y2={ly} stroke="#6366f1" strokeWidth={1} opacity={0.4} />
              <text x={tx} y={ty} textAnchor="middle" dominantBaseline="middle" className="fill-slate-600 text-[9px]">
                {DIMENSION_LABELS[k] ?? k}
              </text>
            </g>
          );
        })}
        <polygon points={dataPoints} fill="rgba(99,102,241,0.25)" stroke="#6366f1" strokeWidth={1.5} />
      </svg>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-slate-600">
        {keys.map((k) => (
          <span key={k}>
            {DIMENSION_LABELS[k]}: {dimensions[k]?.score ?? 0}
          </span>
        ))}
      </div>
    </div>
  );
}
