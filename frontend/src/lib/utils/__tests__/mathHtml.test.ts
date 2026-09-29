// Run: node --experimental-strip-types --test src/lib/utils/__tests__/mathHtml.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { renderMathHtml } from "../mathHtml.ts";
import { findMathSpans } from "../solutionText.ts";

test("text outside math is HTML-escaped", () => {
  const html = renderMathHtml('<img src=x onerror="alert(1)"> i <b>bold</b>');
  assert.ok(!html.includes("<img"), html);
  assert.ok(!html.includes("<b>"), html);
  assert.ok(html.includes("&lt;img"), html);
});

test("inline and display math are rendered by KaTeX", () => {
  const html = renderMathHtml("Niech $a<b$ oraz $$x^2$$.");
  assert.ok(html.includes('class="katex"'), html);
  assert.ok(html.includes("katex-display"), html);
  // "<" inside math is KaTeX's business, not raw HTML
  assert.ok(!html.includes("<b$"), html);
});

test("newlines become line breaks", () => {
  assert.equal(renderMathHtml("a\nb"), "a<br>b");
});

test("bracket delimiters still work", () => {
  const html = renderMathHtml("\\(x\\) i \\[y\\]");
  assert.equal((html.match(/class="katex"/g) || []).length, 2, html);
});

test("an unmatched dollar stays literal text", () => {
  assert.equal(renderMathHtml("koszt 5$ & więcej"), "koszt 5$ &amp; więcej");
});

test("indexMath wraps each formula with its source index, in findMathSpans order", () => {
  const text = "Niech $a$ i \\(b\\); wtedy $$a+b$$ oraz \\[a-b\\].";
  const html = renderMathHtml(text, { indexMath: true });
  const indices = [...html.matchAll(/data-math-index="(\d+)"/g)].map((m) => Number(m[1]));
  assert.deepEqual(indices, [0, 1, 2, 3]);
  assert.equal(findMathSpans(text).length, 4);
  assert.ok(html.includes('class="math-src math-src--display" data-math-index="2"'), html);
  assert.ok(html.includes('role="button" tabindex="0" aria-label="Popraw wzór 1"'), html);
  assert.ok(html.includes('data-math-index="3" role="button" tabindex="0" aria-label="Popraw wzór 4"'), html);
});

test("without indexMath there is no wrapper", () => {
  assert.ok(!renderMathHtml("$x$").includes("data-math-index"));
});

test("a display formula swallows one adjacent newline on each side", () => {
  assert.ok(!renderMathHtml("a\n$$x$$\nb").includes("<br>"));
  const html = renderMathHtml("a\n\n$$x$$\n\nb");
  assert.equal((html.match(/<br>/g) || []).length, 2, html);
  // inline formulas keep their line breaks
  assert.equal((renderMathHtml("a\n$x$\nb").match(/<br>/g) || []).length, 2);
});
