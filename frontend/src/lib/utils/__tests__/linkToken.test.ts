// Run: node --experimental-strip-types --test src/lib/utils/__tests__/linkToken.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { LINK_TOKEN_STATE_KEY, splitTokenFromUrl, tokenFromState } from "../linkToken.ts";

test("the token leaves the URL, other parameters stay", () => {
  const { token, cleanUrl } = splitTokenFromUrl("https://omj.example/rodzic/zgoda?t=abc123&decyzja=nie#x");
  assert.equal(token, "abc123");
  assert.equal(cleanUrl, "/rodzic/zgoda?decyzja=nie#x");
});

test("no token: the URL is unchanged", () => {
  assert.deepEqual(splitTokenFromUrl("https://omj.example/rodzic"), { token: null, cleanUrl: "/rodzic" });
  assert.equal(splitTokenFromUrl("https://omj.example/rodzic?t=").token, null);
});

test("token read back from a history entry's state", () => {
  assert.equal(tokenFromState({ [LINK_TOKEN_STATE_KEY]: "abc", __NA: true }), "abc");
  assert.equal(tokenFromState({ __NA: true }), null);
  assert.equal(tokenFromState(null), null);
  assert.equal(tokenFromState({ [LINK_TOKEN_STATE_KEY]: 42 }), null);
});
