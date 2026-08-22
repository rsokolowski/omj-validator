import type { Metadata } from "next";
import { Box, Typography, Paper, Link as MuiLink } from "@mui/material";
import Link from "next/link";
import { APP_NAME, CONTACT_EMAIL } from "@/lib/utils/constants";

// Okresy przechowywania danych.
// Wartości muszą odpowiadać konfiguracji retencji w app/config.py
// (RETENTION_SUBMISSION_MONTHS, RETENTION_SCORING_THINKING_DAYS,
// RETENTION_INACTIVE_ACCOUNT_MONTHS, RETENTION_ADMIN_AUDIT_MONTHS).
// Zmiana konfiguracji na serwerze wymaga zmiany tych wartości tutaj.
const RETENTION_SUBMISSIONS = "24 miesiące";
const RETENTION_THINKING = "90 dni";
const RETENTION_INACTIVE_ACCOUNT = "36 miesięcy";
const RETENTION_ADMIN_AUDIT = "12 miesięcy";

const LAST_UPDATED = "sierpień 2026";

export const metadata: Metadata = {
  title: "Regulamin i polityka prywatności",
  description:
    "Regulamin serwisu Trener OMJ – zasady korzystania, ochrona danych osobowych, ocena generowana przez AI, prawa użytkownika.",
  alternates: { canonical: "/regulamin" },
};

export default function RegulaminPage() {
  return (
    <Box sx={{ maxWidth: 800, mx: "auto" }}>
      <Typography
        variant="h1"
        sx={{
          fontSize: { xs: "1.75rem", md: "2.25rem" },
          fontWeight: 700,
          mb: 2,
          color: "grey.900",
        }}
      >
        Regulamin i polityka prywatności serwisu {APP_NAME}
      </Typography>

      <Paper
        elevation={0}
        sx={{
          p: { xs: 3, md: 4 },
          mb: 3,
          border: "1px solid",
          borderColor: "primary.light",
          borderRadius: 2,
          bgcolor: "grey.50",
        }}
      >
        <Typography
          variant="h2"
          sx={{ fontSize: "1.25rem", fontWeight: 700, mb: 2, color: "grey.900" }}
        >
          Najważniejsze rzeczy w skrócie
        </Typography>
        <Typography paragraph sx={{ mb: 1 }}>
          Ta strona jest długa, bo tego wymagają przepisy. Jeśli masz przeczytać
          tylko jedną rzecz, przeczytaj to:
        </Typography>
        <Box component="ul" sx={{ pl: 3, mb: 2 }}>
          <li>
            <strong>Punkty i komentarze wystawia sztuczna inteligencja</strong>,
            nie człowiek. Czasem się myli.
          </li>
          <li>
            <strong>To nie są oceny szkolne.</strong> Nie trafiają do dziennika,
            nie wpływają na Twoje stopnie, na promocję do następnej klasy ani na
            rekrutację. To trenażer.
          </li>
          <li>
            <strong>Twoje zdjęcie kartki jest wysyłane do firmy Google</strong>,
            żeby program mógł je przeczytać i ocenić. Nie wysyłamy tam Twojego
            imienia, nazwiska ani adresu e-mail.
          </li>
          <li>
            <strong>Nie podpisuj kartki</strong> imieniem i nazwiskiem. Serwis i
            tak wie, czyja to praca, bo jesteś zalogowany.
          </li>
          <li>
            <strong>Jeśli masz mniej niż 16 lat</strong>, możesz korzystać z
            serwisu tylko za wiedzą i zgodą rodzica lub opiekuna.
          </li>
          <li>
            <strong>Możesz w każdej chwili usunąć swoje konto</strong> razem ze
            wszystkimi zdjęciami i wynikami.
          </li>
        </Box>
      </Paper>

      <Paper
        elevation={0}
        sx={{
          p: { xs: 3, md: 4 },
          border: "1px solid",
          borderColor: "grey.200",
          borderRadius: 2,
        }}
      >
        <Section title="1. Kto prowadzi serwis i kto odpowiada za dane">
          <Typography paragraph>
            Serwis {APP_NAME} działa pod adresem{" "}
            <MuiLink
              href="https://omj-validator.pl"
              target="_blank"
              rel="noopener"
            >
              omj-validator.pl
            </MuiLink>
            . Prowadzi go osoba prywatna &ndash; <strong>Rafał Sokołowski</strong>{" "}
            &ndash; jako niekomercyjny projekt edukacyjny. Serwis jest bezpłatny,
            nie wyświetla reklam i nie zarabia na danych użytkowników.
          </Typography>
          <Typography paragraph>
            <strong>
              Administratorem danych osobowych w rozumieniu RODO jest Rafał
              Sokołowski
            </strong>{" "}
            (rozporządzenie Parlamentu Europejskiego i Rady (UE) 2016/679).
            Kontakt we wszystkich sprawach, także dotyczących danych osobowych:{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</MuiLink>.
          </Typography>
          <Typography paragraph>
            Nie wyznaczono inspektora ochrony danych &ndash; przepisy tego w tym
            przypadku nie wymagają. Wszystkie sprawy prowadzi administrator
            osobiście, pod adresem podanym wyżej.
          </Typography>
          <Typography paragraph>
            Korzystanie z serwisu oznacza akceptację tego regulaminu.
          </Typography>
        </Section>

        <Section title="2. Czym serwis jest, a czym nie jest">
          <Typography paragraph>
            {APP_NAME} to <strong>trenażer</strong>. Rozwiązujesz zadanie
            olimpijskie na kartce, robisz zdjęcie i wysyłasz. Program czyta
            zdjęcie, przyznaje orientacyjną liczbę punktów w skali stosowanej w
            OMJ i pisze kilka zdań o tym, co jest dobre, a czego brakuje.
          </Typography>
          <Typography paragraph>
            Serwis stara się odzwierciedlić punktację OMJ, ale{" "}
            <strong>
              szczegółowe kryteria oceniania nie są publikowane przez
              organizatora
            </strong>{" "}
            &ndash; jawne są zadania i rozwiązania, a nie sposób punktowania prac.
            Punktacja w serwisie jest więc rekonstrukcją opartą na ogólnie
            znanych zasadach, a nie zastosowaniem oficjalnych kryteriów, i ma
            charakter wyłącznie poglądowy. Sama skala zależy dodatkowo od etapu
            zawodów.
          </Typography>
          <Typography paragraph>
            <strong>
              Punkty i komentarze są generowane przez sztuczną inteligencję
              (model językowy Google Gemini) i mogą być błędne.
            </strong>{" "}
            Program myli się najczęściej wtedy, gdy pismo jest nieczytelne, gdy
            zadanie ma rysunek, gdy zdjęcie jest zrobione pod kątem albo gdy
            rozwiązanie jest poprawne, ale zrobione inną metodą niż wzorcowa.
            Traktuj wynik jako wskazówkę, a nie jako wyrok.
          </Typography>
          <Typography paragraph>
            <strong>
              Ocena z serwisu nie jest oceną szkolną i nie ma żadnych skutków
              formalnych.
            </strong>{" "}
            Ocenianie osiągnięć ucznia jest zadaniem nauczyciela (art. 44b ustawy
            o systemie oświaty). Wynik z serwisu nie trafia do dziennika, nie
            wpływa na oceny, klasyfikację, promocję do następnej klasy ani na
            rekrutację. Nie jest też oficjalnym wynikiem olimpiady ani jego
            zapowiedzią.
          </Typography>
          <Typography paragraph>
            Serwis nie jest oficjalnym narzędziem Olimpiady Matematycznej
            Juniorów i nie jest powiązany z jej organizatorem &ndash;
            Stowarzyszeniem na rzecz Edukacji Matematycznej.
          </Typography>
          <Typography paragraph>
            Sztuczna inteligencja generuje w serwisie także inne treści:
            wskazówki do zadań, oznaczenia trudności i kategorii tematycznych,
            powiązania między zadaniami oraz zapis treści zadań. One również mogą
            zawierać błędy i są w serwisie oznaczone. W razie wątpliwości
            rozstrzygający jest oryginalny materiał OMJ dostępny na{" "}
            <MuiLink href="https://omj.edu.pl" target="_blank" rel="noopener">
              omj.edu.pl
            </MuiLink>
            .
          </Typography>
        </Section>

        <Section title="3. Jeśli masz mniej niż 16 lat">
          <Typography paragraph>
            Serwis jest przeznaczony przede wszystkim dla uczniów szkół
            podstawowych, czyli w praktyce dla osób poniżej 16. roku życia.
          </Typography>
          <Typography paragraph>
            W Polsce dziecko może samodzielnie zgodzić się na przetwarzanie
            swoich danych w usłudze internetowej dopiero od{" "}
            <strong>16 lat</strong> (art. 8 RODO w związku z art. 8 ustawy z 10
            maja 2018 r. o ochronie danych osobowych). Dlatego:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>
                jeśli masz mniej niż 16 lat, możesz korzystać z serwisu wyłącznie
                za wiedzą i zgodą rodzica lub opiekuna prawnego
              </strong>{" "}
              &ndash; to on wyraża zgodę na przetwarzanie Twoich danych;
            </li>
            <li>
              zaznaczając zgodę przy zakładaniu konta, oświadczasz, że masz
              ukończone 16 lat albo że Twój rodzic lub opiekun zapoznał się z tym
              dokumentem i zgadza się na korzystanie przez Ciebie z serwisu;
            </li>
            <li>
              rodzic lub opiekun może w każdej chwili napisać na adres{" "}
              <MuiLink href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </MuiLink>{" "}
              i zażądać usunięcia konta dziecka wraz ze wszystkimi danymi.
              Żądanie jest realizowane bez zbędnej zwłoki.
            </li>
          </Box>
          <Typography paragraph>
            <strong>Informacja dla rodziców i opiekunów.</strong> Zachęcamy do
            przeczytania punktów 5&ndash;9 tego dokumentu. Opisują one dokładnie,
            jakie dane dziecka są zbierane, komu są przekazywane (w tym poza Unię
            Europejską) i jak długo są przechowywane. Serwis nie wykorzystuje
            danych do reklam, nie profiluje dzieci w celach marketingowych i nie
            udostępnia danych komukolwiek poza dostawcami wymienionymi w punkcie
            7.
          </Typography>
        </Section>

        <Section title="4. Konto i logowanie">
          <Typography paragraph>
            Logowanie odbywa się przez konto Google (OAuth 2.0). Serwis{" "}
            <strong>nie zna i nie przechowuje Twojego hasła</strong> &ndash;
            uwierzytelnienie odbywa się po stronie Google.
          </Typography>
          <Typography paragraph>
            Konto jest potrzebne po to, żebyś widział wyłącznie swoje prace i
            swoją historię wyników oraz żeby działały limity chroniące serwis
            przed nadużyciami. Bez konta serwis nie może działać.
          </Typography>
          <Typography paragraph>
            Nie udostępniaj swojego konta innym osobom. Na komputerze, z którego
            korzysta więcej osób (szkoła, biblioteka, komputer rodzinny), wyloguj
            się po zakończeniu pracy &ndash; sesja pozostaje aktywna do 30 dni.
          </Typography>
        </Section>

        <Section title="5. Jakie dane zbieramy">
          <Typography paragraph>
            <strong>Dane z konta Google</strong> (przekazywane nam przy
            logowaniu):
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>identyfikator konta Google (trwały numer techniczny),</li>
            <li>adres e-mail,</li>
            <li>imię i nazwisko lub nazwa wyświetlana,</li>
            <li>
              adres zdjęcia profilowego &ndash; przechowywany wyłącznie w Twojej
              sesji (w ciasteczku), <strong>nie zapisujemy go w bazie danych</strong>.
            </li>
          </Box>
          <Typography paragraph>
            <strong>Dane związane z rozwiązywaniem zadań:</strong>
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>przesłane przez Ciebie zdjęcia rozwiązań,</li>
            <li>informacja, którego zadania dotyczyły i kiedy je wysłałeś,</li>
            <li>przyznana liczba punktów i treść informacji zwrotnej,</li>
            <li>
              dane techniczne o przebiegu analizy (nazwa użytego modelu, czas,
              koszt, treść odpowiedzi modelu),
            </li>
            <li>
              automatyczne oznaczenie, jeśli program uzna, że praca dotyczy
              innego zadania albo zawiera próbę wpłynięcia na ocenę (patrz punkt
              10).
            </li>
          </Box>
          <Typography paragraph>
            <strong>Dane techniczne:</strong> ciasteczko sesyjne (ważne 30 dni,
            podpisane kryptograficznie) oraz dzienniki serwera zawierające m.in.
            informacje o logowaniach i błędach. W dziennikach adresy e-mail są
            skracane tak, by nie identyfikowały osoby.
          </Typography>
          <Typography paragraph>
            <strong>Zapisy dostępu administratora:</strong> jeśli administrator
            serwisu zajrzy w Twoje dane, powstaje wpis w osobnym dzienniku
            &ndash; kto, czyje dane, jaki zasób i kiedy. Szczegóły w punkcie 7.
          </Typography>
          <Typography paragraph>
            <strong>To, co jest na zdjęciu kartki.</strong> To najważniejsze
            zdanie w tym punkcie: na fotografii znajduje się wszystko, co
            napisałeś na kartce i co znalazło się w kadrze. Dlatego:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>nie podpisuj kartki</strong> imieniem, nazwiskiem, klasą
              ani nazwą szkoły &ndash; serwis i tak wie, czyja to praca,
            </li>
            <li>fotografuj samą kartkę, nie pokój dookoła,</li>
            <li>
              uważaj, żeby w kadrze nie było innych osób ani cudzych rzeczy,
            </li>
            <li>
              nie wysyłaj kartek z prywatnymi notatkami niezwiązanymi z zadaniem.
            </li>
          </Box>
          <Typography paragraph>
            Nie zbieramy danych szczególnych kategorii (np. o zdrowiu,
            pochodzeniu czy przekonaniach) i prosimy, byś ich nie umieszczał na
            przesyłanych zdjęciach.
          </Typography>
        </Section>

        <Section title="6. Po co i na jakiej podstawie prawnej przetwarzamy dane">
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>
                Prowadzenie konta, ocena rozwiązań i historia postępów
              </strong>{" "}
              &ndash; podstawą jest <strong>zgoda</strong> (art. 6 ust. 1 lit. a
              RODO), a w przypadku osób poniżej 16. roku życia zgoda rodzica lub
              opiekuna prawnego (art. 8 RODO). Zgodę wyrażasz, zakładając konto,
              i możesz ją w każdej chwili cofnąć &ndash; najprościej usuwając
              konto.
            </li>
            <li>
              <strong>
                Bezpieczeństwo serwisu, limity liczby zgłoszeń i wykrywanie
                nadużyć
              </strong>{" "}
              &ndash; podstawą jest <strong>prawnie uzasadniony interes</strong>{" "}
              administratora (art. 6 ust. 1 lit. f RODO), polegający na
              utrzymaniu serwisu w działaniu i ochronie go przed nadużyciami.
              Na tej podstawie prowadzimy też dziennik dostępu administratora do
              danych (punkt 7) oraz krótkotrwały, pseudonimowy zapis
              wykorzystanego limitu po usunięciu konta (punkt 11). Te operacje
              nie mogą zależeć od zgody, bo wtedy każdy mógłby wyłączyć
              zabezpieczenia.
            </li>
            <li>
              <strong>
                Rozpatrywanie Twoich żądań dotyczących danych oraz obrona przed
                roszczeniami
              </strong>{" "}
              &ndash; art. 6 ust. 1 lit. c i lit. f RODO.
            </li>
          </Box>
          <Typography paragraph>
            Podanie danych jest dobrowolne, ale bez konta nie da się korzystać z
            serwisu.
          </Typography>
        </Section>

        <Section title="7. Komu przekazujemy dane">
          <Typography paragraph>
            <strong>Google &ndash; analiza rozwiązania (Gemini API).</strong>{" "}
            Twoje zdjęcia razem z treścią zadania i rozwiązaniem wzorcowym są
            przesyłane do usługi Google Gemini, która wykonuje ocenę. Ważne
            szczegóły:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>
                nie przekazujemy tam Twojego imienia, nazwiska, adresu e-mail ani
                identyfikatora konta
              </strong>{" "}
              &ndash; wysyłane jest samo zdjęcie pracy i treść zadania, a nazwy
              plików są losowe,
            </li>
            <li>
              pliki są <strong>usuwane</strong> z infrastruktury Google zaraz po
              zakończeniu analizy,
            </li>
            <li>
              korzystamy z <strong>płatnej wersji usługi</strong>, w której
              Google zobowiązuje się <strong>nie wykorzystywać</strong>{" "}
              przesyłanych treści ani odpowiedzi do trenowania swoich modeli, a
              rejestry techniczne przechowuje maksymalnie 55 dni wyłącznie po to,
              by wykrywać naruszenia zasad korzystania z usługi.
            </li>
          </Box>
          <Typography paragraph>
            <strong>Google &ndash; pozostałe usługi.</strong> Logowanie odbywa się
            przez usługę Google. Komunikaty o postępie analizy mogą być
            tłumaczone z angielskiego na polski przez usługę Google Cloud
            Translation.
          </Typography>
          <Typography paragraph>
            <strong>Dostawca ochrony i przesyłu ruchu.</strong> Połączenie z
            serwisem jest szyfrowane i przechodzi przez infrastrukturę firmy
            Cloudflare, Inc., która pośredniczy w przesyłaniu ruchu między Twoją
            przeglądarką a serwerem.
          </Typography>
          <Typography paragraph>
            <strong>Powiadomienia techniczne.</strong> Administrator może
            otrzymywać automatyczne powiadomienia o działaniu serwisu (np. że
            jakieś zgłoszenie się nie powiodło). Powiadomienia te zawierają
            wyłącznie dane operacyjne: numer zgłoszenia, oznaczenie zadania,
            liczbę zdjęć i wynik. <strong>Nie zawierają</strong> imienia,
            nazwiska, adresu e-mail ani identyfikatora użytkownika.
          </Typography>
          <Typography paragraph>
            <strong>Nikt inny.</strong> Nie sprzedajemy danych, nie przekazujemy
            ich reklamodawcom, nie korzystamy z zewnętrznej analityki ani
            mechanizmów śledzących. Inni użytkownicy nie widzą Twoich prac ani
            wyników.
          </Typography>
          <Typography paragraph>
            <strong>Dostęp administratora.</strong> Administrator serwisu ma
            techniczną możliwość wglądu we wszystkie zgłoszenia i zdjęcia. Korzysta
            z niej wyłącznie w celu rozwiązywania problemów technicznych i
            rozpatrywania zgłoszeń dotyczących błędnych ocen.
          </Typography>
          <Typography paragraph>
            <strong>Każde takie zajrzenie jest zapisywane.</strong> Serwis
            prowadzi osobny dziennik dostępu administratora: zapisuje adres
            e-mail administratora, informację, czyich danych dotyczył dostęp,
            rodzaj zasobu (np. zdjęcie rozwiązania, lista zgłoszeń, wyszukanie
            użytkownika) oraz datę i godzinę. <strong>Dziennik nie zawiera</strong>{" "}
            treści &ndash; ani zdjęć, ani informacji zwrotnych, ani wpisanej frazy
            wyszukiwania. Dzięki niemu można odpowiedzieć na pytanie
            &bdquo;kto oglądał moje dane i kiedy&rdquo;. Jeśli chcesz to wiedzieć,
            napisz na{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</MuiLink>.
            Zapisy są przechowywane przez {RETENTION_ADMIN_AUDIT}, a gdy usuniesz
            konto, Twój identyfikator jest w nich zastępowany nieodwracalnym
            skrótem &ndash; ślad, że dostęp miał miejsce, zostaje, ale nie da się
            już ustalić, kogo dotyczył.
          </Typography>
        </Section>

        <Section title="8. Przekazywanie danych poza Unię Europejską">
          <Typography paragraph>
            Usługi Google, z których korzysta serwis, oznaczają{" "}
            <strong>
              przekazanie zdjęcia Twojej pracy do Stanów Zjednoczonych
            </strong>
            .
          </Typography>
          <Typography paragraph>
            Podstawą tego przekazania jest{" "}
            <strong>
              decyzja Komisji Europejskiej stwierdzająca odpowiedni stopień
              ochrony danych
            </strong>{" "}
            w ramach programu EU-US Data Privacy Framework (art. 45 RODO).
            Komisja Europejska uznała, że uczestnicy tego programu zapewniają
            ochronę danych odpowiadającą standardowi europejskiemu.
          </Typography>
          <Typography paragraph>
            Informujemy uczciwie o ryzyku, które pozostaje: ważność tej decyzji
            została zaskarżona. Sąd Unii Europejskiej wyrokiem z 3 września 2025
            r. w sprawie T-553/23 oddalił skargę, ale odwołanie do Trybunału
            Sprawiedliwości Unii Europejskiej jest w toku. Decyzja nadal
            obowiązuje. Gdyby przestała obowiązywać, przekazywanie danych zostanie
            wstrzymane.
          </Typography>
        </Section>

        <Section title="9. Jak długo przechowujemy dane">
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>
                Zgłoszenia razem ze zdjęciami rozwiązań, wynikami i informacjami
                zwrotnymi
              </strong>{" "}
              &ndash; przez {RETENTION_SUBMISSIONS} od przesłania. Po tym czasie
              usuwany jest zarówno wpis w bazie, jak i pliki ze zdjęciami.
            </li>
            <li>
              <strong>Zapis szczegółowej analizy wykonanej przez model</strong>{" "}
              (odtwarza treść Twojej pracy słowo w słowo) &ndash; przez{" "}
              {RETENTION_THINKING} od przesłania, czyli znacznie krócej niż samo
              zgłoszenie. Pozostają tylko dane nieosobowe: nazwa modelu, czas i
              koszt analizy.
            </li>
            <li>
              <strong>Konto użytkownika</strong> &ndash; do czasu, aż je
              usuniesz. Jeżeli przez {RETENTION_INACTIVE_ACCOUNT} nie zalogujesz
              się i nie wyślesz żadnego rozwiązania, konto zostanie usunięte
              automatycznie razem ze wszystkim, co do niego należy.
            </li>
            <li>
              <strong>Zapisy dostępu administratora do danych</strong> (patrz
              punkt 7) &ndash; przez {RETENTION_ADMIN_AUDIT} od zdarzenia.
            </li>
            <li>
              <strong>Ciasteczko sesyjne</strong> &ndash; 30 dni.
            </li>
            <li>
              <strong>Dzienniki techniczne serwera</strong> &ndash;
              przechowywane w ograniczonej objętości (do 250 MB na usługę), po
              przekroczeniu której najstarsze wpisy są nadpisywane; przy obecnym
              ruchu odpowiada to kilku miesiącom. Nie zawierają zdjęć ani
              treści rozwiązań, a adresy
              e-mail są w nich skracane tak, by nie identyfikowały osoby
              (np. &bdquo;jan***@***&rdquo;).
            </li>
          </Box>
          <Typography paragraph>
            Usuwanie odbywa się automatycznie, raz na dobę. Jeśli usuniesz konto
            samodzielnie, wszystkie Twoje dane &ndash; konto, zdjęcia i historia
            wyników &ndash; są usuwane niezwłocznie; z kopii zapasowych znikają po
            zakończeniu ich zwykłego cyklu wymiany. Jeden drobny wyjątek opisujemy
            w punkcie 11.
          </Typography>
        </Section>

        <Section title="10. Automatyczna ocena i wykrywanie nadużyć">
          <Typography paragraph>
            Serwis działa automatycznie &ndash; punkty i komentarz generuje
            program, żaden człowiek nie sprawdza wyniku, zanim go zobaczysz.
          </Typography>
          <Typography paragraph>
            <strong>Możesz zakwestionować ocenę.</strong> Jeśli uważasz, że wynik
            jest błędny, napisz na{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</MuiLink> i
            podaj numer zgłoszenia. Pracę obejrzy człowiek i można zlecić ponowną
            analizę.
          </Typography>
          <Typography paragraph>
            <strong>Wykrywanie nieprawidłowości.</strong> Program sprawdza także,
            czy przesłana praca dotyczy wybranego zadania oraz czy nie zawiera
            prób wpłynięcia na ocenę (np. dopisku &bdquo;daj mi 6 punktów&rdquo;
            albo &bdquo;zignoruj kryteria&rdquo;). Jeśli coś takiego wykryje,
            przyznaje 0 punktów i zapisuje przy zgłoszeniu odpowiednie oznaczenie
            widoczne dla administratora.{" "}
            <strong>To wykrywanie bywa zawodne i może się pomylić.</strong> Samo
            oznaczenie nie jest dowodem nieuczciwości, nie pociąga za sobą żadnych
            konsekwencji poza wynikiem 0 punktów w tej jednej próbie i możesz je
            zakwestionować w taki sam sposób jak ocenę.
          </Typography>
          <Typography paragraph>
            <strong>Podgląd postępów.</strong> Twoje wyniki są zestawiane w prosty
            obraz postępów (które zadania zostały opanowane), żeby podpowiadać
            kolejne zadania do ćwiczenia. Widzisz go tylko Ty (oraz administrator,
            w zakresie opisanym w punkcie 7).
          </Typography>
          <Typography paragraph>
            Ponieważ ocena z serwisu nie ma żadnych skutków formalnych (punkt 2),
            nie jest to decyzja wywołująca skutki prawne w rozumieniu art. 22
            RODO.
          </Typography>
        </Section>

        <Section title="11. Twoje prawa">
          <Typography paragraph>
            W związku z przetwarzaniem Twoich danych przysługuje Ci prawo do:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>dostępu do danych</strong> i otrzymania ich kopii (art. 15
              RODO),
            </li>
            <li>
              <strong>sprostowania</strong> danych nieprawidłowych (art. 16
              RODO),
            </li>
            <li>
              <strong>usunięcia danych</strong> (art. 17 RODO),
            </li>
            <li>
              <strong>ograniczenia przetwarzania</strong> (art. 18 RODO),
            </li>
            <li>
              <strong>przenoszenia danych</strong> &ndash; otrzymania ich w
              formacie nadającym się do odczytu maszynowego (art. 20 RODO),
            </li>
            <li>
              <strong>sprzeciwu</strong> wobec przetwarzania opartego na prawnie
              uzasadnionym interesie (art. 21 RODO),
            </li>
            <li>
              <strong>cofnięcia zgody</strong> w dowolnym momencie (art. 7 ust. 3
              RODO) &ndash; cofnięcie nie wpływa na zgodność z prawem
              przetwarzania, którego dokonano wcześniej.
            </li>
          </Box>
          <Typography paragraph>
            <strong>Jak z nich skorzystać:</strong>
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>Usunięcie konta i wszystkich danych</strong> &ndash;
              możesz to zrobić <strong>samodzielnie</strong>, po zalogowaniu, w
              panelu &bdquo;Moje rozwiązania&rdquo;. Usuwane są konto, wszystkie
              przesłane zdjęcia i cała historia wyników. Operacja jest
              nieodwracalna. Jeden wyjątek opisujemy niżej.
            </li>
            <li>
              <strong>Podgląd swoich danych</strong> &ndash; swoje zgłoszenia,
              zdjęcia i wyniki widzisz w panelu &bdquo;Moje rozwiązania&rdquo;.
            </li>
            <li>
              <strong>Pozostałe żądania</strong> &ndash; napisz na{" "}
              <MuiLink href={`mailto:${CONTACT_EMAIL}`}>
                {CONTACT_EMAIL}
              </MuiLink>
              . Odpowiadamy bez zbędnej zwłoki, najpóźniej w ciągu miesiąca.
            </li>
          </Box>
          <Typography paragraph>
            <strong>
              Co zostaje po usunięciu konta &ndash; jedyny wyjątek
            </strong>
            . Po skasowaniu konta zostaje jedna rzecz i chcemy powiedzieć o niej
            wprost: <strong>nieodwracalny skrót</strong> (nie da się z niego
            odtworzyć Twojego identyfikatora ani adresu e-mail) wraz z liczbą
            zgłoszeń wysłanych w ciągu ostatniej doby. Nie ma tam Twojego imienia,
            nazwiska, adresu e-mail, zdjęć ani wyników.
          </Typography>
          <Typography paragraph>
            Po co to jest: limity liczby zgłoszeń są liczone na podstawie
            wysłanych rozwiązań, więc bez tego zapisu usunięcie konta i zalogowanie
            się od nowa byłoby prostym sposobem na wyzerowanie dziennego limitu i
            zablokowanie serwisu innym. Zapis <strong>znika automatycznie</strong>{" "}
            najpóźniej 24 godziny po Twoim ostatnim zgłoszeniu, czyli razem
            z wygaśnięciem samego limitu. Jeśli w ciągu doby przed usunięciem konta
            nie wysłałeś żadnego rozwiązania, nie powstaje w ogóle. Podstawą jest
            prawnie uzasadniony interes administratora (art. 6 ust. 1 lit. f RODO),
            opisany w punkcie 6.
          </Typography>
          <Typography paragraph>
            <strong>Prawo do skargi.</strong> Jeżeli uważasz, że Twoje dane są
            przetwarzane niezgodnie z prawem, możesz wnieść skargę do organu
            nadzorczego: <strong>Prezes Urzędu Ochrony Danych Osobowych</strong>,
            ul. Stawki 2, 00-193 Warszawa. Skargę może wnieść także Twój rodzic
            lub opiekun.
          </Typography>
        </Section>

        <Section title="12. Bezpieczeństwo danych">
          <Typography paragraph>
            Połączenie z serwisem jest szyfrowane (HTTPS). Zdjęcia są dostępne
            wyłącznie po zalogowaniu i tylko dla właściciela konta oraz
            administratora. Baza danych nie jest dostępna z internetu. Serwis nie
            przechowuje haseł.
          </Typography>
          <Typography paragraph>
            Żadne zabezpieczenia nie dają stuprocentowej pewności. Gdyby doszło do
            naruszenia ochrony danych mogącego powodować wysokie ryzyko dla Twoich
            praw, zostaniesz o tym poinformowany, a sprawa zostanie zgłoszona
            Prezesowi Urzędu Ochrony Danych Osobowych zgodnie z art. 33 i 34 RODO.
          </Typography>
        </Section>

        <Section title="13. Zasady korzystania z serwisu">
          <Typography paragraph>Korzystając z serwisu, zobowiązujesz się:</Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              przesyłać wyłącznie zdjęcia własnych rozwiązań zadań
              matematycznych,
            </li>
            <li>
              nie przesyłać zdjęć przedstawiających inne osoby, ich dane lub ich
              prace bez ich wiedzy i zgody,
            </li>
            <li>
              nie przesyłać treści obraźliwych, wulgarnych ani naruszających
              prawa innych osób,
            </li>
            <li>
              nie umieszczać na kartce poleceń kierowanych do systemu w celu
              wpłynięcia na ocenę,
            </li>
            <li>
              nie podejmować prób obchodzenia zabezpieczeń, limitów ani uzyskania
              dostępu do danych innych użytkowników,
            </li>
            <li>nie udostępniać swojego konta innym osobom.</li>
          </Box>
          <Typography paragraph>
            <strong>Limity.</strong> Każde sprawdzenie rozwiązania kosztuje, więc
            obowiązują limity chroniące dostępność serwisu: maksymalnie 30
            zgłoszeń na użytkownika w ciągu doby oraz limit łączny dla wszystkich
            użytkowników. Po wyczerpaniu limitu serwis informuje, kiedy będzie
            można wysłać kolejne rozwiązanie. Jednorazowo można wysłać do 10
            zdjęć, każde o rozmiarze do 10 MB (formaty JPEG, PNG, WebP, HEIC).
          </Typography>
          <Typography paragraph>
            Administrator może ograniczyć lub zablokować dostęp użytkownikowi,
            który narusza regulamin.
          </Typography>
        </Section>

        <Section title="14. Ograniczenie odpowiedzialności">
          <Typography paragraph>
            Serwis jest udostępniany bezpłatnie, &bdquo;tak jak jest&rdquo; (ang.
            &bdquo;as is&rdquo;), bez gwarancji nieprzerwanego działania i bez
            gwarancji poprawności ocen. Przerwy mogą wynikać z prac technicznych,
            awarii, wyczerpania limitów lub niedostępności usług Google.
          </Typography>
          <Typography paragraph>
            Administrator nie ponosi odpowiedzialności za skutki polegania na
            błędnej ocenie wygenerowanej przez sztuczną inteligencję ani za
            przerwy w działaniu serwisu. Nie ogranicza to odpowiedzialności w
            zakresie, w jakim nie może ona zostać wyłączona zgodnie z
            obowiązującymi przepisami, w szczególności odpowiedzialności za
            przetwarzanie danych osobowych.
          </Typography>
          <Typography paragraph>
            Zalecamy zachowanie własnych kopii ważnych rozwiązań &ndash; serwis
            nie jest archiwum i usuwa dane po upływie okresów z punktu 9.
          </Typography>
        </Section>

        <Section title="15. Prawa autorskie i licencja">
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
            . Oznacza to, że każdy &ndash; w tym szkoła &ndash; może uruchomić
            własną instancję tego narzędzia.
          </Typography>
          <Typography paragraph>
            Treści zadań, rozwiązań i materiałów Olimpiady Matematycznej Juniorów
            są utworami chronionymi prawem autorskim. Organizatorem olimpiady jest
            Stowarzyszenie na rzecz Edukacji Matematycznej, a oryginalne materiały
            są dostępne na{" "}
            <MuiLink href="https://omj.edu.pl" target="_blank" rel="noopener">
              omj.edu.pl
            </MuiLink>
            . Serwis udostępnia je wyłącznie w celach edukacyjnych i
            niekomercyjnych. Jeżeli podmiot uprawniony uzna, że sposób
            udostępniania narusza jego prawa, prosimy o kontakt pod adresem{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</MuiLink>{" "}
            &ndash; materiały zostaną niezwłocznie usunięte lub zastąpione
            odnośnikami.
          </Typography>
          <Typography paragraph>
            Zachowujesz wszelkie prawa do przesłanych przez siebie rozwiązań.
            Wykorzystujemy je wyłącznie po to, żeby wygenerować dla Ciebie ocenę i
            pokazać Ci historię prób. Nie publikujemy ich, nie udostępniamy innym
            użytkownikom i nie wykorzystujemy do trenowania modeli.
          </Typography>
        </Section>

        <Section title="16. Zmiany regulaminu i zakończenie działania serwisu">
          <Typography paragraph>
            Administrator może zmienić regulamin. O istotnych zmianach
            użytkownicy zostaną poinformowani komunikatem w serwisie. Dalsze
            korzystanie po wprowadzeniu zmian oznacza ich akceptację.
          </Typography>
          <Typography paragraph>
            <strong>Zakończenie działania serwisu.</strong> Serwis jest projektem
            niekomercyjnym prowadzonym przez jedną osobę i może zostać wygaszony.
            Gdyby do tego doszło, użytkownicy zostaną poinformowani z
            wyprzedzeniem i będą mieli czas na pobranie swoich wyników, a wszystkie
            dane zostaną trwale usunięte.{" "}
            <strong>
              Dane z tego serwisu nie zostaną przekazane żadnemu innemu podmiotowi
            </strong>{" "}
            &ndash; także wtedy, gdyby narzędzie było dalej prowadzone przez
            szkołę lub inną instytucję. Taka instytucja uruchamia własną,
            niezależną instancję na podstawie otwartej licencji kodu i zaczyna od
            pustej bazy danych.
          </Typography>
        </Section>

        <Section title="17. Kontakt" isLast>
          <Typography paragraph>
            We wszystkich sprawach &ndash; w tym dotyczących ochrony danych
            osobowych, błędnych ocen, żądań usunięcia danych oraz zgłoszeń od
            rodziców i opiekunów &ndash; prosimy o kontakt pod adresem:{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</MuiLink>
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
          Ostatnia aktualizacja: {LAST_UPDATED}
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
