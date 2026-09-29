import katex from "katex";

// One pattern for every math delimiter, in priority order: $$...$$ before $...$
// so display math is not split into two inline spans. Exported so
// solutionText.findMathSpans and the preview never disagree on where a
// formula is (matchAll clones the regex, so the shared /g state is safe).
export const MATH_PATTERN =
  /\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$([^$\n]+?)\$/g;

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

type Segment =
  | { kind: "text"; text: string }
  | { kind: "math"; source: string; display: boolean; whole: string };

function splitMath(content: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const match of content.matchAll(MATH_PATTERN)) {
    const index = match.index ?? 0;
    if (index > last) out.push({ kind: "text", text: content.slice(last, index) });
    const [whole, display, bracketDisplay, parenInline, inline] = match;
    out.push({
      kind: "math",
      source: display ?? bracketDisplay ?? parenInline ?? inline ?? "",
      display: display !== undefined || bracketDisplay !== undefined,
      whole,
    });
    last = index + whole.length;
  }
  if (last < content.length) out.push({ kind: "text", text: content.slice(last) });
  // A display formula is already a block: the single line break the author
  // put before and after it would otherwise render as an empty line on each side.
  out.forEach((segment, i) => {
    if (segment.kind !== "math" || !segment.display) return;
    const prev = out[i - 1];
    const next = out[i + 1];
    if (prev?.kind === "text") prev.text = prev.text.replace(/\n$/, "");
    if (next?.kind === "text") next.text = next.text.replace(/^\n/, "");
  });
  return out;
}

export interface RenderMathOptions {
  /** Wrap each formula in <span class="math-src" data-math-index="i"> so a click
   *  in a preview can be traced back to findMathSpans(text)[i]. Off by default -
   *  history views do not need it. The wrapper carries only an integer. */
  indexMath?: boolean;
}

/**
 * Turn text with $...$, $$...$$, \(...\) and \[...\] math into HTML.
 *
 * Everything outside math is HTML-escaped: statements of private tasks and
 * typed solutions are written by students (or read off their photos by the
 * AI), and AI feedback can be steered by that text, so none of it may reach
 * the DOM as markup. KaTeX escapes what it renders itself (trust: false, so
 * \href cannot emit a javascript: link).
 */
export function renderMathHtml(content: string, options: RenderMathOptions = {}): string {
  if (!content) return "";

  let html = "";
  let mathIndex = 0;
  for (const segment of splitMath(content)) {
    if (segment.kind === "text") {
      html += escapeText(segment.text);
      continue;
    }
    const rendered = renderMath(segment.source, segment.display, segment.whole);
    if (options.indexMath) {
      const cls = segment.display ? "math-src math-src--display" : "math-src";
      html +=
        `<span class="${cls}" data-math-index="${mathIndex}" role="button" tabindex="0" ` +
        `aria-label="Popraw wzór">${rendered}</span>`;
    } else {
      html += rendered;
    }
    mathIndex += 1;
  }
  return html;
}
