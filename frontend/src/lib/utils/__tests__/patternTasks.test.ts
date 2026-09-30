// Run: node --experimental-strip-types --test src/lib/utils/__tests__/patternTasks.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { splitTaskRefs, taskRef } from "../patternTasks.ts";

test("task key becomes a label and a task page URL", () => {
  assert.deepEqual(taskRef("2015_etap3_1"), {
    key: "2015_etap3_1",
    label: "2015 · etap III · zad. 1",
    url: "/task/2015/etap3/1",
  });
  assert.equal(taskRef("2015_etap4_1"), null);
  assert.equal(taskRef("../etc"), null);
});

test("reply is split around task references", () => {
  const parts = splitTaskRefs("Zobacz [[2015_etap3_1]] i $a \\mid b$.");
  assert.equal(parts.length, 3);
  assert.deepEqual(parts[0], { text: "Zobacz " });
  assert.equal("task" in parts[1] && parts[1].task.url, "/task/2015/etap3/1");
  assert.deepEqual(parts[2], { text: " i $a \\mid b$." });
});

test("reply without references is one text part", () => {
  assert.deepEqual(splitTaskRefs("Bez zadań."), [{ text: "Bez zadań." }]);
  assert.deepEqual(splitTaskRefs(""), []);
});
