import type { ReactNode } from "react";

/**
 * Wylogowanie to POST formularza (nie link): inna strona nie wyloguje nikogo
 * linkiem ani obrazkiem, a prefetch Next.js nie ma czego pobrac. Backend
 * odpowiada 303 na /years. `children` musi zawierac przycisk type="submit".
 */
export function LogoutForm({ children }: { children: ReactNode }) {
  return (
    <form method="post" action="/logout" style={{ display: "inline-flex", margin: 0 }}>
      {children}
    </form>
  );
}
