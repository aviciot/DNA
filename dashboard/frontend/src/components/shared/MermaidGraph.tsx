"use client";

import { useEffect, useRef, useState } from "react";

interface MermaidGraphProps {
  chart: string;
  className?: string;
}

let mermaidReady = false;

export default function MermaidGraph({ chart, className = "" }: MermaidGraphProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const id = useRef(`mermaid-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    if (!chart || !ref.current) return;

    const render = async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        if (!mermaidReady) {
          mermaid.initialize({
            startOnLoad: false,
            theme: "neutral",
            securityLevel: "loose",
            fontFamily: "ui-monospace, monospace",
          });
          mermaidReady = true;
        }
        const { svg } = await mermaid.render(id.current, chart);
        if (ref.current) ref.current.innerHTML = svg;
        setError(null);
      } catch (e: any) {
        setError(e?.message || "Failed to render diagram");
      }
    };

    render();
  }, [chart]);

  if (error) {
    return (
      <pre className={`text-xs text-gray-500 dark:text-gray-400 whitespace-pre-wrap font-mono bg-gray-50 dark:bg-gray-900 rounded-xl p-4 ${className}`}>
        {chart}
      </pre>
    );
  }

  return (
    <div
      ref={ref}
      className={`overflow-auto flex justify-center [&_svg]:max-w-full [&_svg]:h-auto ${className}`}
    />
  );
}
