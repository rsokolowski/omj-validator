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
- Użytkownik: dowolne dziecko logujące się prywatnym kontem Google.
- Podstawa przetwarzania: **zgoda rodzica lub opiekuna** (art. 6 ust. 1 lit. a RODO)
  — bo grupa docelowa jest poniżej progu 16 lat obowiązującego w Polsce; oraz prawnie
  uzasadniony interes (lit. f) dla bezpieczeństwa i limitów.
- Dokument regulujący: **`frontend/src/app/regulamin/page.tsx`** — regulamin i polityka
  prywatności są częścią samego serwisu, a nie plikiem w tym katalogu.

### Wariant B — instancja szkolna

- Administrator: **szkoła**, reprezentowana przez dyrektora. Szkoła publiczna jest jednostką
  budżetową bez osobowości prawnej — administratorem nie jest gmina ani miasto (stroną umów
  cywilnoprawnych jest natomiast gmina).
- Szkoła uruchamia **własną instancję** z otwartego kodu (licencja MIT), na własnej
  infrastrukturze i z własnym kluczem Google. **Nie następuje przekazanie serwisu ani danych**
  między wariantem A a B — instancja szkolna startuje z pustą bazą.
- Podstawa przetwarzania: **art. 6 ust. 1 lit. e RODO** — zadanie realizowane w interesie
  publicznym (dydaktyka). Eliminuje to problem zgód dzieci poniżej 16 lat.
- Dokumenty regulujące: szablony w tym katalogu.

---

## Zawartość katalogu

| Plik | Czego dotyczy | Dla kogo | Wariant |
|---|---|---|---|
| [`dpia.md`](dpia.md) | Ocena skutków dla ochrony danych (art. 35 RODO). Dokument główny: opis operacji przetwarzania, przepływy danych, test niezbędności i proporcjonalności, rejestr 17 ryzyk z oszacowaniem i środkami, ryzyka szczątkowe, zgodność z AI Act i prawem autorskim, plan wdrożenia środków. | inspektor ochrony danych, dyrektor, administrator | **A i B** |
| [`klauzula-informacyjna-szkola.md`](klauzula-informacyjna-szkola.md) | Klauzula informacyjna (art. 13 RODO). Część A — dla rodziców, część B — prostym językiem dla ucznia (art. 12 ust. 1 RODO wymaga formy zrozumiałej dla dziecka). | rodzice, uczniowie | **B** |
| [`regulamin-szkola.md`](regulamin-szkola.md) | Regulamin korzystania z narzędzia: zasady dla ucznia, zakazy, opis działania AI, rozgraniczenie „trenażer, nie ocenianie", prawa autorskie. | uczniowie, nauczyciele | **B** |
| `../../frontend/src/app/regulamin/page.tsx` | Regulamin i polityka prywatności serwisu publicznego (strona w aplikacji). | użytkownicy serwisu | **A** |

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
  **12 miesięcy**, pseudonimowy znacznik limitu po usunięciu konta **maks. 24 godziny**.
  Dzienniki serwera są ograniczone **objętościowo** (50 MB × 5 plików na usługę), a nie
  czasowo — opisywać mechanizm, nie liczbę dni,
- limity liczby zgłoszeń dobrane do liczebności grupy,
- daty, wersje, podpisy.

### Rozstrzygnąć przed uruchomieniem — sprawy wymagające decyzji lub opinii prawnika

1. **Klucz API musi być kluczem płatnym.** Cała ocena ryzyka opiera się na tym, że na płatnym
   poziomie Gemini API Google nie wykorzystuje przesyłanych treści do trenowania modeli.
   Na poziomie bezpłatnym jest inaczej — uruchomienie na darmowym kluczu unieważnia wnioski DPIA.
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

### Wykonać w konfiguracji instancji szkolnej

- wyłączyć powiadomienia zewnętrzne (Telegram) — brak umowy powierzenia, podmiot spoza EOG,
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
zmianie dostawcy lub modelu AI, zmianie zakresu zbieranych danych, rozszerzeniu kręgu osób
z dostępem do danych uczniów, naruszeniu ochrony danych, zmianie stanu prawnego.
