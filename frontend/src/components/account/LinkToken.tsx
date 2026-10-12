"use client";

import { useEffect, useSyncExternalStore } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import { FormCard } from "./FormCard";

const noopSubscribe = () => () => undefined;

function readStored(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

/**
 * Token z linku w e-mailu (?t=...). Po odczytaniu znika z paska adresu
 * (history.replaceState), zeby nie trafil do historii, zakladek, zrzutow
 * ekranu ani dziennikow serwera przy kolejnych zapytaniach; na czas karty
 * zostaje w sessionStorage, wiec odswiezenie strony dalej dziala.
 * Do API token idzie wylacznie w tresci zapytania POST.
 */
export function useLinkToken(fromUrl: string | null, storageKey: string): { ready: boolean; token: string | null } {
  // false na serwerze i przy hydratacji, true po zamontowaniu w przegladarce
  const isClient = useSyncExternalStore(noopSubscribe, () => true, () => false);

  useEffect(() => {
    if (!fromUrl) return;
    try {
      window.sessionStorage.setItem(storageKey, fromUrl);
    } catch {
      // Tryb prywatny bez sessionStorage - odswiezenie wtedy nie zadziala, reszta tak
    }
    const url = new URL(window.location.href);
    if (url.searchParams.has("t")) {
      url.searchParams.delete("t");
      window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
    }
  }, [fromUrl, storageKey]);

  if (!isClient) return { ready: false, token: null };
  return { ready: true, token: fromUrl ?? readStored(storageKey) };
}

export function LinkTokenLoading() {
  return (
    <FormCard>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 2 }} role="status">
        <CircularProgress size={24} />
        <Typography>Wczytujemy…</Typography>
      </Box>
    </FormCard>
  );
}
