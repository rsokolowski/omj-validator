// Tokens from e-mail links (?t=...). The page reads the token once, moves it
// into the history entry's state and removes it from the address bar, so it
// does not linger in the URL (history, bookmarks, screenshots, Referer).
// A reload of the same entry finds it in history.state; a fresh visit to the
// bare path has no token.

export const LINK_TOKEN_STATE_KEY = "linkToken";

/** The ?t= token of a URL and the same URL without it. */
export function splitTokenFromUrl(href: string): { token: string | null; cleanUrl: string } {
  const url = new URL(href);
  const token = url.searchParams.get("t");
  url.searchParams.delete("t");
  return { token: token || null, cleanUrl: `${url.pathname}${url.search}${url.hash}` };
}

/** The token kept in a history entry's state, if any. */
export function tokenFromState(state: unknown): string | null {
  if (state && typeof state === "object") {
    const value = (state as Record<string, unknown>)[LINK_TOKEN_STATE_KEY];
    if (typeof value === "string" && value) return value;
  }
  return null;
}
