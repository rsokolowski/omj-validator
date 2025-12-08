"use client";

import { useEffect, useRef } from "react";
import katex from "katex";

interface MathContentProps {
  content: string;
  className?: string;
}

/**
 * Component for rendering LaTeX math content using KaTeX.
 * Supports both inline ($...$) and display ($$...$$) math.
 */
export function MathContent({ content, className = "" }: MathContentProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !content) return;

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

    // Also handle \(...\) and \[...\] delimiters
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

    containerRef.current.innerHTML = processedContent;
  }, [content]);

  return (
    <div
      ref={containerRef}
      className={`math-content ${className}`}
      style={{ lineHeight: 1.8 }}
    />
  );
}
