import { useEffect, useId, useState } from "react";

type Props = {
  code: string;
};

export default function MermaidDiagram({ code }: Props) {
  const reactId = useId();
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const trimmed = code.trim();
    if (!trimmed) {
      setSvg(null);
      setError(null);
      return;
    }

    void (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "strict" });
        const renderId = `mermaid-${reactId.replace(/:/g, "")}`;
        const { svg: rendered } = await mermaid.render(renderId, trimmed);
        if (!cancelled) {
          setSvg(rendered);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setSvg(null);
          setError(err instanceof Error ? err.message : "Mermaid 渲染失败");
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [code, reactId]);

  if (error) {
    return (
      <pre className="overflow-x-auto rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
        {code}
      </pre>
    );
  }

  if (!svg) {
    return <div className="h-16 animate-pulse rounded bg-slate-100" aria-hidden />;
  }

  return (
    <div
      className="my-2 overflow-x-auto rounded border border-slate-200 bg-white p-2"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
