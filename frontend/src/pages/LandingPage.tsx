import { ArrowRight, BookOpen, CheckCircle2, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

const highlights = [
  "从提示词到可交付书稿的一站式流程",
  "支持多种图书类型与章节结构化输出",
  "统一管理目录、写作、导出与版本存档",
];

const steps = [
  { title: "输入创作目标", desc: "描述你的选题、目标读者和输出风格，自动生成项目骨架。" },
  { title: "搭建书稿结构", desc: "快速得到章节目录与任务节奏，持续迭代每一章内容。" },
  { title: "编辑并导出", desc: "在统一工作台打磨细节，最终导出可发布版本。" },
];

export default function LandingPage() {
  return (
    <div className="landing-shell page-transition-in min-h-full">
      <header className="landing-header">
        <div className="mx-auto flex w-full max-w-[92rem] items-center justify-between px-6 py-5 sm:px-8">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-brand text-sm font-medium text-white">
              A
            </span>
            <span className="text-xl font-medium text-ink">AutoBooker</span>
          </div>
          <Link to="/login" className="btn-primary">
            登录
          </Link>
        </div>
      </header>

      <main>
        <section className="mx-auto grid w-full max-w-[92rem] gap-14 px-6 py-16 sm:px-8 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="inline-flex items-center gap-1 rounded-[4px] bg-brand-50 px-4 py-1.5 text-xs text-brand-700">
              <Sparkles className="h-3.5 w-3.5" />
              AI 写书工作台
            </p>
            <h1 className="mt-5 text-5xl font-medium leading-tight text-ink sm:text-6xl">
              把灵感快速转成可交付书稿
            </h1>
            <p className="mt-5 max-w-xl text-lg text-slate-600">
              借鉴行业成熟产品体验，AutoBooker 提供从规划、写作到导出的完整创作链路。
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/login" className="btn-primary">
                开始创作
              </Link>
              <Link to="/register" className="btn-secondary">
                创建账号
              </Link>
            </div>
            <ul className="mt-8 space-y-3.5">
              {highlights.map((item) => (
                <li key={item} className="flex items-start gap-2 text-sm text-slate-600">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-500" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="surface-panel landing-showcase">
            <h2 className="text-xl font-medium text-ink">项目示例</h2>
            <div className="mt-5 space-y-4">
              <div className="rounded-xl border border-slate-200 p-5">
                <p className="text-sm font-medium text-ink">商业增长指南</p>
                <p className="mt-1 text-xs text-slate-500">12 章 · 约 35,000 字 · 进行中</p>
              </div>
              <div className="rounded-xl border border-slate-200 p-5">
                <p className="text-sm font-medium text-ink">学术写作方法论</p>
                <p className="mt-1 text-xs text-slate-500">9 章 · APA 引用 · 大纲已完成</p>
              </div>
              <div className="rounded-xl border border-slate-200 p-5">
                <p className="text-sm font-medium text-ink">训练手册</p>
                <p className="mt-1 text-xs text-slate-500">7 章 · 可导出 PDF / EPUB</p>
              </div>
            </div>
          </div>
        </section>

        <section className="py-14">
          <div className="mx-auto w-full max-w-[92rem] px-6 sm:px-8">
            <h2 className="text-3xl font-medium text-ink">三步完成一本书</h2>
            <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-3">
              {steps.map((step, index) => (
                <article key={step.title} className="surface-panel">
                  <p className="text-xs font-medium uppercase tracking-wider text-brand-600">Step {index + 1}</p>
                  <h3 className="mt-2 text-lg font-medium text-ink">{step.title}</h3>
                  <p className="mt-2 text-sm text-slate-600">{step.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto w-full max-w-[92rem] px-6 py-16 sm:px-8">
          <div className="surface-panel flex flex-col justify-between gap-5 md:flex-row md:items-center">
            <div className="flex items-center gap-3">
              <BookOpen className="h-9 w-9 rounded-lg bg-brand-50 p-2 text-brand" />
              <div>
                <p className="text-lg font-medium text-ink">准备好创建你的下一本书了吗？</p>
                <p className="text-sm text-slate-500">从项目建立到章节编辑，立即进入统一工作台。</p>
              </div>
            </div>
            <Link to="/login" className="btn-primary">
              进入控制台
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
