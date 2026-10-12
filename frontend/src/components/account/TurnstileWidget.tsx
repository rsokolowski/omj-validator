"use client";

import { useEffect, useRef, useState } from "react";
import { Box, FormHelperText } from "@mui/material";

// Cloudflare Turnstile ("nie jestem robotem") on the registration step that
// creates the account. Explicit render: the script is loaded only on this
// step, never on the login page. The token is single-use - the parent bumps
// `resetSignal` after every failed attempt so the widget issues a new one.

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

interface TurnstileApi {
  render: (container: HTMLElement, options: Record<string, unknown>) => string;
  reset: (widgetId: string) => void;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let scriptPromise: Promise<TurnstileApi> | null = null;

function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = SCRIPT_SRC;
      script.async = true;
      script.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("turnstile")));
      script.onerror = () => {
        scriptPromise = null; // a later mount may try again
        script.remove();
        reject(new Error("turnstile"));
      };
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

interface TurnstileWidgetProps {
  siteKey: string;
  /** A fresh token, or null when it expired / failed */
  onToken: (token: string | null) => void;
  /** Change it to get a new token (after the previous one was used) */
  resetSignal: number;
  error?: string;
}

export function TurnstileWidget({ siteKey, onToken, resetSignal, error }: TurnstileWidgetProps) {
  const container = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  const tokenCallback = useRef(onToken);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    tokenCallback.current = onToken;
  }, [onToken]);

  useEffect(() => {
    let cancelled = false;
    // A token from an earlier mount of this step is not reused
    tokenCallback.current(null);
    loadTurnstile()
      .then((api) => {
        if (cancelled || !container.current) return;
        widgetId.current = api.render(container.current, {
          sitekey: siteKey,
          action: "register",
          language: "pl",
          theme: "light",
          size: "flexible",
          callback: (token: string) => tokenCallback.current(token),
          "expired-callback": () => tokenCallback.current(null),
          // Turnstile retries on its own (retry: "auto")
          "error-callback": () => tokenCallback.current(null),
        });
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });
    return () => {
      cancelled = true;
      if (widgetId.current && window.turnstile) window.turnstile.remove(widgetId.current);
      widgetId.current = null;
    };
  }, [siteKey]);

  useEffect(() => {
    if (resetSignal === 0) return;
    tokenCallback.current(null);
    if (widgetId.current && window.turnstile) window.turnstile.reset(widgetId.current);
  }, [resetSignal]);

  return (
    <Box sx={{ mt: 2.5 }}>
      <Box ref={container} sx={{ minHeight: 65 }} />
      {(loadFailed || error) && (
        <FormHelperText error role="alert" sx={{ mx: 0 }}>
          {loadFailed
            ? "Nie udało się wczytać zabezpieczenia przed robotami. Sprawdź internet albo wyłącz blokowanie treści na tej stronie i odśwież ją."
            : error}
        </FormHelperText>
      )}
    </Box>
  );
}
