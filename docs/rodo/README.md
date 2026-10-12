# Dokumentacja ochrony danych — Trener OMJ

Katalog zawiera dokumenty dotyczące ochrony danych osobowych w narzędziu Trener OMJ.

> ## Zastrzeżenie
>
> **Wszystkie dokumenty w tym katalogu są projektami przygotowanymi przez autora
> oprogramowania na podstawie analizy kodu źródłowego. Nie są poradą prawną.**
>
> Przed użyciem wymagają weryfikacji przez **inspektora ochrony danych** i **radcę prawnego
> lub obsługę prawną szkoły**. Autor nie jest prawnikiem; dokumenty mają dać punkt wyjścia
> i rzetelnie opisać, co oprogramowanie faktycznie robi z danymi — reszta należy do osób
> odpowiedzialnych za zgodność.
>
> Miejsca oznaczone `[UZUPEŁNIĆ: …]` i `[DO USTALENIA]` wymagają decyzji człowieka.
> Dokumentu nie należy wdrażać bez ich wypełnienia.

---

## Dwa warianty wdrożenia

Ten sam kod może działać w dwóch scenariuszach, które **różnią się administratorem danych
i podstawą prawną przetwarzania**. Dobór dokumentu zaczyna się od ustalenia wariantu.

### Wariant A — serwis publiczny `omj-validator.pl`

- Administrator: **Rafał Sokołowski**, osoba fizyczna prowadząca niekomercyjny serwis.
- Użytkownik: dowolne dziecko logujące się prywatnym kontem Google albo loginem i hasłem
  (konto dla dziecka bez adresu e-mail; zawsze z adresem rodzica).
- Podstawa przetwarzania: **zgoda** (art. 6 ust. 1 lit. a RODO) — osoby od 16 lat (pole
  wyboru przy rejestracji), a za osobę młodszą i przy każdym koncie z loginem **zgoda rodzica
  lub opiekuna weryfikowana e-mailem** (art. 8 ust. 2 RODO; wytyczne EDPB 05/2020, pkt
  132–137): konto czeka nieaktywne, aż rodzic kliknie „Wyrażam zgodę” na stronie otwartej
  z wiadomości; bez zgody jest usuwane po 14 dniach. Oraz prawnie uzasadniony interes
  (lit. f) dla bezpieczeństwa i limitów.
- Dokument regulujący: **`frontend/src/app/regulamin/page.tsx`** — regulamin i polityka
  prywatności są częścią samego serwisu, a nie plikiem w tym katalogu.

### Wariant B — instancja szkolna

- Administrator: **szkoła**, reprezentowana przez dyrektora. Szkoła publiczna jest jednostką
  budżetową bez osobowości prawnej — administratorem nie jest gmina ani miasto (stroną umów
  cywilnoprawnych jest natomiast gmina).
- Szkoła uruchamia **własną instancję** z otwartego kodu (licencja MIT), na własnej
  infrastrukturze i z własnym kluczem API dostawcy AI. **Nie następuje przekazanie serwisu ani danych**
  między wariantem A a B — instancja szkolna startuje z pustą bazą.
- Podstawa przetwarzania: **art. 6 ust. 1 lit. e RODO** — zadanie realizowane w interesie
  publicznym (dydaktyka). Eliminuje to problem zgód dzieci poniżej 16 lat.
- Dokumenty regulujące: szablony w tym katalogu.

---

## Zawartość katalogu

| Plik | Czego dotyczy | Dla kogo | Wariant |
|---|---|---|---|
| [`dpia.md`](dpia.md) | Ocena skutków dla ochrony danych (art. 35 RODO). Dokument główny: opis operacji przetwarzania, przepływy danych, test niezbędności i proporcjonalności, rejestr ryzyk (R1–R21) z oszacowaniem i środkami, ryzyka szczątkowe, zgodność z AI Act i prawem autorskim, plan wdrożenia środków. | inspektor ochrony danych, dyrektor, administrator | **A i B** |
| [`ocena-skutkow-transferu-anthropic.md`](ocena-skutkow-transferu-anthropic.md) | Ocena skutków transferu do USA dla Anthropic (Claude API) — wymagana, bo transfer opiera się na standardowych klauzulach umownych, a nie na decyzji o adekwatności. Warunek ustawienia `ANTHROPIC_PROCESSOR_APPROVED=true`. | administrator, inspektor ochrony danych | **A i B** (tylko gdy używany jest Anthropic) |
| [`klauzula-informacyjna-szkola.md`](klauzula-informacyjna-szkola.md) | Klauzula informacyjna (art. 13 RODO). Część A — dla rodziców, część B — prostym językiem dla ucznia (art. 12 ust. 1 RODO wymaga formy zrozumiałej dla dziecka). | rodzice, uczniowie | **B** |
| [`regulamin-szkola.md`](regulamin-szkola.md) | Regulamin korzystania z narzędzia: zasady dla ucznia, zakazy, opis działania AI, rozgraniczenie „trenażer, nie ocenianie", prawa autorskie. | uczniowie, nauczyciele | **B** |
| `../../frontend/src/app/regulamin/page.tsx` | Regulamin i polityka prywatności serwisu publicznego (strona w aplikacji). | użytkownicy serwisu | **A** |

**Zmiana z 13 października 2026:** Google jako dostawca podstawowy, **Anthropic jako zapasowy**
z automatycznym przełączeniem przy niedostępności Gemini (za tą samą blokadą
`ANTHROPIC_PROCESSOR_APPROVED`); **Telegram** dostaje tylko zestawienia liczbowe i alarmy (bez danych osobowych);
**Cloudflare** (terminacja TLS, Turnstile przy rejestracji) jako nowe ryzyko R21; dziennik
dostępu administratora opisany z ograniczeniami; lista śladów po usunięciu konta; kopie
zapasowe; budżet dzienny AI i nowe limity; osobne pola akceptacji regulaminu i zgody (16+).
W DPIA: 2.3–2.7, 3.2, 3.4, R3, R4, R6a, R8, R9, R11, R15, R16, R20, R21, plan poz. 23–26;
w regulaminie serwisu punkty 1, 3–13, 16.

**Zmiana z 12 października 2026 (2):** rok urodzenia przy rejestracji, **zgoda rodzica
e-mailem** dla osób poniżej 16 lat i dla kont z loginem i hasłem, strona rodzica (usunięcie
konta = cofnięcie zgody, nowe hasło), **Resend** jako podmiot przetwarzający (wysyłka
e-maili; region wysyłki w UE, przetwarzanie głównie w USA — standardowe klauzule umowne
i DPF). W DPIA: 2.1, 2.5, 2.6, R15, R18–R20; w regulaminie serwisu punkty 3–9, 11, 12.

**Zmiana z 12 października 2026:** drugi, alternatywny dostawca AI — **Anthropic (Claude API)**
obok Google (Gemini API); w danym momencie aktywny jest jeden, wybrany przez administratora.
Uwzględniono we wszystkich czterech dokumentach (w DPIA: 2.5, 2.6, R6, R6a, R7, R12, plan
wdrożenia, przegląd).

> **Uwaga o spójności z kodem.** Okresy retencji podane w regulaminie serwisu publicznego
> (`frontend/src/app/regulamin/page.tsx`, stałe `RETENTION_*`) muszą odpowiadać konfiguracji
> w `app/config.py`. Zmiana konfiguracji na serwerze wymaga równoległej zmiany treści na stronie
> `/regulamin` — inaczej publiczna polityka prywatności przestaje być prawdziwa.

**Kolejność czytania:** `dpia.md` → następnie dokumenty operacyjne. DPIA zawiera ustalenia
faktyczne (co system naprawdę zbiera, komu wysyła, jak długo trzyma), z których pozostałe
dokumenty korzystają.

---

## Co trzeba zrobić przed użyciem

### Wypełnić we wszystkich dokumentach

- pełną nazwę i adres szkoły, dane kontaktowe,
- dane inspektora ochrony danych,
- imiona i nazwiska lub funkcje: nauczyciela prowadzącego, administratora narzędzia,
- adres instancji szkolnej,
- **okresy retencji** — pola celowo puste w szablonach szkolnych, bo mają być decyzją
  administratora. Wartości domyślne zaimplementowane w narzędziu (`app/config.py`) i obowiązujące
  w serwisie publicznym: zgłoszenia wraz ze zdjęciami **24 miesiące**, surowy zapis rozumowania
  modelu **90 dni**, konta nieaktywne **36 miesięcy**, dziennik dostępu administratora
  **12 miesięcy**, pseudonimowy znacznik limitu po usunięciu konta (zgłoszenia i wywołania AI
  przy zadaniach prywatnych i wzorcach) **24 godziny** od ostatniego użycia (przy dobowym
  przebiegu retencji do ok. 48 godzin),
  konto czekające na zgodę rodzica **14 dni**, adres e-mail rodzica — dopóki istnieje konto
  dziecka z nim powiązane (adres zastąpiony innym: doba), skróty linków wysłanych rodzicom
  **30 dni od wygaśnięcia**, nieudane próby logowania **24 godziny** (stałe w
  `app/retention.py`, nie konfiguracja). W wariancie B zgoda rodzica nie jest podstawą
  przetwarzania — instancja szkolna może te mechanizmy zostawić jako weryfikację kontaktu
  z rodzicem albo je wyłączyć w kodzie; do decyzji szkoły,
  Dzienniki serwera są ograniczone **objętościowo** (50 MB × 5 plików na usługę), a nie
  czasowo — opisywać mechanizm, nie liczbę dni,
- limity liczby zgłoszeń dobrane do liczebności grupy,
- daty, wersje, podpisy.

### Rozstrzygnąć przed uruchomieniem — sprawy wymagające decyzji lub opinii prawnika

1. **Klucz Gemini API musi być kluczem płatnym (przy Gemini).** Ocena ryzyka dla Google opiera
   się na tym, że na płatnym poziomie Gemini API Google nie wykorzystuje przesyłanych treści do
   trenowania modeli. Na poziomie bezpłatnym jest inaczej — uruchomienie na darmowym kluczu
   unieważnia wnioski DPIA. Odpowiednik dla Anthropic — punkt 9.
2. **Dostęp do materiałów olimpijskich musi zostać zamknięty za logowaniem.** W wyjściowej
   wersji kodu 162 pliki PDF i pełne treści zadań są serwowane publicznie. Dozwolony użytek
   instytucji oświatowych (art. 27 ust. 2 prawa autorskiego) wymaga ograniczenia dostępu do
   zidentyfikowanych uczniów i nauczycieli. **Wymaga zmiany w kodzie — nie jest zrobione.**
3. **Rola szkoły w rozumieniu AI Act** (dostawca czy podmiot stosujący) — do ustalenia
   z prawnikiem; wpływa na zakres obowiązków.
4. **Udokumentowanie oceny z art. 6 ust. 3 AI Act** — argumentacji, że narzędzie nie jest
   systemem wysokiego ryzyka, bo jego wynik nie ma skutków formalnych. Warunkiem jest
   utrzymanie zasady „to nie jest ocena szkolna" w regulaminie **i w praktyce**.
5. **Obowiązki z ustawy z 3.07.2026 o systemach sztucznej inteligencji** (Dz.U. 2026 poz. 1003;
   organ nadzoru: KRiBSI) wobec podmiotu stosującego — do sprawdzenia z prawnikiem.
6. **Tryb wprowadzenia regulaminu** (zarządzenie dyrektora, załącznik do statutu, regulamin
   pracowni) — do ustalenia.
7. **Umowy powierzenia** z dostawcą hostingu lub obsługi informatycznej, jeśli infrastruktura
   nie jest w całości szkolna.
8. **Prawa do treści zadań** — brak publicznej licencji OMJ na redystrybucję. Rozważyć
   wystąpienie do Stowarzyszenia na rzecz Edukacji Matematycznej o zgodę.
9. **Anthropic jako dostawca AI — tylko po zatwierdzeniu.** Wyboru Claude w panelu nie da się
   dokonać, a automatyczne przełączenie na Claude przy niedostępności Gemini nie działa, dopóki
   na serwerze nie ustawiono `ANTHROPIC_PROCESSOR_APPROVED=true`. Ustawić ją
   dopiero po akceptacji DPA Anthropic i ocenie skutków transferu (podstawą są standardowe
   klauzule umowne, nie DPF) — albo, jeśli szkoła korzysta tylko z Google, zostawić wyłączoną
   i usunąć Anthropic z klauzuli informacyjnej i regulaminu.

### Wykonać w konfiguracji instancji szkolnej

- wyłączyć powiadomienia zewnętrzne (Telegram) albo upewnić się, że wysyłane są wyłącznie
  zestawienia liczbowe bez danych osobowych (DPIA, R11),
- ustalić, czy instancja korzysta z Cloudflare (tunel, Turnstile przy rejestracji) i z Resend
  (e-maile do rodziców); jeśli tak — umowy i wpis do klauzuli, jeśli nie — usunąć te wiersze
  z klauzuli (DPIA, R20, R21),
- wyłączyć tłumaczenie komunikatów przez zewnętrzną usługę albo udokumentować je w rejestrze
  czynności (nagłówki dotyczą treści pracy ucznia),
- ograniczyć listę kont administracyjnych i wystawić upoważnienia z art. 29 RODO,
- ustalić, kto i jak często przegląda **dziennik dostępu administratora** (`admin_access_log`) —
  sam dziennik nikogo nie powstrzymuje, dopóki nikt do niego nie zagląda,
- rozważyć rotację **czasową** dzienników, gdyby potrzebny był ścisły okres przechowywania —
  rotacja objętościowa i maskowanie adresów są już wdrożone,
- skonfigurować i **przetestować** szyfrowane kopie zapasowe.

### Uzupełnić dokumentację poza tym katalogiem

- **rejestr czynności przetwarzania** (art. 30 RODO) — wpisać czynność do rejestru szkoły,
- **procedurę reakcji na naruszenie ochrony danych** (72 godziny, art. 33–34),
- **procedurę obsługi żądań** osób, których dane dotyczą,
- **ewidencję upoważnień**,
- **przeszkolenie nauczycieli** z ograniczeń narzędzia (art. 4 AI Act — kompetencje w zakresie
  sztucznej inteligencji dotyczą również podmiotów stosujących).

---

## Zasada, na której trzyma się cała konstrukcja

Narzędzie pozostaje poza kategorią systemów wysokiego ryzyka i poza zakresem art. 22 RODO
tylko dopóty, dopóki prawdziwe są jednocześnie trzy zdania:

1. wynik z narzędzia **nie jest oceną szkolną** i nie trafia do dokumentacji przebiegu nauczania,
2. wynik **nie wpływa** na klasyfikację, promocję, rekrutację ani na kwalifikację do zawodów,
3. korzystanie z narzędzia jest **dobrowolne**, a rezygnacja nie ma negatywnych skutków.

Jeśli którekolwiek przestanie być prawdziwe — w regulaminie albo tylko w praktyce nauczycielskiej
— kwalifikacja prawna narzędzia zmienia się, a DPIA wymaga ponownego przeprowadzenia.

---

## Przegląd dokumentów

Aktualizacja co najmniej raz na 12 miesięcy oraz niezwłocznie po każdej istotnej zmianie:
wprowadzeniu dostawcy AI innego niż Google i Anthropic, pierwszym włączeniu Anthropic jako
aktywnego dostawcy, zmianie modelu AI lub warunków przetwarzania danych u któregokolwiek
z dostawców, zmianie zakresu zbieranych danych, rozszerzeniu kręgu osób z dostępem do danych
uczniów, naruszeniu ochrony danych, zmianie stanu prawnego. Samo przełączenie między Google
a Anthropic nie wymaga zmiany dokumentów (DPIA, R6a).
