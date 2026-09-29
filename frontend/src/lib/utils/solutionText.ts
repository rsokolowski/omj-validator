// Pure text logic for typed solutions. No DOM, no React - tested with the node
// test runner (npm test), which is why the local import carries its extension.
import { MATH_PATTERN } from "./mathHtml.ts";

/** A formula in the source text. Offsets are UTF-16 indices (what a textarea's
 *  selectionStart uses); `source` is the LaTeX between the delimiters. */
export interface MathSpan {
  start: number;
  end: number;
  source: string;
  display: boolean;
}

// Python's str.isspace() set, minus the Cc characters already removed above.
// Not String.prototype.trim(): that also strips U+FEFF, which Python keeps.
const PY_STRIP =
  /^[\t\n \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\t\n \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/g;

/**
 * Mirror of app/uploads.py::normalize_solution_text: line endings to "\n",
 * control characters (Unicode Cc) dropped except tab and newline, then
 * stripped like Python's str.strip(). Format characters (Cf, e.g. U+200B,
 * U+FEFF) are kept on both sides. The counter must show what the server counts.
 */
export function normalizeSolutionText(raw: string): string {
  return raw
    .replace(/\r\n?/g, "\n")
    .replace(/\p{Cc}/gu, (ch) => (ch === "\n" || ch === "\t" ? ch : ""))
    .replace(PY_STRIP, "");
}

/** Code points, like Python's len() - not UTF-16 units. */
export function countChars(text: string): number {
  return [...text].length;
}

/** "20 000" with a plain space, so tests and the server message match. */
export function formatCount(n: number): string {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

export function findMathSpans(text: string): MathSpan[] {
  const spans: MathSpan[] = [];
  for (const match of text.matchAll(MATH_PATTERN)) {
    const [whole, display, bracketDisplay, parenInline, inline] = match;
    const start = match.index ?? 0;
    spans.push({
      start,
      end: start + whole.length,
      source: display ?? bracketDisplay ?? parenInline ?? inline ?? "",
      display: display !== undefined || bracketDisplay !== undefined,
    });
  }
  return spans;
}

/** MathLive's virtual keyboard leaves \placeholder{} / \placeholder[id]{x} tokens behind. */
export function stripPlaceholders(latex: string): string {
  return latex.replace(/\\placeholder(?:\[[^\]]*\])?\{[^{}]*\}/g, "");
}

/** Placeholders out, whitespace (including line breaks - an inline $...$ cannot
 *  contain one) collapsed to single spaces, trimmed. */
export function sanitizeLatex(latex: string): string {
  return stripPlaceholders(latex).replace(/\s+/g, " ").trim();
}

function wrap(latex: string, display: boolean): string {
  const body = sanitizeLatex(latex);
  return display ? `$$${body}$$` : `$${body}$`;
}

/** Insert a formula at the cursor, replacing the selection [selStart, selEnd).
 *  A display formula gets its own line. Returns the new text and cursor. */
export function insertFormula(
  text: string,
  selStart: number,
  selEnd: number,
  latex: string,
  display: boolean
): { text: string; cursor: number } {
  const before = text.slice(0, selStart);
  const after = text.slice(selEnd);
  let snippet = wrap(latex, display);
  if (display) {
    if (before.length > 0 && !before.endsWith("\n")) snippet = "\n" + snippet;
    if (after.length > 0 && !after.startsWith("\n")) snippet = snippet + "\n";
  }
  return { text: before + snippet + after, cursor: selStart + snippet.length };
}

export function replaceMathSpan(text: string, span: MathSpan, latex: string, display: boolean): string {
  return text.slice(0, span.start) + wrap(latex, display) + text.slice(span.end);
}

/**
 * Replace the index-th formula of the current text, provided it is still the
 * one the student opened (same source). The text can change while the formula
 * dialog is open, so offsets taken earlier are not trusted. Returns null when
 * that formula is gone or another one took its place - the caller then inserts
 * the result instead of overwriting something else.
 */
export function replaceMathAt(
  text: string,
  index: number,
  expectedSource: string,
  latex: string,
  display: boolean
): { text: string; cursor: number } | null {
  const span = findMathSpans(text)[index];
  if (!span || span.source !== expectedSource) return null;
  return { text: replaceMathSpan(text, span, latex, display), cursor: span.start };
}

/**
 * The minimal .tex reading (see the spec, section 1.2): body of the document if
 * there is one, % comments and title boilerplate dropped, \section* text kept,
 * \[..\] -> $$..$$ and \(..\) -> $..$, runs of blank lines collapsed. Anything
 * else stays as it is - KaTeX renders what it can and the preview shows the rest.
 */
export function extractTexBody(text: string): string {
  const document = text.match(/\\begin\{document\}([\s\S]*?)\\end\{document\}/);
  const body = document ? document[1] : text;
  return body
    .replace(/(^|[^\\])%.*$/gm, "$1")
    .replace(/\\(maketitle|title\{[^}]*\}|author\{[^}]*\}|date\{[^}]*\})/g, "")
    .replace(/\\section\*?\{([^}]*)\}/g, "$1")
    .replace(/\\\[([\s\S]*?)\\\]/g, (_m, inner: string) => `$$${inner}$$`)
    .replace(/\\\(([\s\S]*?)\\\)/g, (_m, inner: string) => `$${inner}$`)
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export const SOLUTION_FILE_MAX_BYTES = 200 * 1024;

/** A problem with a .txt/.tex file the student chose; the message is shown as-is. */
export class SolutionFileError extends Error {}

export async function readSolutionFile(file: File): Promise<string> {
  if (file.size > SOLUTION_FILE_MAX_BYTES) {
    throw new SolutionFileError("Plik jest za duży (maksymalnie 200 KB)");
  }
  let text: string;
  try {
    // fatal: a Windows-1250 file must be refused, not silently mangled;
    // a leading BOM is dropped by the decoder (ignoreBOM defaults to false)
    text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
  } catch {
    throw new SolutionFileError("Plik musi być zapisany w kodowaniu UTF-8");
  }
  return file.name.toLowerCase().endsWith(".tex") ? extractTexBody(text) : text;
}
