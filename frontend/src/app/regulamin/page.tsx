"use client";

import { Box, Typography, Paper, Link as MuiLink } from "@mui/material";
import Link from "next/link";
import { APP_NAME, CONTACT_EMAIL } from "@/lib/utils/constants";

export default function RegulaminPage() {
  return (
    <Box sx={{ maxWidth: 800, mx: "auto" }}>
      <Typography
        variant="h1"
        sx={{
          fontSize: { xs: "1.75rem", md: "2.25rem" },
          fontWeight: 700,
          mb: 4,
          color: "grey.900",
        }}
      >
        Regulamin serwisu {APP_NAME}
      </Typography>

      <Paper
        elevation={0}
        sx={{
          p: { xs: 3, md: 4 },
          border: "1px solid",
          borderColor: "grey.200",
          borderRadius: 2,
        }}
      >
        <Section title="1. Postanowienia ogólne">
          <Typography paragraph>
            Niniejszy regulamin określa zasady korzystania z serwisu {APP_NAME}{" "}
            dostępnego pod adresem{" "}
            <MuiLink
              href="https://omj-validator.duckdns.org"
              target="_blank"
              rel="noopener"
            >
              omj-validator.duckdns.org
            </MuiLink>
            .
          </Typography>
          <Typography paragraph>
            Serwis {APP_NAME} jest niekomercyjnym projektem edukacyjnym,
            stworzonym w celu pomocy uczniom w przygotowaniu do Olimpiady
            Matematycznej Juniorów (OMJ).
          </Typography>
          <Typography paragraph>
            Korzystanie z serwisu jest bezpłatne i wymaga akceptacji niniejszego
            regulaminu.
          </Typography>
        </Section>

        <Section title="2. Charakter serwisu i ograniczenia">
          <Typography paragraph>
            <strong>
              Serwis ma charakter wyłącznie edukacyjny i pomocniczy.
            </strong>{" "}
            Nie jest oficjalnym narzędziem Olimpiady Matematycznej Juniorów ani
            nie jest powiązany z organizatorami OMJ.
          </Typography>
          <Typography paragraph>
            <strong>
              Treści zadań, wskazówki, powiązania między zadaniami oraz oceny
              rozwiązań są generowane przez sztuczną inteligencję (AI) i mogą
              zawierać błędy.
            </strong>{" "}
            Oceny wystawiane przez serwis nie mają charakteru oficjalnego i nie
            powinny być traktowane jako ostateczna weryfikacja poprawności
            rozwiązania.
          </Typography>
          <Typography paragraph>
            Oryginalne treści zadań w formacie PDF pochodzą z oficjalnych
            materiałów Olimpiady Matematycznej Juniorów dostępnych na stronie{" "}
            <MuiLink href="https://omj.edu.pl" target="_blank" rel="noopener">
              omj.edu.pl
            </MuiLink>
            .
          </Typography>
        </Section>

        <Section title="3. Rejestracja i logowanie">
          <Typography paragraph>
            Logowanie do serwisu odbywa się za pośrednictwem konta Google (OAuth
            2.0). Serwis nie przechowuje haseł użytkowników.
          </Typography>
          <Typography paragraph>
            Podczas logowania serwis uzyskuje dostęp do następujących danych z
            konta Google:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>Adres e-mail</li>
            <li>Imię i nazwisko (nazwa wyświetlana)</li>
            <li>Zdjęcie profilowe</li>
          </Box>
          <Typography paragraph>
            Dane te są wykorzystywane wyłącznie w celu identyfikacji użytkownika
            w serwisie i nie są udostępniane osobom trzecim.
          </Typography>
        </Section>

        <Section title="4. Polityka prywatności">
          <Typography paragraph>
            <strong>Dane przechowywane przez serwis:</strong>
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>Identyfikator Google (do identyfikacji konta)</li>
            <li>Adres e-mail i nazwa użytkownika</li>
            <li>Przesłane zdjęcia rozwiązań (przechowywane na serwerze)</li>
            <li>Historia ocen i informacji zwrotnych</li>
          </Box>
          <Typography paragraph>
            <strong>Przesłane rozwiązania</strong> mogą być analizowane przez
            zewnętrzne usługi AI (Google Gemini) w celu wygenerowania oceny.
            Przesyłając rozwiązanie, użytkownik wyraża na to zgodę.
          </Typography>
          <Typography paragraph>
            Użytkownik może zażądać usunięcia swoich danych, kontaktując się pod
            adresem{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </MuiLink>
            .
          </Typography>
        </Section>

        <Section title="5. Zasady korzystania">
          <Typography paragraph>Użytkownik zobowiązuje się do:</Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>Korzystania z serwisu zgodnie z jego przeznaczeniem</li>
            <li>
              Nieprzesyłania treści niezwiązanych z rozwiązaniami zadań
              matematycznych
            </li>
            <li>Niepodejmowania prób obejścia zabezpieczeń serwisu</li>
            <li>
              Nienadużywania zasobów serwisu (np. masowego przesyłania
              rozwiązań)
            </li>
          </Box>
          <Typography paragraph>
            Administrator zastrzega sobie prawo do ograniczenia lub
            zablokowania dostępu użytkownikom naruszającym regulamin.
          </Typography>
        </Section>

        <Section title="6. Ograniczenie odpowiedzialności">
          <Typography paragraph>
            Serwis jest udostępniany &bdquo;tak jak jest&rdquo; (ang. &bdquo;as
            is&rdquo;), bez jakichkolwiek gwarancji, wyraźnych lub
            dorozumianych.
          </Typography>
          <Typography paragraph>
            Administrator nie ponosi odpowiedzialności za:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>Błędy w ocenach generowanych przez AI</li>
            <li>Przerwy w działaniu serwisu</li>
            <li>Utratę danych użytkownika</li>
            <li>
              Szkody wynikłe z korzystania lub niemożności korzystania z serwisu
            </li>
          </Box>
        </Section>

        <Section title="7. Prawa autorskie i licencja">
          <Typography paragraph>
            Kod źródłowy serwisu {APP_NAME} jest udostępniony na licencji MIT i
            dostępny w repozytorium{" "}
            <MuiLink
              href="https://github.com/rsokolowski/omj-validator"
              target="_blank"
              rel="noopener"
            >
              GitHub
            </MuiLink>
            .
          </Typography>
          <Typography paragraph>
            Treści zadań są własnością Olimpiady Matematycznej Juniorów i są
            wykorzystywane w celach edukacyjnych.
          </Typography>
        </Section>

        <Section title="8. Zmiany regulaminu">
          <Typography paragraph>
            Administrator zastrzega sobie prawo do zmiany regulaminu w dowolnym
            czasie. O istotnych zmianach użytkownicy zostaną poinformowani
            poprzez komunikat w serwisie.
          </Typography>
          <Typography paragraph>
            Dalsze korzystanie z serwisu po wprowadzeniu zmian oznacza ich
            akceptację.
          </Typography>
        </Section>

        <Section title="9. Kontakt" isLast>
          <Typography paragraph>
            W sprawach związanych z serwisem można kontaktować się pod adresem:{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>
              {CONTACT_EMAIL}
            </MuiLink>
          </Typography>
        </Section>

        <Typography
          sx={{
            mt: 4,
            pt: 3,
            borderTop: "1px solid",
            borderColor: "grey.200",
            color: "grey.500",
            fontSize: "0.875rem",
            textAlign: "center",
          }}
        >
          Ostatnia aktualizacja: grudzień 2025
        </Typography>
      </Paper>

      <Box sx={{ mt: 4, textAlign: "center" }}>
        <Link href="/" style={{ textDecoration: "none" }}>
          <Typography sx={{ color: "primary.main" }}>
            ← Powrót do strony głównej
          </Typography>
        </Link>
      </Box>
    </Box>
  );
}

function Section({
  title,
  children,
  isLast = false,
}: {
  title: string;
  children: React.ReactNode;
  isLast?: boolean;
}) {
  return (
    <Box sx={{ mb: isLast ? 0 : 4 }}>
      <Typography
        variant="h2"
        sx={{
          fontSize: "1.25rem",
          fontWeight: 600,
          mb: 2,
          color: "grey.800",
        }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );
}
