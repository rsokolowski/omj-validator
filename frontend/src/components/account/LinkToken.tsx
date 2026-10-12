"use client";

import { useEffect, useSyncExternalStore } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import { LINK_TOKEN_STATE_KEY, splitTokenFromUrl, tokenFromState } from "@/lib/utils/linkToken";
import { FormCard } from "./FormCard";

const noopSubscribe = () => () => undefined;

/**
 * Token z linku w e-mailu (?t=...). Po odczytaniu przenosimy go do stanu
 * biezacego wpisu historii i usuwamy z paska adresu (history.replaceState),
 * zeby nie zostal w adresie, historii, zakladkach ani naglowku Referer.
 * Odswiezenie tego samego wpisu znajduje go w history.state; nowe wejscie na
 * goly adres tokenu nie ma. Do API token idzie wylacznie w tresci POST.
 *
 * Stan przekazujemy BEZ wewnetrznych kluczy Next.js (__NA): wtedy Next
 * dopisuje swoje, uaktualnia adres w routerze i zachowuje nasz klucz.
 */
export function useLinkToken(fromUrl: string | null): { ready: boolean; token: string | null } {
  // false na serwerze i przy hydratacji, true po zamontowaniu w przegladarce
  const isClient = useSyncExternalStore(noopSubscribe, () => true, () => false);

  useEffect(() => {
    if (!fromUrl) return;
    const { cleanUrl } = splitTokenFromUrl(window.location.href);
    window.history.replaceState({ [LINK_TOKEN_STATE_KEY]: fromUrl }, "", cleanUrl);
  }, [fromUrl]);

  if (!isClient) return { ready: false, token: null };
  return { ready: true, token: fromUrl ?? tokenFromState(window.history.state) };
}

/** Po dzialaniu konczacym (zgoda, usuniecie konta, nowe haslo) token nie jest juz potrzebny. */
export function forgetLinkToken(): void {
  if (tokenFromState(window.history.state)) {
    window.history.replaceState({}, "", splitTokenFromUrl(window.location.href).cleanUrl);
  }
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
