import katex from "katex";

// One pattern for every math delimiter, in priority order: $$...$$ before $...$
// so display math is not split into two inline spans.
const MATH_PATTERN = /\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$([^$\n]+?)\$/g;

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeText(text: string): string {
  return text.replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]).replace(/\n/g, "<br>");
}

function renderMath(source: string, displayMode: boolean, original: string): string {
  try {
    return katex.renderToString(source.trim(), { displayMode, throwOnError: false });
  } catch {
    return escapeText(original);
  }
}

/**
 * Turn text with $...$, $$...$$, \(...\) and \[...\] math into HTML.
 *
 * Everything outside math is HTML-escaped: statements of private tasks are
 * typed by students (or read off their photos by the AI), and AI feedback can
 * be steered by that text, so none of it may reach the DOM as markup. KaTeX
 * escapes what it renders itself.
 */
export function renderMathHtml(content: string): string {
  if (!content) return "";

  let html = "";
  let last = 0;
  for (const match of content.matchAll(MATH_PATTERN)) {
    const index = match.index ?? 0;
    html += escapeText(content.slice(last, index));
    const [whole, display, bracketDisplay, parenInline, inline] = match;
    if (display !== undefined) html += renderMath(display, true, whole);
    else if (bracketDisplay !== undefined) html += renderMath(bracketDisplay, true, whole);
    else if (parenInline !== undefined) html += renderMath(parenInline, false, whole);
    else html += renderMath(inline ?? "", false, whole);
    last = index + whole.length;
  }
  html += escapeText(content.slice(last));
  return html;
}
