# Ocena skutków dla ochrony danych (DPIA)

## Trener OMJ — narzędzie do samodzielnego ćwiczenia zadań Olimpiady Matematycznej Juniorów z automatyczną informacją zwrotną generowaną przez AI

**Status dokumentu:** PROJEKT do weryfikacji przez inspektora ochrony danych i radcę prawnego.
Dokument przygotował autor oprogramowania na podstawie analizy kodu źródłowego, a nie prawnik.
Nie stanowi porady prawnej.

| Pole | Wartość |
|---|---|
| Wersja | 1.0 (projekt) |
| Data sporządzenia | [UZUPEŁNIĆ: data] |
| Autor projektu dokumentu | Rafał Sokołowski (autor oprogramowania) |
| Administrator danych — wariant A | Rafał Sokołowski, osoba fizyczna prowadząca niekomercyjny serwis omj-validator.pl |
| Administrator danych — wariant B | [UZUPEŁNIĆ: pełna nazwa szkoły], reprezentowana przez Dyrektora |
| Inspektor ochrony danych (wariant B) | [UZUPEŁNIĆ: imię, nazwisko, e-mail, telefon] |
| Opiniował IOD | [UZUPEŁNIĆ: data i podpis] |
| Zatwierdził administrator | [UZUPEŁNIĆ: data i podpis] |
| Data następnego przeglądu | [UZUPEŁNIĆ — nie rzadziej niż co 12 miesięcy oraz przy każdej istotnej zmianie] |
| Wersja oprogramowania objęta oceną | [UZUPEŁNIĆ: commit / tag repozytorium] |

---

## 0. Dwa warianty wdrożenia objęte tą oceną

Dokument opisuje jedno oprogramowanie w dwóch scenariuszach, ponieważ zmienia się w nich
administrator i podstawa prawna, a nie same operacje techniczne.

- **Wariant A — serwis publiczny `omj-validator.pl`.** Administratorem jest osoba fizyczna
  (autor). Użytkownikiem jest dowolne dziecko, które zaloguje się kontem Google. Serwis nie ma
  związku ze szkołą ucznia.
- **Wariant B — instancja szkolna.** Kod jest udostępniony na licencji MIT, więc szkoła uruchamia
  **własną, niezależną instancję** na własnej infrastrukturze, z własnym kluczem Google.
  Administratorem danych jest szkoła. Nie następuje przekazanie serwisu ani powierzenie danych
  między wariantem A a B — to dwa oddzielne zbiory danych. Po przejęciu ruchu przez szkołę autor
  wygasza serwis publiczny i usuwa dane zgodnie z sekcją 3.7.

Sekcje 1–9 dotyczą obu wariantów; różnice są zaznaczone wprost.

---

## 1. Czy DPIA jest obowiązkowa

Tak. Ocena skutków jest wymagana na podstawie art. 35 ust. 1 i ust. 4 RODO.

**Przesłanki z komunikatu Prezesa UODO** — wykaz rodzajów operacji przetwarzania wymagających
oceny skutków dla ochrony danych (M.P. 2019 poz. 666, komunikat z 17.06.2019). Występują
jednocześnie dwa kryteria z wykazu:

1. **Dane osób, których ochrona wymaga szczególnej uwagi — dane dzieci.** Grupą docelową
   narzędzia są uczniowie klas VII–VIII szkoły podstawowej, typowo w wieku 10–15 lat.
2. **Innowacyjne wykorzystanie lub zastosowanie nowych rozwiązań technologicznych.** Ocena pracy
   ucznia i wygenerowanie informacji zwrotnej odbywa się przez duży model językowy
   (Google Gemini), któremu przekazywane są fotografie odręcznej pracy dziecka.

Do tego dochodzą przesłanki uzupełniające, które same nie przesądzają obowiązku, ale podnoszą
poziom ryzyka: przekazanie danych do państwa trzeciego (USA), przetwarzanie na dużą skalę
w stosunku do liczebności grupy docelowej oraz automatyczna klasyfikacja zachowania użytkownika
(wykrywanie prób manipulacji oceną).

Wytyczne WP248 Grupy Roboczej Art. 29 (zatwierdzone przez EROD) wskazują 9 kryteriów; spełnione
są tu co najmniej cztery: ocena/scoring, dane wrażliwych kategorii osób (dzieci), innowacyjne
technologie, dane przetwarzane na dużą skalę. Zgodnie z WP248 spełnienie dwóch kryteriów
uzasadnia przeprowadzenie DPIA.

**Wniosek:** DPIA jest obowiązkowa w obu wariantach. Powinna być przeprowadzona **przed**
rozpoczęciem przetwarzania (art. 35 ust. 1) — w wariancie B przed uruchomieniem instancji
szkolnej; w wariancie A jest sporządzana z opóźnieniem, co samo w sobie stanowi uchybienie
i jest odnotowane w ryzyku R16.

---

## 2. Systematyczny opis planowanych operacji przetwarzania (art. 35 ust. 7 lit. a)

### 2.1 Do czego służy narzędzie

Uczeń wybiera archiwalne zadanie olimpijskie, rozwiązuje je odręcznie na kartce, fotografuje
kartkę telefonem i przesyła zdjęcia przez przeglądarkę. System przesyła te zdjęcia razem z PDF-em
zawierającym treści zadań i PDF-em z rozwiązaniami wzorcowymi do modelu Google Gemini wraz
z instrukcją odtwarzającą oficjalne kryteria punktacji OMJ. Model zwraca:

- liczbę punktów (0/1/3 dla etapu I, 0/2/5/6 dla etapów II i III),
- kilkuzdaniową informację zwrotną po polsku (4–7 zdań), która ma wskazać mocne strony i luki
  w rozumowaniu, ale — zgodnie z instrukcją systemową — **nie podawać rozwiązania**,
- klasyfikację nieprawidłowości: `none` / `wrong_task` (rozwiązanie innego zadania) /
  `injection` (próba manipulacji oceną) wraz z liczbą 0–100 wyrażającą pewność klasyfikacji.

Wynik jest zapisywany, a uczeń widzi go w historii swoich prób i na grafie postępów.

### 2.2 Kategorie osób, których dane dotyczą

| Kategoria | Liczebność (szacunek) | Uwagi |
|---|---|---|
| Uczniowie korzystający z narzędzia (dzieci 10–15 lat) | wariant A: [UZUPEŁNIĆ]; wariant B: [UZUPEŁNIĆ: liczba uczniów] | grupa główna, wymaga szczególnej ochrony (motyw 38 RODO) |
| Osoby przypadkowo utrwalone na fotografii kartki | nieznana, niezamierzona | np. druga osoba w kadrze, cudze notatki |
| Nauczyciele / administratorzy narzędzia | wariant A: 1–2; wariant B: [UZUPEŁNIĆ] | konta z podwyższonymi uprawnieniami |

### 2.3 Kategorie danych — stan faktyczny odczytany z kodu

**Tabela `users`** (`app/db/models.py`):

| Pole | Treść | Źródło |
|---|---|---|
| `google_sub` | trwały identyfikator konta Google, klucz główny | token OAuth (claim `sub`) |
| `email` | adres e-mail konta Google | token OAuth |
| `name` | imię i nazwisko lub nazwa wyświetlana | token OAuth |
| `created_at`, `updated_at` | znaczniki czasu | system |

**Tabela `submissions`** (jedno zgłoszenie = jedna próba rozwiązania):

| Pole | Treść |
|---|---|
| `id` | 8-znakowy identyfikator zgłoszenia |
| `user_id` | powiązanie z użytkownikiem (`google_sub`) |
| `year`, `etap`, `task_number` | które zadanie |
| `timestamp`, `created_at` | kiedy |
| `status` | pending / processing / completed / failed |
| `images` | lista ścieżek do plików ze zdjęciami |
| `score` | liczba punktów przyznana przez model |
| `feedback` | pełna treść informacji zwrotnej po polsku |
| `error_message` | treść błędu, jeśli analiza się nie powiodła |
| `issue_type` | `none` / `wrong_task` / `injection` — automatyczna klasyfikacja |
| `abuse_score` | 0–100, pewność powyższej klasyfikacji |
| `scoring_meta` | metadane wywołania modelu: nazwa modelu, liczba tokenów, szacowany koszt, czas, surowa odpowiedź modelu |

**Tabela `admin_access_log`** (dziennik dostępu administratora, wdrożony jako środek
rozliczalności — art. 5 ust. 2 RODO):

| Pole | Treść |
|---|---|
| `admin_email` | adres e-mail administratora, który sięgnął po dane |
| `subject_user_id` | identyfikator użytkownika, którego dane oglądano (pusty przy listach nieograniczonych do jednej osoby); **zastępowany nieodwracalnym skrótem, gdy ten użytkownik usunie konto** |
| `resource` | rodzaj zasobu: `upload` (zdjęcie), `admin_submissions_list`, `admin_user_search`, `admin_submission_rerun` |
| `resource_id` | identyfikator konkretnego obiektu (np. identyfikator zgłoszenia lub ścieżka pliku) |
| `created_at` | data i godzina |

Dziennik **nie zawiera treści** — ani zdjęć, ani informacji zwrotnych, ani wyników, ani wpisanej
frazy wyszukiwania (fraza sama byłaby daną osobową). Nie jest wystawiony przez żadne API; odczyt
odbywa się bezpośrednio z bazy podczas audytu. Dostęp administratora do własnych danych nie jest
rejestrowany (to szum, nie zdarzenie audytowe). Nieudany zapis do dziennika nie przerywa operacji
administratora, tylko trafia do logu ostrzeżeń — jest to świadomy kompromis dostępności nad
kompletnością śladu, wart odnotowania przy audycie.

**Tabela `deleted_account_quota`** (pseudonimowy znacznik limitu po usunięciu konta):

| Pole | Treść |
|---|---|
| `user_hash` | HMAC-SHA256 identyfikatora Google, liczony kluczem serwera; nieodwracalny i bezużyteczny bez tego klucza |
| `submission_count` | liczba zgłoszeń wysłanych w oknie limitu |
| `oldest_submission_at` | znacznik najstarszego liczonego zgłoszenia (do nagłówków `Retry-After`) |
| `expires_at` | koniec okna, po którym wpis jest kasowany |

Wpis powstaje **wyłącznie** wtedy, gdy usuwane konto miało zgłoszenia w oknie 24 godzin, i jest
usuwany, gdy okno się zamknie. Nie zawiera imienia, nazwiska, adresu e-mail ani czytelnego
identyfikatora. Cel: uniemożliwić obejście limitu dobowego przez usunięcie konta i zalogowanie
się ponownie tym samym kontem Google — bez tego jeden użytkownik mógłby wyczerpać budżet całego
wdrożenia (zob. R8). Podstawa: art. 6 ust. 1 lit. f RODO (cel A4).

**Pliki na dysku serwera:** fotografie w katalogu
`data/uploads/{google_sub}/{rok}/{etap}/{nr_zadania}/{losowy_uuid}.{jpg|png|webp|heic}`.
Nazwa pliku jest losowa i nie zawiera danych ucznia, ale **struktura katalogów zawiera
identyfikator konta Google**. Limity: maksymalnie 10 plików na zgłoszenie, 10 MB na plik,
dozwolone typy JPEG/PNG/WebP/HEIC. Zdjęcia większe niż 2048 px w którymkolwiek wymiarze są
zmniejszane i zapisywane ponownie jako JPEG (co usuwa metadane EXIF); **zdjęcia mniejsze
zachowują oryginalne metadane EXIF, w tym potencjalnie współrzędne GPS** — zob. ryzyko R4.

**Dane, które faktycznie znajdują się na fotografii kartki** — kategoria najbardziej wrażliwa
i najsłabiej kontrolowana. Uczniowie odruchowo podpisują prace. Realnie na zdjęciach pojawiają
się: imię i nazwisko, klasa, nazwa szkoły, data, charakter pisma (dana biometryczna w sensie
potocznym, ale nie w rozumieniu art. 4 pkt 14 RODO — nie służy identyfikacji technicznej),
notatki na marginesie niezwiązane z matematyką, fragmenty innych prac, a w tle kadru — elementy
mieszkania lub inne osoby.

**Sesja (cookie).** Podpisane kryptograficznie ciasteczko sesyjne Starlette, ważne 30 dni,
przechowuje: `google_sub`, `email`, `name`, adres URL zdjęcia profilowego Google,
flagę uprawnień oraz znacznik czasu ostatniej weryfikacji uprawnień. **Zdjęcie profilowe nie jest
zapisywane w bazie danych** — jest tylko odnośnikiem trzymanym w sesji (obecny regulamin serwisu
publicznego twierdził inaczej; nowa treść to prostuje).

**Logi aplikacji.** Zapisywane do dziennika kontenera Docker. Zawierają m.in. adres e-mail
użytkownika przy każdym udanym logowaniu, skrócony identyfikator użytkownika przy zgłoszeniach,
nazwy i rozmiary plików, wynik punktowy oraz treści błędów. Dla logów nie zdefiniowano dotąd
okresu retencji — zob. R17.

### 2.4 Cele przetwarzania i podstawy prawne

**Wariant A — administrator: osoba fizyczna**

| # | Cel | Zakres danych | Podstawa prawna |
|---|---|---|---|
| A1 | Prowadzenie konta i umożliwienie korzystania z narzędzia | `google_sub`, e-mail, imię i nazwisko | art. 6 ust. 1 lit. a RODO — zgoda rodzica lub opiekuna prawnego (art. 8 ust. 1 RODO w zw. z art. 8 ustawy z 10.05.2018 o ochronie danych osobowych) |
| A2 | Ocena przesłanego rozwiązania i wygenerowanie informacji zwrotnej | fotografie, treść pracy, wynik, informacja zwrotna | art. 6 ust. 1 lit. a — jw. |
| A3 | Prowadzenie historii prób i grafu postępów | wyniki, daty, identyfikatory zadań | art. 6 ust. 1 lit. a — jw. |
| A4 | Bezpieczeństwo usługi, limity liczby zgłoszeń, wykrywanie nadużyć i prób manipulacji oceną | `issue_type`, `abuse_score`, liczniki zgłoszeń, logi | art. 6 ust. 1 lit. f — prawnie uzasadniony interes administratora polegający na zapewnieniu integralności i dostępności usługi (motyw 49 RODO) |
| A5 | Rozpatrywanie żądań osób, których dane dotyczą, i obrona przed roszczeniami | korespondencja, minimalny zapis o wykonaniu żądania | art. 6 ust. 1 lit. c (art. 12 RODO) oraz art. 6 ust. 1 lit. f |

**Dlaczego zgoda rodzica, a nie sam prawnie uzasadniony interes — uzasadnienie wyboru**

Polska nie skorzystała z możliwości obniżenia progu z art. 8 ust. 1 RODO: art. 8 ustawy
z 10.05.2018 o ochronie danych osobowych utrzymuje **16 lat**. Serwis jest usługą społeczeństwa
informacyjnego oferowaną bezpośrednio dziecku, a jego grupa docelowa jest w całości poniżej tego
progu. Zgoda samego dziecka byłaby zatem nieskuteczna.

Rozważono trzy warianty podstawy:

- **Art. 6 ust. 1 lit. b (umowa).** Odrzucono. Umowa o świadczenie usługi drogą elektroniczną
  zawarta z dzieckiem poniżej 13 lat jest w prawie polskim nieważna (art. 14 Kodeksu cywilnego),
  a z osobą 13–18 lat wymaga potwierdzenia przez przedstawiciela ustawowego (art. 17–18 k.c.).
  Budowanie podstawy przetwarzania na czynności prawnej, której ważność jest wątpliwa, byłoby
  wadą konstrukcyjną. Wyjątek z art. 20 k.c. (drobne bieżące sprawy życia codziennego) jest zbyt
  niepewny dla usługi wysyłającej zdjęcia dziecka do dostawcy w państwie trzecim.
- **Art. 6 ust. 1 lit. f (prawnie uzasadniony interes) jako podstawa główna.** Odrzucono dla
  operacji podstawowych. Motyw 38 RODO nakazuje szczególną ochronę dzieci, a motyw 47 wskazuje,
  że przy teście równowagi trzeba uwzględnić rozsądne oczekiwania osoby. Dziecko nie oczekuje,
  że fotografia jego pracy trafi do dostawcy modeli AI w USA i że powstanie trwały zapis jego
  niepowodzeń. Test równowagi wypada więc na niekorzyść administratora, a dodatkowo taka
  konstrukcja pozbawiłaby rodzica realnej kontroli.
- **Art. 6 ust. 1 lit. a (zgoda rodzica lub opiekuna) — wybrano.** Daje osobie sprawującej władzę
  rodzicielską rzeczywistą decyzję, jest odwoływalna, a odwołanie ma czytelny skutek techniczny
  (usunięcie konta i wszystkich danych, funkcja dostępna samodzielnie w serwisie). Odpowiada
  charakterowi usługi: dobrowolnej, darmowej, bez której dziecko nie traci niczego, do czego
  byłoby uprawnione.

Prawnie uzasadniony interes pozostaje podstawą **wyłącznie** dla celu A4 (bezpieczeństwo
i limity). Jest to świadome rozdzielenie: gdyby wykrywanie nadużyć opierało się na zgodzie,
użytkownik mógłby ją wycofać i tym samym wyłączyć mechanizm ochronny.

> **Luka do zamknięcia (R15).** Art. 8 ust. 2 RODO wymaga „rozsądnych starań" o weryfikację,
> że zgodę wyraziła osoba sprawująca władzę rodzicielską. Obecnie serwis dysponuje wyłącznie
> polem wyboru („Akceptuję regulamin…") na ekranie logowania, co samo w sobie takich starań nie
> stanowi. Rekomendowane środki w sekcji 6, R15.

**Wariant B — administrator: szkoła publiczna**

| # | Cel | Podstawa prawna |
|---|---|---|
| B1 | Udostępnienie uczniom narzędzia do samodzielnego ćwiczenia w ramach zajęć i przygotowania do olimpiady | **art. 6 ust. 1 lit. e RODO** — przetwarzanie niezbędne do wykonania zadania realizowanego w interesie publicznym, tj. zadania dydaktycznego szkoły, w zw. z ustawą z 14.12.2016 Prawo oświatowe (m.in. art. 1, art. 68 ust. 1) i ustawą z 07.09.1991 o systemie oświaty |
| B2 | Ocena rozwiązania i informacja zwrotna dla ucznia | art. 6 ust. 1 lit. e — jw. |
| B3 | Bezpieczeństwo instancji, limity, wykrywanie nadużyć | art. 6 ust. 1 lit. e w zw. z art. 32 RODO |
| B4 | Rozpatrywanie żądań osób | art. 6 ust. 1 lit. c |

Wybór lit. e w wariancie B jest celowy i rozwiązuje problem zgód. Szkoła publiczna realizuje
zadanie oświatowe wynikające z ustawy; korzystanie z narzędzia dydaktycznego mieści się w tym
zadaniu. Konsekwencje, które trzeba przyjąć świadomie:

- **nie stosuje się** prawa do przenoszenia danych (art. 20 RODO dotyczy tylko lit. a i lit. b),
- **przysługuje** prawo sprzeciwu z art. 21 ust. 1 RODO, a szkoła musi mieć procedurę jego
  rozpatrzenia (praktycznie: rezygnacja ucznia z narzędzia bez negatywnych konsekwencji —
  narzędzie musi pozostać dobrowolne, zob. sekcja 4.1),
- prawo do usunięcia jest ograniczone (art. 17 ust. 3 lit. b), ale w praktyce nic nie stoi na
  przeszkodzie, by szkoła usunęła dane ucznia, który zrezygnował,
- **art. 8 RODO nie ma zastosowania**, bo podstawą nie jest zgoda; nie trzeba zbierać zgód
  rodziców na samo przetwarzanie. Rodzic powinien natomiast otrzymać klauzulę informacyjną,
  a szkoła powinna rozważyć poinformowanie rodziców o narzędziu przed jego wdrożeniem —
  z uwagi na przejrzystość, nie z uwagi na obowiązek zgody.

> Uwaga ustrojowa: szkoła publiczna prowadzona przez gminę jest jednostką budżetową bez
> osobowości prawnej. Administratorem danych jest **szkoła** reprezentowana przez dyrektora
> (a nie gmina, nie miasto, nie organ prowadzący). Stroną ewentualnych umów cywilnoprawnych
> — w tym umowy z Google na usługi API — jest natomiast **gmina**, działająca przez dyrektora
> szkoły na podstawie pełnomocnictwa wójta/burmistrza/prezydenta.

### 2.5 Odbiorcy danych i podmioty przetwarzające

| Podmiot | Rola | Co otrzymuje | Ramy prawne |
|---|---|---|---|
| Google Ireland Ltd. / Google LLC — usługa logowania (OAuth 2.0) | odrębny administrator dla swojego konta użytkownika | fakt logowania do naszej aplikacji; my otrzymujemy `sub`, e-mail, imię i nazwisko, adres zdjęcia profilowego | zakres `openid email profile` |
| Google — Gemini API (płatny poziom usługi) | podmiot przetwarzający | **fotografie pracy ucznia**, PDF zadań, PDF rozwiązań wzorcowych, instrukcja oceniania; **nie przekazujemy** e-maila, imienia, nazwiska ani identyfikatora konta | Gemini API Additional Terms + Google Cloud Data Processing Addendum; transfer: EU-US Data Privacy Framework |
| Google — Cloud Translation API v2 (funkcja opcjonalna, `TRANSLATE_ENABLED`) | podmiot przetwarzający | krótkie nagłówki toku rozumowania modelu tłumaczone z angielskiego na polski — **dotyczą treści pracy ucznia** | jw. |
| Cloudflare, Inc. | podmiot przetwarzający | ruch HTTPS między użytkownikiem a serwerem (tunel, terminacja TLS) | [DO USTALENIA: potwierdzić zawarcie DPA / warunki Cloudflare i wpisać do rejestru] |
| Telegram FZ-LLC | odbiorca powiadomień technicznych | komunikaty operacyjne: identyfikator zgłoszenia, oznaczenie zadania, liczba zdjęć, wynik punktowy, treść błędu. **Bez imienia, nazwiska, e-maila i identyfikatora użytkownika.** Funkcja wyłączana konfiguracją | brak umowy powierzenia — zob. R12; **w wariancie B zalecane wyłączenie** |
| Dostawca hostingu / miejsce serwera | — | całość danych | wariant A: serwer własny autora; wariant B: [UZUPEŁNIĆ: infrastruktura szkoły / dostawca] |

**Poziom płatny Gemini API — dlaczego to ma znaczenie.** Produkcja korzysta z płatnego klucza API.
Na płatnym poziomie Google zobowiązuje się nie wykorzystywać przekazywanych treści (promptów)
ani odpowiedzi do trenowania swoich modeli, a logi zachowuje maksymalnie 55 dni wyłącznie w celu
wykrywania naruszeń polityki korzystania z usługi. Na poziomie bezpłatnym takiego zobowiązania
**nie ma** — treści mogą być wykorzystywane do ulepszania produktów Google. Jest to warunek
brzegowy całej oceny: **uruchomienie instancji na bezpłatnym kluczu API unieważnia wnioski
niniejszej DPIA i wymaga jej ponownego przeprowadzenia.** W wariancie B szkoła musi
udokumentować, że jej własny klucz jest kluczem płatnym (fakturowanym projektem Google Cloud).

Dodatkowo: fotografie są przesyłane do Gemini File API na czas analizy i **usuwane po jej
zakończeniu** przez kod aplikacji (usuwanie „najlepszym staraniem" — błąd usunięcia jest logowany,
ale nie przerywa działania; niezależnie od tego pliki wygasają po stronie Google po ok. 48 godz.).
PDF-y z zadaniami są celowo utrzymywane w pamięci podręcznej do 24 godzin, bo nie zawierają
danych osobowych.

### 2.6 Przepływ danych

```
[Uczeń: przeglądarka]
    │  1. logowanie
    ▼
[Google OAuth]  ──────► zwraca: sub, e-mail, imię i nazwisko, URL zdjęcia profilowego
    │
    ▼
[Serwer aplikacji (FastAPI) — za tunelem Cloudflare]
    │  2. zapis konta w PostgreSQL (sub, e-mail, imię i nazwisko)
    │  3. cookie sesyjne (30 dni, podpisane, HTTPS)
    │
    │  4. przesłanie 1–10 fotografii  ──►  zapis na dysku serwera
    │                                       data/uploads/{sub}/{rok}/{etap}/{nr}/
    │
    │  5. wysłanie do Gemini File API:
    │       • fotografie ucznia  (bez pamięci podręcznej, kasowane po analizie)
    │       • PDF z zadaniami     (pamięć podręczna do 24 h)
    │       • PDF z rozwiązaniami (pamięć podręczna do 24 h)
    │       • instrukcja oceniania po polsku
    ├──────────────────────────────────────► [Google Gemini — USA / DPF]
    │  6. odpowiedź: score, feedback, issue_type, abuse_score
    │
    │  6a. (opcjonalnie) nagłówki toku rozumowania EN→PL
    ├──────────────────────────────────────► [Google Cloud Translation — USA / DPF]
    │
    │  7. zapis wyniku w PostgreSQL (w tym surowa odpowiedź modelu w scoring_meta)
    │  8. przesłanie wyniku do przeglądarki ucznia przez WebSocket
    │  9. powiadomienie techniczne bez tożsamości
    └──────────────────────────────────────► [Telegram — poza EOG]
```

Dane nie opuszczają tej ścieżki. Nie ma analityki zewnętrznej, reklam, mechanizmów śledzących
ani udostępniania danych podmiotom komercyjnym.

### 2.7 Okresy przechowywania

| Dane | Okres | Parametr konfiguracji | Uwagi |
|---|---|---|---|
| Zgłoszenie (wiersz w bazie) **wraz z fotografiami pracy** | **24 miesiące** od utworzenia | `RETENTION_SUBMISSION_MONTHS` | mechanizm usuwa wiersz i pliki łącznie; ustawienie 0 lub braku wartości **wyłącza** wygasanie — niedopuszczalne we wdrożeniu produkcyjnym. Okres dobrany tak, by objąć dwa lata szkolne, przez które biegnie cykl olimpijski |
| Surowy zapis toku rozumowania modelu w `scoring_meta` | **90 dni** od utworzenia | `RETENTION_SCORING_THINKING_DAYS` | zapis odtwarza treść pracy ucznia dosłownie, dlatego jest usuwany znacznie wcześniej niż samo zgłoszenie; pozostałe metadane (nazwa modelu, liczba tokenów, koszt, czasy) nie są danymi osobowymi i zostają |
| Konto użytkownika (`users`) wraz ze wszystkim, co do niego należy | **36 miesięcy** bez logowania i bez zgłoszenia | `RETENTION_INACTIVE_ACCOUNT_MONTHS` | aktywność liczona jako późniejsza z dwóch dat: ostatniego logowania i ostatniego zgłoszenia (sesja trwa 30 dni, więc sam znacznik logowania byłby mylący). Pomijane są konta administracyjne i konto deweloperskie. Okres dłuższy niż retencja zgłoszeń, by wracający uczeń zastał swoją historię |
| Dziennik dostępu administratora (`admin_access_log`) | **12 miesięcy** od zdarzenia | `RETENTION_ADMIN_AUDIT_MONTHS` | dość długo, by zbadać skargę, dość krótko, by nie stać się archiwum tego, kto na kogo patrzył |
| Pseudonimowy znacznik limitu po usunięciu konta (`deleted_account_quota`) | do zamknięcia okna limitu, czyli **maks. 24 godziny** od ostatniego zgłoszenia | okno limitu (24 h) | usuwany automatycznie; powstaje tylko wtedy, gdy konto miało zgłoszenia w oknie |
| Pliki osierocone (bez odpowiadającego zgłoszenia) | usuwane przy każdym przebiegu retencji | `RETENTION_AUTO_PURGE` (przebieg dobowy) | zabezpieczenie na wypadek niepowodzenia usunięcia plików |
| Cookie sesyjne | 30 dni (wartość zaszyta w kodzie) | — | |
| Dzienniki aplikacji (dziennik kontenera) | **ograniczone objętościowo**: 50 MB × 5 plików na usługę (250 MB), najstarsze wpisy nadpisywane | `docker-compose.prod.yml` (`x-logging`) | rotacja wdrożona; przy obecnym ruchu odpowiada to kilku miesiącom, ale jest to limit objętości, a nie gwarantowany okres — zob. R13 |
| Kopie zapasowe bazy | [UZUPEŁNIĆ] | — | usunięcie danych musi obejmować także kopie po upływie cyklu ich rotacji |
| Dane po samodzielnym usunięciu konta przez użytkownika | usuwane niezwłocznie | funkcja usunięcia konta | usuwane są: konto, wszystkie zgłoszenia (kaskadowo) i wszystkie pliki; w dzienniku dostępu administratora identyfikator jest zastępowany nieodwracalnym skrótem; pozostaje wyłącznie znacznik limitu opisany wyżej; kopie zapasowe — po cyklu rotacji |
| Dane po wygaszeniu serwisu (wariant A) | usunięcie całości nie później niż [UZUPEŁNIĆ] od zamknięcia serwisu | — | użytkownicy informowani z wyprzedzeniem [UZUPEŁNIĆ: np. 30 dni] |

**Uwagi:**

1. Wartości powyżej to **wartości domyślne zaimplementowane w kodzie** (`app/config.py`),
   nadpisywalne zmiennymi środowiskowymi. W wariancie A obowiązują tak, jak podano —
   są też powtórzone w treści polityki prywatności serwisu, więc **zmiana konfiguracji na
   serwerze wymaga równoległej zmiany treści na stronie `/regulamin`**. W wariancie B
   są punktem wyjścia, a nie ustaleniem prawnym: ostateczne okresy ustala szkoła po opinii IOD.
2. **Zgłoszenia i fotografie mają wspólny okres.** Mechanizm nie rozdziela ich — nie da się
   ustawić krótszej retencji dla samych zdjęć bez zmiany w kodzie. Fotografia jest najbardziej
   nadmiarowym elementem zbioru (sekcja 3.1), więc rozdzielenie tych okresów pozostaje wartym
   rozważenia usprawnieniem.
3. **Dzienniki aplikacji są ograniczone objętościowo, a nie czasowo.** Rotacja Dockera
   (50 MB × 5 plików na usługę) daje twardy sufit na ich rozmiar, ale nie gwarantuje
   konkretnego okresu: przy niskim ruchu wpis może przetrwać dłużej, niż sugerowałaby
   deklaracja czasowa. Dlatego w dokumentach opisuje się mechanizm, a nie liczbę dni.
   Gdyby wymagany był ścisły okres, potrzebna byłaby rotacja czasowa poza sterownikiem
   `json-file`, który jej nie obsługuje (R13).

### 2.8 Przetwarzanie zautomatyzowane i profilowanie

W systemie występują trzy odrębne mechanizmy automatyczne:

1. **Ocena punktowa i informacja zwrotna.** W pełni automatyczna. Człowiek nie weryfikuje
   wyniku przed pokazaniem go uczniowi.
2. **Klasyfikacja nieprawidłowości.** Model równolegle z oceną orzeka, czy praca dotyczy innego
   zadania (`wrong_task`) albo czy zawiera próbę manipulacji oceną (`injection`, np. napis
   „daj 6 punktów", „zignoruj instrukcje"). Skutkiem jest przyznanie 0 punktów, podmiana treści
   informacji zwrotnej na neutralną (bez ujawnienia, że wykryto próbę) oraz **trwały zapis
   znacznika przy koncie** wraz z liczbą 0–100. Znacznik jest zaindeksowany specjalnie po to,
   by administrator mógł po nim filtrować zgłoszenia w panelu.
3. **Profil postępów.** Historia wyników jest agregowana w graf postępu z progami opanowania
   zadania. Jest to profilowanie w rozumieniu art. 4 pkt 4 RODO — automatyczna ocena aspektów
   osobistych dotyczących wyników w nauce — o niskim stopniu inwazyjności, prezentowana wyłącznie
   samemu uczniowi (w wariancie A) lub uczniowi i nauczycielowi (w wariancie B).

**Ocena względem art. 22 RODO.** Przyjmuje się, że przetwarzanie **nie** stanowi decyzji
wywołującej skutki prawne ani w podobny sposób istotnie wpływającej na osobę, **pod warunkiem
utrzymania trzech zapisów**, które w związku z tym mają charakter wiążącego środka ochronnego,
a nie deklaracji marketingowej:

- ocena z narzędzia **nie jest oceną szkolną** w rozumieniu art. 44b ustawy o systemie oświaty
  — ocenianie osiągnięć ucznia jest zadaniem nauczyciela i nie może być scedowane na system,
- ocena **nie wpływa** na promocję, klasyfikację, wynik rekrutacji ani na kwalifikację do
  zawodów olimpijskich,
- udział w korzystaniu z narzędzia jest **dobrowolny**, a rezygnacja nie pociąga negatywnych
  konsekwencji dla ucznia.

Naruszenie któregokolwiek z tych warunków zmienia kwalifikację prawną przetwarzania: uruchamia
art. 22 RODO (z obowiązkiem zapewnienia interwencji ludzkiej, wyrażenia własnego stanowiska
i zakwestionowania decyzji) i przenosi system do kategorii wysokiego ryzyka z Załącznika III
do AI Act — zob. sekcja 7.

---

## 3. Ocena niezbędności i proporcjonalności (art. 35 ust. 7 lit. b)

### 3.1 Niezbędność

Celem jest umożliwienie dziecku samodzielnego sprawdzenia rozwiązania zadania olimpijskiego
i otrzymania informacji zwrotnej wtedy, gdy nad tym zadaniem pracuje. Alternatywą realną
w polskiej szkole jest sprawdzenie pracy przez nauczyciela — dostępne w skali kilku prac
tygodniowo, z opóźnieniem kilkudniowym i tylko tam, gdzie w szkole jest nauczyciel prowadzący
przygotowania olimpijskie. Narzędzie nie zastępuje nauczyciela; obniża próg wejścia dla ucznia,
który chce pracować samodzielnie i częściej.

Przetwarzanie następujących danych jest niezbędne do osiągnięcia celu:

- **fotografia pracy** — bez niej nie ma czego oceniać; alternatywa (przepisywanie rozwiązania
  w edytorze) jest dla ucznia klas VII–VIII nierealna, zwłaszcza w zadaniach geometrycznych
  z rysunkiem,
- **trwały identyfikator użytkownika** — konieczny, by uczeń widział wyłącznie własne prace
  i własną historię; anonimowe korzystanie uniemożliwiłoby zarówno historię, jak i limity
  chroniące przed nadużyciem,
- **wynik i informacja zwrotna** — stanowią rezultat usługi.

Dane, których niezbędności **nie** wykazano i które podlegają weryfikacji:

- **adres e-mail i imię i nazwisko.** Do działania serwisu wystarczyłby sam identyfikator
  `sub`. E-mail jest realnie potrzebny do jednej rzeczy: kontaktu z użytkownikiem
  (np. powiadomienia o wygaszeniu serwisu) i do mechanizmu listy uprawnionych/administratorów,
  który operuje adresami. Imię i nazwisko nie pełni żadnej funkcji poza wyświetleniem
  w interfejsie. **Rekomendacja:** w wariancie B rozważyć rezygnację z zapisywania pola `name`
  albo zastąpienie go pierwszym imieniem.
- **surowa odpowiedź modelu w `scoring_meta`** — przydatna diagnostycznie, ale zawiera pełny
  tekst analizy pracy ucznia i podwaja zbiór.

### 3.2 Minimalizacja — co już zrobiono

- do modelu AI **nie trafia** żaden identyfikator ucznia: ani e-mail, ani imię i nazwisko,
  ani `sub`; nazwy plików są losowymi identyfikatorami,
- fotografie są usuwane z infrastruktury Google zaraz po zakończeniu analizy,
- powiadomienia techniczne nie zawierają tożsamości użytkownika (opcjonalny, nieodwracalny
  pseudonim HMAC jest domyślnie wyłączony),
- pliki użytkownika są serwowane wyłącznie po zalogowaniu i po sprawdzeniu, że należą do tego
  użytkownika,
- limity liczby zgłoszeń ograniczają objętość gromadzonych danych,
- adresy e-mail i identyfikatory są maskowane w dziennikach aplikacji,
- każde sięgnięcie administratora po cudze dane zostawia ślad w dzienniku dostępu,
- kod jest jawny (licencja MIT), co umożliwia niezależną weryfikację powyższych twierdzeń.

### 3.3 Rozważone i odrzucone rozwiązania alternatywne

| Alternatywa | Ocena |
|---|---|
| Model uruchamiany lokalnie, bez wysyłania danych poza serwer | Docelowo najlepsza z punktu widzenia ochrony danych. Odrzucona obecnie: jakość odczytu odręcznego pisma matematycznego i rozumowania na zadaniach olimpijskich przez modele możliwe do uruchomienia na sprzęcie szkolnym jest niewystarczająca, a błędna ocena to główne ryzyko dla ucznia (R1). **Do ponownej oceny przy przeglądzie DPIA.** |
| Rezygnacja z kont — narzędzie w pełni anonimowe | Odrzucona: bez identyfikacji nie da się pokazać uczniowi wyłącznie jego prac, prowadzić historii ani egzekwować limitów; anonimowy dostęp otwarty na świat oznaczałby też niekontrolowany koszt. |
| Logowanie własnym hasłem zamiast konta Google | Odrzucona: oznaczałoby przechowywanie haseł dzieci i budowanie własnego mechanizmu odzyskiwania konta — więcej danych i większe ryzyko niż delegacja uwierzytelnienia. W wariancie B naturalną alternatywą jest **konto szkolne** (Google Workspace for Education lub Microsoft 365), a nie prywatne konto dziecka — zob. rekomendacja przy R15. |
| Usuwanie fotografii natychmiast po ocenie | Rozwiązanie mocno ograniczające ryzyko, odrzucone tylko częściowo: uczeń traci możliwość powrotu do własnej pracy i porównania jej z informacją zwrotną, a administrator — możliwość zbadania skargi na błędną ocenę. Kompromis: ograniczony okres retencji (sekcja 2.7) oraz wcześniejsze usuwanie dosłownego zapisu analizy modelu. **Uwaga:** wdrożony mechanizm wiąże okres fotografii z okresem zgłoszenia — rozdzielenie ich pozostaje rekomendacją. |
| Zgoda ucznia zamiast zgody rodzica (wariant A) | Prawnie niedopuszczalna — próg 16 lat, zob. 2.4. |

### 3.4 Realizacja praw osób, których dane dotyczą

| Prawo | Wariant A | Wariant B |
|---|---|---|
| Informacja (art. 13–14) | regulamin i polityka prywatności w serwisie, język przystępny dla dziecka i rodzica | klauzula informacyjna dla ucznia i rodzica (`klauzula-informacyjna-szkola.md`) |
| Dostęp (art. 15) | historia prób i zdjęcia widoczne w panelu „Moje rozwiązania"; kopia całości na żądanie e-mailem; na żądanie także informacja z dziennika dostępu administratora, kto i kiedy sięgał po dane tej osoby | jw. + wniosek do szkoły |
| Sprostowanie (art. 16) | e-mail do administratora | wniosek do szkoły |
| Usunięcie (art. 17) | **samodzielne usunięcie konta wraz ze zdjęciami i historią** w panelu użytkownika; alternatywnie e-mail. Przeżywa je wyłącznie pseudonimowy znacznik limitu (maks. 24 h, sekcja 2.3), ujawniony w polityce prywatności; w dzienniku dostępu administratora identyfikator zastępowany jest nieodwracalnym skrótem | wniosek; ograniczone art. 17 ust. 3 lit. b, w praktyce realizowane przy rezygnacji z narzędzia |
| Ograniczenie (art. 18) | e-mail | wniosek |
| Przenoszenie (art. 20) | przysługuje (podstawa: zgoda) | **nie przysługuje** (podstawa: lit. e) |
| Sprzeciw (art. 21) | wobec celu A4 (uzasadniony interes) | **przysługuje** wobec całości; skutek: zaprzestanie korzystania z narzędzia przez ucznia |
| Cofnięcie zgody (art. 7 ust. 3) | w każdej chwili, bez wpływu na zgodność z prawem przetwarzania przed cofnięciem | nie dotyczy |
| Skarga (art. 77) | Prezes UODO, ul. Stawki 2, 00-193 Warszawa | jw. |

---

## 4. Metodyka oceny ryzyka

Ryzyko oceniane jest z perspektywy **praw i wolności osoby, której dane dotyczą** (a nie ryzyka
organizacji), zgodnie z motywem 75 RODO.

**Prawdopodobieństwo (P):** 1 — mało prawdopodobne; 2 — możliwe; 3 — prawdopodobne lub
występujące regularnie.

**Waga skutku (W):** 1 — niedogodność bez trwałych następstw; 2 — istotny skutek, możliwy do
odwrócenia (np. utrata prywatności wobec ograniczonego kręgu, zniechęcenie do nauki);
3 — skutek trwały lub trudny do odwrócenia (np. ujawnienie danych dziecka szerokiemu kręgowi,
utrwalone błędne przekonanie o własnych zdolnościach, wykorzystanie danych w decyzji o uczniu).

**Poziom ryzyka = P × W:** 1–2 niskie · 3–4 średnie · 6 wysokie · 9 bardzo wysokie.

Kolumna „szczątkowe" podaje poziom po pełnym wdrożeniu wymienionych środków.

---

## 5. Rejestr ryzyk i środki zaradcze (art. 35 ust. 7 lit. c i d)

### R1. Błędna ocena punktowa i jej wpływ na dziecko

**P = 3 · W = 2 · poziom = 6 (wysokie) → szczątkowe: 3 (średnie)**

Model ocenia zdjęcie odręcznego rozwiązania zadania olimpijskiego. Źródła błędu są liczne
i nakładają się: nieczytelne pismo, rysunek geometryczny, zdjęcie pod kątem lub nieostre,
rozwiązanie poprawne, lecz inną metodą niż wzorcowa, rozwiązanie zapisane w nietypowej
kolejności, brak jednej ze stron pracy. Skala punktowa OMJ jest przy tym skokowa (0/2/5/6) —
pomyłka o jeden stopień to różnica między „prawie nic" a „prawie wszystko".

Skutek dla dziecka nie jest formalny, lecz psychologiczny i realny: zaniżona ocena zniechęca
i buduje fałszywy obraz własnych możliwości, zawyżona — usypia czujność przed zawodami.
Dziecko w wieku 10–15 lat ma ograniczoną zdolność krytycznej oceny werdyktu wydanego przez
„komputer", co jest tu okolicznością obciążającą (motyw 38 RODO).

Środki:

- oznaczenie w interfejsie **przy każdym wyniku**, że ocena i informacja zwrotna pochodzą od AI
  i mogą być błędne — nie tylko w regulaminie,
- wyraźny zapis (regulamin, klauzula, interfejs), że to **nie jest ocena szkolna** i nie wpływa
  na oceny, promocję ani rekrutację (zob. też sekcja 2.8),
- stały dostęp ucznia do **oficjalnego rozwiązania wzorcowego** obok wyniku, żeby mógł
  samodzielnie zweryfikować werdykt,
- ścieżka zakwestionowania wyniku: zgłoszenie do administratora / nauczyciela i możliwość
  ponownej oceny (funkcja ponownego uruchomienia analizy istnieje w panelu administratora),
- instrukcja fotografowania pracy (całe strony, w kadrze, dobre światło) ograniczająca
  najczęstszą przyczynę błędu,
- w wariancie B: przeszkolenie nauczyciela, by potrafił wyjaśnić uczniowi ograniczenia narzędzia
  (jest to jednocześnie realizacja art. 4 AI Act — zob. sekcja 7),
- [DO ROZWAŻENIA] okresowy przegląd próbki ocen przez nauczyciela i rejestrowanie odsetka
  ocen błędnych; bez pomiaru nie wiadomo, czy ryzyko maleje.

Ryzyko szczątkowe pozostaje średnie: błędnych ocen nie da się wyeliminować, można jedynie
zapewnić, że nie mają skutków formalnych i że dziecko ma narzędzia do ich zakwestionowania.

---

### R2. Informacja zwrotna ujawniająca rozwiązanie

**P = 2 · W = 1 · poziom = 2 (niskie) → szczątkowe: 2 (niskie)**

Instrukcja systemowa wyraźnie zakazuje modelowi podawania rozwiązania, jego fragmentów
i przeprowadzania brakującego rozumowania za ucznia (wolno jedynie **nazwać** lukę). Model
językowy nie gwarantuje jednak przestrzegania zakazu w każdym przypadku.

Skutek dotyka wartości dydaktycznej, a nie praw i wolności — stąd niska waga. Odnotowany, bo
przesądza o sensowności narzędzia i był przedmiotem świadomej decyzji projektowej.

Środki: zakaz w instrukcji systemowej; okresowy przegląd próbki informacji zwrotnych;
udostępnianie rozwiązania wzorcowego osobno, jako świadomy wybór ucznia, a nie jako element
oceny.

---

### R3. Ujawnienie treści pracy i niepowodzeń ucznia osobie trzeciej wewnątrz systemu

**P = 2 · W = 2 · poziom = 4 (średnie) → szczątkowe: 2 (niskie)**

Konto oznaczone jako administracyjne (lista adresów e-mail w konfiguracji) ma dostęp do
**wszystkich zgłoszeń wszystkich użytkowników**, w tym do pełnych fotografii prac, treści
informacji zwrotnych, wyników i znaczników nadużyć, a także do wyszukiwania użytkowników po
adresie e-mail. Zwykły użytkownik jest od cudzych plików odcięty sprawdzeniem właściciela ścieżki.

W wariancie B ryzyko ma dodatkowy wymiar: nauczyciel widzi ciąg niepowodzeń konkretnego ucznia
— materiał, który łatwo (choć nieformalnie) przełożyć na oczekiwania wobec dziecka i na ocenę
szkolną. Uczeń, który wie, że nauczyciel to widzi, przestanie używać narzędzia do ryzykownych
prób, czyli do tego, do czego jest ono najbardziej przydatne (efekt mrożący).

Środki:

- liczba kont administracyjnych ograniczona do minimum, lista zapisana wyłącznie w konfiguracji
  serwera i objęta przeglądem [UZUPEŁNIĆ: częstotliwość],
- upoważnienia do przetwarzania danych (art. 29 RODO) dla każdej osoby z takim dostępem,
  w wariancie B — wpisane do ewidencji upoważnień szkoły,
- pisemna zasada, że dostęp służy wyłącznie diagnostyce i rozpatrywaniu skarg,
- zasada, że dane z narzędzia nie są przekazywane innym nauczycielom, wychowawcy ani rodzicom
  bez wyraźnego powodu i podstawy,
- poinformowanie ucznia wprost, kto widzi jego prace (klauzula informacyjna),
- **[WDROŻONE] dziennik dostępu administratora** (`admin_access_log`, sekcja 2.3): każde
  odczytanie cudzego zdjęcia, wyświetlenie listy zgłoszeń, wyszukanie użytkownika i ponowne
  uruchomienie oceny zostawia wpis (kto, czyje dane, jaki zasób, kiedy) — bez treści i bez frazy
  wyszukiwania. Retencja 12 miesięcy. Pozwala wykazać rozliczalność (art. 5 ust. 2) i odpowiedzieć
  osobie na pytanie „kto oglądał moje dane". Ograniczenia, o których trzeba pamiętać przy audycie:
  dziennik nie jest wystawiony żadnym API (odczyt bezpośrednio z bazy), a nieudany zapis nie
  przerywa operacji administratora, więc ślad nie jest gwarantowany w 100%;
- **[DO ROZWAŻENIA]** okresowy przegląd dziennika przez osobę inną niż administrator — sam
  dziennik nikogo nie powstrzymuje, dopóki nikt do niego nie zagląda.

---

### R4. Dane nadmiarowe utrwalone na fotografii kartki

**P = 3 · W = 2 · poziom = 6 (wysokie) → szczątkowe: 3 (średnie)**

System kontroluje, jakie pola bazy zbiera, ale nie kontroluje, co dziecko sfotografuje.
W praktyce na zdjęciach pojawiają się: imię i nazwisko oraz klasa (uczniowie odruchowo podpisują
prace), nazwa szkoły, notatki na marginesie niezwiązane z zadaniem, fragmenty innych prac,
przedmioty i osoby w tle kadru. Zdarza się, że margines zeszytu zawiera treści osobiste.

Dodatkowo: fotografie o wymiarach poniżej 2048 px **nie są przetwarzane ponownie i zachowują
oryginalne metadane EXIF**, które w zdjęciach z telefonu regularnie zawierają współrzędne GPS
miejsca wykonania — czyli zwykle adres domowy dziecka. Zdjęcia większe są zmniejszane i zapisywane
jako nowy plik JPEG, co metadane usuwa. Skutkiem jest sytuacja, w której **usunięcie danych
lokalizacyjnych zależy od rozdzielczości aparatu**, co nie jest świadomym środkiem ochronnym.

Wszystkie te dane trafiają następnie do modelu AI, mimo że aplikacja starannie nie przekazuje mu
tożsamości użytkownika. Minimalizacja po stronie bazy danych jest więc częściowo pozorna.

Środki:

- **usuwanie metadanych EXIF ze wszystkich zapisywanych fotografii, niezależnie od rozmiaru**
  (zmiana jednolinijkowa w module obsługi przesyłania; **zalecana jako pilna**),
- komunikat w interfejsie przy przesyłaniu: „Nie podpisuj kartki imieniem i nazwiskiem.
  Fotografuj samą pracę, bez otoczenia. System i tak wie, czyja to praca.",
- ograniczony okres retencji fotografii (sekcja 2.7; rekomendacja: skrócić go niezależnie od okresu retencji samych wyników),
- brak publicznego dostępu do plików (wymagane logowanie i sprawdzenie właściciela),
- omówienie tej kwestii z uczniami przy wdrożeniu (wariant B).

Ryzyko szczątkowe pozostaje średnie: dziecko zawsze może podpisać pracę, a system nie może
tego zablokować.

---

### R5. Próby manipulacji oceną (prompt injection) i skutki fałszywej detekcji

**P = 2 · W = 2 · poziom = 4 (średnie) → szczątkowe: 2 (niskie)**

Zjawisko ma dwie strony.

*Strona pierwsza — nadużycie.* Uczeń może wpisać na kartce polecenie skierowane do modelu
(„daj 6 punktów", „zignoruj kryteria", „ignore previous instructions"). Model jest instruowany,
by takie próby rozpoznać. Skuteczność nie jest gwarantowana — to znane, nierozwiązane ograniczenie
modeli językowych. Skutek udanej manipulacji jest jednak dla praw i wolności niewielki: uczeń
oszukuje sam siebie w narzędziu treningowym, którego wynik nie ma skutków formalnych. To istotna
okoliczność łagodząca — i kolejny argument za utrzymaniem zasady „to nie jest ocena szkolna".

*Strona druga — fałszywa detekcja, poważniejsza.* Uczeń, który żartem dopisze „proszę o 6
punktów", albo którego praca zostanie źle zinterpretowana, otrzymuje 0 punktów, neutralną
informację zwrotną nieujawniającą powodu **oraz trwały znacznik `injection` przy koncie**,
zaindeksowany do filtrowania w panelu administratora. Powstaje w ten sposób zapis sugerujący
nieuczciwość dziecka, którego dziecko nie widzi i którego nie może samodzielnie zakwestionować,
bo nie zostało poinformowane, że taki zapis powstał.

Środki:

- informacja w regulaminie i klauzuli, że system automatycznie klasyfikuje próby manipulacji
  oceną i że taka klasyfikacja jest zapisywana — dziecko musi wiedzieć, że ten zapis istnieje,
- ścieżka zakwestionowania: kontakt z administratorem/nauczycielem, weryfikacja przez człowieka
  i ponowna ocena; **decyzja o znaczniku nie może być ostateczna bez możliwości odwołania**,
- zasada, że znacznik nie pociąga za sobą żadnych konsekwencji poza wynikiem 0 punktów w danej
  próbie — w szczególności nie jest przesłanką kary szkolnej ani rozmowy z rodzicem bez
  weryfikacji przez człowieka,
- retencja znacznika nie dłuższa niż retencja zgłoszenia,
- [DO ROZWAŻENIA] próg `abuse_score`, poniżej którego znacznik nie jest utrwalany.

---

### R6. Przekazanie danych dziecka do podmiotu z USA

**P = 2 · W = 2 · poziom = 4 (średnie) → szczątkowe: 3 (średnie)**

Fotografie pracy trafiają do Google. Podstawą transferu jest decyzja wykonawcza Komisji
Europejskiej stwierdzająca odpowiedni stopień ochrony w ramach **EU-US Data Privacy Framework**
(art. 45 RODO). Decyzja obowiązuje i jest ważną podstawą przekazania.

Ryzyko ma charakter **rezydualny i systemowy**, nie operacyjny: Sąd Unii Europejskiej wyrokiem
z 3 września 2025 r. w sprawie **T-553/23 (Latombe)** oddalił skargę o stwierdzenie nieważności
decyzji o adekwatności, jednak **odwołanie do Trybunału Sprawiedliwości UE pozostaje w toku**.
Historia unieważnień poprzednich mechanizmów (Safe Harbour, Tarcza Prywatności) uzasadnia
traktowanie tego ryzyka jako realnego, choć odległego. Odrębnym czynnikiem jest stabilność
mechanizmów nadzorczych po stronie amerykańskiej, na których opiera się decyzja.

Środki:

- **płatny poziom Gemini API**: brak wykorzystania treści do trenowania modeli, logi wyłącznie
  do wykrywania naruszeń polityki, maksymalnie 55 dni (warunek brzegowy, sekcja 2.5),
- **minimalizacja tego, co przekracza granicę**: żadnych identyfikatorów ucznia; wyłącznie obraz
  pracy i treść zadania,
- usuwanie plików z infrastruktury dostawcy niezwłocznie po analizie,
- weryfikacja, że dostawca figuruje na liście uczestników DPF (przy wdrożeniu i przy każdym
  przeglądzie DPIA), oraz zawarcie umowy powierzenia obejmującej standardowe klauzule umowne
  jako podstawę zapasową,
- **plan awaryjny**: warstwa dostawcy AI jest w kodzie wydzielona za wspólnym interfejsem, co
  umożliwia zamianę dostawcy bez przebudowy aplikacji. Administrator powinien wskazać dostawcę
  zapasowego z siedzibą w EOG i orientacyjny czas przełączenia — [UZUPEŁNIĆ],
- monitorowanie losów odwołania w sprawie Latombe i gotowość do wstrzymania przetwarzania,
  jeśli decyzja o adekwatności upadnie.

---

### R7. Uzależnienie od jednego dostawcy AI

**P = 2 · W = 1 · poziom = 2 (niskie) → szczątkowe: 2 (niskie)**

Cała funkcja oceniania opiera się na jednym dostawcy. Skutki: przerwa w działaniu usługi przy
awarii lub wycofaniu modelu (nazwy modeli w rodzinie Gemini zmieniają się co kilka miesięcy),
jednostronna zmiana warunków przetwarzania danych przez dostawcę, zmiana cennika wpływająca na
możliwość utrzymania narzędzia. Dla praw i wolności osoby skutek jest niewielki (utrata dostępu
do darmowego narzędzia dodatkowego), stąd niska waga — ale ryzyko zmiany warunków przetwarzania
przez dostawcę przekłada się na R6.

Środki: wydzielony interfejs dostawcy AI; monitorowanie komunikatów o wycofywaniu modeli;
okresowy (co najmniej roczny) przegląd warunków przetwarzania danych u dostawcy; odnotowanie
w DPIA, że zmiana modelu na model innego dostawcy wymaga aktualizacji rejestru czynności
i klauzuli informacyjnej.

---

### R8. Limity i koszt jako mechanizm dostępności usługi

**P = 2 · W = 1 · poziom = 2 (niskie) → szczątkowe: 1 (niskie)**

Każde zgłoszenie kosztuje — wywołanie modelu na fotografiach w wysokiej rozdzielczości z PDF-ami
zadań jest operacją płatną. Bez limitów jedno konto mogłoby wyczerpać budżet całego wdrożenia.
Obecna konfiguracja: 30 zgłoszeń na użytkownika na dobę, 500 zgłoszeń łącznie na dobę,
50 nowych kont na dobę. Lista adresów uprzywilejowanych omija limity.

Skutek: limit globalny jest **wspólny dla wszystkich** — intensywna praca kilku uczniów
(np. przed zawodami) może odciąć pozostałych, a komunikat brzmi wtedy „system osiągnął dzienny
limit". Lista adresów omijających limity oznacza nierówne traktowanie użytkowników, co w szkole
wymaga uzasadnienia (np. konto nauczyciela do testów) i nie powinno być stosowane wobec uczniów.

**[WDROŻONE] zabezpieczenie przed obejściem limitu przez usunięcie konta.** Limity liczone są
na podstawie wierszy zgłoszeń, które przy kasowaniu konta znikają — bez dodatkowego środka
usunięcie konta i ponowne zalogowanie tym samym kontem Google zerowałoby limit w nieskończoność.
Dlatego po usunięciu konta zostaje pseudonimowy znacznik (sekcja 2.3, `deleted_account_quota`):
nieodwracalny skrót identyfikatora i liczba zgłoszeń w oknie, kasowany po maksymalnie 24 godzinach.
Ponieważ jest to jedyna rzecz przeżywająca żądanie „usuń wszystko", **musi być ujawniona
w polityce prywatności** — i jest (sekcja 3.4).

Pozostałe środki: dobranie limitów do liczebności grupy przed wdrożeniem (wariant B — [UZUPEŁNIĆ]);
monitorowanie zużycia budżetu; czytelny komunikat dla ucznia z informacją, kiedy limit się
odnowi (jest już implementowany przez nagłówki `Retry-After`); zasada, że lista omijająca limity
zawiera wyłącznie konta służbowe; jawne poinformowanie o limitach w regulaminie.

---

### R9. Naruszenie bezpieczeństwa serwera lub bazy danych

**P = 2 · W = 3 · poziom = 6 (wysokie) → szczątkowe: 3 (średnie)**

Zbiór jest atrakcyjny: fotografie prac dzieci, ich imiona i nazwiska, adresy e-mail i wyniki,
w jednym miejscu. W wariancie A serwis działa na komputerze w lokalu autora, wystawionym do
internetu przez tunel Cloudflare; baza w kontenerze z danymi na dysku hosta; kopie zapasowe
wykonywane ręcznie poleceniem `pg_dump` (zgodnie z dokumentacją wdrożeniową). W wariancie B
infrastrukturę zapewnia szkoła.

Skutek naruszenia byłby trwały i dotyczyłby dzieci — stąd najwyższa waga.

Środki:

- szyfrowanie dysku serwera oraz szyfrowanie kopii zapasowych; przechowywanie kopii w innej
  lokalizacji niż serwer,
- automatyzacja kopii zapasowych i **przetestowanie odtworzenia** (kopia nieodtworzona to kopia
  nieistniejąca) — [UZUPEŁNIĆ: częstotliwość i osoba odpowiedzialna],
- aktualizacje systemu i obrazów kontenerów; kontenery uruchamiane bez dodatkowych uprawnień
  (już skonfigurowane w wdrożeniu produkcyjnym),
- dostęp administracyjny do serwera wyłącznie kluczem SSH, bez haseł; baza niedostępna spoza
  sieci kontenerów (już skonfigurowane),
- rotacja i ochrona sekretów (klucz API, klucz podpisu sesji, hasło bazy) — przechowywane poza
  repozytorium,
- **procedura reakcji na naruszenie ochrony danych**: kto ocenia, kto zgłasza do Prezesa UODO
  w ciągu 72 godzin (art. 33), kto zawiadamia osoby (art. 34), gdzie prowadzony jest wewnętrzny
  rejestr naruszeń. W wariancie B — procedura szkolna; w wariancie A — [UZUPEŁNIĆ, brak],
- w wariancie B: umiejscowienie serwera w infrastrukturze szkoły objętej jej polityką
  bezpieczeństwa; jeśli u zewnętrznego dostawcy — umowa powierzenia (art. 28) i weryfikacja
  lokalizacji przetwarzania.

---

### R10. Przejęcie sesji użytkownika

**P = 1 · W = 2 · poziom = 2 (niskie) → szczątkowe: 2 (niskie)**

Sesja jest przechowywana w podpisanym ciasteczku ważnym **30 dni**, zawierającym e-mail, imię
i nazwisko oraz flagę uprawnień. Ujawnienie klucza podpisującego pozwoliłoby sfałszować sesję
dowolnego użytkownika, w tym administratora. Długi czas życia sesji na współdzielonym urządzeniu
(komputer w pracowni, tablet rodzinny) oznacza, że kolejna osoba może zobaczyć prace poprzedniej.

Środki: transmisja wyłącznie po HTTPS z flagą `Secure`; klucz podpisujący ustawiany wyłącznie ze
zmiennej środowiskowej i objęty rotacją [UZUPEŁNIĆ: częstotliwość]; widoczna funkcja wylogowania;
komunikat zalecający wylogowanie na urządzeniu współdzielonym; [DO ROZWAŻENIA] skrócenie czasu
życia sesji w wariancie szkolnym (30 dni to wartość dobrana dla wygody, nie dla bezpieczeństwa).

---

### R11. Powiadomienia techniczne wysyłane poza EOG

**P = 2 · W = 1 · poziom = 2 (niskie) → szczątkowe: 1 (niskie)**

Aplikacja może wysyłać powiadomienia o cyklu życia zgłoszenia na czat obsługiwany przez
Telegram FZ-LLC (podmiot spoza EOG, bez zawartej umowy powierzenia). Powiadomienia zawierają
wyłącznie dane operacyjne: identyfikator zgłoszenia, oznaczenie zadania, liczbę zdjęć, wynik
i treść błędu — **bez imienia, nazwiska, e-maila i identyfikatora użytkownika**; opcjonalny,
nieodwracalny pseudonim jest domyślnie wyłączony. Sam identyfikator zgłoszenia jest jednak
danymi osobowymi pośrednio (pozwala administratorowi ustalić ucznia w panelu), a **treść błędu
— skracana do 500 znaków — może w skrajnym przypadku zawierać fragment odpowiedzi modelu
dotyczącej pracy ucznia.**

Środki: funkcja domyślnie wyłączona i włączana wyłącznie świadomą konfiguracją; **w wariancie B
zalecane pozostawienie wyłączonej** albo zastąpienie kanałem wewnętrznym szkoły (poczta
służbowa); przegląd treści komunikatów o błędach pod kątem możliwości wycieku treści pracy;
odnotowanie w rejestrze czynności przetwarzania, jeśli funkcja jest używana.

---

### R12. Tłumaczenie komunikatów o postępie przez zewnętrzną usługę

**P = 2 · W = 1 · poziom = 2 (niskie) → szczątkowe: 1 (niskie)**

Opcjonalna funkcja wysyła krótkie nagłówki toku rozumowania modelu do Google Cloud Translation
API w celu przetłumaczenia ich z angielskiego na polski i pokazania uczniowi jako komunikatu
o postępie. Nagłówki **dotyczą treści pracy ucznia** (np. „Sprawdzam uzasadnienie parzystości").
Jest to więc drugi, mniej oczywisty strumień danych do Google, łatwy do przeoczenia w rejestrze
czynności przetwarzania.

Środki: udokumentowanie funkcji w rejestrze i klauzuli informacyjnej, jeśli jest włączona;
rozważenie wyłączenia i zastąpienia stałą listą komunikatów po polsku (funkcja czysto
kosmetyczna, a usuwa cały strumień danych); w wariancie B — domyślnie wyłączona.

---

### R13. Dane osobowe w dziennikach aplikacji

**P = 3 · W = 1 · poziom = 3 (średnie) → szczątkowe: 1 (niskie)**

Dzienniki kontenera zawierają informacje o logowaniach, nazwy i rozmiary plików, wyniki
punktowe i treści błędów. **Adresy e-mail i identyfikatory użytkowników są w nich maskowane**
(`app/privacy.py`: `jan***@***`), co usuwa główny problem — w dziennikach nie ma już danych
wprost identyfikujących dziecko. **Rotacja dzienników została skonfigurowana** — sterownik
`json-file` z limitem 50 MB × 5 plików na usługę (`docker-compose.prod.yml`, kotwica
`x-logging`) — więc dzienniki nie gromadzą się już bez końca. Pozostaje ograniczenie tego
rozwiązania: jest to limit **objętości, a nie czasu**, więc przy niskim ruchu wpis może
przetrwać dłużej, niż wynikałoby z deklarowanego okresu; dodatkowo maskowany prefiks trzech
znaków wraz z kontekstem może w małej grupie pozwolić na powiązanie z osobą.

Środki: **[WDROŻONE]** maskowanie adresów e-mail i identyfikatorów w dziennikach;
**[WDROŻONE]** rotacja dzienników z twardym limitem objętości; **[DO ROZWAŻENIA]** rotacja
czasowa poza sterownikiem `json-file`, gdyby administrator chciał deklarować ścisły okres
przechowywania; ograniczenie dostępu do dzienników do osób upoważnionych.

---

### R14. Ujawnienie danych przy zmianie administratora i wygaszaniu serwisu publicznego

**P = 1 · W = 2 · poziom = 2 (niskie) → szczątkowe: 1 (niskie)**

Scenariusz docelowy zakłada, że szkoła uruchomi własną instancję, a serwis publiczny zostanie
wygaszony. Ryzykiem jest tu **nieuprawnione przekazanie bazy danych** między dwoma odrębnymi
administratorami — technicznie łatwe („po prostu skopiujemy bazę"), prawnie wymagające
odrębnej podstawy, której nie ma.

Środki: przyjęcie wprost, że **dane z serwisu publicznego nie są przekazywane szkole**; instancja
szkolna startuje z pustą bazą; użytkownicy serwisu publicznego są informowani o terminie
wygaszenia z wyprzedzeniem [UZUPEŁNIĆ: np. 30 dni] i mają w tym czasie możliwość pobrania
własnych danych; po wygaszeniu — trwałe usunięcie bazy, plików i kopii zapasowych, potwierdzone
notatką. Otwarty kod na licencji MIT umożliwia szkole uruchomienie narzędzia bez jakiegokolwiek
transferu danych — i to jest właśnie powód, dla którego wybrano tę drogę.

---

### R15. Brak weryfikacji wieku i zgody rodzica (dotyczy wariantu A)

**P = 3 · W = 2 · poziom = 6 (wysokie) → szczątkowe: 4 (średnie)**

Serwis publiczny opiera przetwarzanie na zgodzie, a jego użytkownikami są w większości dzieci
poniżej 16 lat. Art. 8 ust. 2 RODO wymaga „rozsądnych starań" o weryfikację, że zgodę wyraziła
lub zaaprobowała osoba sprawująca władzę rodzicielską. Obecnie serwis: **nie pyta o wiek**
i **nie weryfikuje zgody rodzica** — dysponuje wyłącznie polem wyboru z akceptacją regulaminu.
Konsekwencją jest ryzyko, że przetwarzanie odbywa się bez ważnej podstawy prawnej, co jest wadą
poważniejszą niż którekolwiek z ryzyk technicznych w tym rejestrze.

Środki:

- pytanie o rok urodzenia (lub wybór „mam mniej niż 16 lat") przy pierwszym logowaniu,
- dla użytkowników poniżej 16 lat — potwierdzenie zgody przez rodzica: podanie adresu e-mail
  rodzica i potwierdzenie odnośnikiem wysłanym na ten adres (mechanizm dwustopniowy).
  To rozwiązanie proporcjonalne do niskiego ryzyka usługi, zgodne z art. 8 ust. 2
  („z uwzględnieniem dostępnej technologii"). Wymaga przetwarzania jednej dodatkowej danej
  (adresu e-mail rodzica) — należy ją objąć retencją i klauzulą,
- do czasu wdrożenia: wyraźna, widoczna informacja przed logowaniem, że osoba poniżej 16 lat
  może korzystać z serwisu wyłącznie za wiedzą i zgodą rodzica, oraz łatwa ścieżka kontaktu dla
  rodzica żądającego usunięcia konta dziecka,
- **rozwiązanie docelowe i najlepsze: wariant B.** W instancji szkolnej problem znika, bo
  podstawą nie jest zgoda, lecz zadanie realizowane w interesie publicznym, a uczeń loguje się
  kontem szkolnym. Jest to istotny argument merytoryczny za przejściem na model szkolny,
  niezależny od względów organizacyjnych.

Ryzyko szczątkowe pozostaje średnie, bo żaden mechanizm weryfikacji wieku dostępny w darmowej
usłudze internetowej nie jest szczelny.

---

### R16. Przechowywanie bezterminowe i brak przeglądu

**P = 3 · W = 2 · poziom = 6 (wysokie) → szczątkowe: 2 (niskie)**

Przed wdrożeniem mechanizmu retencji zgłoszenia, fotografie i konta były przechowywane
bezterminowo, co naruszało art. 5 ust. 1 lit. e RODO. Fotografia pracy sprzed trzech lat nie służy
już żadnemu celowi, a nadal stanowi zbiór danych dziecka.

Środki: wdrożony mechanizm automatycznej retencji uruchamiany raz na dobę, usuwający
przeterminowane zgłoszenia razem z fotografiami, wcześniej usuwający dosłowny zapis rozumowania
modelu i sprzątający pliki osierocone (**wymaga skonfigurowania konkretnych wartości — pola do
uzupełnienia w sekcji 2.7**); samodzielne usuwanie konta przez użytkownika wraz ze wszystkimi
zdjęciami i historią; objęcie retencją także dzienników (R13) i kopii zapasowych; jednorazowe
usunięcie danych zgromadzonych przed wdrożeniem retencji i wykraczających poza nowe okresy —
[UZUPEŁNIĆ: termin wykonania].

**[WDROŻONE] wygasanie kont nieaktywnych** (36 miesięcy bez logowania i bez zgłoszenia) —
zamyka wcześniejszą lukę polegającą na tym, że po usunięciu zgłoszeń zostawało „puste" konto
z identyfikatorem Google, adresem e-mail i nazwiskiem dziecka. Aktywność liczona jako późniejsza
z dat: ostatniego logowania i ostatniego zgłoszenia.

**Pozostała luka:** kopie zapasowe nadal nie mają ustalonego okresu, a dzienniki aplikacji są
ograniczone objętościowo, a nie czasowo (R13) — dlatego ryzyko szczątkowe wynosi **2 (niskie)**
zamiast możliwego 1.

---

### R17. Utrata rozliczalności — brak rejestru czynności i dokumentacji

**P = 2 · W = 2 · poziom = 4 (średnie) → szczątkowe: 1 (niskie)**

Niniejsza DPIA nie zastępuje pozostałych obowiązków dokumentacyjnych. W wariancie A brakuje
rejestru czynności przetwarzania (art. 30 — wyjątek dla podmiotów poniżej 250 osób **nie ma
zastosowania**, bo przetwarzanie nie ma charakteru sporadycznego i obejmuje dane dzieci),
procedury reakcji na naruszenie i procedury obsługi żądań osób.

Środki: sporządzenie rejestru czynności przetwarzania (wariant B — wpisanie czynności do rejestru
szkoły); procedura reakcji na naruszenie; procedura obsługi żądań z terminem miesiąca (art. 12
ust. 3); ewidencja upoważnień; w wariancie B — weryfikacja, czy narzędzie ujęto w polityce
ochrony danych szkoły i czy poinformowano IOD.

---

## 6. Podsumowanie ryzyk i ryzyko szczątkowe (art. 35 ust. 7 lit. c)

| # | Ryzyko | Przed środkami | Po środkach |
|---|---|---|---|
| R1 | Błędna ocena i jej wpływ na dziecko | **6 wysokie** | 3 średnie |
| R2 | Informacja zwrotna ujawniająca rozwiązanie | 2 niskie | 2 niskie |
| R3 | Wgląd administratora/nauczyciela w niepowodzenia ucznia | 4 średnie | 2 niskie (dziennik dostępu wdrożony) |
| R4 | Dane nadmiarowe na fotografii kartki (w tym EXIF/GPS) | **6 wysokie** | 3 średnie |
| R5 | Manipulacja oceną i skutki fałszywej detekcji | 4 średnie | 2 niskie |
| R6 | Przekazanie danych do USA | 4 średnie | 3 średnie |
| R7 | Uzależnienie od jednego dostawcy AI | 2 niskie | 2 niskie |
| R8 | Limity i koszt jako mechanizm dostępności | 2 niskie | 1 niskie (znacznik po usunięciu konta wdrożony) |
| R9 | Naruszenie bezpieczeństwa serwera lub bazy | **6 wysokie** | 3 średnie |
| R10 | Przejęcie sesji | 2 niskie | 2 niskie |
| R11 | Powiadomienia poza EOG | 2 niskie | 1 niskie |
| R12 | Tłumaczenie komunikatów przez usługę zewnętrzną | 2 niskie | 1 niskie |
| R13 | Dane osobowe w dziennikach | 3 średnie | 1 niskie (maskowanie i rotacja wdrożone) |
| R14 | Zmiana administratora i wygaszenie serwisu | 2 niskie | 1 niskie |
| R15 | Brak weryfikacji wieku i zgody rodzica (wariant A) | **6 wysokie** | 4 średnie |
| R16 | Przechowywanie bezterminowe | **6 wysokie** | 2 niskie (retencja i wygasanie kont wdrożone) |
| R17 | Braki w dokumentacji i rozliczalności | 4 średnie | 1 niskie |

**Ryzyka pozostające po zastosowaniu środków — świadomie zaakceptowane:**

1. **Błędna ocena (R1, poziom średni).** Nieusuwalne z natury narzędzia. Akceptowalne wyłącznie
   dlatego, że ocena nie ma skutków formalnych i jest oznaczona jako pochodząca od AI. Gdyby
   którykolwiek z tych warunków przestał obowiązywać, ryzyko wraca do poziomu wysokiego
   i wymaga ponownej oceny.
2. **Dane nadmiarowe na fotografii (R4, poziom średni).** Ograniczalne instrukcją i retencją,
   ale zależne od zachowania dziecka.
3. **Transfer do USA (R6, poziom średni).** Zależny od trwałości decyzji o adekwatności,
   pozostającej poza wpływem administratora. Wymaga monitorowania.
4. **Bezpieczeństwo infrastruktury (R9, poziom średni).** Typowe dla każdego wdrożenia
   samodzielnie utrzymywanego; obniżane środkami organizacyjnymi, nie eliminowane.
5. **Weryfikacja wieku (R15, poziom średni, tylko wariant A).** Znika w wariancie B.

**Czy wymagane są uprzednie konsultacje z Prezesem UODO (art. 36 ust. 1)?**
Konsultacja jest obowiązkowa, gdy DPIA wskazuje, że przetwarzanie powodowałoby **wysokie
ryzyko mimo zastosowania środków**. Po wdrożeniu wszystkich środków z sekcji 5 żadne ryzyko nie
pozostaje na poziomie wysokim. **Wstępny wniosek: uprzednie konsultacje nie są wymagane** —
z zastrzeżeniem, że wniosek ten jest ważny wyłącznie przy spełnieniu warunków brzegowych:
płatny poziom API, ocena bez skutków formalnych, wdrożona retencja, wdrożona weryfikacja zgody
rodzica (wariant A). **Ocena ta wymaga potwierdzenia przez inspektora ochrony danych.**

---

## 7. Zgodność z innymi reżimami prawnymi

### 7.1 Akt o sztucznej inteligencji (rozporządzenie 2024/1689)

**Role.** Podmiot, który udostępnia system AI pod własną nazwą, jest **dostawcą**; szkoła
korzystająca z narzędzia we własnej działalności jest **podmiotem stosującym** (deployer).
W wariancie B szkoła, uruchamiając własną instancję z otwartego kodu, może wejść w rolę
dostawcy — [DO USTALENIA z prawnikiem; ma to znaczenie dla zakresu obowiązków].

**Klasyfikacja ryzyka.** Załącznik III do AI Act obejmuje w obszarze edukacji m.in. systemy
przeznaczone do oceny efektów uczenia się. Narzędzie ocenia rozwiązania zadań, więc pytanie
o klasyfikację jest realne i nie można go zbyć. Argumentacja za pozostawieniem poza kategorią
wysokiego ryzyka opiera się na **art. 6 ust. 3 AI Act**: system nie stwarza istotnego ryzyka
szkody dla praw podstawowych, ponieważ nie wpływa istotnie na wynik podejmowania decyzji —
jego wynik nie jest oceną szkolną, nie wpływa na klasyfikację, promocję ani rekrutację
(art. 44b ustawy o systemie oświaty pozostawia ocenianie nauczycielowi), a korzystanie
z narzędzia jest dobrowolne.

Warunki utrzymania tej kwalifikacji:

- zapisy z sekcji 2.8 muszą pozostać w regulaminie i w praktyce szkoły,
- ocena z narzędzia nie może być wpisywana do dziennika ani stanowić podstawy oceny,
- korzystanie z art. 6 ust. 3 wymaga **udokumentowania oceny przed wprowadzeniem systemu do
  używania**; przy klasyfikacji z Załącznika III towarzyszy temu obowiązek rejestracji
  w bazie danych UE. **Do potwierdzenia przez prawnika.**

Gdyby szkoła zaczęła wykorzystywać wyniki do oceniania — system staje się systemem wysokiego
ryzyka ze wszystkimi tego konsekwencjami. To najważniejsza granica w całym dokumencie.

**Terminy.** Obowiązki dotyczące systemów wysokiego ryzyka z Załącznika III zostały przesunięte
przepisami tzw. Digital Omnibus (wejście w życie 27.07.2026) z 2 sierpnia 2026 r. na
**2 grudnia 2027 r.** Obowiązki przejrzystości z art. 50 stosuje się od **2 sierpnia 2026 r.**
Art. 4 (kompetencje w zakresie AI) stosuje się od **2 lutego 2025 r.**

**Art. 50 — przejrzystość.** Użytkownik musi wiedzieć, że wchodzi w interakcję z systemem AI
i że treść, którą czyta, została wygenerowana przez AI. Realizacja: oznaczenie przy każdym
wyniku i informacji zwrotnej, oznaczenie treści generowanych przez AI w pozostałych miejscach
serwisu (wskazówki do zadań, opisy trudności i kategorii, treści zadań przepisane do postaci
LaTeX), zapis w regulaminie.

**Art. 4 — kompetencje w zakresie AI.** Dostawcy i podmioty stosujące mają zapewnić
odpowiedni poziom kompetencji AI u osób zajmujących się obsługą i użytkowaniem systemów.
W wariancie B obejmuje to nauczycieli korzystających z narzędzia: powinni rozumieć, na czym
polega ocena przez model, jakie są jej ograniczenia i dlaczego nie wolno jej traktować jak
oceny szkolnej. **Uwaga:** art. 99 AI Act nie przewiduje bezpośredniej sankcji pieniężnej za
naruszenie samego art. 4 — w obiegu publicznym powielana jest błędna informacja o karze
7,5 mln EUR za ten przepis. Nie należy jej powtarzać w dokumentach szkoły.

### 7.2 Ustawa krajowa o systemach sztucznej inteligencji

Ustawa z 3 lipca 2026 r. o systemach sztucznej inteligencji (Dz.U. 2026 poz. 1003) — główne
przepisy weszły w życie 11 sierpnia 2026 r. Organem nadzoru jest **KRiBSI**. Przepisy dotyczące
kontroli i kar stosuje się od 28 października 2026 r. Przy wdrożeniu szkolnym należy sprawdzić,
czy ustawa nakłada obowiązki zgłoszeniowe lub informacyjne na podmiot stosujący —
[DO USTALENIA z prawnikiem; nie opisano tu szczegółów, by nie zgadywać].

### 7.3 Prawo oświatowe

Ocenianie osiągnięć edukacyjnych ucznia jest zadaniem nauczyciela (art. 44b ustawy z 07.09.1991
o systemie oświaty). Wyniki z narzędzia nie mogą być ocenami szkolnymi ani ich substytutem.
Jeżeli narzędzie ma być używane na lekcji, warto rozważyć wzmiankę w statucie lub w programie
zajęć — [DO USTALENIA ze szkołą].

### 7.4 Prawo autorskie — zidentyfikowane ryzyko, nierozwiązane

To ryzyko nie dotyczy ochrony danych, ale jest istotne dla obu wariantów i zostaje odnotowane
uczciwie, jako otwarte.

Treści zadań olimpijskich są utworami w rozumieniu ustawy z 04.02.1994 o prawie autorskim
i prawach pokrewnych. Organizatorem olimpiady jest Stowarzyszenie na rzecz Edukacji
Matematycznej. Stan faktyczny:

- serwis hostuje **162 własne kopie plików PDF (ok. 80 MB)** z zadaniami i rozwiązaniami
  wzorcowymi, serwowane **publicznie, bez logowania**,
- serwis udostępnia **pełne treści zadań przepisane do postaci LaTeX** (352 pliki metadanych),
  również publicznie,
- pliki PDF są ponadto **przekazywane do dostawcy AI** (zwielokrotnienie i udostępnienie
  podmiotowi trzeciemu),
- **nie ustalono publicznej licencji zezwalającej na taką redystrybucję.** Prawo cytatu
  (art. 29) nie obejmuje udostępniania utworów w całości.

W **wariancie A** (osoba prywatna) nie przysługuje żaden dozwolony użytek, który by to
legalizował. Rekomendacja: uzyskać pisemną zgodę Stowarzyszenia na rzecz Edukacji Matematycznej
albo zastąpić własne kopie odnośnikami do materiałów na `omj.edu.pl`.

W **wariancie B** zastosowanie może mieć art. 27 ustawy o prawie autorskim — instytucje
oświatowe mogą korzystać z rozpowszechnionych utworów w celach dydaktycznych. Przepis ma jednak
warunek, który zmienia architekturę wdrożenia: w przypadku publicznego udostępniania utworów
w sposób umożliwiający dostęp w wybranym miejscu i czasie korzystanie jest dozwolone **wyłącznie
dla ograniczonego kręgu osób uczących się i nauczających, zidentyfikowanych przez instytucję**.
Praktycznie oznacza to, że w instancji szkolnej **pliki PDF i pełne treści zadań muszą być
dostępne dopiero po zalogowaniu**, wyłącznie dla uczniów i nauczycieli tej szkoły — inaczej niż
w serwisie publicznym, gdzie są dostępne dla każdego.

**Rekomendacja dla wdrożenia szkolnego (do wykonania przed uruchomieniem):** zamknąć dostęp do
`/pdf/...` i do pełnych treści zadań za uwierzytelnieniem. **Nie jest to obecnie zaimplementowane
w kodzie** — wymaga zmiany, której autor niniejszego dokumentu nie wprowadził.

---

## 8. Plan wdrożenia środków

Kolumny do wypełnienia przez administratora — to jest lista zadań, nie deklaracja stanu.

| # | Środek | Ryzyko | Priorytet | Odpowiedzialny | Termin | Status |
|---|---|---|---|---|---|---|
| 1 | ~~Ustalić i skonfigurować okresy retencji (sekcja 2.7)~~ | R16 | wysoki | autor | — | **WDROŻONE** (24 mies. / 90 dni / 36 mies. / 12 mies.); wariant B potwierdza wartości |
| 1a | ~~Dodać automatyczne usuwanie kont nieaktywnych~~ | R16 | wysoki | autor | — | **WDROŻONE** (36 miesięcy bez aktywności) |
| 2 | Usuwać metadane EXIF ze **wszystkich** fotografii, nie tylko zmniejszanych | R4 | wysoki | [ ] | [ ] | [ ] |
| 3 | Wdrożyć weryfikację wieku i zgody rodzica (wariant A) | R15 | wysoki | [ ] | [ ] | [ ] |
| 4 | ~~Wdrożyć rejestr dostępu administratora do cudzych danych~~ | R3 | wysoki | autor | — | **WDROŻONE** (`admin_access_log`, retencja 12 mies.) |
| 4a | Wprowadzić okresowy przegląd dziennika dostępu przez osobę inną niż administrator | R3 | średni | [ ] | [ ] | [ ] |
| 5 | Oznaczyć w interfejsie każdą treść pochodzącą od AI | R1, art. 50 AI Act | wysoki | [ ] | [ ] | [ ] |
| 6 | Sporządzić rejestr czynności przetwarzania | R17 | wysoki | [ ] | [ ] | [ ] |
| 7 | Opracować procedurę reakcji na naruszenie (72 h) | R9, R17 | wysoki | [ ] | [ ] | [ ] |
| 8 | Zamknąć dostęp do PDF i treści zadań za logowaniem (wariant B) | prawo autorskie | wysoki | [ ] | [ ] | [ ] |
| 9 | Potwierdzić, że klucz API jest kluczem płatnym | warunek brzegowy | wysoki | [ ] | [ ] | [ ] |
| 10 | Ustawić rotację i retencję dzienników aplikacji (maskowanie adresów e-mail **już wdrożone**) | R13 | średni | [ ] | [ ] | [ ] |
| 11 | Zautomatyzować i przetestować kopie zapasowe; zaszyfrować | R9 | średni | [ ] | [ ] | [ ] |
| 12 | Wystawić upoważnienia do przetwarzania (art. 29) | R3 | średni | [ ] | [ ] | [ ] |
| 13 | Dobrać limity zgłoszeń do liczebności grupy | R8 | średni | [ ] | [ ] | [ ] |
| 14 | Wyłączyć powiadomienia zewnętrzne i tłumaczenie w wariancie szkolnym | R11, R12 | średni | [ ] | [ ] | [ ] |
| 15 | Przeszkolić nauczycieli (art. 4 AI Act) | R1, AI Act | średni | [ ] | [ ] | [ ] |
| 16 | Udokumentować ocenę z art. 6 ust. 3 AI Act | AI Act | średni | [ ] | [ ] | [ ] |
| 17 | Uregulować prawa do treści zadań (zgoda SEM lub odnośniki) | prawo autorskie | średni | [ ] | [ ] | [ ] |
| 18 | Wprowadzić przegląd próbki ocen i mierzyć odsetek błędnych | R1 | niski | [ ] | [ ] | [ ] |
| 19 | Rozważyć skrócenie czasu życia sesji poniżej 30 dni | R10 | niski | [ ] | [ ] | [ ] |
| 20 | Rozważyć rezygnację z zapisywania imienia i nazwiska | 3.1 | niski | [ ] | [ ] | [ ] |

---

## 9. Przegląd i aktualizacja

DPIA podlega przeglądowi co najmniej raz na 12 miesięcy oraz **niezwłocznie** w razie:

- zmiany dostawcy lub modelu AI albo zmiany warunków przetwarzania danych przez dostawcę,
- przejścia na bezpłatny poziom API (unieważnia wnioski oceny),
- jakiejkolwiek zmiany zasady, że wynik nie jest oceną szkolną,
- rozszerzenia kręgu osób mających dostęp do danych uczniów,
- upadku lub zawieszenia decyzji o adekwatności dla przekazań do USA,
- naruszenia ochrony danych związanego z narzędziem,
- zmiany stanu prawnego (AI Act, ustawa krajowa o AI, przepisy oświatowe).

Wynik każdego przeglądu odnotowuje się w tabeli poniżej.

| Data | Zakres przeglądu | Wynik | Podpis |
|---|---|---|---|
| [ ] | [ ] | [ ] | [ ] |

---

## 10. Zasięgnięcie opinii

| Podmiot | Czy zasięgnięto | Data | Stanowisko |
|---|---|---|---|
| Inspektor ochrony danych (art. 35 ust. 2) | [ ] | [ ] | [ ] |
| Osoby, których dane dotyczą, lub ich przedstawiciele (art. 35 ust. 9) — np. rada rodziców, samorząd uczniowski | [ ] | [ ] | [ ] |
| Radca prawny / obsługa prawna szkoły | [ ] | [ ] | [ ] |
| Podmiot odpowiedzialny za bezpieczeństwo IT | [ ] | [ ] | [ ] |

Art. 35 ust. 9 RODO: administrator w stosownych przypadkach zasięga opinii osób, których dane
dotyczą. Przy narzędziu dla dzieci konsultacja z radą rodziców i samorządem uczniowskim jest
zalecana — także dlatego, że pozwala sprawdzić, czy informacja o narzędziu jest dla nich
zrozumiała (art. 12 ust. 1 RODO wymaga formy przystępnej dla dziecka).
