"use client";

import { useMemo } from "react";
import { renderMathHtml } from "@/lib/utils/mathHtml";

interface MathContentProps {
  content: string;
  className?: string;
}

/**
 * Component for rendering LaTeX math content using KaTeX.
 * Supports both inline ($...$) and display ($$...$$) math.
 * Uses dangerouslySetInnerHTML for proper React hydration - safe because
 * renderMathHtml escapes all non-math text (it may come from students).
 */
export function MathContent({ content, className = "" }: MathContentProps) {
  const html = useMemo(() => renderMathHtml(content), [content]);

  return (
    <div
      className={`math-content ${className}`}
      style={{ lineHeight: 1.8 }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
