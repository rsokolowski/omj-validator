# Deklaracja dostępności — projekt do uzupełnienia przez podmiot publiczny

> **UWAGA — to jest szablon, a nie gotowy dokument.**
>
> Wszystkie miejsca oznaczone `[…]` musi wypełnić szkoła. Deklaracja opublikowana z niewypełnionymi polami albo z nieprawdziwym statusem zgodności jest deklaracją wadliwą i podlega karze pieniężnej do 5 000 zł (art. 19 ust. 1 pkt 2 ustawy z dnia 4 kwietnia 2019 r. o dostępności cyfrowej stron internetowych i aplikacji mobilnych podmiotów publicznych, Dz.U. 2019 poz. 848).
>
> **Status zgodności podany niżej („częściowo zgodna") odpowiada rzeczywistemu stanowi serwisu ustalonemu w audycie z 20 sierpnia 2026 r.** ([`audyt-wcag.md`](./audyt-wcag.md)). Jeżeli przed publikacją deklaracji część usterek zostanie usunięta, należy odpowiednio skrócić listę nieprawidłowości — ale **nie wolno zadeklarować pełnej zgodności, dopóki wszystkie 17 niespełnionych kryteriów nie zostanie naprawionych i potwierdzonych testem**.
>
> Instrukcja techniczna publikacji znajduje się na końcu dokumentu (rozdział „Jak opublikować deklarację").

---

## Deklaracja dostępności serwisu Trener OMJ

**[NAZWA SZKOŁY — np. Szkoła Podstawowa nr … im. … w …]** zobowiązuje się zapewnić dostępność swojej strony internetowej zgodnie z przepisami ustawy z dnia 4 kwietnia 2019 r. o dostępności cyfrowej stron internetowych i aplikacji mobilnych podmiotów publicznych.

Niniejsza deklaracja dostępności dotyczy serwisu internetowego **Trener OMJ**, dostępnego pod adresem **https://omj-validator.pl**.

| | |
|---|---|
| **Data publikacji strony internetowej** | `[DD-MM-RRRR — data pierwszego udostępnienia serwisu uczniom szkoły]` |
| **Data ostatniej istotnej aktualizacji** | `[DD-MM-RRRR]` |
| **Data sporządzenia deklaracji** | `[DD-MM-RRRR]` |
| **Data ostatniego przeglądu deklaracji** | `[DD-MM-RRRR]` |

---

### Status pod względem zgodności z ustawą

Strona internetowa jest **częściowo zgodna** z ustawą z dnia 4 kwietnia 2019 r. o dostępności cyfrowej stron internetowych i aplikacji mobilnych podmiotów publicznych **z powodu niezgodności lub wyłączeń wymienionych poniżej**.

#### Treści niedostępne — wykaz nieprawidłowości wraz z uzasadnieniem

Poniższa lista odzwierciedla stan serwisu ustalony w audycie z dnia `[DD-MM-RRRR]`. Po każdej pozycji podano kryterium WCAG 2.1 oraz planowany termin usunięcia.

**A. Nieprawidłowości uniemożliwiające skorzystanie z podstawowej funkcji serwisu**

1. **Przesłanie zdjęcia rozwiązania nie jest możliwe wyłącznie za pomocą klawiatury.** Pole wyboru pliku jest ukryte w sposób usuwający je z kolejności tabulacji, a obszar „Przeciągnij zdjęcia lub kliknij, aby wybrać" reaguje tylko na kliknięcie myszą. Osoba korzystająca wyłącznie z klawiatury, czytnika ekranu, przełącznika lub sterowania głosem nie może wykonać podstawowej czynności w serwisie.
   *Kryteria: 2.1.1 Klawiatura (A), 4.1.2 Nazwa, rola, wartość (A), 3.3.2 Etykiety lub instrukcje (A). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

2. **Przebieg oceniania rozwiązania nie jest komunikowany czytnikom ekranu.** Analiza rozwiązania trwa kilkanaście sekund, a informacje o jej postępie („Przesyłam pliki…", „Analizuję rozwiązanie…") wyświetlają się wyłącznie wizualnie. Użytkownik niewidomy nie otrzymuje potwierdzenia, że system pracuje. (Sam wynik końcowy wraz z komentarzem jest prawidłowo ogłaszany.)
   *Kryterium: 4.1.3 Komunikaty o stanie (AA). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

**B. Nieprawidłowości utrudniające nawigację i orientację**

3. **Brak możliwości pominięcia powtarzalnych bloków.** Serwis nie zawiera linku „Przejdź do treści głównej", a menu główne nie jest oznaczone jako punkt orientacyjny nawigacji. Użytkownik klawiatury musi na każdej podstronie przechodzić przez wszystkie linki nagłówka.
   *Kryterium: 2.4.1 Możliwość pominięcia bloków (A). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

4. **Nieprawidłowa hierarchia nagłówków.** Na stronach występują nagłówki poziomu 6 przed nagłówkiem poziomu 1, brakuje poziomów pośrednich, a część nagłówków zawiera wyłącznie liczby. Utrudnia to nawigację po strukturze strony czytnikiem ekranu.
   *Kryteria: 1.3.1 Informacje i relacje (A), 2.4.6 Nagłówki i etykiety (AA). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

5. **Trzy podstrony (logowanie, „Moje rozwiązania", panel administratora) nie mają własnych tytułów** i posługują się tytułem strony głównej.
   *Kryterium: 2.4.2 Tytuł strony (A). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

**C. Nieprawidłowości dotyczące osób słabowidzących**

6. **Treść wymaga przewijania w poziomie na wąskich ekranach i przy dużym powiększeniu.** Przy szerokości odpowiadającej 320 pikselom (powiększenie 400 %) strona ma szerokość 379 pikseli. Przyczyną jest pasek nawigacji, który nie zawija się ani nie zwija do menu; dodatkowo wzory matematyczne wpisane w tekst wykraczają poza szerokość ekranu.
   *Kryterium: 1.4.10 Zawijanie tekstu (AA). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

7. **Niewystarczający kontrast części elementów.** Kilkanaście par kolorów nie osiąga wymaganego współczynnika. Najpoważniejsze przypadki (wartości zmierzone przy wymaganym minimum 4,5:1 dla tekstu i 3:1 dla elementów interfejsu): gwiazdki poziomu trudności 1,92–3,76:1; oznaczenie „tylko odczyt" 2,16:1; link „Wyloguj" 2,54:1; wynik punktowy 3,19–3,77:1; liczby na kafelkach statystyk 2,15–2,54:1; obramowanie pola przesyłania plików 1,41:1; wypełnienie paska postępu 1,84:1.
   *Kryteria: 1.4.3 Kontrast minimalny (AA), 1.4.11 Kontrast elementów nietekstowych (AA). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

**D. Nieprawidłowości dotyczące ruchu i animacji**

8. **Animowany obrazek na stronie głównej odtwarza się automatycznie w nieskończonej pętli i nie można go zatrzymać.** Animacja trwa 18,7 sekundy i powtarza się bez końca. Serwis nie respektuje też systemowego ustawienia ograniczenia animacji (`prefers-reduced-motion`).
   *Kryterium: 2.2.2 Pauza, zatrzymanie, ukrycie (A). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

**E. Nieprawidłowości dotyczące informacji dodatkowych**

9. **Poziom trudności zadania, opis kategorii tematycznej oraz tytuł zadania powiązanego są dostępne wyłącznie po najechaniu kursorem myszy.** Elementy te nie są osiągalne z klawiatury, a ich opisy nie są prawidłowo powiązane z czytnikiem ekranu. Poziom trudności jest dodatkowo sygnalizowany kolorem.
   *Kryteria: 1.1.1 Treść nietekstowa (A), 1.4.1 Użycie koloru (A), 2.1.1 Klawiatura (A), 1.4.13 Treść spod kursora lub fokusu (AA). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

10. **Sekcje rozwijane (wskazówki, umiejętności, historia rozwiązań) nie przekazują informacji o swoim stanie** — czytnik ekranu nie ogłasza, czy sekcja jest zwinięta czy rozwinięta, a odsłonięcie nowej wskazówki nie jest komunikowane. Część przycisków rozwijających zawiera wyłącznie ikonę i nie ma nazwy dostępnej.
    *Kryteria: 4.1.2 Nazwa, rola, wartość (A), 4.1.3 Komunikaty o stanie (AA), 2.4.4 Cel linku w kontekście (A). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

11. **Lista rozwiązań doładowuje się automatycznie przy przewijaniu**, bez przycisku „Załaduj więcej" i bez komunikatu o doładowaniu. Utrudnia to dotarcie do stopki i korzystanie z listy przy pomocy klawiatury.
    *Kryteria: 2.4.1 Możliwość pominięcia bloków (A), 4.1.3 Komunikaty o stanie (AA). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

12. **Zakończenie odliczania czasu w trybie „Próbny Etap 2" nie jest sygnalizowane dźwiękowo ani komunikatem dla czytnika ekranu.** Panel z zegarem znika bez powiadomienia.
    *Kryterium: 4.1.3 Komunikaty o stanie (AA). Planowany termin usunięcia: `[DD-MM-RRRR]`.*

#### Elementy, które są dostępne — informacja dla użytkowników

Dla jasności obrazu podajemy również, co w serwisie działa prawidłowo:

- **Wzory matematyczne są dostępne dla czytników ekranu.** Każdy wzór jest publikowany równolegle w formacie MathML, czytelnym dla oprogramowania asystującego, a jego wersja graficzna jest przed czytnikiem ukrywana. Uwaga: jakość odczytu wzorów zależy od używanego czytnika ekranu i syntezatora mowy — zalecamy program NVDA z dodatkiem MathCAT.
- Język stron jest prawidłowo zadeklarowany jako polski.
- Ikony dekoracyjne są prawidłowo pomijane przez czytniki ekranu, a wszystkie obrazy mają tekst alternatywny.
- Element aktywny (fokus klawiatury) jest widocznie oznaczony.
- Nierozwinięte wskazówki są prawidłowo ukryte także przed czytnikiem ekranu.
- Wynik oceny wraz z komentarzem jest ogłaszany czytnikowi ekranu automatycznie po zakończeniu analizy.
- Serwis nie zawiera treści migających w sposób mogący wywołać napad padaczki `[UWAGA: to twierdzenie wymaga potwierdzenia — animacja na stronie głównej nie została przeanalizowana klatka po klatce. Do czasu weryfikacji ZDANIE NALEŻY USUNĄĆ albo przeprowadzić badanie narzędziem PEAT]`.

#### Wyłączenia

`[Wypełnić, jeżeli dotyczy. Możliwe podstawy wyłączenia — art. 3 ust. 2 ustawy:]`

- Dokumenty PDF z treściami zadań i rozwiązaniami olimpiady pochodzą ze strony Olimpiady Matematycznej Juniorów (https://omj.edu.pl) i **nie zostały wytworzone przez `[NAZWA SZKOŁY]`**. Są udostępniane jako materiały źródłowe. `[Zweryfikować, czy pliki te podlegają wyłączeniu z art. 3 ust. 2 pkt 5 (treści niewytworzone przez podmiot publiczny i przez niego niefinansowane) — jeżeli nie podlegają, konieczne jest zapewnienie ich dostępności lub zapewnienie dostępu alternatywnego.]`
- `[Inne wyłączenia, jeżeli występują.]`

---

### Przygotowanie deklaracji dostępności

- **Data sporządzenia deklaracji:** `[DD-MM-RRRR]`
- **Deklarację sporządzono na podstawie:** `[wybrać jedno:]`
  - `[ ] samooceny przeprowadzonej przez podmiot publiczny`
  - `[ ] oceny przeprowadzonej przez podmiot zewnętrzny: [nazwa podmiotu]`
- **Metoda oceny:** analiza kodu źródłowego aplikacji, testy w przeglądarce z wykorzystaniem narzędzi automatycznych, obliczenie współczynników kontrastu zgodnie z metodyką WCAG 2.1. `[Uzupełnić o wynik testów z czytnikiem ekranu, gdy zostaną przeprowadzone.]`
- **Data ostatniego przeglądu deklaracji:** `[DD-MM-RRRR]`

> Przypomnienie: **deklarację należy przeglądać i aktualizować nie rzadziej niż raz w roku**, a także każdorazowo po istotnej zmianie w serwisie (art. 10 ust. 3 ustawy).

---

### Skróty klawiaturowe

Serwis nie zawiera własnych skrótów klawiaturowych. Obsługa odbywa się przy pomocy standardowych skrótów przeglądarki internetowej (`Tab` — następny element, `Shift + Tab` — poprzedni element, `Enter` / `Spacja` — uruchomienie elementu).

`[Zaktualizować, jeżeli po wdrożeniu poprawek zostaną dodane skróty — np. link „Przejdź do treści głównej" dostępny po naciśnięciu Tab na początku strony.]`

---

### Informacje zwrotne i dane kontaktowe

W przypadku problemów z dostępnością strony internetowej prosimy o kontakt.

| | |
|---|---|
| **Osoba do kontaktu / koordynator do spraw dostępności** | `[IMIĘ I NAZWISKO]` |
| **Stanowisko** | `[np. koordynator do spraw dostępności]` |
| **Adres e-mail** | `[adres@szkola.edu.pl]` |
| **Numer telefonu** | `[+48 …]` |
| **Adres do korespondencji** | `[ulica, kod pocztowy, miejscowość]` |

Tą samą drogą można składać **wnioski o udostępnienie informacji niedostępnej** oraz **żądania zapewnienia dostępności**.

> **Uwaga dla szkoły:** wyznaczenie koordynatora do spraw dostępności jest odrębnym obowiązkiem ustawowym, wynikającym z art. 14 ustawy z dnia 19 lipca 2019 r. o zapewnianiu dostępności osobom ze szczególnymi potrzebami (Dz.U. 2019 poz. 1696 z późn. zm.). Dane koordynatora muszą być podane w deklaracji i opublikowane w Biuletynie Informacji Publicznej.

---

### Procedura wnioskowo-skargowa

Każdy ma prawo wystąpić z **żądaniem zapewnienia dostępności cyfrowej** strony internetowej, aplikacji mobilnej lub ich elementu, albo o **udostępnienie informacji za pomocą alternatywnego sposobu dostępu** — na przykład przez odczytanie niedostępnego cyfrowo dokumentu, opisanie zawartości filmu bez audiodeskrypcji, przekazanie treści w formie pliku tekstowego lub kontakt telefoniczny.

**Żądanie powinno zawierać:**

1. dane kontaktowe osoby występującej z żądaniem,
2. wskazanie strony internetowej lub elementu strony, które mają być dostępne cyfrowo,
3. wskazanie sposobu kontaktu dogodnego dla osoby występującej z żądaniem,
4. jeżeli osoba żądająca zgłasza potrzebę otrzymania informacji za pomocą alternatywnego sposobu dostępu — wskazanie dogodnego dla niej sposobu przedstawienia tej informacji.

**Terminy rozpatrzenia:**

- Podmiot publiczny realizuje żądanie **niezwłocznie, nie później niż w ciągu 7 dni** od dnia wystąpienia z żądaniem.
- Jeżeli dotrzymanie tego terminu nie jest możliwe, podmiot **niezwłocznie powiadamia** osobę występującą z żądaniem o przyczynach opóźnienia i wskazuje nowy termin, **nie dłuższy niż 2 miesiące** od dnia wystąpienia z żądaniem.
- Jeżeli zapewnienie dostępności cyfrowej nie jest możliwe, podmiot publiczny **proponuje alternatywny sposób dostępu** do informacji.

**Skarga.** W przypadku odmowy zapewnienia dostępności cyfrowej wskazanego elementu, gdy osoba występująca z żądaniem uzna to za niewłaściwe, oraz w przypadku odmowy skorzystania z alternatywnego sposobu dostępu — osobie występującej z żądaniem przysługuje prawo **złożenia skargi w sprawie zapewnienia dostępności cyfrowej**. Skargę składa się do `[NAZWA SZKOŁY]` na adres podany powyżej, z zastosowaniem przepisów ustawy z dnia 14 czerwca 1960 r. — Kodeks postępowania administracyjnego.

**Rzecznik Praw Obywatelskich.** Po wyczerpaniu wskazanej wyżej procedury można także złożyć wniosek do Rzecznika Praw Obywatelskich:

- Strona internetowa: **https://www.rpo.gov.pl**
- Adres: Biuro Rzecznika Praw Obywatelskich, al. Solidarności 77, 00-090 Warszawa
- Infolinia: **800 676 676** (połączenie bezpłatne z telefonów stacjonarnych i komórkowych)
- E-mail: **biurorzecznika@brpo.gov.pl**

---

### Dostępność architektoniczna

`[Poniższy rozdział dotyczy budynku szkoły, nie serwisu internetowego. Jest obowiązkowym elementem deklaracji zgodnie z art. 10 ust. 4 ustawy o dostępności cyfrowej w związku z art. 6 ustawy o zapewnianiu dostępności osobom ze szczególnymi potrzebami. Musi zostać wypełniony przez szkołę na podstawie faktycznego stanu budynku — poniższe punkty to lista kontrolna, a nie opis rzeczywistości.]`

**`[NAZWA SZKOŁY]`, `[pełny adres]`**

1. **Dojście i wejście do budynku.** `[Opisać: czy prowadzi utwardzona droga, czy są schody, czy jest pochylnia/podjazd, jakie jest nachylenie, czy przy wejściu są poręcze, czy drzwi są automatyczne, jaka jest szerokość otworu drzwiowego.]`
2. **Komunikacja pozioma i pionowa w budynku.** `[Opisać: liczba kondygnacji, obecność windy lub platformy przyschodowej, szerokość korytarzy, obecność progów, oznaczenia kontrastowe na schodach, poręcze.]`
3. **Toalety.** `[Opisać: czy w budynku znajduje się toaleta przystosowana dla osób z niepełnosprawnością ruchową, na której kondygnacji.]`
4. **Miejsca parkingowe.** `[Opisać: czy przy budynku wyznaczono miejsce parkingowe dla osób z niepełnosprawnościami, ile miejsc, gdzie.]`
5. **Prawo wstępu z psem asystującym.** `[Standardowo: „Do budynku i wszystkich jego pomieszczeń można wejść z psem asystującym i psem przewodnikiem." — potwierdzić i wpisać ewentualne ograniczenia.]`
6. **Tłumacz języka migowego.** `[Opisać: czy szkoła zapewnia usługę tłumacza polskiego języka migowego (PJM) na miejscu lub online, w jakim trybie i z jakim wyprzedzeniem należy ją zgłosić. Jeżeli usługa nie jest dostępna — napisać to wprost.]`
7. **Informacja o rozkładzie pomieszczeń.** `[Opisać: czy w budynku jest tablica informacyjna, plan tyflograficzny, oznaczenia w alfabecie Braille'a, oznaczenia kontrastowe lub druk powiększony.]`
8. **Pętla indukcyjna i inne udogodnienia dla osób słabosłyszących.** `[Opisać lub napisać, że nie występują.]`
9. **Ewakuacja.** `[Opisać: czy przygotowano procedurę ewakuacji osób ze szczególnymi potrzebami, czy w budynku są krzesła ewakuacyjne, czy system alarmowy obejmuje sygnalizację świetlną dla osób niesłyszących.]`

---

### Aplikacje mobilne

`[NAZWA SZKOŁY]` nie udostępnia aplikacji mobilnych. Serwis Trener OMJ jest dostępny wyłącznie jako strona internetowa działająca w przeglądarce.

`[Zaktualizować, jeżeli stan faktyczny jest inny.]`

---

### Informacja o serwisie i jego dostawcy

Serwis Trener OMJ jest niekomercyjnym projektem edukacyjnym o otwartym kodzie źródłowym (licencja MIT), udostępnianym pod adresem https://omj-validator.pl. Kod źródłowy: https://github.com/rsokolowski/omj-validator.

`[UWAGA DLA SZKOŁY — zagadnienie do rozstrzygnięcia przed publikacją deklaracji:]`
`[Serwis nie jest utrzymywany przez szkołę, lecz przez osobę trzecią. Jeżeli szkoła udostępnia go uczniom jako własne narzędzie edukacyjne, ponosi odpowiedzialność za jego dostępność cyfrową. Należy ustalić z dostawcą serwisu — najlepiej w formie pisemnego porozumienia — kto i w jakim terminie odpowiada za usunięcie nieprawidłowości wymienionych w tej deklaracji oraz kto realizuje żądania zapewnienia dostępności zgłaszane przez użytkowników w terminach ustawowych (7 dni / 2 miesiące). Bez takiego ustalenia szkoła nie będzie w stanie dotrzymać terminów, do których zobowiązuje ją ustawa.]`

`[Do rozważenia: dopóki nieprawidłowości z grupy A (przesyłanie rozwiązań z klawiatury, komunikaty o stanie) nie zostaną usunięte, szkoła powinna zapewnić alternatywny sposób dostępu — na przykład możliwość przekazania rozwiązania nauczycielowi w innej formie i uzyskania oceny bez korzystania z serwisu. Informację o takiej możliwości należy dopisać do sekcji „Informacje zwrotne i dane kontaktowe".]`

---
---

## Jak opublikować deklarację — instrukcja techniczna

`[Ta część NIE wchodzi w skład deklaracji. Usunąć przed publikacją.]`

### Wymagania formalne

1. **Deklaracja musi być dostępna ze strony głównej serwisu.** Ustawa wymaga, by odnośnik do deklaracji był umieszczony na stronie głównej albo był dostępny z każdej podstrony. W praktyce najlepiej dodać link „Deklaracja dostępności" do stopki serwisu — plik `frontend/src/components/layout/Footer.tsx`, w sekcji „Linki", obok istniejącego odnośnika do regulaminu.
2. **Deklaracja musi być sama dostępna cyfrowo.** Nie wolno publikować jej jako skanu PDF ani obrazu. Zalecana forma: osobna podstrona HTML, np. `/deklaracja-dostepnosci`, zbudowana analogicznie do istniejącej strony `frontend/src/app/regulamin/page.tsx` — z prawidłową hierarchią nagłówków (`h1` → `h2` → `h3`) i własnym tytułem strony w `export const metadata`.
3. **Deklaracja musi być opublikowana także w Biuletynie Informacji Publicznej szkoły.**
4. **Przegląd co najmniej raz w roku** oraz po każdej istotnej zmianie serwisu. Warto ustawić przypomnienie w kalendarzu.

### Kolejność czynności

1. Uzupełnić wszystkie pola `[…]` w niniejszym szablonie.
2. Zweryfikować, które z 12 nieprawidłowości zostały już usunięte, i skreślić je z listy. **Nie skracać listy „na wyrost".**
3. Usunąć niniejszy rozdział instrukcyjny oraz wszystkie komentarze w nawiasach kwadratowych.
4. Przenieść treść na podstronę HTML serwisu i do BIP.
5. Dodać link w stopce serwisu.
6. Zapisać datę sporządzenia i wpisać do kalendarza datę kolejnego przeglądu (12 miesięcy).

### Podstawa prawna

- Ustawa z dnia 4 kwietnia 2019 r. o dostępności cyfrowej stron internetowych i aplikacji mobilnych podmiotów publicznych (Dz.U. 2019 poz. 848 z późn. zm.) — w szczególności art. 5 (wymóg WCAG 2.1 AA wg załącznika), art. 10 (treść i przegląd deklaracji), art. 18 (żądanie zapewnienia dostępności), art. 19 (kary pieniężne: do 10 000 zł za utrzymującą się niedostępność, do 5 000 zł za brak lub wadliwą deklarację).
- Ustawa z dnia 19 lipca 2019 r. o zapewnianiu dostępności osobom ze szczególnymi potrzebami (Dz.U. 2019 poz. 1696 z późn. zm.) — art. 6 (dostępność architektoniczna, informacyjno-komunikacyjna i cyfrowa), art. 14 (koordynator do spraw dostępności).
- Wzór deklaracji dostępności: załącznik do decyzji wykonawczej Komisji (UE) 2018/1523 z dnia 11 października 2018 r.

### Powiązane dokumenty

- [`audyt-wcag.md`](./audyt-wcag.md) — pełny audyt dostępności cyfrowej z 20 sierpnia 2026 r., wraz z listą ustaleń, tabelą 50 kryteriów WCAG 2.1 AA, wyceną prac i wykazem tego, czego nie udało się zweryfikować.
