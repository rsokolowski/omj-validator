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
const RETENTION_PRIVATE_TASKS = "24 miesiące";
const RETENTION_PATTERNS = "24 miesiące";
const RETENTION_AI_USAGE = "90 dni";
const RETENTION_ADMIN_AUDIT = "12 miesięcy";

// Zmieniajac tekst, zmien tez TERMS_VERSION w app/config.py (data zapisywana
// przy kazdej zgodzie) - obie wartosci opisuja te sama wersje dokumentu.
const LAST_UPDATED = "12 października 2026";
// Konto czekajace na zgode rodzica - app/accounts/service.py PENDING_TTL
const PENDING_DAYS = 14;

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
            <strong>Twoje zdjęcie kartki albo wpisany tekst rozwiązania (i rysunek) są wysyłane do firmy Google albo Anthropic</strong>,
            żeby program mógł je przeczytać i ocenić. Serwis używa w danej
            chwili tylko jednej z tych firm, więc rozwiązanie nie trafia do obu
            naraz. Nie wysyłamy tam Twojego imienia, nazwiska ani adresu e-mail.
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
              (model językowy Google Gemini lub Anthropic Claude) i mogą być
              błędne.
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
            maja 2018 r. o ochronie danych osobowych). Dlatego przy zakładaniu
            konta pytamy o <strong>rok urodzenia</strong> (sam rok, bez dnia i
            miesiąca). Jeśli kończysz 16 lat w tym roku, pytamy jeszcze, czy masz
            je już ukończone.
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>
                Jeśli masz mniej niż 16 lat, podajesz adres e-mail rodzica lub
                opiekuna prawnego, a my wysyłamy mu prośbę o zgodę.
              </strong>{" "}
              To rodzic decyduje, czy możesz korzystać z serwisu.
            </li>
            <li>
              Dopóki rodzic nie potwierdzi zgody, możesz się zalogować i
              przeglądać zadania, ale <strong>nie możesz przesyłać rozwiązań</strong>{" "}
              ani niczego zapisywać.
            </li>
            <li>
              Jeśli rodzic nie potwierdzi konta w ciągu {PENDING_DAYS} dni,
              usuwamy je razem ze wszystkimi danymi. Jeśli kliknie &bdquo;Nie
              zgadzam się&rdquo;, usuwamy je od razu.
            </li>
            <li>
              Konto z loginem i hasłem (dla osób bez adresu e-mail, punkt 4)
              zawsze wymaga zgody rodzica &ndash; niezależnie od wieku, bo adres
              rodzica jest jedynym sposobem odzyskania dostępu.
            </li>
            <li>
              Jeśli Twoje konto powstało, zanim wprowadziliśmy te zasady, przy
              najbliższej wizycie zapytamy o rok urodzenia. Gdy masz mniej niż 16
              lat, Twoje konto też poczeka na zgodę rodzica (dotychczasowe dane
              zostają, obowiązuje ta sama zasada {PENDING_DAYS} dni).
            </li>
          </Box>
          <Typography paragraph>
            <strong>Co dostaje rodzic.</strong> Wiadomość e-mail z informacją,
            kim jesteśmy, którego konta dotyczy prośba (adres konta Google
            dziecka albo login), jakie dane przetwarzamy i jak długo, oraz dwa
            przyciski: &bdquo;Wyrażam zgodę&rdquo; i &bdquo;Nie zgadzam się
            &ndash; usuń konto&rdquo;. Przyciski otwierają stronę, na której
            rodzic potwierdza wybór. Każda nasza wiadomość do rodzica zawiera też
            link do <strong>strony rodzica</strong>.
          </Typography>
          <Typography paragraph>
            <strong>Strona rodzica</strong> (
            <MuiLink href="/rodzic">
              omj-validator.pl/rodzic
            </MuiLink>
            ) pokazuje konta dzieci powiązane z adresem rodzica. Rodzic może tam
            w każdej chwili <strong>usunąć konto dziecka razem ze wszystkimi
            danymi</strong> &ndash; to jest zarazem cofnięcie zgody &ndash; a przy
            koncie z loginem ustawić nowe hasło. Link działa 30 dni; nowy
            wyślemy po wpisaniu adresu na tej stronie. Rodzic może też w każdej
            chwili napisać na adres{" "}
            <MuiLink href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</MuiLink>.
          </Typography>
          <Typography paragraph>
            <strong>Jak sprawdzamy, że to rodzic.</strong> Zgodę potwierdza
            kliknięcie w link wysłany na podany adres. Przy serwisie o niskim
            ryzyku to rozsądny, proporcjonalny sposób weryfikacji (wytyczne
            Europejskiej Rady Ochrony Danych 05/2020 w sprawie zgody), ale nie
            daje pewności, że adres naprawdę należy do rodzica. Prosimy: podaj
            prawdziwy adres rodzica lub opiekuna.
          </Typography>
          <Typography paragraph>
            <strong>Informacja dla rodziców i opiekunów.</strong> Zachęcamy do
            przeczytania punktów 5&ndash;9 tego dokumentu. Opisują one dokładnie,
            jakie dane dziecka są zbierane, komu są przekazywane (w tym poza Unię
            Europejską) i jak długo są przechowywane. Serwis nie wykorzystuje
            danych do reklam, nie profiluje dzieci w celach marketingowych i nie
            udostępnia danych komukolwiek poza dostawcami wymienionymi w punkcie
            7.
          </Typography>
          <Typography paragraph>
            <strong>Zgodność z przepisami.</strong> Serwis działa zgodnie
            z obowiązującymi przepisami o ochronie dzieci i o ochronie danych
            osobowych, w tym z RODO, które szczególnie chroni dane dzieci,
            i z polską ustawą o ochronie danych osobowych. Oceny i wskazówki
            przygotowuje program komputerowy (sztuczna inteligencja), a nie
            człowiek &ndash; więcej o tym w punkcie 10.
          </Typography>
        </Section>

        <Section title="4. Konto i logowanie">
          <Typography paragraph>
            Konto możesz założyć na dwa sposoby:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>przez konto Google</strong> (OAuth 2.0) &ndash; serwis{" "}
              <strong>nie zna Twojego hasła do Google</strong>, uwierzytelnienie
              odbywa się po stronie Google;
            </li>
            <li>
              <strong>loginem i hasłem</strong> &ndash; dla osób, które nie mają
              adresu e-mail. Nie pytamy wtedy o Twój adres e-mail. Zapisujemy
              login, rok urodzenia, adres e-mail rodzica i{" "}
              <strong>skrót hasła</strong> (argon2id) &ndash; samego hasła nie
              znamy i nie da się go z tego skrótu odczytać. Nie używaj imienia i
              nazwiska jako loginu. Jeśli zapomnisz hasła, link do ustawienia
              nowego wyślemy <strong>rodzicowi</strong>.
            </li>
          </Box>
          <Typography paragraph>
            Konto jest potrzebne po to, żebyś widział wyłącznie swoje prace i
            swoją historię wyników oraz żeby działały limity chroniące serwis
            przed nadużyciami. Bez konta serwis nie może działać.
          </Typography>
          <Typography paragraph>
            Nie udostępniaj swojego konta innym osobom. Po zalogowaniu przez
            Google sesja trwa do 30 dni. Po zalogowaniu loginem i hasłem trwa 12
            godzin, a do 30 dni tylko wtedy, gdy zaznaczysz &bdquo;Zapamiętaj mnie
            na tym urządzeniu&rdquo;. Na komputerze, z którego korzysta więcej
            osób (szkoła, biblioteka, komputer rodzinny), nie zaznaczaj tej opcji
            i wyloguj się po zakończeniu pracy. Zmiana hasła wylogowuje konto na
            wszystkich urządzeniach.
          </Typography>
          <Typography paragraph>
            Po 5 nieudanych próbach logowania na ten sam login z jednego
            urządzenia lub sieci logowanie jest tam wstrzymywane na 15 minut
            (chroni to przed odgadywaniem haseł). Urządzenie, na którym już się
            zalogowałeś, zapamiętujemy w osobnym ciasteczku, więc czyjeś próby
            zgadywania Twojego hasła z innego miejsca nie zablokują Ci
            logowania na Twoim urządzeniu.
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
            <strong>Konto z loginem i hasłem</strong> (zamiast danych z Google):
            login i skrót hasła (argon2id).
          </Typography>
          <Typography paragraph>
            <strong>Wiek i zgoda</strong> (każde konto):
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>rok urodzenia (bez dnia i miesiąca),</li>
            <li>
              adres e-mail rodzica lub opiekuna &ndash; przy koncie osoby poniżej
              16 lat i przy każdym koncie z loginem,
            </li>
            <li>
              zapis zgody: czyja to zgoda (Twoja albo rodzica), kiedy ją wyrażono
              i której wersji regulaminu dotyczyła &ndash; bez adresu IP i bez
              informacji o urządzeniu,
            </li>
            <li>
              linki, które wysłaliśmy rodzicowi: zapisujemy tylko ich skrót
              kryptograficzny (sam link jest wyłącznie w wiadomości), cel oraz
              kiedy został wysłany, wykorzystany i kiedy wygasa &ndash; to także
              podstawa limitów wysyłki,
            </li>
            <li>
              nieudane próby logowania loginem i hasłem: wpisany login, czas i
              skrót kryptograficzny adresu IP albo identyfikatora urządzenia (nie
              sam adres).
            </li>
          </Box>
          <Typography paragraph>
            <strong>Dane związane z rozwiązywaniem zadań:</strong>
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              przesłane przez Ciebie zdjęcia rozwiązań i rysunki wykonane w
              przeglądarce oraz wpisany przez Ciebie tekst rozwiązania,
            </li>
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
            <strong>Własne zadania (&bdquo;Moje zadania&rdquo;)</strong>, jeśli z
            nich korzystasz:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              treść zadania, którą wpisałeś albo która została odczytana ze
              zdjęcia i przez Ciebie zatwierdzona, wraz z tytułem, źródłem,
              kategorią i trudnością,
            </li>
            <li>zdjęcie strony z zadaniem, jeśli dodałeś zadanie ze zdjęcia,</li>
            <li>
              wygenerowane wskazówki i informacja, ile z nich odkryłeś przed
              wysłaniem rozwiązania,
            </li>
            <li>
              techniczny zapis wywołań modelu przy dodawaniu zadań (rodzaj i czas
              wywołania, liczba tokenów, koszt &ndash; bez treści), potrzebny do
              limitu dziennego.
            </li>
          </Box>
          <Typography paragraph>
            Własne zadania widzisz tylko Ty. Nie są publikowane, udostępniane
            innym użytkownikom ani indeksowane przez wyszukiwarki.
          </Typography>
          <Typography paragraph>
            <strong>Wzorce</strong> (zapisane pomysły na rozwiązywanie zadań), jeśli z nich korzystasz:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              treść wzorca, którą napisałeś albo wybrałeś z propozycji programu
              (&bdquo;kiedy w treści widzę&hellip;, to warto spróbować&hellip;&rdquo;),
              wraz z przykładem i kategorią,
            </li>
            <li>
              przebieg dopracowywania wzorca z programem: Twoje szkice i odpowiedzi
              oraz zaproponowane wersje i pytania,
            </li>
            <li>
              zadania powiązane ze wzorcem (zadania OMJ albo Twoje własne),
            </li>
            <li>
              historia powtórek: termin, Twoja samoocena albo wynik oceny
              rozwiązania oraz tekst, który wpisałeś z pamięci.
            </li>
          </Box>
          <Typography paragraph>
            Wzorce widzisz tylko Ty. Nie są publikowane ani udostępniane innym
            użytkownikom.
          </Typography>
          <Typography paragraph>
            <strong>Dane techniczne:</strong> ciasteczko sesyjne (ważne do 30 dni,
            podpisane kryptograficznie; patrz punkt 4), przy logowaniu loginem i
            hasłem także ciasteczko urządzenia (rok; zawiera losowy identyfikator
            urządzenia i podpisane skróty kryptograficzne loginów, które się na
            nim zalogowały &ndash; nie identyfikuje osoby, służy tylko temu, by
            cudze próby zgadywania hasła nie blokowały logowania na Twoim
            urządzeniu; po zmianie hasła przestaje działać dla tego loginu)
            oraz dzienniki serwera zawierające m.in.
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
            przesyłanych zdjęciach ani we wpisywanym tekście rozwiązania.
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
              opiekuna prawnego (art. 8 RODO). Mając co najmniej 16 lat, wyrażasz
              zgodę, zaznaczając ją przy zakładaniu konta. Za osobę młodszą
              &ndash; i przy każdym koncie z loginem &ndash; zgodę wyraża rodzic,
              klikając &bdquo;Wyrażam zgodę&rdquo; na stronie otwartej z
              wiadomości e-mail. Zgodę można w każdej chwili cofnąć &ndash;
              najprościej usuwając konto (rodzic może to zrobić na stronie
              rodzica).
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
              danych (punkt 7), krótkotrwały, pseudonimowy zapis
              wykorzystanego limitu po usunięciu konta (punkt 11), zapis
              nieudanych prób logowania oraz zapis wysłanych wiadomości
              potrzebny do limitów wysyłki. Te operacje
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
            <strong>Dostawca analizy rozwiązania (AI).</strong> Twoje zdjęcia i
            wpisany tekst rozwiązania razem z treścią zadania i rozwiązaniem
            wzorcowym są przesyłane do usługi sztucznej inteligencji, która
            wykonuje ocenę. Serwis może korzystać z jednej z dwóch firm:{" "}
            <strong>Google</strong> (Gemini) albo <strong>Anthropic</strong>{" "}
            (Claude).{" "}
            <strong>W danej chwili używa tylko jednej z nich</strong> &ndash;
            wybiera ją administrator. Twoje rozwiązanie jest wysyłane tylko do
            tej jednej, nie do obu naraz. Zasady wspólne dla obu firm:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>
                nie przekazujemy tam Twojego imienia, nazwiska, adresu e-mail ani
                identyfikatora konta
              </strong>{" "}
              &ndash; wysyłane jest samo zdjęcie pracy lub wpisany tekst
              rozwiązania i treść zadania, a nazwy plików są losowe,
            </li>
            <li>
              przy pracy ze <strong>wzorcami</strong> trafia tam tylko tekst:
              szkic wzorca, Twoje odpowiedzi, treść zadania, przy którym go
              zauważyłeś, i informacja zwrotna z oceny &ndash; bez zdjęć i bez
              danych konta,
            </li>
            <li>
              przy <strong>własnych zadaniach</strong> trafia tam też zdjęcie
              strony z zadaniem (żeby odczytać jego treść) i sama treść zadania
              (żeby przygotować wskazówki i ocenić rozwiązanie).
            </li>
          </Box>
          <Typography paragraph>
            <strong>Google (Gemini API)</strong> &ndash; gdy serwis używa
            Google:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              pliki, także zdjęcia stron z własnymi zadaniami, są{" "}
              <strong>usuwane</strong> z infrastruktury Google zaraz po
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
            <strong>Anthropic (Claude API)</strong> &ndash; gdy serwis używa
            Anthropic:
          </Typography>
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              zdjęcia są wysyłane razem z prośbą o ocenę, a{" "}
              <strong>nie jako osobne pliki</strong> zapisywane u Anthropic,
            </li>
            <li>
              Anthropic <strong>usuwa</strong> przesłane treści i odpowiedzi w
              ciągu 30 dni. Dłużej może je zatrzymać tylko wtedy, gdy sprawdza
              naruszenie zasad korzystania z usługi albo gdy wymaga tego prawo,
            </li>
            <li>
              Anthropic zgodnie z umową{" "}
              <strong>nie może wykorzystywać</strong> przesyłanych treści do
              trenowania swoich modeli.
            </li>
          </Box>
          <Typography paragraph>
            <strong>Google &ndash; pozostałe usługi.</strong> Logowanie kontem
            Google odbywa się przez usługę Google. Komunikaty o postępie analizy mogą być
            tłumaczone z angielskiego na polski przez usługę Google Cloud
            Translation &ndash; niezależnie od tego, która firma ocenia
            rozwiązanie.
          </Typography>
          <Typography paragraph>
            <strong>Dostawca poczty e-mail.</strong> Wiadomości do rodziców
            (prośba o zgodę, potwierdzenie aktywacji konta, link do strony
            rodzica, zmiana hasła) wysyłamy przez firmę <strong>Resend</strong>,
            która robi to w naszym imieniu na podstawie umowy powierzenia
            przetwarzania danych. Resend otrzymuje adres e-mail rodzica i treść
            wiadomości &ndash; a w niej adres konta Google dziecka albo jego
            login. Żadnych innych danych dziecka (zdjęć, rozwiązań, wyników) tam
            nie przekazujemy. Wiadomości są wysyłane z centrum danych w Unii
            Europejskiej (Irlandia).
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
            Korzystanie z usług Google albo Anthropic oznacza{" "}
            <strong>
              przekazanie zdjęcia Twojej pracy do Stanów Zjednoczonych
            </strong>
            . Podstawa prawna tego przekazania jest u każdej z tych firm inna.
          </Typography>
          <Typography paragraph>
            <strong>Google.</strong> Podstawą przekazania jest{" "}
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
            obowiązuje. Gdyby przestała obowiązywać, przekazywanie danych do
            Google zostanie wstrzymane.
          </Typography>
          <Typography paragraph>
            <strong>Resend.</strong> Wiadomości e-mail wychodzą z centrum danych
            w Unii Europejskiej, ale Resend jest firmą amerykańską, więc adres
            e-mail rodzica i treść wiadomości mogą być dostępne z USA. Resend jest
            uczestnikiem programu EU-US Data Privacy Framework &ndash; podstawą
            jest ta sama decyzja Komisji Europejskiej co w przypadku Google (art.
            45 RODO), z tym samym zastrzeżeniem co do toczącego się postępowania.
          </Typography>
          <Typography paragraph>
            <strong>Anthropic.</strong> Podstawą przekazania są{" "}
            <strong>standardowe klauzule umowne</strong> przyjęte przez Komisję
            Europejską (art. 46 ust. 2 lit. c RODO). Są one częścią umowy o
            przetwarzaniu danych zawartej z Anthropic Ireland, Limited. To
            gotowe zapisy przygotowane przez Komisję Europejską, w których
            odbiorca danych spoza Unii zobowiązuje się je chronić.
          </Typography>
        </Section>

        <Section title="9. Jak długo przechowujemy dane">
          <Box component="ul" sx={{ pl: 3, mb: 2 }}>
            <li>
              <strong>
                Zgłoszenia razem ze zdjęciami i rysunkami, wpisanym tekstem
                rozwiązania, wynikami i informacjami zwrotnymi
              </strong>{" "}
              &ndash; przez {RETENTION_SUBMISSIONS} od przesłania. Po tym czasie
              usuwany jest zarówno wpis w bazie (razem z wpisanym tekstem), jak
              i pliki ze zdjęciami.
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
              <strong>Własne zadania</strong> razem ze zdjęciami, wskazówkami i
              rozwiązaniami &ndash; przez {RETENTION_PRIVATE_TASKS} od ostatniej
              aktywności przy zadaniu (dodanie, edycja albo wysłanie
              rozwiązania). Możesz je też usunąć w każdej chwili. Zdjęcia
              przesłane do odczytania, ale niezapisane jako zadanie, są usuwane
              po 24 godzinach.
            </li>
            <li>
              <strong>Wzorce</strong> razem z historią dopracowania i powtórek
              &ndash; przez {RETENTION_PATTERNS} od ostatniej aktywności przy
              wzorcu (edycja, powtórka albo ocenione rozwiązanie). Możesz je też
              usunąć w każdej chwili.
            </li>
            <li>
              <strong>Techniczny zapis wywołań modelu przy dodawaniu zadań</strong>{" "}
              &ndash; przez {RETENTION_AI_USAGE}.
            </li>
            <li>
              <strong>Zapisy dostępu administratora do danych</strong> (patrz
              punkt 7) &ndash; przez {RETENTION_ADMIN_AUDIT} od zdarzenia.
            </li>
            <li>
              <strong>Konto czekające na zgodę rodzica</strong> &ndash;{" "}
              {PENDING_DAYS} dni od założenia (przy koncie założonym wcześniej:
              od podania adresu rodzica). Bez zgody jest usuwane razem ze
              wszystkimi danymi, a po kliknięciu &bdquo;Nie zgadzam się&rdquo;
              &ndash; od razu.
            </li>
            <li>
              <strong>Rok urodzenia, login, skrót hasła i zapis zgody</strong>{" "}
              &ndash; razem z kontem.
            </li>
            <li>
              <strong>Adres e-mail rodzica</strong> &ndash; dopóki jest z nim
              powiązane choć jedno konto dziecka. Po usunięciu ostatniego konta
              albo zastąpieniu adresu innym (np. po poprawieniu literówki) jest
              usuwany najpóźniej po dobie od ostatniej wiadomości &ndash; tyle
              liczą się limity wysyłki, które chronią skrzynkę rodzica przed
              zasypaniem wiadomościami.
            </li>
            <li>
              <strong>Linki wysłane rodzicowi</strong> (ich skróty) &ndash; 30
              dni od wygaśnięcia; po usunięciu konta przestają wskazywać na
              dziecko. Link do zgody jest ważny 14 dni, do zmiany
              hasła godzinę, do strony rodzica 30 dni.
            </li>
            <li>
              <strong>Nieudane próby logowania</strong> &ndash; 24 godziny.
            </li>
            <li>
              <strong>Ciasteczko sesyjne</strong> &ndash; do 30 dni (12 godzin
              przy logowaniu loginem i hasłem bez &bdquo;Zapamiętaj mnie&rdquo;);
              ciasteczko urządzenia &ndash; rok.
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
              <strong>Rodzic lub opiekun</strong> może usunąć konto dziecka
              samodzielnie na{" "}
              <MuiLink href="/rodzic">
                stronie rodzica
              </MuiLink>{" "}
              &ndash; link jest w każdej wiadomości od nas, a nowy wyślemy po
              wpisaniu adresu na tej stronie. Usunięcie konta jest zarazem
              cofnięciem zgody.
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
            administratora. Baza danych nie jest dostępna z internetu. Hasła do
            kont Google w ogóle do nas nie trafiają, a hasła do kont z loginem
            przechowujemy wyłącznie jako skrót argon2id &ndash; samego hasła nie
            znamy. Logowanie jest chronione limitem nieudanych prób, a linki
            wysyłane rodzicom są jednorazowe albo krótko ważne i zapisujemy tylko
            ich skróty.
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
              jako &bdquo;własne zadania&rdquo; dodawać tylko treści zadań
              matematycznych, z których korzystasz do własnej nauki, i nie
              rozpowszechniać ich dalej,
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
            awarii, wyczerpania limitów lub niedostępności usług Google albo
            Anthropic.
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
