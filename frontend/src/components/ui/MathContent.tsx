"use client";

import { useMemo } from "react";
import katex from "katex";

interface MathContentProps {
  content: string;
  className?: string;
}

/**
 * Process content string, rendering LaTeX math using KaTeX.
 * Supports both inline ($...$) and display ($$...$$) math,
 * as well as \(...\) and \[...\] delimiters.
 */
function processContent(content: string): string {
  if (!content) return "";

  // Convert newlines to <br> for proper rendering
  let processedContent = content.replace(/\n/g, "<br>");

  // Render display math first ($$...$$)
  processedContent = processedContent.replace(
    /\$\$([\s\S]*?)\$\$/g,
    (_, math) => {
      try {
        return katex.renderToString(math.trim(), {
          displayMode: true,
          throwOnError: false,
        });
      } catch {
        return `$$${math}$$`;
      }
    }
  );

  // Render inline math ($...$)
  processedContent = processedContent.replace(
    /\$([^$\n]+?)\$/g,
    (_, math) => {
      try {
        return katex.renderToString(math.trim(), {
          displayMode: false,
          throwOnError: false,
        });
      } catch {
        return `$${math}$`;
      }
    }
  );

  // Also handle \[...\] delimiters (display mode)
  processedContent = processedContent.replace(
    /\\\[([\s\S]*?)\\\]/g,
    (_, math) => {
      try {
        return katex.renderToString(math.trim(), {
          displayMode: true,
          throwOnError: false,
        });
      } catch {
        return `\\[${math}\\]`;
      }
    }
  );

  // Handle \(...\) delimiters (inline mode)
  processedContent = processedContent.replace(
    /\\\(([\s\S]*?)\\\)/g,
    (_, math) => {
      try {
        return katex.renderToString(math.trim(), {
          displayMode: false,
          throwOnError: false,
        });
      } catch {
        return `\\(${math}\\)`;
      }
    }
  );

  return processedContent;
}

/**
 * Component for rendering LaTeX math content using KaTeX.
 * Supports both inline ($...$) and display ($$...$$) math.
 * Uses dangerouslySetInnerHTML for proper React hydration.
 */
export function MathContent({ content, className = "" }: MathContentProps) {
  const html = useMemo(() => processContent(content), [content]);

  return (
    <div
      className={`math-content ${className}`}
      style={{ lineHeight: 1.8 }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
