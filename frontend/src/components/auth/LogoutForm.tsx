"use client";

import type { FormEvent, ReactNode } from "react";
import { forgetThisDevice } from "@/lib/push/device";

/**
 * Wylogowanie to POST formularza (nie link): inna strona nie wyloguje nikogo
 * linkiem ani obrazkiem, a prefetch Next.js nie ma czego pobrac. Backend
 * odpowiada 303 na /years. `children` musi zawierac przycisk type="submit".
 *
 * Przed wylogowaniem wylacza przypomnienia na tym urzadzeniu - na wspolnym
 * telefonie wzorce poprzedniej osoby nie moga trafiac na ekran blokady.
 */
export function LogoutForm({ children }: { children: ReactNode }) {
  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    await forgetThisDevice();
    form.submit();
  };

  return (
    <form method="post" action="/logout" onSubmit={onSubmit} style={{ display: "inline-flex", margin: 0 }}>
      {children}
    </form>
  );
}
