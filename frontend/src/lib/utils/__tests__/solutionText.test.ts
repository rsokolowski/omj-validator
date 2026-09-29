// Run: node --experimental-strip-types --test src/lib/utils/__tests__/solutionText.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SolutionFileError,
  countChars,
  extractTexBody,
  findMathSpans,
  formatCount,
  insertFormula,
  normalizeSolutionText,
  readSolutionFile,
  replaceMathSpan,
  sanitizeLatex,
  stripPlaceholders,
} from "../solutionText.ts";

test("normalizeSolutionText mirrors the server rule", () => {
  assert.equal(normalizeSolutionText("a\r\nb\rc"), "a\nb\nc");
  assert.equal(normalizeSolutionText("linia 1\rlinia 2\u0000koniec"), "linia 1\nlinia 2koniec");
  assert.equal(normalizeSolutionText("a\u0000b\tc\u0007d\n\u001be"), "ab\tcd\ne");
  assert.equal(normalizeSolutionText("  \n Niech $n$. \n\t"), "Niech $n$.");
  assert.equal(normalizeSolutionText("   "), "");
});

test("format characters (Unicode Cf) are kept and counted, like the server does", () => {
  // Python's str.strip() does not treat U+200B or U+FEFF as whitespace, and
  // unicodedata drops only Cc - JS trim() would strip a BOM, so the rule is explicit.
  // Mirrored in tests/test_solution_text_validation.py::TestNormalize.
  assert.equal(normalizeSolutionText("​a​b​"), "​a​b​");
  assert.equal(normalizeSolutionText(" ﻿a﻿ "), "﻿a﻿");
  assert.equal(countChars(normalizeSolutionText("​a​")), 3);
  // Unicode whitespace Python strips is stripped here too
  assert.equal(normalizeSolutionText("　 a  "), "a");
});

test("countChars counts code points, formatCount groups thousands with a plain space", () => {
  assert.equal(countChars("𝑥".repeat(3)), 3);
  assert.equal("𝑥".repeat(3).length, 6);
  assert.equal(countChars("ąę\n"), 3);
  assert.equal(formatCount(20000), "20 000");
  assert.equal(formatCount(999), "999");
  assert.equal(formatCount(1234567), "1 234 567");
});

test("findMathSpans reports every delimiter kind with source offsets", () => {
  const text = "A $x$ B \\(y\\) C $$z$$ D \\[w\\] E";
  const spans = findMathSpans(text);
  assert.deepEqual(
    spans.map((s) => [text.slice(s.start, s.end), s.source, s.display]),
    [
      ["$x$", "x", false],
      ["\\(y\\)", "y", false],
      ["$$z$$", "z", true],
      ["\\[w\\]", "w", true],
    ]
  );
});

test("a lone dollar in prose stays literal and cannot reach a formula on a later line", () => {
  assert.deepEqual(findMathSpans("koszt 5$ i więcej"), []);
  const text = "koszt 5$ i więcej.\nZatem $a+b$";
  const spans = findMathSpans(text);
  assert.equal(spans.length, 1);
  assert.equal(text.slice(spans[0].start, spans[0].end), "$a+b$");
  // On one line the two dollars pair up - the live preview is what shows the student
  assert.equal(findMathSpans("koszt 5$ i $a$").length, 1);
});

test("stripPlaceholders and sanitizeLatex", () => {
  // The whole token goes, including a default value the keyboard put inside it
  assert.equal(stripPlaceholders("\\frac{\\placeholder{}}{\\placeholder[den]{2}}"), "\\frac{}{}");
  assert.equal(sanitizeLatex("  a \n+\n b \\placeholder{} "), "a + b");
  assert.equal(sanitizeLatex("\\placeholder{}"), "");
});

test("insertFormula at start, middle, end and over a selection", () => {
  assert.deepEqual(insertFormula("abc", 0, 0, "x", false), { text: "$x$abc", cursor: 3 });
  assert.deepEqual(insertFormula("abc", 1, 1, "x", false), { text: "a$x$bc", cursor: 4 });
  assert.deepEqual(insertFormula("abc", 3, 3, "x", false), { text: "abc$x$", cursor: 6 });
  assert.deepEqual(insertFormula("a[sel]b", 1, 6, "y", false), { text: "a$y$b", cursor: 4 });
});

test("a display formula is put on its own line", () => {
  assert.deepEqual(insertFormula("", 0, 0, "x", true), { text: "$$x$$", cursor: 5 });
  assert.deepEqual(insertFormula("ab", 1, 1, "x", true), { text: "a\n$$x$$\nb", cursor: 8 });
  assert.deepEqual(insertFormula("a\n", 2, 2, "x", true), { text: "a\n$$x$$", cursor: 7 });
  assert.deepEqual(insertFormula("\nb", 0, 0, "x", true), { text: "$$x$$\nb", cursor: 5 });
});

test("insertFormula collapses line breaks inside the LaTeX so inline math still renders", () => {
  const { text } = insertFormula("", 0, 0, "a\n+\nb", false);
  assert.equal(text, "$a + b$");
  assert.equal(findMathSpans(text).length, 1);
});

test("replaceMathSpan replaces exactly one span and leaves neighbours intact", () => {
  const text = "p $a$ q $$b$$ r $c$";
  const spans = findMathSpans(text);
  assert.equal(replaceMathSpan(text, spans[1], "B", true), "p $a$ q $$B$$ r $c$");
  assert.equal(replaceMathSpan(text, spans[1], "B", false), "p $a$ q $B$ r $c$");
  assert.equal(replaceMathSpan(text, spans[2], "C", false), "p $a$ q $$b$$ r $C$");
});

test("extractTexBody keeps the document body and rewrites bracket delimiters", () => {
  const tex = [
    "\\documentclass{article}",
    "\\title{Zad 1} \\author{Ja} \\date{}",
    "\\begin{document}",
    "\\maketitle",
    "\\section*{Rozwiązanie} % komentarz",
    "Niech \\(n\\) będzie liczbą. 50\\% to połowa.",
    "\\[ n^2 \\ge 0 \\]",
    "",
    "",
    "",
    "Koniec.",
    "\\end{document}",
  ].join("\n");
  assert.equal(
    extractTexBody(tex),
    "Rozwiązanie \nNiech $n$ będzie liczbą. 50\\% to połowa.\n$$ n^2 \\ge 0 $$\n\nKoniec."
  );
});

test("extractTexBody without \\end{document} keeps the whole text", () => {
  const out = extractTexBody("\\begin{document}\nTekst \\(x\\)");
  assert.equal(out, "\\begin{document}\nTekst $x$");
});

test("readSolutionFile: strict UTF-8, BOM stripped, size cap, .tex handled", async () => {
  const bom = new Uint8Array([0xef, 0xbb, 0xbf, 0x61, 0xc4, 0x85]); // BOM + "aą"
  assert.equal(await readSolutionFile(new File([bom], "n.txt")), "aą");

  const tex = new File(["\\begin{document}x \\(y\\)\\end{document}"], "s.TEX");
  assert.equal(await readSolutionFile(tex), "x $y$");

  const bad = new File([new Uint8Array([0xff, 0xfe, 0x41])], "bad.txt");
  await assert.rejects(readSolutionFile(bad), (e: unknown) =>
    e instanceof SolutionFileError && e.message === "Plik musi być zapisany w kodowaniu UTF-8"
  );

  const big = new File([new Uint8Array(200 * 1024 + 1)], "big.txt");
  await assert.rejects(readSolutionFile(big), (e: unknown) =>
    e instanceof SolutionFileError && e.message.startsWith("Plik jest za duży")
  );
});
