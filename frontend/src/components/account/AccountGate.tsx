"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Box, Container, Link as MuiLink, Typography } from "@mui/material";
import HourglassTop from "@mui/icons-material/HourglassTop";
import { useAuth } from "@/lib/hooks/useAuth";

// Strony dostepne mimo braku roku urodzenia: sam krok, zasady, wylogowanie,
// strony z linkow w e-mailach (rodzic moze otworzyc je na urzadzeniu dziecka)
// i "Moje rozwiazania" - tam jest usuniecie konta (RODO art. 17), ktore nie
// moze zalezec od podania roku urodzenia.
const PROFILE_EXEMPT = [
  "/konto/uzupelnij",
  "/regulamin",
  "/logout",
  "/rodzic",
  "/reset-hasla",
  "/my-solutions",
];
// Bez paska "czeka na zgode": sama strona oczekiwania i strony dla rodzica
const BANNER_HIDDEN = ["/konto/oczekuje", "/konto/uzupelnij", "/rodzic", "/reset-hasla"];

function matches(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

/**
 * Pilnuje stanu konta na kazdej stronie: konto bez roku urodzenia trafia na
 * /konto/uzupelnij, konto czekajace na zgode rodzica widzi pasek z odnosnikiem.
 */
export function AccountGate() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { account, needsProfile, isPendingParent } = useAuth({ revalidateOnFocus: true });

  useEffect(() => {
    if (needsProfile && !matches(pathname, PROFILE_EXEMPT)) {
      router.replace("/konto/uzupelnij");
    }
  }, [needsProfile, pathname, router]);

  if (!account || !isPendingParent || needsProfile || matches(pathname, BANNER_HIDDEN)) {
    return null;
  }

  return (
    <Box
      role="region"
      aria-label="Stan konta"
      sx={{ bgcolor: "#fffbeb", borderBottom: "1px solid", borderColor: "#fde68a" }}
    >
      <Container maxWidth="lg">
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 1 }}>
          <HourglassTop aria-hidden="true" sx={{ fontSize: 18, color: "warning.main", flexShrink: 0 }} />
          <Typography variant="body2" sx={{ color: "grey.800" }}>
            Twoje konto czeka na zgodę rodzica.{" "}
            <MuiLink
              component={Link}
              href="/konto/oczekuje"
              sx={{ color: "#92400e", fontWeight: 600, whiteSpace: "nowrap" }}
            >
              Zobacz, co dalej →
            </MuiLink>
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}
