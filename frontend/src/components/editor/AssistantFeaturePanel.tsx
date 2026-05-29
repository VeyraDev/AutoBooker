import { ChevronDown, ImageIcon, Type } from "lucide-react";
import { useState } from "react";

import type { AssistantIntent } from "@/api/assistant";

export type FeatureSelection = {
  intent: AssistantIntent;
  label: string;
  placeholder: string;
  chart_type?: string;
  sub_kind?: string;
};

const TEXT_FEATURES: FeatureSelection[] = [
  { intent: "polish", label: "润色当前段落", placeholder: "补充润色方向，如：更正式、更简洁…" },
  { intent: "rewrite", label: "改写（指定方向）", placeholder: "说明改写方向或要求…" },
  { intent: "condense", label: "缩写", placeholder: "可选：说明需保留的重点…" },
  { intent: "expand", label: "扩写", placeholder: "可选：希望补充哪类细节…" },
  { intent: "style_adjust", label: "风格调整", placeholder: "目标风格，如：更学术、更口语…" },
  { intent: "term_check", label: "术语一致性检查", placeholder: "可选：列出需统一的术语…" },
];

const CHART_SUB: FeatureSelection[] = [
  { intent: "gen_chart", label: "折线图", placeholder: "描述 X/Y 轴与数据趋势…", chart_type: "line" },
  { intent: "gen_chart", label: "柱状图", placeholder: "描述分类与数值…", chart_type: "bar" },
  { intent: "gen_chart", label: "热力图", placeholder: "描述矩阵维度与数值分布…", chart_type: "heatmap" },
  { intent: "gen_chart", label: "散点图", placeholder: "描述变量关系与数据点…", chart_type: "scatter" },
];

const IMAGE_FEATURES: FeatureSelection[] = [
  { intent: "gen_flowchart", label: "流程图", placeholder: "描述节点、流向与分支…" },
  { intent: "gen_figure", label: "架构示意图", placeholder: "描述系统组件与连接关系…", sub_kind: "architecture" },
  { intent: "gen_figure", label: "概念示意图", placeholder: "描述抽象概念与层级关系…", sub_kind: "concept_diagram" },
  { intent: "gen_figure", label: "信息图", placeholder: "描述要点对比或结构化信息…", sub_kind: "infographic" },
  {
    intent: "gen_figure",
    label: "章节总结图",
    placeholder: "描述本章核心结论与视觉结构…",
    sub_kind: "chapter_summary",
  },
  { intent: "gen_figure", label: "场景插画", placeholder: "描述场景与视觉元素…", sub_kind: "illustration" },
];

type Props = {
  active: FeatureSelection | null;
  onSelect: (f: FeatureSelection | null) => void;
  chartMenuOpen: boolean;
  onChartMenuOpen: (open: boolean) => void;
};

export default function AssistantFeaturePanel({
  active,
  onSelect,
  chartMenuOpen,
  onChartMenuOpen,
}: Props) {
  const [textOpen, setTextOpen] = useState(false);
  const [imageOpen, setImageOpen] = useState(false);

  function pick(f: FeatureSelection) {
    onSelect(active?.label === f.label && active?.intent === f.intent ? null : f);
    setTextOpen(false);
    setImageOpen(false);
    onChartMenuOpen(false);
  }

  return (
    <div className="assistant-feature-bar sticky bottom-0 z-10 border-t border-slate-100 bg-white px-2 py-2">
      <div className="relative flex flex-wrap gap-2">
        <div className="relative">
          <button
            type="button"
            className={`inline-flex h-8 items-center gap-1 rounded-lg border px-3 text-xs font-medium ${
              textOpen || TEXT_FEATURES.some((t) => t.label === active?.label)
                ? "border-violet-400 bg-violet-50 text-violet-900"
                : "border-slate-200 text-slate-700 hover:border-violet-300"
            }`}
            onClick={() => {
              setTextOpen((v) => !v);
              setImageOpen(false);
              onChartMenuOpen(false);
            }}
          >
            <Type className="h-3.5 w-3.5" />
            文字处理
            <ChevronDown className="h-3 w-3" />
          </button>
          {textOpen ? (
            <div className="absolute bottom-full left-0 z-20 mb-1 min-w-[11rem] rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
              {TEXT_FEATURES.map((f) => (
                <button
                  key={f.label}
                  type="button"
                  className="block w-full px-3 py-2 text-left text-xs hover:bg-violet-50"
                  onClick={() => pick(f)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="relative">
          <button
            type="button"
            className={`inline-flex h-8 items-center gap-1 rounded-lg border px-3 text-xs font-medium ${
              imageOpen ||
              IMAGE_FEATURES.some((t) => t.label === active?.label) ||
              CHART_SUB.some((t) => t.label === active?.label)
                ? "border-violet-400 bg-violet-50 text-violet-900"
                : "border-slate-200 text-slate-700 hover:border-violet-300"
            }`}
            onClick={() => {
              setImageOpen((v) => !v);
              setTextOpen(false);
              onChartMenuOpen(false);
            }}
          >
            <ImageIcon className="h-3.5 w-3.5" />
            图像生成
            <ChevronDown className="h-3 w-3" />
          </button>
          {imageOpen ? (
            <div className="absolute bottom-full left-0 z-20 mb-1 min-w-[11rem] rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
              <button
                type="button"
                className="block w-full px-3 py-2 text-left text-xs hover:bg-violet-50"
                onClick={() => pick(IMAGE_FEATURES[0])}
              >
                流程图
              </button>
              <div className="relative">
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-xs hover:bg-violet-50"
                  onClick={() => onChartMenuOpen(!chartMenuOpen)}
                >
                  数据图表
                  <ChevronDown className="h-3 w-3" />
                </button>
                {chartMenuOpen ? (
                  <div className="border-t border-slate-100 py-1 pl-2">
                    {CHART_SUB.map((f) => (
                      <button
                        key={f.label}
                        type="button"
                        className="block w-full px-3 py-1.5 text-left text-xs text-slate-600 hover:bg-violet-50"
                        onClick={() => pick(f)}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
              {IMAGE_FEATURES.slice(1).map((f) => (
                <button
                  key={f.label}
                  type="button"
                  className="block w-full px-3 py-2 text-left text-xs hover:bg-violet-50"
                  onClick={() => pick(f)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export { TEXT_FEATURES, IMAGE_FEATURES, CHART_SUB };
