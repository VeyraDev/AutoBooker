import { useMemo, type ReactNode } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";

import MermaidDiagram from "@/features/assistant/components/MermaidDiagram";

type Props = {
  content: string;
  className?: string;
};

function CodeBlock({ className, children }: { className?: string; children?: ReactNode }) {
  const text = String(children ?? "").replace(/\n$/, "");
  const lang = (className || "").replace(/^language-/, "").trim().toLowerCase();
  if (lang === "mermaid") {
    return <MermaidDiagram code={text} />;
  }
  return (
    <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
      <code className={className}>{children}</code>
    </pre>
  );
}

export default function AssistantMarkdown({ content, className }: Props) {
  const components = useMemo<Components>(
    () => ({
      code({ className: codeClass, children, ...props }) {
        const inline = !codeClass && !String(children).includes("\n");
        if (inline) {
          return (
            <code className="rounded bg-slate-100 px-1 py-0.5 text-[0.9em]" {...props}>
              {children}
            </code>
          );
        }
        return <CodeBlock className={codeClass}>{children}</CodeBlock>;
      },
    }),
    [],
  );

  if (!content.trim()) return null;

  return (
    <div className={`book-md-body prose prose-slate max-w-none text-sm prose-p:my-2 prose-headings:my-2 ${className ?? ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
