"use client";

import { useMemo } from "react";
import { renderMathHtml } from "@/lib/utils/mathHtml";

interface MathContentProps {
  content: string;
  className?: string;
  /** Wrap formulas with data-math-index so a parent can offer click-to-edit */
  indexMath?: boolean;
}

/**
 * Component for rendering LaTeX math content using KaTeX.
 * Supports both inline ($...$) and display ($$...$$) math.
 * Uses dangerouslySetInnerHTML for proper React hydration - safe because
 * renderMathHtml escapes all non-math text (it may come from students).
 */
export function MathContent({ content, className = "", indexMath = false }: MathContentProps) {
  // The object itself is memoised, not just the string: React 19 re-applies
  // innerHTML whenever this prop's identity changes, which would replace the
  // formula spans on every parent render and drop focus from them.
  const markup = useMemo(() => ({ __html: renderMathHtml(content, { indexMath }) }), [content, indexMath]);

  return (
    <div
      className={`math-content ${className}`}
      style={{ lineHeight: 1.8 }}
      dangerouslySetInnerHTML={markup}
    />
  );
}
