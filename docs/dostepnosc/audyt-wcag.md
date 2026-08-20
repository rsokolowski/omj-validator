# Audyt dostępności cyfrowej — Trener OMJ (omj-validator.pl)

**Zakres:** frontend aplikacji (Next.js 16 / React 19 / Material-UI v7), katalogi `frontend/src/app`, `frontend/src/components`, `frontend/src/lib`.
**Podstawa prawna:** ustawa z dnia 4 kwietnia 2019 r. o dostępności cyfrowej stron internetowych i aplikacji mobilnych podmiotów publicznych (Dz.U. 2019 poz. 848), załącznik — WCAG 2.1 na poziomie AA.
**Data audytu:** 20 sierpnia 2026 r.
**Metoda:** analiza kodu źródłowego (stan drzewa roboczego repozytorium) + testy w przeglądarce Chromium (Playwright) na wersji produkcyjnej https://omj-validator.pl + obliczenia współczynników kontrastu wg wzoru WCAG + uruchomienie lintera `eslint-plugin-jsx-a11y` w zestawie `recommended`.
**Czego NIE zrobiono:** testów z prawdziwym czytnikiem ekranu (NVDA/JAWS/VoiceOver), testów z udziałem użytkowników, testów części aplikacji dostępnych wyłącznie po zalogowaniu przez Google. Zakres tych ograniczeń opisuje rozdział 6.

---

## 1. Streszczenie dla dyrekcji

**Czy serwis spełnia dziś wymagania ustawy? Nie.** Serwis jest **częściowo zgodny** z WCAG 2.1 AA. Nie nadaje się w obecnej postaci do wdrożenia jako narzędzie publicznej szkoły podstawowej, zwłaszcza szkoły z oddziałami integracyjnymi.

**Jak daleko mu do zgodności?** Bliżej, niż mogłoby się wydawać. Fundament jest zrobiony dobrze — i to jest najważniejsza dobra wiadomość tego audytu:

- **Wzory matematyczne są dostępne.** To był największy znak zapytania. Biblioteka KaTeX generuje dla każdego wzoru równoległą wersję w formacie MathML (zrozumiałym dla czytników ekranu), a wersję graficzną poprawnie ukrywa przed czytnikiem. Sprawdzono to na żywej stronie: na jednej stronie zadania znajduje się 16 wzorów i wszystkie mają wersję MathML. Gdyby tego zabrakło, serwis wymagałby przepisania od zera.
- Strony mają poprawnie zadeklarowany język polski, ikony są prawidłowo oznaczone jako dekoracyjne, obramowanie fokusu klawiatury nie zostało usunięte, a zwinięte sekcje są poprawnie ukrywane przed czytnikiem ekranu.

**Co jest zepsute?** Pięć rzeczy blokujących i kilkanaście poważnych. Trzy najgorsze:

1. **Uczeń korzystający wyłącznie z klawiatury nie prześle rozwiązania.** Pole wyboru zdjęcia jest schowane w sposób, który usuwa je z kolejności tabulacji, a klikalny obszar „Przeciągnij zdjęcia" to zwykły blok tekstu, którego klawiatura nie widzi. To główna funkcja serwisu i jest ona dziś niedostępna dla ucznia z niesprawnością ruchową, dla ucznia niewidomego i dla każdego, kto nie używa myszy.
2. **Ocenianie trwa kilkanaście sekund i przebiega w ciszy.** Uczeń niewidomy wysyła zdjęcie i nie dostaje żadnej informacji, że cokolwiek się dzieje — komunikaty „Przesyłam pliki…", „Analizuję rozwiązanie…" pojawiają się na ekranie, ale nie są przekazywane czytnikowi ekranu. (Sam wynik końcowy na szczęście jest ogłaszany.)
3. **Na telefonie o wąskim ekranie strona przewija się w bok.** Sprawdzono pomiarem: przy szerokości 320 px treść ma 379 px. Osoba słabowidząca, która powiększy stronę, będzie musiała przewijać każdą linijkę tekstu w dwóch kierunkach.

Do tego dochodzi zestaw kolorów, w którym kilkanaście par „tekst na tle" nie osiąga wymaganego kontrastu (najgorsze: gwiazdki poziomu trudności — 1,92:1 przy wymaganych 4,5:1), brak linku „przejdź do treści", pomieszana hierarchia nagłówków i animowany obrazek na stronie głównej, który zapętla się bez końca i którego nie da się zatrzymać.

**Ile to realnie pracy?** Dla jednego doświadczonego programisty frontendu:

| Etap | Nakład |
|---|---|
| Usunięcie 5 blokerów (rozdz. 4, priorytet 1) | ok. 3 dni robocze |
| Usunięcie usterek poważnych (priorytet 2) | ok. 5 dni roboczych |
| Testy z czytnikiem ekranu NVDA + poprawki po testach | ok. 2 dni robocze |
| Sporządzenie i publikacja deklaracji dostępności | ok. 0,5 dnia |
| **Razem** | **ok. 10–11 dni roboczych (2–2,5 tygodnia)** |

To nie jest przepisywanie aplikacji. To jest seria punktowych poprawek w kilkunastu plikach. Żadna z nich nie wymaga zmiany architektury.

**Rekomendacja:** nie uruchamiać serwisu pod szyldem szkoły przed usunięciem blokerów z priorytetu 1 i opublikowaniem deklaracji dostępności. Projekt deklaracji przygotowano w pliku [`deklaracja-dostepnosci.md`](./deklaracja-dostepnosci.md).

---

## 2. Ustalenia — uporządkowane wg wpływu na użytkownika

Odniesienia do plików wskazują stan **drzewa roboczego repozytorium** z 20.08.2026 (część plików ma niezacommitowane zmiany, numery linii mogą się nieznacznie przesunąć). Weryfikacja w przeglądarce dotyczy wersji wdrożonej na produkcji.

### Priorytet 1 — blokery uruchomienia

---

#### B1. Przesłanie zdjęcia rozwiązania jest niemożliwe z klawiatury

**Gdzie:** `frontend/src/components/task/SubmitSection.tsx:296` (obszar upuszczania), `frontend/src/components/task/SubmitSection.tsx:321-329` (ukryte pole pliku)

**Na czym polega problem.** Obszar „Przeciągnij zdjęcia lub kliknij, aby wybrać" to element `<Box>` (czyli `<div>`) z podpiętym wyłącznie `onClick`. Nie ma `tabIndex`, nie ma `role="button"`, nie ma obsługi `onKeyDown`. Ukryte pod nim pole `<input type="file">` ma `style={{ display: "none" }}` — a `display: none` usuwa element z kolejności tabulacji i z drzewa dostępności całkowicie. Nie ma też elementu `<label>` powiązanego z polem.

W efekcie: nie istnieje żadna ścieżka klawiaturowa prowadząca do wyboru pliku. Tabulacja przeskakuje z linku „Zgłoś błąd" wprost na przycisk „Prześlij rozwiązanie", który jest w tym momencie nieaktywny (`disabled={files.length === 0}`), więc użytkownik trafia w ślepy zaułek.

**Kryteria WCAG:** 2.1.1 Klawiatura (poziom A) — niespełnione; 4.1.2 Nazwa, rola, wartość (poziom A) — niespełnione; 3.3.2 Etykiety lub instrukcje (poziom A) — niespełnione.

**Kto na tym traci:** użytkownik czytnika ekranu (całkowicie), osoba korzystająca wyłącznie z klawiatury (całkowicie), osoba używająca przełącznika/sterowania głosem (całkowicie). To główna funkcja serwisu.

**Jak naprawić w tym kodzie.** Zamienić ukryte pole na etykietę-przycisk i zachować przeciąganie jako dodatek, a nie jako jedyną drogę:

```tsx
// zamiast style={{ display: "none" }} — technika "visually hidden"
const visuallyHidden = {
  position: "absolute", width: 1, height: 1, padding: 0, margin: -1,
  overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap", border: 0,
} as const;

<Button component="label" variant="outlined" disabled={isProcessing}>
  Wybierz zdjęcia rozwiązania
  <Box component="input" sx={visuallyHidden}
       ref={fileInputRef} type="file" accept="image/*" multiple
       onChange={handleFileSelect} disabled={isProcessing} />
</Button>
```

Obszar `<Box>` z `onDrop` zostawić jako wzbogacenie dla myszy, ale usunąć z niego `onClick` jako jedyny sposób działania i dodać `aria-hidden` na sam tekst instrukcji przeciągania, albo — prościej — nadać obszarowi `role="button" tabIndex={0}` i obsługę `onKeyDown` dla `Enter`/`Space`. Przycisk `component="label"` jest rozwiązaniem czystszym i mniej podatnym na regresje.

Dodatkowo: przycisk „Usuń" przy każdym pliku (`SubmitSection.tsx:363-370`) ma dla wszystkich plików identyczną nazwę dostępną. Dodać `aria-label={`Usuń plik ${file.name}`}`.

**Nakład:** 0,5 dnia (wraz z testem klawiaturowym).

**Weryfikacja:** wyłącznie analiza kodu — sekcja przesyłania jest dostępna dopiero po zalogowaniu przez Google, więc nie dało się jej przetestować w przeglądarce. Kod jest jednak jednoznaczny: `display: none` bezwarunkowo usuwa element z kolejności tabulacji.

---

#### B2. Przebieg oceniania (kilkanaście sekund) nie jest ogłaszany czytnikowi ekranu

**Gdzie:** `frontend/src/components/task/SubmitSection.tsx:376-394` (blok statusu), `frontend/src/components/task/SubmitSection.tsx:126-132` (obsługa wiadomości WebSocket typu `status`)

**Na czym polega problem.** Po wysłaniu zdjęć aplikacja otwiera połączenie WebSocket i odbiera strumień komunikatów o postępie. Backend wysyła kolejno „Przesyłam pliki…", „Analizuję rozwiązanie…", „Finalizowanie…" oraz tłumaczone nagłówki od modelu (`app/websocket/handler.py:79,101,133`, `app/websocket/progress.py:171`). Frontend wstawia je do zwykłego `<Typography>` wewnątrz `<Box>`. Nie ma tam `aria-live`, `role="status"` ani `aria-busy`.

**Zweryfikowano w przeglądarce:** na stronie zadania liczba elementów z `aria-live`, `role="status"` lub `role="alert"` wynosi **0**.

Kręcący się wskaźnik `<CircularProgress>` jest czystą grafiką (MUI renderuje `<svg aria-hidden="true">`), więc też nic nie komunikuje. Uczeń niewidomy naciska „Prześlij rozwiązanie", przycisk zmienia napis na „Przetwarzanie…" (to akurat zostanie odczytane, jeśli fokus pozostał na przycisku) i przez kilkanaście sekund nie dzieje się nic, co da się usłyszeć.

**Kryteria WCAG:** 4.1.3 Komunikaty o stanie (poziom AA) — niespełnione.

**Kto na tym traci:** użytkownik czytnika ekranu, użytkownik lupy ekranowej patrzący w inny fragment strony, osoba z trudnościami poznawczymi (brak potwierdzenia, że akcja się powiodła).

**Jak naprawić.** Otoczyć blok statusu regionem żywym o uprzejmości `polite` i renderować go zawsze (region żywy dodany do DOM razem z treścią bywa pomijany przez czytniki):

```tsx
{/* zawsze w DOM, nie tylko gdy isProcessing */}
<Box role="status" aria-live="polite" aria-atomic="true" sx={visuallyHidden}>
  {isProcessing ? (uploadState.statusMessage || "Przetwarzanie rozwiązania…") : ""}
</Box>
```

i osobno zostawić widoczny blok z `<CircularProgress>` bez `aria-live`, żeby komunikat nie był ogłaszany dwa razy.

**Stan pozytywny do zachowania:** wynik końcowy jest ogłaszany. Komponent MUI `<Alert>` domyślnie ustawia `role="alert"` (zweryfikowano w `frontend/node_modules/@mui/material/Alert/Alert.js:167`), więc treść „Wynik: 5 / 6 punktów" wraz z komentarzem trafia do czytnika. Warto jednak rozważyć zmianę na `role="status"` — `role="alert"` jest asertywne i przerywa czytanie, a informacja zwrotna od AI bywa długa.

**Nakład:** 0,5 dnia.

**Weryfikacja:** brak `aria-live` potwierdzony w przeglądarce; samo zachowanie w trakcie oceniania — wyłącznie analiza kodu (wymaga zalogowania).

---

#### B3. Brak linku „przejdź do treści", nawigacja główna poza znacznikiem `<nav>`, zaburzona hierarchia nagłówków

**Gdzie:** `frontend/src/app/layout.tsx:96-106`, `frontend/src/components/layout/Header.tsx:34-43` (logo jako `<h6>`), `frontend/src/components/layout/Header.tsx:47-87` (linki nawigacji w `<Box>`)

**Na czym polega problem — trzy powiązane usterki.**

*(a) Brak pominięcia do treści.* Zweryfikowano w przeglądarce: liczba linków `a[href^="#"]` na stronie zadania wynosi **0**. Element `<main>` nie ma `id`. Użytkownik klawiatury musi przy każdym przejściu na nową stronę przetabulować przez logo i 4–5 linków nawigacji, zanim dotrze do treści zadania.

*(b) Nawigacja główna nie jest punktem orientacyjnym.* Zweryfikowano: na stronie zadania istnieją punkty orientacyjne `HEADER`, `MAIN`, `NAV`, `FOOTER` — ale jedyny `<nav>` to okruszki (MUI `Breadcrumbs` renderuje `<nav aria-label="breadcrumb">`). Linki „Zadania / Nauka / Praktyka / Moje rozwiązania" siedzą w zwykłym `<Box>` (`Header.tsx:47`). Czytnik ekranu nie może przeskoczyć do menu głównego.

*(c) Hierarchia nagłówków jest zaburzona.* Zweryfikowano na żywej stronie zadania — kolejność nagłówków w kodzie HTML to:

```
H6: Trener OMJ          ← logo w nagłówku strony, PRZED H1
H1: Zadanie 1
H6: Treść zadania
H6: Umiejętności (3)
H6: Wymagane umiejętności:
H6: Zdobywane umiejętności:
H6: Wskazówki (0/4)
H6: Prześlij rozwiązanie
H6: O projekcie / H6: Linki / H6: Kontakt
```

Nie ma ani jednego `H2`, `H3`, `H4` ani `H5`. Na stronie głównej jest podobnie: `H6` (logo) → `H1` → `H2` → `H6`. Przyczyna jest techniczna: MUI `<Typography variant="h6">` domyślnie renderuje faktyczny element `<h6>`, a autorzy używali `variant="h6"` do doboru rozmiaru czcionki, nie do budowy struktury. Użytkownik czytnika ekranu, który nawiguje po nagłówkach (najczęstsza technika przeglądania strony), dostaje płaską listę bez informacji o zagnieżdżeniu, a nagłówek poziomu 6 pojawia się przed nagłówkiem poziomu 1.

Dotknięte pliki (wszystkie używają `variant="h6"` jako nagłówka sekcji): `frontend/src/components/task/SubmitSection.tsx:270,289`, `frontend/src/components/task/HintsSection.tsx:27`, `frontend/src/components/task/SkillsSection.tsx:28`, `frontend/src/components/task/SubmissionHistory.tsx:115`, `frontend/src/app/task/[year]/[etap]/[num]/page.tsx:134`, `frontend/src/components/progress/RecommendationsList.tsx:16`, `frontend/src/components/progress/Etap2PrepList.tsx:69`, `frontend/src/components/common/LoginPrompt.tsx:20`, `frontend/src/components/my-solutions/SubmissionsList.tsx:48`, `frontend/src/app/page.tsx:269,501`, `frontend/src/components/layout/Footer.tsx:45,70,116`. Osobno: `frontend/src/components/progress/ProgressStats.tsx:29` renderuje `<h3>` zawierający wyłącznie liczbę (np. „342") — to nie jest nagłówek.

**Kryteria WCAG:** 2.4.1 Możliwość pominięcia bloków (poziom A) — niespełnione; 1.3.1 Informacje i relacje (poziom A) — niespełnione; 2.4.6 Nagłówki i etykiety (poziom AA) — niespełnione częściowo.

**Kto na tym traci:** użytkownik czytnika ekranu (nawigacja po nagłówkach i punktach orientacyjnych to jego podstawowe narzędzie), osoba korzystająca wyłącznie z klawiatury (brak pominięcia bloków), osoba z trudnościami poznawczymi (brak czytelnej struktury).

**Jak naprawić.**

W `frontend/src/app/layout.tsx`:
```tsx
<body className="min-h-screen flex flex-col">
  <a href="#tresc-glowna" className="skip-link">Przejdź do treści głównej</a>
  ...
  <main id="tresc-glowna" tabIndex={-1} className="flex-1 py-8">
```
plus reguła w `frontend/src/app/globals.css` (link ukryty do momentu otrzymania fokusu):
```css
.skip-link { position: absolute; left: -9999px; }
.skip-link:focus { left: 1rem; top: 1rem; z-index: 2000; background: #fff;
  padding: .75rem 1rem; border: 2px solid var(--color-primary); border-radius: var(--radius); }
```

W `frontend/src/components/layout/Header.tsx`: otoczyć blok linków `<Box component="nav" aria-label="Nawigacja główna">` (linia 47) i zmienić logo z `variant="h6"` na `variant="h6" component="span"` (linia 34), żeby przestało być nagłówkiem.

We wszystkich wymienionych wyżej miejscach: dodać jawne `component="h2"` (albo `h3`, zgodnie z zagnieżdżeniem) tam, gdzie `variant="h6"` pełni funkcję nagłówka sekcji, oraz `component="p"` / `component="div"` tam, gdzie nie pełni. W `ProgressStats.tsx:29` zamienić `variant="h3"` na `variant="h3" component="p"`.

**Nakład:** 0,5 dnia.

**Weryfikacja:** w pełni zweryfikowane w przeglądarce (odczyt drzewa nagłówków i punktów orientacyjnych na żywej stronie).

---

#### B4. Strona wymaga przewijania w poziomie przy szerokości 320 px

**Gdzie:** `frontend/src/components/layout/Header.tsx:47` (`gap: 3` w pasku nawigacji, brak wersji mobilnej), `frontend/src/app/globals.css:84-87` (obsługa przepełnienia tylko dla wzorów blokowych)

**Na czym polega problem.** Zweryfikowano pomiarem w przeglądarce przy oknie 320 × 640 px:

| Strona | `document.scrollWidth` | Szerokość okna | Przewijanie poziome |
|---|---|---|---|
| `/` | 379 px | 320 px | **tak, 59 px nadmiaru** |
| `/task/2024/etap2/1` | 379 px | 320 px | **tak, 59 px nadmiaru** |

Winowajcą jest pasek nawigacji w nagłówku: „Zadania Nauka Praktyka Zaloguj" w kontenerze flex z odstępem 24 px, bez zawijania i bez menu hamburgerowego. Zmierzona krawędź prawa tego bloku to 379 px.

Osobno: wzory **wpisane w tekst** (inline) też wystają poza ekran — zmierzono element `∠DAE + ∠EBC = ∠ABE` o prawej krawędzi 338 px. Reguła `overflow-x: auto` w `globals.css:84` obejmuje tylko `.katex-display` (wzory blokowe), nie obejmuje `.katex` w tekście.

**Kryteria WCAG:** 1.4.10 Zawijanie tekstu / Reflow (poziom AA) — niespełnione. Kryterium wymaga, by treść dała się wyświetlić bez przewijania w dwóch kierunkach przy szerokości odpowiadającej 320 px CSS (czyli przy powiększeniu 400 % na ekranie 1280 px).

**Kto na tym traci:** osoba słabowidząca powiększająca stronę (przy powiększeniu 400 % musi przewijać każdą linijkę w bok), użytkownik telefonu o małym ekranie, użytkownik lupy ekranowej.

**Jak naprawić.**
- `Header.tsx`: dodać wersję mobilną nawigacji — menu w `<IconButton>` z `aria-label="Menu"` i `aria-expanded`, albo prostsze rozwiązanie: `flexWrap: "wrap"` i responsywny `gap: { xs: 1, sm: 3 }` z mniejszą czcionką na `xs`. Menu hamburgerowe jest lepsze, ale wymaga poprawnej pułapki fokusa w otwartym panelu.
- `globals.css`: dodać obsługę przepełnienia dla wzorów w tekście, np. `.math-content { overflow-wrap: anywhere; }` oraz `.math-content .katex { max-width: 100%; overflow-x: auto; }`. Uwaga: rozwiązanie wymaga sprawdzenia, czy nie psuje wyrównania linii bazowej wzorów w tekście — to trzeba obejrzeć w przeglądarce.

**Nakład:** 1 dzień (menu mobilne to najdroższy element w tym zestawieniu).

**Weryfikacja:** w pełni zweryfikowane pomiarem w przeglądarce.

---

#### B5. Animowany GIF na stronie głównej zapętla się bez końca i nie da się go zatrzymać

**Gdzie:** `frontend/src/app/page.tsx:380-388`, plik `frontend/public/images/omj-demo.gif`

**Na czym polega problem.** Zbadano plik: **27 klatek, 18,7 sekundy na pętlę, znacznik pętli `loop = 0` czyli nieskończona**, wymiary 1221 × 1218 px, rozmiar 909 KB. Animacja startuje automatycznie po wejściu na stronę główną (dodatkowo `<link rel="preload">` w nagłówku HTML przyspiesza jej pobranie), trwa dłużej niż 5 sekund i nie ma żadnej kontrolki pauzy, zatrzymania ani ukrycia.

Powiązane ustalenie: zweryfikowano, że w całym arkuszu stylów serwisu jest **0 reguł `@media (prefers-reduced-motion)`**. Dotyczy to także pulsującej ikony zegara w `frontend/src/components/practice/FloatingTimer.tsx:60-65` (animacja `pulse 1s infinite` przy końcówce czasu) oraz wszystkich efektów `transform: translateY(-2px)` przy najechaniu na kartę zadania.

**Kryteria WCAG:** 2.2.2 Pauza, zatrzymanie, ukrycie (poziom A) — niespełnione; 2.3.3 Animacja z interakcji (poziom AAA, poza obowiązkiem, ale wskazane).

**Kto na tym traci:** osoba z ADHD i z trudnościami w skupieniu uwagi (ruchoma treść odciąga uwagę od tekstu obok), osoba z zaburzeniami przedsionkowymi i migreną (ruch wywołuje objawy), osoba z padaczką światłoczułą (o ile animacja zawiera szybkie zmiany jasności — tego nie sprawdzono klatka po klatce), osoba na wolnym łączu (909 KB).

**Jak naprawić.** Najprostsze i najskuteczniejsze: zamienić GIF na `<video>` z atrybutami `controls muted playsInline` bez `autoplay`, z plakatem (`poster`) jako pierwszą klatką. Rozwiązanie zachowujące GIF: dodać przycisk „Zatrzymaj animację / Odtwórz animację" przełączający `src` między GIF-em a nieruchomą klatką PNG. Niezależnie od wyboru dodać w `globals.css`:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Warto też sprawdzić animację pod kątem kryterium 2.3.1 Trzy błyski (poziom A) — audyt nie analizował jej klatka po klatce.

**Nakład:** 0,5 dnia.

**Weryfikacja:** parametry pliku GIF i brak reguł `prefers-reduced-motion` — zweryfikowane pomiarem. Zawartość samej animacji pod kątem migotania — niesprawdzona.

---

### Priorytet 2 — usterki poważne

---

#### P1. Kontrast kolorów — kilkanaście par poniżej progu

**Gdzie:** `frontend/src/app/globals.css:53-64`, `frontend/src/components/ui/DifficultyStars.tsx:20`, `frontend/src/components/layout/Header.tsx:168,179`, `frontend/src/components/progress/ProgressStats.tsx:14-17,64`, `frontend/src/components/my-solutions/StatisticsCards.tsx:91,104,116,128`, `frontend/src/components/task/SubmitSection.tsx:302`

**Wartości obliczone** wzorem WCAG (luminancja względna, sRGB). Nie są to szacunki.

**Nie spełniają progu 4,5:1 dla zwykłego tekstu:**

| Element | Kolory | Kontrast | Wymagane | Plik |
|---|---|---|---|---|
| Gwiazdki trudność 3 (14 px) | `#eab308` na białym | **1,92:1** | 4,5:1 | `globals.css:62` |
| Gwiazdki trudność 2 | `#84cc16` na białym | **1,98:1** | 4,5:1 | `globals.css:61` |
| Gwiazdki trudność 1 | `#22c55e` na białym | **2,28:1** | 4,5:1 | `globals.css:60` |
| Gwiazdki trudność 4 | `#f97316` na białym | **2,80:1** | 4,5:1 | `globals.css:63` |
| Gwiazdki trudność 5 | `#ef4444` na białym | **3,76:1** | 4,5:1 | `globals.css:64` |
| Plakietka „tylko odczyt" (11 px) | biały na `#ff9800` | **2,16:1** | 4,5:1 | `Header.tsx:168` |
| Link „Wyloguj" | `#9ca3af` na białym | **2,54:1** | 4,5:1 | `Header.tsx:179` |
| Wynik 2 pkt | `#d97706` na białym | **3,19:1** | 4,5:1 | `globals.css:55` |
| Wynik 6 pkt | `#059669` na białym | **3,77:1** | 4,5:1 | `globals.css:57` |

**Nie spełniają progu 3:1 dla tekstu dużego (≥ 18,66 px pogrubiony):**

| Element | Kolory | Kontrast | Plik |
|---|---|---|---|
| Statystyka „Opanowane" | `#22c55e` na białym | **2,28:1** | `ProgressStats.tsx:15` |
| Statystyka „Sugerowane później" | `#9ca3af` na białym | **2,54:1** | `ProgressStats.tsx:17` |
| Kafelek „Średnia" | `#f59e0b` na białym | **2,15:1** | `StatisticsCards.tsx:116` |
| Kafelek „Ukończone" | `#22c55e` na białym | **2,28:1** | `StatisticsCards.tsx:104` |

**Nie spełniają progu 3:1 dla elementów interfejsu i grafiki (kryterium 1.4.11):**

| Element | Kolory | Kontrast | Plik |
|---|---|---|---|
| Obramowanie obszaru upuszczania plików | `#d1d5db` na `#f9fafb` | **1,41:1** | `SubmitSection.tsx:302` |
| Wypełnienie paska postępu | `#22c55e` na `#e5e7eb` | **1,84:1** | `ProgressStats.tsx:64` |
| Obramowanie kart i sekcji | `#e5e7eb` na białym | **1,24:1** | motyw MUI, `ThemeProvider.tsx:32` |

**Spełniają wymagania (do zachowania bez zmian):** wszystkie plakietki kategorii (4,83–7,15:1), plakietki wyniku w historii (6,37–7,60:1), plakietki statusu „Błąd"/„W trakcie" (5,57–7,60:1), karty etapów (6,38–6,49:1), tekst podstawowy `#1f2937` na `#f9fafb` (14,05:1), tekst drugorzędny MUI (5,74:1), linki nawigacji `#4b5563` (7,56:1), kolor główny `#2563eb` (5,17:1).

**Kryteria WCAG:** 1.4.3 Kontrast — minimum (poziom AA) — niespełnione; 1.4.11 Kontrast elementów nietekstowych (poziom AA) — niespełnione.

**Kto na tym traci:** osoba słabowidząca, osoba z zaćmą lub innym schorzeniem obniżającym wrażliwość na kontrast, osoba z zaburzeniami rozpoznawania barw, każdy użytkownik przy słabym oświetleniu lub na ekranie o niskiej jakości.

**Jak naprawić.** Przyciemnić paletę pomocniczą do wariantów spełniających próg. Propozycje zamienników (wszystkie sprawdzone tym samym wzorem):

Wszystkie podane niżej wartości zostały przeliczone tym samym wzorem — to pomiary, nie szacunki.

```css
/* globals.css — trudność (na białym tle karty) */
.difficulty-1 { color: #15803d; }  /* 5,02:1 zamiast 2,28 */
.difficulty-2 { color: #4d7c0f; }  /* 4,99:1 zamiast 1,98 */
.difficulty-3 { color: #a16207; }  /* 4,92:1 zamiast 1,92 */
.difficulty-4 { color: #c2410c; }  /* 5,18:1 zamiast 2,80 */
.difficulty-5 { color: #b91c1c; }  /* 6,47:1 zamiast 3,76 */
/* globals.css — wynik */
.score-2 { color: #b45309; }       /* 5,02:1 zamiast 3,19 */
.score-6 { color: #047857; }       /* 5,48:1 zamiast 3,77 */
```

- `Header.tsx:179`: „Wyloguj" z `#9ca3af` na `#4b5563` → **7,56:1**.
- `Header.tsx:165-172`: plakietka „tylko odczyt" — biały tekst na tle `#b45309` → **5,02:1**, albo tekst `#7c2d12` na tle `#ffedd5` → **8,18:1**.
- `ProgressStats.tsx`, `StatisticsCards.tsx`: te same przyciemnione odcienie co wyżej (`#15803d`, `#b45309`).
- `SubmitSection.tsx:302`: obramowanie obszaru upuszczania z `grey.300` na `grey.500` — `#6b7280` na `#f9fafb` → **4,63:1**.
- Pasek postępu: przyciemnić wypełnienie do `#15803d` — na `#e5e7eb` daje **4,05:1**, z zapasem ponad wymagane 3:1. Pasek niesie informację, więc podlega kryterium 1.4.11.
- Obramowania kart `grey.200` można zostawić — pełnią rolę wyłącznie dekoracyjną, informacja o granicy karty nie jest niezbędna do zrozumienia treści. Warto to jednak potwierdzić przy testach z użytkownikami.

**Nakład:** 1,5 dnia (zmiana palety plus przegląd wszystkich miejsc, gdzie kolory są zapisane na sztywno w `sx`).

**Weryfikacja:** wartości obliczone; wygląd po zmianie wymaga obejrzenia w przeglądarce.

---

#### P2. Poziom trudności, kategorie i powiązania zadań są niedostępne poza myszą

**Gdzie:** `frontend/src/components/ui/DifficultyStars.tsx:17-30`, `frontend/src/components/ui/CategoryBadge.tsx:24-40`, `frontend/src/components/task/SkillsSection.tsx:45,71`, `frontend/src/app/task/[year]/[etap]/[num]/page.tsx:102-125`

**Na czym polega problem.** Wszystkie te elementy używają MUI `<Tooltip>` do przekazania właściwej informacji: opisu poziomu trudności („Średnie — kilka kroków rozumowania"), opisu kategorii („Geometria płaska: trójkąty, czworokąty, okręgi"), opisu umiejętności i tytułu zadania powiązanego. Zbadano w przeglądarce, jak to wygląda w DOM:

```
<span class="difficulty-3 MuiBox-root" aria-label="Średnie - kilka kroków rozumowania"
      tabindex=null>★★★☆☆</span>

<div class="MuiChip-root" aria-label="Geometria płaska: trójkąty, czworokąty, okręgi"
     tabindex=null>Geometria</div>

<div class="MuiChip-root" aria-label=null tabindex=null>Zad. 1 (2022)</div>   ← zadanie powiązane
```

Trzy odrębne problemy:

*(a) Brak dostępu z klawiatury.* Żaden z tych elementów nie ma `tabindex` (potwierdzone pomiarem: `tabindex: null` dla wszystkich 7 plakietek na stronie zadania). MUI `Chip` staje się elementem fokusowalnym dopiero po podaniu `onClick` (`Chip.js:417-418`). Użytkownik klawiatury nie może wywołać dymka — informacja jest dla niego niedostępna. Dotyczy to również użytkownika ekranu dotykowego, gdzie najechanie myszą nie istnieje.

*(b) `aria-label` na elemencie bez roli.* Tam, gdzie `title` jest zwykłym tekstem, MUI `Tooltip` dokłada dziecku `aria-label`. Ale dziecko to `<div>`/`<span>` bez atrybutu `role`, czyli element o roli `generic`. Specyfikacja ARIA nie przewiduje nazywania elementów o roli `generic` i większość czytników ekranu taki `aria-label` ignoruje. Prawdopodobnie więc opis trudności nie jest odczytywany wcale, a czytnik ogłasza surowe znaki „★★★☆☆" (albo je pomija, zależnie od ustawienia poziomu interpunkcji i symboli).

*(c) Zadania powiązane nie mają nawet `aria-label`.* Na stronie zadania (`page.tsx:104`) do `Tooltip` przekazano jako `title` komponent React (`<MathContent … />`), a nie tekst. MUI nie potrafi z tego zbudować `aria-label` — potwierdzono pomiarem: plakietka „Zad. 1 (2022)" ma `aria-label = null`. Tytuł zadania będącego wymaganiem wstępnym jest niedostępny dla wszystkich poza użytkownikami myszy.

**Kryteria WCAG:** 2.1.1 Klawiatura (poziom A) — niespełnione; 1.1.1 Treść nietekstowa (poziom A) — niespełnione dla gwiazdek; 4.1.2 Nazwa, rola, wartość (poziom A) — niespełnione; 1.4.13 Treść spod kursora lub fokusu (poziom AA) — niespełnione częściowo (treść pojawia się tylko po najechaniu, nigdy po otrzymaniu fokusu).

**Kto na tym traci:** użytkownik czytnika ekranu, osoba korzystająca wyłącznie z klawiatury, użytkownik telefonu/tabletu (brak najechania), osoba z drżeniem rąk (trudność w utrzymaniu kursora nad małym elementem).

**Jak naprawić.**

`DifficultyStars.tsx` — nadać elementowi rolę obrazu, wtedy `aria-label` staje się wiążący, a same gwiazdki znikną z odczytu:
```tsx
<Box component="span" role="img"
     aria-label={`Poziom trudności ${difficulty} z 5: ${DIFFICULTY_LABELS[difficulty]}`}
     className={`difficulty-${difficulty}`} sx={{ fontSize, letterSpacing, cursor: "help" }}>
  <span aria-hidden="true">{filledStars}{emptyStars}</span>
</Box>
```

`CategoryBadge.tsx` — treść dymka przenieść do widocznego tekstu pomocniczego albo powiązać przez `aria-describedby` z elementem fokusowalnym. Najprościej: dodać `<Chip … tabIndex={0} />` i `describeChild` w `Tooltip`, dzięki czemu dymek pojawi się także po otrzymaniu fokusu, a nazwa plakietki („Geometria") pozostanie nazwą, zaś opis trafi do `aria-describedby`.

Strona zadania, plakietki zadań powiązanych (`page.tsx:102-125`) — plakietka jest opakowana w `<Link>`, więc jest fokusowalna; dodać do linku `aria-label` z tekstem tytułu pozbawionym LaTeX-a, np.:
```tsx
<Link href={prereq.url} aria-label={`Zadanie ${prereq.number} z ${prereq.year}: ${stripLatex(prereq.title)}${isMastered ? " — opanowane" : hasStatus ? " — do rozwiązania" : ""}`}>
```
Zwróć uwagę, że status opanowania jest dziś przekazywany wyłącznie kolorem tła i znakiem `✓`/`○` wewnątrz `<span>` bez opisu — to również kryterium 1.4.1 Użycie koloru (poziom A).

**Nakład:** 1 dzień.

**Weryfikacja:** obecność/brak `aria-label` i `tabindex` zweryfikowane w przeglądarce. To, czy `aria-label` na `<div>` bez roli jest odczytywany przez NVDA — **niesprawdzone**, wymaga testu z czytnikiem.

---

#### P3. Rozwijane sekcje nie informują o swoim stanie

**Gdzie:** `frontend/src/components/task/HintsSection.tsx:32-40`, `frontend/src/components/task/SkillsSection.tsx:19-34`, `frontend/src/components/task/SubmissionHistory.tsx:126-154`, `frontend/src/components/my-solutions/SubmissionCard.tsx` (nagłówek karty, ok. linii 128-208 w wersji roboczej)

**Na czym polega problem.** Wzorzec jest wszędzie ten sam: klikalny `<Box>` (czyli `<div>`) z `onClick`, a w środku przycisk MUI z napisem „Rozwiń"/„Zwiń" bez własnej obsługi zdarzeń — działa dzięki temu, że kliknięcie przycisku „bąbelkuje" do rodzica.

**Zweryfikowano w przeglądarce, że z klawiatury to działa:** ustawiono fokus na przycisku „Rozwiń" w sekcji Umiejętności, naciśnięto `Enter` — panel się rozwinął (`visibility` zmieniło się z `hidden` na `visible`, wysokość z 0 px na 200,9 px), a napis przycisku zmienił się na „Zwiń". Kryterium 2.1.1 jest więc tu spełnione, choć przypadkiem.

Problemy, które pozostają:
- Przyciski nie mają `aria-expanded` ani `aria-controls`. Zweryfikowano: `expanded: null, controls: null` dla wszystkich przycisków na stronie. Czytnik ekranu nie ogłasza, czy sekcja jest zwinięta czy rozwinięta.
- Nazwa dostępna przycisków jest nieinformująca. Na stronie „Moje rozwiązania" lista zawiera kilkadziesiąt przycisków o identycznej nazwie „Rozwiń" (a w `SubmissionCard.tsx` przycisk zawiera wyłącznie ikonę strzałki, więc jego nazwa dostępna jest **pusta** — MUI ustawia ikonom `aria-hidden="true"`). Użytkownik przeglądający listę przycisków usłyszy ciąg pustych elementów.
- Obszar klikalny jest większy dla myszy niż dla klawiatury (cały wiersz vs. sam przycisk) — to nie jest naruszenie, ale niespójność, która myli.
- Świeżo odsłonięta wskazówka nie jest ogłaszana (kryterium 4.1.3, patrz B2).

**Kryteria WCAG:** 4.1.2 Nazwa, rola, wartość (poziom A) — niespełnione; 2.4.6 Nagłówki i etykiety (poziom AA) — niespełnione częściowo; 4.1.3 Komunikaty o stanie (poziom AA) — niespełnione.

**Kto na tym traci:** użytkownik czytnika ekranu.

**Jak naprawić.** Przenieść `onClick` z `<Box>` na sam przycisk i uzupełnić atrybuty:
```tsx
const panelId = `umiejetnosci-panel`;
<Button size="small" onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded} aria-controls={panelId}>
  {expanded ? "Zwiń" : "Rozwiń"} umiejętności
</Button>
<Collapse in={expanded}><Box id={panelId}> … </Box></Collapse>
```
W `SubmissionCard.tsx`, gdzie przycisk zawiera samą ikonę, dodać `aria-label={`${isExpanded ? "Zwiń" : "Rozwiń"} szczegóły rozwiązania zadania ${submission.task_number} z ${submission.year}`}`.

W `HintsSection.tsx` dodatkowo: po odsłonięciu wskazówki treść powinna trafić do regionu żywego albo fokus powinien przenieść się na nowo odsłonięty blok (`tabIndex={-1}` + `.focus()`), inaczej użytkownik czytnika nie wie, że coś się pojawiło i gdzie.

**Nakład:** 0,5 dnia.

**Weryfikacja:** brak `aria-expanded` oraz działanie klawiatury — zweryfikowane w przeglądarce.

---

#### P4. Tytuły stron nie są unikalne

**Gdzie:** `frontend/src/app/login/page.tsx`, `frontend/src/app/my-solutions/page.tsx`, `frontend/src/app/admin/submissions/page.tsx` — żaden z tych plików nie eksportuje `metadata` ani `generateMetadata`

**Na czym polega problem.** Bez własnych metadanych Next.js użyje domyślnego tytułu z `frontend/src/app/layout.tsx:18`, czyli `„Trener OMJ - Olimpiada Matematyczna Juniorów"`. Trzy różne strony mają identyczny tytuł. Użytkownik czytnika ekranu, dla którego tytuł strony jest pierwszą i często jedyną informacją o tym, gdzie się znalazł, po przejściu na logowanie usłyszy dokładnie to samo, co na stronie głównej. To samo dotyczy osoby z wieloma otwartymi kartami.

Pozostałe strony mają tytuły poprawne i opisowe (zweryfikowano na produkcji: `„Zadanie 1 – Etap II 2024 | Trener OMJ"`).

**Kryteria WCAG:** 2.4.2 Tytuł strony (poziom A) — niespełnione dla trzech stron.

**Kto na tym traci:** użytkownik czytnika ekranu, osoba z trudnościami poznawczymi, każdy użytkownik zakładek i historii przeglądarki.

**Jak naprawić.** Dodać w każdym z trzech plików:
```tsx
export const metadata: Metadata = { title: "Zaloguj się" };        // login
export const metadata: Metadata = { title: "Moje rozwiązania" };   // my-solutions
export const metadata: Metadata = { title: "Panel administratora" }; // admin
```
Szablon z `layout.tsx:19` dołoży `„ | Trener OMJ"` automatycznie. W panelu administratora warto dodać `robots: { index: false }`.

**Nakład:** 15 minut.

**Weryfikacja:** brak eksportu metadanych — zweryfikowany w kodzie; tytuł strony logowania na produkcji — potwierdzony.

---

#### P5. Nieskończone przewijanie bez alternatywy klawiaturowej

**Gdzie:** `frontend/src/components/my-solutions/MySolutionsDashboard.tsx:97-101`, `frontend/src/lib/hooks/useInfiniteScroll.ts:54-69`, `frontend/src/components/my-solutions/SubmissionsList.tsx:85`

**Na czym polega problem.** Lista rozwiązań doładowuje kolejne 20 pozycji, gdy pusty `<div style={{height:1}}>` na końcu listy wejdzie w pole widzenia. Nie ma przycisku „Załaduj więcej". Konsekwencje:
- Użytkownik klawiatury nie ma jak wywołać doładowania inaczej niż przewijając kółkiem/klawiszami — a przewijanie samo w sobie nie jest kontrolowane fokusem, więc doładowanie następuje w sposób dla niego nieprzewidywalny.
- Stopka strony (regulamin, kontakt, licencja) staje się praktycznie nieosiągalna dla użytkownika z dużą liczbą rozwiązań — każde dojście do dołu doładowuje kolejne 20 kart.
- Doładowane pozycje pojawiają się bez żadnego komunikatu (kryterium 4.1.3).
- `<div ref={sentinelRef} />` jest pustym elementem bez roli i bez treści.

**Kryteria WCAG:** 2.4.1 Możliwość pominięcia bloków (poziom A) — niespełnione częściowo; 4.1.3 Komunikaty o stanie (poziom AA) — niespełnione; 2.1.1 Klawiatura (poziom A) — niespełnione częściowo.

**Kto na tym traci:** osoba korzystająca wyłącznie z klawiatury, użytkownik czytnika ekranu, osoba z trudnościami poznawczymi (treść „rośnie" pod palcami bez ostrzeżenia).

**Jak naprawić.** Zostawić obserwator przecięcia jako wygodę dla myszy, ale **dodać widoczny przycisk** „Załaduj kolejne rozwiązania (20)" renderowany zawsze, gdy `hasMore`. Po doładowaniu ogłosić stan w regionie żywym: `<div role="status" aria-live="polite">Załadowano kolejne 20 rozwiązań. Łącznie: {submissions.length} z {totalCount}.</div>`. Rozważyć wyłączenie automatycznego doładowywania, gdy użytkownik ma ustawione `prefers-reduced-motion` albo gdy nawiguje klawiaturą.

**Nakład:** 0,5 dnia.

**Weryfikacja:** wyłącznie analiza kodu — strona wymaga zalogowania.

---

#### P6. Karta zadania to jeden wielki link o bardzo długiej nazwie

**Gdzie:** `frontend/src/components/task/TaskCard.tsx:22-99`, analogicznie `frontend/src/components/progress/RecommendationsList.tsx:25-65`, `frontend/src/components/progress/Etap2PrepList.tsx:120-188`, `frontend/src/app/years/page.tsx:52-75`

**Na czym polega problem.** Cała karta — numer zadania, treść z wzorami, gwiazdki trudności, plakietki kategorii, statystyka najwyższego wyniku — jest zawartością pojedynczego `<Link>`. Nazwa dostępna takiego linku to sklejka całego tekstu karty, np. „Zadanie 5 Dane są liczby całkowite a i b takie, że … ★★★☆☆ Geometria Teoria liczb Najwyższy wynik: 5/6". Użytkownik czytnika ekranu przeglądający listę linków (`Insert+F7` w NVDA) dostanie kilkanaście takich potworków. Dodatkowo `<Card>` zawiera `<Typography>` renderowane jako `<p>` wewnątrz `<a>` — to poprawne wg HTML5 (model zawartości `<a>` jest przezroczysty), ale utrudnia nawigację.

Nie jest to twarde naruszenie — nazwa linku jest w pełni opisowa, tylko rozwlekła — ale w praktyce mocno pogarsza użyteczność.

**Kryteria WCAG:** 2.4.4 Cel linku w kontekście (poziom A) — na granicy, formalnie spełnione; 1.3.1 Informacje i relacje (poziom A) — niespełnione częściowo (brak nagłówka dla pozycji listy).

**Kto na tym traci:** użytkownik czytnika ekranu.

**Jak naprawić.** Przekształcić kartę: numer zadania jako nagłówek `<h3>` zawierający jedyny link, reszta karty jako zwykła treść poza linkiem, cała lista jako `<ul>`/`<li>`:
```tsx
<Card component="li">
  <CardContent>
    <Typography variant="h3" component="h3" sx={{ fontSize: "1rem" }}>
      <Link href={href}>Zadanie {task.number}</Link>
    </Typography>
    <MathContent content={task.title} />
    …
  </CardContent>
</Card>
```
Alternatywa mniej inwazyjna, jeśli klikalność całej karty jest wymogiem projektowym: zostawić strukturę, ale dodać do `<Link>` atrybut `aria-label={`Zadanie ${task.number}, ${etapName} ${year}`}` — wtedy nazwa linku będzie krótka, a reszta treści pozostanie odczytywalna w trybie przeglądania.

**Nakład:** 0,5 dnia.

**Weryfikacja:** analiza kodu + odczyt drzewa dostępności na produkcji.

---

#### P7. Opisy alternatywne miniatur przesłanych zdjęć

**Gdzie:** `frontend/src/components/task/SubmissionHistory.tsx:180` (`alt="Rozwiązanie ${imgIndex + 1}"`), `frontend/src/components/my-solutions/SubmissionCard.tsx:182` (`alt="Zdjęcie ${imgIndex + 1}"`)

**Na czym polega problem.** Miniatury to fotografie odręcznych rozwiązań ucznia. Automatyczne wygenerowanie sensownego opisu ich treści jest niemożliwe i nie jest wymagane — WCAG nie żąda opisania treści zdjęcia, którego nie da się opisać. Ale obecne opisy nie mówią nawet, **czym jest** ten obrazek i **do czego prowadzi kliknięcie**. Link otwierający zdjęcie w nowej karcie (`target="_blank"`) nie ostrzega o otwarciu nowego okna.

Osobno: dwa komponenty robiące to samo używają dwóch różnych sformułowań („Rozwiązanie" vs „Zdjęcie") — niespójność (kryterium 3.2.4 Spójna identyfikacja, poziom AA).

**Kryteria WCAG:** 1.1.1 Treść nietekstowa (poziom A) — spełnione minimalnie, do poprawy; 3.2.4 Spójna identyfikacja (poziom AA) — niespełnione; 2.4.4 Cel linku (poziom A) — niespełnione częściowo.

**Kto na tym traci:** użytkownik czytnika ekranu.

**Jak naprawić.** Ujednolicić i uzupełnić:
```tsx
<a href={`/uploads/${image}`} target="_blank" rel="noopener noreferrer">
  <Box component="img"
       alt={`Fotografia ${imgIndex + 1} z ${submission.images.length} przesłanego rozwiązania — otwiera się w nowej karcie`}
       src={`/uploads/${image}`} … />
</a>
```
Ucznia niewidomego to i tak nie uczyni zdolnym do sprawdzenia własnego zdjęcia — ale przynajmniej będzie wiedział, ile plików wysłał i że dostały się na serwer.

**Nakład:** 15 minut.

**Weryfikacja:** analiza kodu.

---

#### P8. Timer próbnego Etapu 2 — zakończenie odliczania w ciszy, pulsowanie bez zabezpieczenia

**Gdzie:** `frontend/src/lib/contexts/TimerContext.tsx:84-103`, `frontend/src/components/practice/FloatingTimer.tsx:16,57-66`, `frontend/src/components/practice/PracticeTimer.tsx:63-78`

**Na czym polega problem.**
- Trzygodzinne odliczanie **da się zapauzować** przyciskiem „Pauza" (`PracticeTimer.tsx:84-92`, `FloatingTimer.tsx:88-96`), więc kryterium 2.2.1 Dostosowanie czasu jest formalnie spełnione.
- Ale gdy czas dobiegnie końca, stan przechodzi na zero i `FloatingTimer` **znika bez śladu** (`FloatingTimer.tsx:16` zwraca `null`). Nie ma żadnego komunikatu — ani wizualnego, ani dla czytnika ekranu. Osoba niewidoma dowie się o upływie czasu tylko wtedy, gdy sama sprawdzi zegar.
- Wyświetlacz czasu (`FloatingTimer.tsx:74-84`) aktualizuje się co sekundę bez `aria-live` — to akurat dobrze (region żywy odczytywałby każdą sekundę), ale brakuje mu w ogóle etykiety: `<Typography variant="h6">` renderuje `<h6>` z treścią „02:47:13", co ląduje w spisie nagłówków jako bezsensowna pozycja.
- Ikona zegara pulsuje w nieskończoność przy ostatnich 10 minutach (`FloatingTimer.tsx:60-65`, `animation: "pulse 1s infinite"`) bez zabezpieczenia `prefers-reduced-motion` (patrz B5).
- Panel jest `position: fixed` w prawym dolnym rogu z `z-index: 1200`. Przy powiększeniu 200–400 % może zasłonić przycisk „Prześlij rozwiązanie" i nie da się go odsunąć.

**Kryteria WCAG:** 4.1.3 Komunikaty o stanie (poziom AA) — niespełnione (koniec czasu); 1.3.1 Informacje i relacje (poziom A) — niespełnione (`<h6>` z czasem); 2.2.2 Pauza, zatrzymanie, ukrycie (poziom A) — niespełnione dla pulsowania; 1.4.10 Zawijanie tekstu (poziom AA) — do sprawdzenia (przesłanianie treści).

**Kto na tym traci:** użytkownik czytnika ekranu, osoba słabowidząca powiększająca stronę, osoba wrażliwa na ruch.

**Jak naprawić.**
```tsx
// FloatingTimer.tsx — zamiast wariantu nagłówkowego
<Typography variant="h6" component="p" aria-label={`Pozostały czas: ${formatTimeSpoken(remainingMs)}`}>
  {formatTime(remainingMs)}
</Typography>

// komunikat o końcu czasu, renderowany zawsze
<Box role="status" aria-live="assertive" sx={visuallyHidden}>
  {remainingMs === 0 ? "Czas na rozwiązanie zadań dobiegł końca." : ""}
</Box>
```
Dodać przycisk zamknięcia panelu pływającego (dziś przycisk `<CloseIcon>` resetuje timer, a nie zamyka panel — to mylące) albo pozwolić na przesunięcie panelu na dół strony przy wąskim ekranie.

**Nakład:** 0,5 dnia.

**Weryfikacja:** wyłącznie analiza kodu — timer wymaga zalogowania i uruchomionej sesji.

---

#### P9. Arkusz stylów KaTeX ładowany z zewnętrznego CDN — ryzyko w sieci szkolnej

**Gdzie:** `frontend/src/app/layout.tsx:82-86`

**Na czym polega problem.** Aplikacja pobiera `https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css`, podczas gdy w `package.json` zainstalowana jest biblioteka `katex` w wersji **0.16.27** (rozbieżność wersji sama w sobie jest usterką).

Poważniejszy jest jednak fakt, że reguła, która ukrywa warstwę MathML przed wzrokiem użytkownika, znajduje się właśnie w tym pliku CSS (zweryfikowano w `frontend/node_modules/katex/dist/katex.css:157-166`):

```css
.katex .katex-mathml {
  /* Accessibility hack to only show to screen readers */
  position: absolute; clip: rect(1px, 1px, 1px, 1px);
  padding: 0; border: 0; height: 1px; width: 1px; overflow: hidden;
}
```

Jeśli szkolny filtr treści, proxy albo blokada reklam odetnie `cdn.jsdelivr.net` — a to w sieciach szkolnych zdarza się regularnie — to **każdy wzór wyświetli się dwukrotnie**: raz jako surowy tekst MathML, raz jako rozsypane elementy KaTeX bez pozycjonowania. Treść zadań stanie się nieczytelna dla wszystkich użytkowników, nie tylko dla osób z niepełnosprawnościami. To ryzyko dostępności usługi jako takiej, a nie tylko dostępności cyfrowej w rozumieniu WCAG.

Dodatkowo: odpytywanie zewnętrznego CDN przy każdej wizycie ucznia przekazuje jego adres IP i nagłówek `Referer` podmiotowi trzeciemu — do rozważenia przez inspektora ochrony danych szkoły.

**Kryteria WCAG:** brak bezpośredniego naruszenia (kryterium 4.1.1 Poprawność kodu zostało w WCAG 2.1 uznane za spełnione z definicji). Usterka niezawodnościowa o skutkach dostępnościowych.

**Kto na tym traci:** wszyscy użytkownicy w sieci z blokadą CDN.

**Jak naprawić.** Usunąć `<link>` z `layout.tsx` i zaimportować arkusz lokalnie — plik jest już w `node_modules`:
```tsx
// frontend/src/app/layout.tsx
import "katex/dist/katex.min.css";
```
Next.js dołączy go do własnego pakietu. Rozwiązuje to jednocześnie rozbieżność wersji, ryzyko blokady i wyciek danych.

**Nakład:** 15 minut + test wizualny.

**Weryfikacja:** obecność linku do CDN potwierdzona w kodzie HTML strony produkcyjnej; treść reguły CSS potwierdzona w pliku biblioteki.

---

#### P10. Graf postępów (Cytoscape.js) — dziś nieaktywny, ale gotowy do wybuchu

**Gdzie:** `frontend/src/components/progress/ProgressGraph.tsx` (cały plik)

**Ustalenie kluczowe: komponent jest martwym kodem.** Przeszukano całe repozytorium — jedyne wystąpienia nazwy `ProgressGraph` znajdują się w samym pliku, który go definiuje. Strona `/progress` (`frontend/src/app/progress/page.tsx:39-63`) renderuje `ProgressStats`, `CategoryFilter`, `RecommendationsList` i `Etap2PrepList` — wszystkie oparte na zwykłym HTML-u i w pełni odczytywalne. **Graf nie jest dziś barierą dostępności, bo nikt go nie widzi.**

Ale biblioteka `cytoscape` (ok. 400 KB) nadal jest w zależnościach i komponent czeka na ponowne włączenie. Gdyby wrócił w obecnej postaci, naruszałby jednocześnie:

| Problem w kodzie | Kryterium |
|---|---|
| Rysunek na `<canvas>` bez `role="img"`, bez `aria-label`, bez tekstowej alternatywy (`ProgressGraph.tsx:156-166`) | 1.1.1 (A) |
| Nawigacja tylko przez `cy.on("tap", …)` → `window.location.href` (`:113-119`); brak jakiejkolwiek obsługi klawiatury, kontener nie jest fokusowalny | 2.1.1 (A) |
| Status zadania niesiony **wyłącznie** kolorem wypełnienia węzła (`:26-36`) — `#22c55e` opanowane / `#3b82f6` do rozwiązania / `#9ca3af` zablokowane | 1.4.1 (A) |
| Kontrast węzłów wobec tła `#fafafa`: 2,18:1 / 3,52:1 / 2,43:1 (obliczone) | 1.4.11 (AA) |
| Kontrast etykiet (biały numer na węźle): 2,28:1 / 3,68:1 / 2,54:1 (obliczone) | 1.4.3 (AA) |
| Krawędzie `#d1d5db` na `#fafafa` = **1,41:1** (obliczone) | 1.4.11 (AA) |
| `window.location.href` zamiast routera — pełne przeładowanie, fokus wraca na początek dokumentu | 3.2.5 (AAA), 2.4.3 (A) częściowo |

**Rekomendacja.** Skoro graf i tak nie jest używany, są dwa sensowne wyjścia:
1. **Usunąć komponent i zależność `cytoscape`** z `package.json` — zamyka temat, odchudza pakiet o ok. 400 KB i eliminuje przyszłe ryzyko.
2. Jeśli graf ma wrócić: zbudować obok niego **równoważną ścieżkę tekstową** — listę zadań pogrupowaną po statusie, z jawnym tekstem statusu („opanowane", „do rozwiązania", „sugerowane później") i jawnie wypisanymi zależnościami („wymaga wcześniejszego rozwiązania: Zadanie 2 z 2022"). Taka lista faktycznie już istnieje w `Etap2PrepList.tsx` i `RecommendationsList.tsx` — wystarczy ją rozszerzyć. Sam graf oznaczyć wtedy `aria-hidden="true"` jako wzbogacenie wizualne i dodać do niego przycisk „Pokaż wersję tekstową".

**Nakład:** 15 minut na usunięcie (opcja 1) albo 2–3 dni na zbudowanie równoważnej alternatywy (opcja 2).

**Weryfikacja:** brak użycia komponentu — zweryfikowany przeszukaniem całego repozytorium; wartości kontrastu — obliczone; zachowanie klawiatury w grafie — niesprawdzone (komponent się nie renderuje).

---

### Priorytet 3 — usterki drobne i zalecenia

| # | Ustalenie | Plik | Kryterium | Nakład |
|---|---|---|---|---|
| D1 | Separator okruszków `#d1d5db` na białym = 1,47:1. Ikona jest dekoracyjna (MUI nada jej `aria-hidden`), ale wizualnie niewidoczna dla osoby słabowidzącej. | `components/layout/Breadcrumb.tsx:17` | 1.4.11 (AA) — dyskusyjne | 5 min |
| D2 | `MathContent` używa `dangerouslySetInnerHTML` na treści z bazy. Sprawdzono wszystkie 342 pliki zadań: **0 wystąpień** sekwencji przypominających znaczniki HTML, więc dziś treść nie jest zjadana. Ryzyko pozostaje na przyszłość (treści są generowane przez AI) i jest zarazem furtką XSS. | `components/ui/MathContent.tsx:16-99` | brak bezpośredniego; bezpieczeństwo | 0,5 dnia |
| D3 | Formuły w tekście nie mają oznaczenia języka. Jeśli wzór zawiera `\text{dla każdego}`, czytnik przeczyta to polską syntezą tylko wtedy, gdy jest ustawiony na polski — a MathML nie niesie tu `lang`. | `components/ui/MathContent.tsx` | 3.1.2 (AA) — do sprawdzenia | 0,5 dnia |
| D4 | Etykiety pól filtrowania używają MUI `InputLabel` bez jawnego `id`/`labelId`. MUI wiąże je automatycznie, ale warto to potwierdzić w drzewie dostępności. | `components/my-solutions/FiltersBar.tsx:72-100` | 1.3.1, 3.3.2 (A) — do sprawdzenia | 15 min |
| D5 | Pole wyboru „Akceptuję regulamin" ma w etykiecie zagnieżdżony link. Kliknięcie linku wewnątrz `<label>` może przełączyć pole zamiast otworzyć regulamin (zachowanie zależne od przeglądarki). | `components/auth/LoginForm.tsx:52-73` | 3.2.2 (A) — do sprawdzenia | 15 min |
| D6 | Pierścień fokusu to domyślny pierścień przeglądarki (`outline: auto 1px rgb(16,16,16)` — zmierzone). Formalnie spełnia 2.4.7, ale na jasnych tłach jest słabo widoczny i znika na przyciskach o ciemnym tle. | globalne | 2.4.7 (AA) — spełnione, do wzmocnienia | 2 h |
| D7 | Linki zewnętrzne (`target="_blank"`) w stopce, w linkach do PDF i przy miniaturach nie ostrzegają o otwarciu nowego okna. | `layout/Footer.tsx:58,78,86`, `app/task/…/page.tsx:143-163` | 3.2.5 (AAA) — zalecenie | 30 min |
| D8 | `frontend/src/app/globals.css:44` ustawia `scrollbar-gutter: stable` — dobra praktyka, bez zastrzeżeń. Odnotowane jako pozytyw. | — | — | — |
| D9 | Karta zadania i kafelki statystyk zmieniają się przy najechaniu przez `transform: translateY(-2px)` bez zabezpieczenia ruchu. Objęte poprawką z B5. | `task/TaskCard.tsx:26-29`, `my-solutions/StatisticsCards.tsx:36-39` | 2.3.3 (AAA) | objęte B5 |
| D10 | Panel administratora nie ma `robots: { index: false }` i nie ma własnego tytułu (patrz P4). | `app/admin/submissions/page.tsx` | — | 5 min |

---

## 3. Co działa dobrze — do zachowania przy poprawkach

Wymienione niżej rzeczy zweryfikowano i **nie należy ich psuć** przy wdrażaniu poprawek.

| Ustalenie | Dowód |
|---|---|
| **Warstwa dostępności wzorów matematycznych działa.** `katex.renderToString` używa domyślnego trybu `htmlAndMathml`: dla każdego wzoru powstaje `<span class="katex-mathml"><math>…</math></span>` z pełnym drzewem MathML oraz `<span class="katex-html" aria-hidden="true">` z warstwą graficzną. | Zmierzone na `https://omj-validator.pl/task/2024/etap2/1`: 16 elementów `<math>`, `.katex-html` ma `aria-hidden="true"`, `.katex-mathml` ma wyliczony styl `position:absolute; clip:rect(1px,1px,1px,1px); width:1px; height:1px; overflow:hidden`. Przykładowy MathML: `<math xmlns="…"><semantics><mrow><mi>E</mi></mrow><annotation encoding="application/x-tex">E</annotation></semantics></math>`. |
| Język strony zadeklarowany poprawnie: `<html lang="pl">` na wszystkich sprawdzonych stronach. | Zmierzone. Spełnia 3.1.1 (A). |
| Wszystkie ikony MUI renderują się jako `<svg aria-hidden="true" focusable="false">` — poprawne potraktowanie grafiki dekoracyjnej. Zero obrazków bez atrybutu `alt`. | Zmierzone: 0 elementów `<img>` bez `alt`, wszystkie `<svg>` z `aria-hidden="true"`. |
| Pierścień fokusu nie został usunięty. MUI `CssBaseline` nie wygasza `outline`. | Zmierzone: `outline: auto 1px rgb(16, 16, 16)` na linku w treści. Spełnia 2.4.7 (AA). |
| Zwinięte sekcje są poprawnie usuwane z drzewa dostępności. MUI `Collapse` nadaje `visibility: hidden` (nie tylko `height: 0`). Nierozwinięte wskazówki nie są „podglądalne" czytnikiem ekranu — co jest tu istotne również dydaktycznie. | Zmierzone: `.MuiCollapse-hidden` → `visibility: hidden`, `height: 0px`. Kod: `node_modules/@mui/material/Collapse/Collapse.js:85`. |
| Wynik oceny jest ogłaszany czytnikowi ekranu — MUI `<Alert>` domyślnie ma `role="alert"`. | Kod: `node_modules/@mui/material/Alert/Alert.js:167`. |
| Sekcje rozwijane działają z klawiatury (mimo braku `aria-expanded`). | Zmierzone: `Enter` na przycisku „Rozwiń" → `visibility` z `hidden` na `visible`, wysokość 0 → 200,9 px. |
| Nie wykryto pułapki fokusa. Aplikacja nie używa modali ani okien dialogowych, więc kryterium 2.1.2 nie ma tu zastosowania w praktyce. | Przegląd kodu — brak `Dialog`, `Modal`, `Drawer` w `frontend/src/`. |
| Kontrast tekstu podstawowego i wszystkich plakietek kategorii/statusu/wyniku jest w normie (4,83–14,05:1). | Obliczone. |
| Tytuły stron zadań, lat, etapów, postępów, regulaminu i praktyki są unikalne i opisowe. | Zmierzone na produkcji + przegląd `generateMetadata` w `frontend/src/app/`. |
| Nowy komponent `AiGeneratedNotice` (niezacommitowany) został napisany z myślą o dostępności — tekst w DOM, ikona `aria-hidden`, kontrast `#475569` na `#f8fafc` ≈ 7:1, `role="note"`. Dobry wzorzec. | `frontend/src/components/ui/AiGeneratedNotice.tsx` |

---

## 4. Zbiorcza tabela kryteriów WCAG 2.1 AA

Stan: **S** = spełnione, **N** = niespełnione, **?** = niesprawdzone (wymaga testu w przeglądarce lub z czytnikiem ekranu), **nd.** = nie dotyczy (w serwisie nie występuje treść objęta kryterium).

### Zasada 1 — Postrzegalność

| Kryterium | Poziom | Stan | Uwagi |
|---|---|---|---|
| 1.1.1 Treść nietekstowa | A | **N** | Gwiazdki trudności bez tekstowego odpowiednika (P2); ikony i obrazki poprawne. |
| 1.2.1 Tylko audio / tylko wideo | A | nd. | Brak nagrań. GIF demonstracyjny nie niesie informacji niedostępnej inaczej. |
| 1.2.2 Napisy rozszerzone | A | nd. | Brak nagrań wideo. |
| 1.2.3 Audiodeskrypcja lub alternatywa | A | nd. | |
| 1.2.4 Napisy na żywo | AA | nd. | |
| 1.2.5 Audiodeskrypcja | AA | nd. | |
| 1.3.1 Informacje i relacje | A | **N** | Hierarchia nagłówków (B3); nawigacja poza `<nav>` (B3); nagłówki-liczby (B3); brak `aria-expanded` (P3); `<h6>` z odliczaniem (P8). |
| 1.3.2 Zrozumiała kolejność | A | **S** | Kolejność DOM zgodna z wizualną; brak `order`/`float` łamiących kolejność. |
| 1.3.3 Właściwości zmysłowe | A | **S** | Instrukcje nie odwołują się wyłącznie do kształtu/położenia. |
| 1.3.4 Orientacja | AA | **?** | Brak blokady orientacji w kodzie; wymaga testu na urządzeniu mobilnym. |
| 1.3.5 Określenie prawidłowej wartości | AA | **?** | Brak `autocomplete` na polach — ale serwis nie zbiera danych osobowych użytkownika w formularzach (logowanie przez Google). Prawdopodobnie nie dotyczy. |
| 1.4.1 Użycie koloru | A | **N** | Status zadania powiązanego niesiony kolorem tła (P2); poziom trudności — kolor + liczba gwiazdek (częściowo OK); graf, gdyby wrócił (P10). |
| 1.4.2 Kontrola odtwarzania dźwięku | A | nd. | Brak automatycznie odtwarzanego dźwięku. |
| 1.4.3 Kontrast (minimum) | AA | **N** | 9 par poniżej 4,5:1 i 4 pary tekstu dużego poniżej 3:1 (P1). |
| 1.4.4 Zmiana rozmiaru tekstu | AA | **?** | Rozmiary w `rem`/`em`, co dobrze rokuje, ale nie sprawdzono zachowania przy powiększeniu tekstu do 200 % w przeglądarce. |
| 1.4.5 Obrazy tekstu | AA | **S** | Brak tekstu w obrazkach (logo jest tekstem). |
| 1.4.10 Zawijanie tekstu (Reflow) | AA | **N** | Zmierzone: 379 px przy oknie 320 px (B4); wzory w tekście wystają (B4). |
| 1.4.11 Kontrast elementów nietekstowych | AA | **N** | Obramowanie obszaru upuszczania 1,41:1; pasek postępu 1,84:1 (P1). |
| 1.4.12 Odstępy w tekście | AA | **?** | Brak sztywnych wysokości kontenerów tekstu w kodzie, ale nie przetestowano z arkuszem wymuszającym odstępy. |
| 1.4.13 Treść spod kursora lub fokusu | AA | **N** | Dymki MUI wyzwalane wyłącznie najechaniem, na elementach niefokusowalnych (P2). |

### Zasada 2 — Funkcjonalność

| Kryterium | Poziom | Stan | Uwagi |
|---|---|---|---|
| 2.1.1 Klawiatura | A | **N** | Przesyłanie zdjęć niedostępne (B1); dymki niedostępne (P2); doładowywanie listy (P5); graf, gdyby wrócił (P10). |
| 2.1.2 Brak pułapki na klawiaturę | A | **S** | Brak modali i osadzonych ramek; nie wykryto pułapki. |
| 2.1.4 Jednoznakowe skróty klawiszowe | A | nd. | Serwis nie definiuje skrótów jednoznakowych. |
| 2.2.1 Dostosowanie czasu | A | **S** | Timer da się zapauzować (`PracticeTimer.tsx:84`). Sesja logowania — wymaga potwierdzenia po stronie backendu. |
| 2.2.2 Pauza, zatrzymanie, ukrycie | A | **N** | GIF w nieskończonej pętli bez kontrolki (B5); pulsująca ikona zegara (P8). |
| 2.3.1 Trzy błyski | A | **?** | Nie przeanalizowano `omj-demo.gif` klatka po klatce pod kątem migotania. |
| 2.4.1 Możliwość pominięcia bloków | A | **N** | Brak linku pomijającego; nawigacja poza `<nav>` (B3); nieskończona lista (P5). |
| 2.4.2 Tytuł strony | A | **N** | Trzy strony bez własnego tytułu (P4). |
| 2.4.3 Kolejność fokusu | A | **S** | Kolejność DOM zgodna z wizualną; brak dodatnich `tabindex`. Wymaga potwierdzenia po naprawie B1. |
| 2.4.4 Cel linku w kontekście | A | **N** | Puste nazwy przycisków rozwijania w kartach rozwiązań (P3); linki-karty (P6). |
| 2.4.5 Wiele sposobów | AA | **S** | Nawigacja główna + okruszki + mapa witryny (`sitemap.ts`) + strona archiwum. |
| 2.4.6 Nagłówki i etykiety | AA | **N** | Nagłówki nieopisowe/nieprawidłowe (B3); etykiety „Rozwiń" bez kontekstu (P3). |
| 2.4.7 Widoczny fokus | AA | **S** | Domyślny pierścień przeglądarki zachowany (zmierzone). Zalecane wzmocnienie (D6). |
| 2.5.1 Gesty dotykowe | A | **S** | Przeciąganie plików ma alternatywę w postaci kliknięcia jednym wskaźnikiem. (Graf Cytoscape wymagałby gestów wielopunktowych, ale nie jest renderowany — P10.) |
| 2.5.2 Rezygnacja ze wskazania | A | **S** | Wszystkie akcje wywoływane przez `onClick` (zdarzenie podniesienia palca/przycisku), brak akcji na `onMouseDown`. |
| 2.5.3 Etykieta w nazwie | A | **?** | Wzorzec dymka MUI zastępuje widoczną etykietę opisem — np. plakietka umiejętności o widocznym tekście „Obliczanie kątów" dostaje nazwę dostępną „Systematyczne znajdowanie miar kątów w figurach…" (zmierzone). Dopóki plakietki nie są elementami interaktywnymi, kryterium formalnie nie ma zastosowania. **Po naprawie P2 stanie się naruszeniem**, jeżeli nazwa dostępna nie będzie zaczynać się od widocznego tekstu — opis należy wtedy przenieść do `aria-describedby`, nie do `aria-label`. |
| 2.5.4 Aktywowanie ruchem | A | nd. | Serwis nie korzysta z czujników ruchu ani orientacji urządzenia. |

### Zasada 3 — Zrozumiałość

| Kryterium | Poziom | Stan | Uwagi |
|---|---|---|---|
| 3.1.1 Język strony | A | **S** | `<html lang="pl">` — zweryfikowane. |
| 3.1.2 Język części | AA | **?** | Nazwy własne i fragmenty angielskie (np. „Open Source", „GitHub") bez `lang="en"`; tekst wewnątrz wzorów (D3). Wpływ niewielki. |
| 3.2.1 Po otrzymaniu fokusu | A | **S** | Brak zmiany kontekstu przy otrzymaniu fokusu. |
| 3.2.2 Podczas wprowadzania danych | A | **?** | Filtry na „Moich rozwiązaniach" przeładowują listę natychmiast po zmianie `Select` — to zmiana treści, nie kontekstu, więc prawdopodobnie OK. Pole wyboru w formularzu logowania (D5) do sprawdzenia. |
| 3.2.3 Spójna nawigacja | AA | **S** | Nagłówek i stopka identyczne na wszystkich stronach. |
| 3.2.4 Spójna identyfikacja | AA | **N** | Ta sama funkcja opisana różnie: „Rozwiązanie N" vs „Zdjęcie N" (P7); „Rozwiń" jako tekst vs jako sama ikona (P3). |
| 3.3.1 Identyfikacja błędu | A | **S** | Błędy przesyłania pokazywane w `<Alert severity="error">` z `role="alert"`. |
| 3.3.2 Etykiety lub instrukcje | A | **N** | Pole wyboru pliku bez etykiety (B1). Pozostałe pola (filtry, zgoda) mają etykiety. |
| 3.3.3 Sugestie korekty błędu | AA | **S** | Komunikaty błędów zawierają wskazówkę („Spróbuj przesłać rozwiązanie ponownie"). |
| 3.3.4 Zapobieganie błędom (prawne, finansowe) | AA | nd. | Serwis nie przetwarza transakcji ani zobowiązań prawnych. Usunięcie konta — do sprawdzenia po scaleniu `components/account/DeleteAccountSection.tsx`. |

### Zasada 4 — Solidność

| Kryterium | Poziom | Stan | Uwagi |
|---|---|---|---|
| 4.1.1 Parsowanie | A | **S** | W WCAG 2.1 kryterium uznane za zawsze spełnione (erratum W3C z 2023 r.). |
| 4.1.2 Nazwa, rola, wartość | A | **N** | Obszar upuszczania bez roli (B1); brak `aria-expanded` (P3); `aria-label` na elementach o roli `generic` (P2); przyciski bez nazwy (P3). |
| 4.1.3 Komunikaty o stanie | AA | **N** | Strumień postępu oceniania (B2); doładowywanie listy (P5); odsłanianie wskazówek (P3); koniec odliczania (P8). |

### Podsumowanie liczbowe

| Stan | Liczba kryteriów |
|---|---|
| Spełnione (S) | 16 |
| **Niespełnione (N)** | **17** |
| Niesprawdzone (?) | 8 |
| Nie dotyczy (nd.) | 9 |
| **Razem kryteriów A + AA w WCAG 2.1** | **50** |

Rozkład niespełnionych kryteriów wg poziomu:

- **10 na poziomie A:** 1.1.1, 1.3.1, 1.4.1, 2.1.1, 2.2.2, 2.4.1, 2.4.2, 2.4.4, 3.3.2, 4.1.2
- **7 na poziomie AA:** 1.4.3, 1.4.10, 1.4.11, 1.4.13, 2.4.6, 3.2.4, 4.1.3

Naruszenia poziomu A są poważniejsze — to najniższy próg dostępności, poniżej którego treść nie jest dla części użytkowników uciążliwa, tylko po prostu niedostępna.

---

## 5. Proponowana kolejność prac

### Etap I — bez tego nie wolno uruchamiać serwisu w szkole (ok. 3 dni)

| Kolejność | Zadanie | Ustalenie | Nakład |
|---|---|---|---|
| 1 | Przesyłanie zdjęć dostępne z klawiatury (`Button component="label"` + pole ukryte techniką „visually hidden") | B1 | 0,5 d |
| 2 | Region żywy dla przebiegu oceniania | B2 | 0,5 d |
| 3 | Link „przejdź do treści", `<nav>` dla nawigacji, naprawa hierarchii nagłówków | B3 | 0,5 d |
| 4 | Responsywny nagłówek + zawijanie wzorów w tekście (reflow 320 px) | B4 | 1 d |
| 5 | Zatrzymanie animacji GIF + globalna reguła `prefers-reduced-motion` | B5 | 0,5 d |

Po etapie I serwis nadaje się do użycia przez ucznia korzystającego wyłącznie z klawiatury i przez ucznia niewidomego. Nadal nie jest w pełni zgodny, ale przestaje wykluczać.

### Etap II — do wykonania przed przeglądem deklaracji, najpóźniej w ciągu 3 miesięcy (ok. 5 dni)

| Kolejność | Zadanie | Ustalenie | Nakład |
|---|---|---|---|
| 6 | Nowa paleta kolorów pomocniczych spełniająca 4,5:1 / 3:1 | P1 | 1,5 d |
| 7 | Trudność, kategorie i zadania powiązane dostępne poza myszą | P2 | 1 d |
| 8 | `aria-expanded` / `aria-controls` / nazwy przycisków rozwijania | P3 | 0,5 d |
| 9 | Lokalny arkusz KaTeX zamiast CDN | P9 | 0,25 d |
| 10 | Przycisk „Załaduj więcej" zamiast wyłącznie nieskończonego przewijania | P5 | 0,5 d |
| 11 | Komunikat o końcu odliczania + etykieta zegara | P8 | 0,5 d |
| 12 | Unikalne tytuły trzech stron | P4 | 0,25 d |
| 13 | Ujednolicone opisy miniatur | P7 | 0,25 d |
| 14 | Usunięcie martwego komponentu `ProgressGraph` i zależności `cytoscape` (albo decyzja o alternatywie tekstowej) | P10 | 0,25 d / 3 d |

### Etap III — weryfikacja i utrzymanie (ok. 2,5 dnia)

| Kolejność | Zadanie | Nakład |
|---|---|---|
| 15 | Testy z czytnikiem ekranu NVDA + Firefox oraz NVDA + Chrome, ze szczególnym uwzględnieniem odczytu wzorów MathML po polsku; w razie potrzeby rozważyć dodatek MathCAT | 1 d |
| 16 | Test pełnej ścieżki „wybierz zadanie → wyślij zdjęcie → odbierz ocenę" wyłącznie z klawiatury, po zalogowaniu | 0,5 d |
| 17 | Test powiększenia 200 % i 400 %, test odstępów w tekście (kryterium 1.4.12), test orientacji na telefonie | 0,5 d |
| 18 | Sporządzenie i publikacja deklaracji dostępności (szablon: [`deklaracja-dostepnosci.md`](./deklaracja-dostepnosci.md)) | 0,5 d |

### Można zrobić później

Ustalenia D1–D10 oraz zalecenia z poziomu AAA. Nie wpływają na zgodność z ustawą.

### Zalecenie procesowe

Aby dostępność nie zdegradowała się przy kolejnych zmianach, warto dołożyć do repozytorium:
- rozszerzoną konfigurację `eslint-plugin-jsx-a11y` (patrz rozdział 6 — domyślna konfiguracja Next.js praktycznie nic nie wykrywa),
- automatyczny test dostępności w pakiecie testów `e2e/` (biblioteka `@axe-core/playwright` — projekt już używa Playwrighta),
- pozycję „sprawdzono z klawiatury" na liście kontrolnej przeglądu kodu.

---

## 6. Granice audytu — co sprawdzono, a czego nie

### Sprawdzono narzędziami — wyniki są pomiarem, nie oceną

| Co | Jak |
|---|---|
| Struktura nagłówków, punkty orientacyjne, brak linku pomijającego, brak regionów żywych, atrybuty `aria-*`, `tabindex`, `alt` | Chromium przez Playwright, odczyt DOM i drzewa dostępności na `https://omj-validator.pl/` i `/task/2024/etap2/1` |
| Reflow przy 320 px | Pomiar `document.documentElement.scrollWidth` przy oknie 320 × 640 px, z listą elementów wystających poza widok |
| Obecność i poprawność warstwy MathML | Odczyt DOM + wyliczonych styli `.katex-mathml` i `.katex-html` na żywej stronie |
| Działanie sekcji rozwijanych z klawiatury | Ustawienie fokusu + rzeczywiste naciśnięcie `Enter`, odczyt `visibility`/`height` przed i po |
| Widoczność pierścienia fokusu | Odczyt wyliczonego `outline` po `.focus()` |
| Brak reguł `prefers-reduced-motion` | Przeszukanie wszystkich arkuszy stylów załadowanych na stronie |
| 60 par kontrastu | Obliczenie wzorem WCAG (luminancja względna sRGB) na kolorach odczytanych z kodu; wyniki podano z dokładnością do 0,01 |
| Parametry animacji GIF | Odczyt 27 klatek, czasów i znacznika pętli biblioteką PIL |
| Zawartość 342 plików zadań pod kątem sekwencji HTML | Skrypt przeszukujący `data/tasks/*/*/task_*.json` |
| Analiza statyczna dostępności | `eslint-plugin-jsx-a11y` w zestawie `recommended` + 6 reguł dodatkowych (`click-events-have-key-events`, `no-static-element-interactions`, `label-has-associated-control`, `no-noninteractive-element-interactions`, `anchor-is-valid`, `interactive-supports-focus`) |

**Ważna uwaga o linterze.** Uruchomienie `eslint-plugin-jsx-a11y` na całym katalogu `frontend/src` **nie zwróciło ani jednego ostrzeżenia dostępnościowego** — mimo że audyt ręczny znalazł 17 niespełnionych kryteriów. Powód jest techniczny: reguły `jsx-a11y` analizują wyłącznie elementy DOM (`<div>`, `<button>`, `<a>`), a w tym projekcie procedury obsługi zdarzeń są podpięte do komponentów Material-UI (`<Box onClick>`, `<Paper>`, `<Chip>`), których linter nie rozpoznaje. Dodatkowo domyślna konfiguracja `eslint-config-next/core-web-vitals` włącza tylko sześć najprostszych reguł `jsx-a11y` (dotyczących `alt` i poprawności atrybutów ARIA), a nie te dotyczące klawiatury.

**Wniosek: w tym projekcie automatyczna analiza statyczna nie daje żadnego sygnału o dostępności i nie może zastąpić przeglądu ręcznego.** Jeśli linter ma coś wykrywać, trzeba dodać do `frontend/eslint.config.mjs` zestaw `jsx-a11y` z jawnym mapowaniem komponentów, np.:
```js
settings: { "jsx-a11y": { components: { Box: "div", Paper: "div", Chip: "div", Button: "button", MuiLink: "a" } } }
```

### Sprawdzono wyłącznie w kodzie — bez potwierdzenia w działającej aplikacji

Poniższe obszary są dostępne dopiero po zalogowaniu przez Google, którego audyt nie mógł wykonać. Ustalenia opierają się na lekturze kodu i są w mojej ocenie pewne co do faktu, ale nie zostały zaobserwowane w działaniu:

- **cała ścieżka przesyłania rozwiązania** (B1) — w tym rzeczywista kolejność tabulacji w sekcji przesyłania i zachowanie fokusu po otrzymaniu wyniku,
- **strumieniowanie postępu oceniania przez WebSocket** (B2) — treść i częstotliwość komunikatów,
- **historia rozwiązań, „Moje rozwiązania", panel administratora, próbny Etap 2 z timerem** (P3, P5, P8),
- **miniatury przesłanych zdjęć** (P7),
- niezacommitowane komponenty `frontend/src/components/account/DeleteAccountSection.tsx` i `frontend/src/components/ui/AiGeneratedNotice.tsx` — przejrzane, ale nieprzetestowane.

### Nie sprawdzono w ogóle — wymaga osobnych testów

| Obszar | Dlaczego to ważne | Jak sprawdzić |
|---|---|---|
| **Rzeczywisty odczyt wzorów przez czytnik ekranu po polsku** | Audyt potwierdził, że MathML jest generowany i poprawnie eksponowany. To warunek konieczny, ale **niewystarczający**. Jakość polskiej syntezy mowy dla MathML jest znacznie słabsza niż angielskiej; NVDA bez dodatku (MathCAT / Access8Math) może odczytywać wzory ubogo albo pomijać strukturę ułamków i indeksów. Od tego zależy, czy uczeń niewidomy w ogóle zrozumie treść zadania. **To najważniejszy niezweryfikowany punkt całego audytu.** | NVDA 2024+ z dodatkiem MathCAT, Firefox i Chrome, na 10 zadaniach o różnej gęstości LaTeX-a; równolegle VoiceOver + Safari |
| Czy `aria-label` umieszczony na `<div>`/`<span>` bez atrybutu `role` jest odczytywany | Decyduje o tym, czy opisy trudności i kategorii docierają do użytkownika (P2). Specyfikacja mówi, że nie powinien; praktyka czytników bywa różna | NVDA + JAWS na stronie zadania |
| Powiększenie tekstu do 200 % (kryterium 1.4.4) i wymuszone odstępy (1.4.12) | Osobne kryteria od reflow; przycinanie tekstu w kartach jest prawdopodobne (`Etap2PrepList.tsx:177-185` używa `whiteSpace: "nowrap"` z `textOverflow: "ellipsis"`) | Ctrl+= w przeglądarce; zakładka użytkownika z arkuszem wymuszającym odstępy |
| Zachowanie na telefonie, orientacja pozioma/pionowa (1.3.4) | Uczniowie będą korzystać głównie z telefonów — tam też robią zdjęcia rozwiązań | Prawdziwe urządzenie z Androidem i iOS |
| Czytniki mobilne (TalkBack, VoiceOver na iOS) | Wsparcie MathML na urządzeniach mobilnych jest jeszcze słabsze niż na komputerach | Prawdziwe urządzenie |
| Migotanie w pliku `omj-demo.gif` (kryterium 2.3.1) | Ryzyko dla ucznia z padaczką światłoczułą | Analiza klatka po klatce narzędziem PEAT lub równoważnym |
| Zachowanie sesji logowania i limitu czasu po stronie backendu (2.2.1) | Wygaśnięcie sesji w trakcie 3-godzinnego próbnego etapu oznaczałoby utratę pracy | Test funkcjonalny na środowisku produkcyjnym |
| Testy z udziałem uczniów z niepełnosprawnościami | Żaden audyt techniczny nie zastąpi obserwacji rzeczywistego użycia. W szkole z oddziałami integracyjnymi to jest realnie wykonalne i najbardziej wartościowe | Sesje obserwacyjne z 3–5 uczniami, po usunięciu blokerów z etapu I |

---

*Dokument sporządzono 20 sierpnia 2026 r. Wersję deklaracji dostępności do uzupełnienia przez podmiot publiczny zawiera plik [`deklaracja-dostepnosci.md`](./deklaracja-dostepnosci.md).*
