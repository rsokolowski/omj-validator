// Run: node --experimental-strip-types --test src/lib/utils/__tests__/mathHtml.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { renderMathHtml } from "../mathHtml.ts";

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
