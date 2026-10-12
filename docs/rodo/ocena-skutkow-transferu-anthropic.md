# Ocena skutków transferu (TIA) — Anthropic (Claude API), USA

**Trener OMJ** · dokument uzupełniający do [DPIA](dpia.md), ryzyko R6

| | |
|---|---|
| Wersja | 1.0 — projekt |
| Data | 12.10.2026 |
| Sporządził | autor oprogramowania (na podstawie źródeł wskazanych w sekcji 8) |
| Zatwierdził administrator | [UZUPEŁNIĆ: data i podpis — wariant A: Rafał Sokołowski; wariant B: dyrektor szkoły] |
| Opiniował IOD | [UZUPEŁNIĆ: data i podpis — obowiązkowo w wariancie B] |
| Następny przegląd | przy przeglądzie DPIA lub wcześniej, gdy zajdzie zdarzenie z sekcji 7 |

> Dokument jest projektem przygotowanym przez autora oprogramowania i nie jest poradą prawną
> (zob. zastrzeżenie w [README](README.md)). Ustalenia faktyczne dotyczące Anthropic i prawa
> USA sprawdzono 12.10.2026; przed zatwierdzeniem należy je potwierdzić.

---

## 1. Po co ta ocena

Przekazanie danych do USA na podstawie **standardowych klauzul umownych** (art. 46 ust. 2
lit. c RODO) wymaga od administratora oceny, czy prawo i praktyka państwa odbiorcy pozwalają
odbiorcy faktycznie wywiązać się z klauzul (wyrok TSUE C-311/18 *Schrems II*; zalecenia EROD
01/2020; klauzula 14 standardowych klauzul umownych). Przy Google ta ocena nie jest potrzebna,
bo podstawą transferu jest decyzja o adekwatności (EU-US Data Privacy Framework). Przy Anthropic
— jest, bo Anthropic nie uczestniczy w tym programie (sekcja 3).

Ocena jest warunkiem ustawienia `ANTHROPIC_PROCESSOR_APPROVED=true` (DPIA, R6a i plan wdrożenia,
poz. 22).

## 2. Opis transferu

| | |
|---|---|
| Eksporter | administrator danych (wariant A: Rafał Sokołowski; wariant B: szkoła) |
| Importer | **Anthropic Ireland, Limited** (strona umowy dla klientów z EOG) — przetwarzanie odbywa się na serwerach Anthropic, PBC w USA i u jej podprocesorów |
| Status importera | podmiot przetwarzający (moduł drugi SCC); Anthropic Ireland → Anthropic, PBC — moduł trzeci |
| Konto API (wariant A) | zarejestrowane jako klient z EOG — potwierdzone przez administratora 12.10.2026 |
| Kategorie osób | uczniowie (w większości 13–15 lat, czyli dzieci w rozumieniu motywu 38 RODO) |
| Kategorie danych | fotografia odręcznego rozwiązania i/lub wpisany tekst rozwiązania; przy zadaniach prywatnych zdjęcie strony z treścią i treść zadania; przy wzorcach tekst wzorca i rozmowy o nim. **Bez** imienia, nazwiska, adresu e-mail i identyfikatora konta; nazwy plików są losowe |
| Dane szczególne | nie są przetwarzane celowo. Na zdjęciu może się przypadkowo znaleźć podpis ucznia lub otoczenie kartki (DPIA, R4) |
| Częstotliwość | Claude jest dostawcą **zapasowym**: dane trafiają do Anthropic przy wywołaniach AI wykonywanych, gdy Gemini API jest niedostępne (automatyczne przełączenie, `app/ai/failover.py` — przez czas otwarcia bezpiecznika wszystkie wywołania), albo gdy administrator ręcznie wybierze Claude. Oba tryby działają dopiero po ustawieniu `ANTHROPIC_PROCESSOR_APPROVED=true` |
| Sposób przekazania | HTTPS (TLS) do Messages API; zdjęcia i PDF-y w treści zapytania (base64), **bez** Files API |
| Okres przechowywania u importera | wejścia i wyjścia usuwane **w ciągu 30 dni**; dłużej tylko przy egzekwowaniu zasad korzystania z usługi (Usage Policy) lub z obowiązku prawnego |
| Wykorzystanie do trenowania modeli | wyłączone umownie (Commercial Terms: Anthropic may not train models on Customer Content) |
| Dalsze przekazania | do podprocesorów z listy Anthropic (anthropic.com/subprocessors), z prawem sprzeciwu w ciągu 15 dni od powiadomienia (DPA, sekcja C) — [UZUPEŁNIĆ: przejrzeć listę podprocesorów i odnotować datę przeglądu] |

## 3. Narzędzie transferu

- **EU-US Data Privacy Framework — nie ma zastosowania.** W oficjalnym rejestrze
  (dataprivacyframework.gov/list) 12.10.2026 nie ma Anthropic ani wśród uczestników aktywnych,
  ani nieaktywnych; wyszukiwanie kontrolne tym samym narzędziem zwraca „Google LLC", więc
  wyszukiwarka działała. Polityka prywatności Anthropic (obowiązująca od 10.09.2026) również
  nie powołuje się na DPF, tylko na decyzje o adekwatności i standardowe klauzule umowne.
- **Standardowe klauzule umowne** — włączone przez odesłanie do Data Processing Addendum
  Anthropic (obowiązującego od 24.02.2025): moduł drugi (administrator → podmiot przetwarzający)
  i/lub moduł trzeci (podmiot przetwarzający → podmiot przetwarzający). DPA wchodzi w skład
  Commercial Terms, akceptowanych przy założeniu konta API — nie wymaga odrębnego podpisu.

## 4. Prawo i praktyka USA mające znaczenie dla transferu

**Podstawy dostępu władz publicznych do danych.**

- **Art. 702 FISA** pozwala na pozyskiwanie danych cudzoziemców od dostawców usług łączności
  elektronicznej, do których najpewniej zalicza się dostawca API takiego jak Anthropic. Stan
  prawny na 12.10.2026 jest niepewny: ustawa RISAA z 2024 r. przewidywała wygaśnięcie 20.04.2026,
  Kongres przedłużył ją krótkoterminowo, a w czerwcu 2026 r. upoważnienie ustawowe wygasło bez
  ponownego uchwalenia. Według dostępnych informacji certyfikacje zatwierdzone przez sąd FISC
  w marcu 2026 r. pozostają jednak w mocy do ich wygaśnięcia (marzec 2027). **Ocena zakłada, że
  pozyskiwanie na podstawie art. 702 jest możliwe** — to założenie ostrożnościowe.
- **Executive Order 12333** — działania wywiadowcze poza FISA, w tym przechwytywanie danych
  w tranzycie.

**Zabezpieczenia.**

- **Executive Order 14086** (2022) ogranicza działania wywiadowcze do tego, co niezbędne
  i proporcjonalne, i tworzy dwustopniowy mechanizm skargowy z **Data Protection Review
  Court**. Komisja Europejska oceniła te zabezpieczenia w decyzji o adekwatności (2023/1795),
  a w opublikowanych z nią pytaniach i odpowiedziach (10.07.2023) wskazała, że obejmują one
  wszystkie dane przekazywane do USA, niezależnie od narzędzia transferu — także na podstawie
  standardowych klauzul umownych. To podstawowy argument tej
  oceny: poziom ochrony przed dostępem władz publicznych jest dla Anthropic taki sam jak dla
  Google, różni się tylko podstawa formalna.
- Sąd UE w wyroku T-553/23 (*Latombe*, 3.09.2025) uznał te zabezpieczenia za wystarczające;
  **odwołanie do TSUE (C-703/25 P) jest w toku**.

**Czynniki osłabiające (stan na 12.10.2026).**

- Rada PCLOB, która ma nadzorować stosowanie EO 14086, nie ma od 2025 r. kworum.
- EO 14086 jest aktem wykonawczym — każdy prezydent może go zmienić lub uchylić.
- Rozstrzygnięcie TSUE w sprawie *Latombe* może podważyć ocenę Komisji, a wraz z nią argument
  z poprzedniego punktu.

**Praktyka importera.** Raporty przejrzystości Anthropic (Transparency Hub, aktualizacja
29.01.2026): w okresie styczeń–czerwiec 2025 — zero żądań władz; lipiec–grudzień 2025 —
2 żądania treści (dane przekazano w 2 przypadkach) i 20 żądań danych innych niż treść.
Anthropic deklaruje badanie zasadności każdego żądania, kwestionowanie żądań nadmiernie
szerokich i powiadamianie klientów, o ile prawo tego nie zabrania. Raporty z natury nie
obejmują żądań objętych tajemnicą (np. FISA), więc świadczą tylko o tym, że dostęp do danych
klientów API nie jest zjawiskiem masowym.

## 5. Ocena ryzyka dla tego transferu

**Czy dane mogą zainteresować służby?** W praktyce nie: są to zdjęcia i teksty rozwiązań zadań
matematycznych z olimpiady dla młodzieży, bez imienia, nazwiska, e-maila i identyfikatora
konta. Nie dotyczą łączności, polityki, bezpieczeństwa ani osób, które mogłyby być celem
działań wywiadowczych. Prawdopodobieństwo, że te dane zostaną celowo pozyskane, jest bardzo
małe. Pozyskanie przy okazji szerszego przechwytywania (EO 12333) teoretycznie możliwe, ale
transmisja jest szyfrowana (TLS).

**Co by się stało, gdyby jednak zostały pozyskane?** Bez identyfikatorów powiązanie pracy
z konkretnym dzieckiem wymagałoby dodatkowych danych, których importer nie ma. Wyjątek: podpis
ucznia na kartce (DPIA, R4). Skutek dla dziecka byłby ograniczony (utrata prywatności wobec
wąskiego kręgu, bez dalszych następstw) — waga 2 w skali DPIA.

**Które środki działają przeciw dostępowi władz, a które nie.**

| Środek | Działa przeciw dostępowi władz? |
|---|---|
| Brak identyfikatorów ucznia, losowe nazwy plików (minimalizacja) | **tak** — ogranicza skutek |
| Szyfrowanie w tranzycie (TLS) | **tak** — przeciw przechwytywaniu w tranzycie (EO 12333) |
| Usuwanie w ciągu 30 dni, brak Files API | częściowo — skraca okno, w którym dane w ogóle istnieją |
| Zakaz trenowania modeli na danych | nie dotyczy dostępu władz, ale ogranicza dalsze wykorzystanie |
| Obowiązki importera z klauzul (powiadamianie, kwestionowanie żądań) | częściowo — w granicach prawa USA |
| Szyfrowanie end-to-end / pseudonimizacja treści | **niemożliwe** — model musi widzieć treść rozwiązania, żeby je ocenić |

Ostatni wiersz jest istotny: dla tego typu usługi (przetwarzanie treści przez AI) nie istnieje
środek techniczny, który uniemożliwiłby importerowi dostęp do treści. Ocena opiera się więc na
tym, że **dane mają niewielką wartość dla służb i są pozbawione identyfikatorów**, a nie na
tym, że dostęp jest technicznie niemożliwy.

## 6. Wniosek

Transfer do Anthropic na podstawie standardowych klauzul umownych **może się odbywać**.
Poziom ochrony przed dostępem władz USA jest w praktyce taki sam jak przy Google (te same
zabezpieczenia EO 14086), a charakter danych — rozwiązania zadań bez identyfikatorów ucznia —
sprawia, że ryzyko dla dzieci jest niskie co do prawdopodobieństwa i umiarkowane co do skutku.

Ocena ryzyka R6 w DPIA pozostaje bez zmian: **P = 2 · W = 2 → szczątkowe 3 (średnie)**,
wspólnie dla obu dostawców. Przy Anthropic ryzyko systemowe jest nieco wyższe niż przy Google
(brak decyzji o adekwatności dla tego importera, brak kworum PCLOB, niepewny stan art. 702),
ale nie przesuwa żadnego z czynników na wyższy poziom skali.

Warunki tego wniosku:

1. Do Anthropic nie trafiają identyfikatory ucznia — to zapewnia kod (DPIA, sekcja 2.5);
   zmiana tego założenia wymaga ponownej oceny.
2. Aplikacja nie korzysta z Files API ani z żadnej usługi Anthropic o dłuższym
   przechowywaniu.
3. Konto API pozostaje kontem klienta z EOG (umowa z Anthropic Ireland, Limited).

## 7. Kiedy ocenę trzeba powtórzyć

- TSUE wyda wyrok w sprawie *Latombe* (C-703/25 P) albo Komisja zmieni lub uchyli decyzję
  2023/1795;
- EO 14086 zostanie uchylony lub istotnie zmieniony, albo Data Protection Review Court
  przestanie działać;
- Kongres uchwali nowe przepisy zastępujące art. 702 FISA albo poszerzające jego zakres;
- Anthropic przystąpi do EU-US Data Privacy Framework (wtedy podstawą staje się art. 45 RODO,
  a ta ocena przestaje być wymagana);
- Anthropic zmieni okres przechowywania, zasady trenowania, DPA lub listę podprocesorów
  w sposób istotny dla tego transferu;
- raport przejrzystości Anthropic wykaże istotny wzrost liczby żądań dotyczących treści;
- aplikacja zacznie wysyłać do Anthropic nowe kategorie danych albo Anthropic stanie się
  dostawcą podstawowym zamiast zapasowego (wzrośnie skala transferu).

## 8. Źródła (stan na 12.10.2026)

- Anthropic Commercial Terms, obowiązujące od 17.06.2025 — anthropic.com/legal/commercial-terms
- Anthropic Data Processing Addendum, obowiązujący od 24.02.2025 —
  anthropic.com/legal/data-processing-addendum
- Anthropic Privacy Policy, obowiązująca od 10.09.2026 — anthropic.com/legal/privacy
- Okres przechowywania danych organizacji (aktualizacja 1.07.2026) — privacy.claude.com
- Anthropic Transparency Hub (aktualizacja 29.01.2026) i raporty o żądaniach władz
- Rejestr Data Privacy Framework — dataprivacyframework.gov/list (wyszukiwanie 12.10.2026)
- Decyzja wykonawcza Komisji (UE) 2023/1795 (adekwatność EU-US DPF) oraz pytania
  i odpowiedzi Komisji do tej decyzji (10.07.2023)
- Wyrok Sądu UE T-553/23 *Latombe v Komisja* (3.09.2025); odwołanie C-703/25 P
- Zalecenia EROD 01/2020 w sprawie środków uzupełniających
- Informacje prasowe i analizy o statusie art. 702 FISA (kwiecień–czerwiec 2026) — stan po
  czerwcu 2026 nie został potwierdzony w źródłach urzędowych; [UZUPEŁNIĆ: sprawdzić na
  congress.gov przed zatwierdzeniem]
