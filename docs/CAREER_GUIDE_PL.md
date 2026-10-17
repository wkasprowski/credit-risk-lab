# Projekt w CV i na rozmowie

Materiał opisuje zakres projektu portfolio, a nie doświadczenie komercyjne. Użyj sformułowań po poznaniu kodu, uruchomieniu procesu i przejściu wyników. Nie deklaruj samodzielnego autorstwa nieprzejrzanego kodu ani ukończonego Power BI.

## Trzy krótkie punkty do polskiego CV

- Projekt portfolio SQL/Python: przetwarzanie syntetycznego portfela 6 000 umów i 72 000 rekordów kontrakt–miesiąc, kontrola jakości danych i analizy w SQLite.
- Analiza PD i LGD z walidacją czasową oraz scenariuszowa kalkulacja ECL uwzględniająca etapy ryzyka, harmonogram ekspozycji i dyskonto.
- Weryfikacja obliczeń przez 26 testów Python oraz dashboard HTML z wynikami zgodnymi z SQL dla 768 kombinacji filtrów.

Nagłówek: **Credit Risk Lab — projekt portfolio | Python, SQL, analiza danych, ryzyko kredytowe**.

W opisie umieść adres repozytorium dopiero po jego faktycznej publikacji. Nie wpisuj fikcyjnego stanowiska, pracodawcy ani komercyjnego wdrożenia.

## Dziesięć pytań rekrutera i poprawne odpowiedzi

### 1 Co jest problemem biznesowym projektu

Oszacowanie oczekiwanej straty w portfelu i wyjaśnienie jej źródeł według produktu, etapu ryzyka oraz scenariusza. Dane są syntetyczne, więc wynik demonstruje proces analityczny, nie straty rzeczywistej instytucji.

### 2 Czym różnią się PD LGD EAD i ECL

PD to prawdopodobieństwo defaultu w danym okresie, LGD to udział straty pod warunkiem defaultu, EAD to ekspozycja w momencie tego zdarzenia. ECL łączy te elementy, uwzględniając czas i scenariusze. Prosty przykład bez dyskonta: 10 000 zł × 5% PD × 60% LGD = 300 zł.

### 3 Dlaczego 72 000 wierszy nie oznacza 72 000 kredytów

Ziarnistość wyniku to kontrakt i miesiąc. 6 000 kontraktów występuje na 12 datach raportowych. Sumy sald z różnych dat nie są bieżącym portfelem; karty i podsumowanie wymagają jednej daty.

### 4 Jak SQL zapobiega zawyżeniu sum przez duplikaty

Najpierw sprawdzana jest unikalność kluczy źródłowych przed JOIN. ROW_NUMBER wybiera najnowszą wersję snapshotu dla kontraktu i daty według ingestion_id. Nieprawidłowe rekordy trafiają do kwarantanny, a klucz kontrakt/data w warstwie wynikowej jest unikalny.

### 5 Jak zabezpieczono projekt przed data leakage

Predyktory mają jawną listę. Nie zawierają targetu, dat przyszłego defaultu i późniejszych odzysków. Imputacja oraz skala są dopasowane tylko na treningu, klienci nie przechodzą między kohortami, a okna wyników wcześniejszego zbioru kończą się przed obserwacjami kolejnego.

### 6 Czym AUC różni się od kalibracji

AUC mierzy porządkowanie ryzyka: czy przyszły default dostaje wyższy wynik niż brak defaultu. Kalibracja sprawdza, czy np. grupa z PD 10% ma około 10% defaultów. AUC 0,743 nie oznacza 74,3% poprawnych klasyfikacji. Brier nie jest wyłącznie miarą kalibracji.

### 7 Jak wyznaczono LGD i jakie ma ograniczenie

Cel to 1 minus zdyskontowane odzyski netto podzielone przez ekspozycję w default. Następnie Ridge przewiduje tę wartość z cech dostępnych w default. Użyto tylko zakończonych przypadków: brak korekty otwartych windykacji i cenzurowania może powodować bias.

### 8 Jak etapy zmieniają odpis

Stage 1 obejmuje default możliwy w ciągu maksymalnie 12 miesięcy; Stage 2 wydłuża horyzont do pozostałego życia po znaczącym wzroście ryzyka. Stage 3 oznacza już zidentyfikowany default i w projekcie używa proxy LGD. Progi SICR są założeniami demonstratora, a nie uniwersalnym wymogiem liczbowym standardu.

### 9 Dlaczego rocznej PD nie mnożymy po prostu przez lata

Trzeba uwzględnić przeżycie do kolejnego okresu. Przy stałej rocznej PD 12% prawdopodobieństwo defaultu przez dwa lata to 1−0,88²=22,56%, nie 24%. Silnik sumuje miesięczne prawdopodobieństwa marginalne z harmonogramem EAD i dyskontem.

### 10 Jak sprawdziłeś wynik i czego jeszcze nie wdrożono

Ręczne tożsamości finansowe są w testach, kwoty uzgodniono między SQL i Pythonem, a składniki miesięczne audytu sumują się do ECL wybranych kontraktów. Dashboard porównano z SQL dla 768 filtrów i sprawdzono w przeglądarce. Nie ma PBIX ani wdrożenia bankowego; scenariusze są założone, a wysoki PSI trening/portfel wymagałby dalszej analizy.

## Wypowiedź na około minutę

„Chciałbym pokazać mój projekt portfolio Credit Risk Lab, który łączy SQL, Pythona i analizę ryzyka kredytowego. Na syntetycznych danych obejmuje 6 tysięcy umów i 72 tysiące obserwacji miesięcznych. SQL odpowiada za łączenie źródeł, deduplikację, kontrolę jakości i analizy portfela. Python estymuje PD oraz LGD, a następnie liczy oczekiwaną stratę dla trzech scenariuszy i etapów ryzyka. W projekcie rozdzielone są okresy treningu, kalibracji i testu, żeby ograniczyć wyciek informacji z przyszłości. Wyniki można obejrzeć w dashboardzie HTML. Proces ma 26 testów, a wyniki filtrów są uzgodnione z SQL. Najważniejsze ograniczenia to syntetyczne dane, uproszczony hazard i założone scenariusze. Przy przygotowaniu bazowego kodu i dokumentacji korzystałem z AI. Projekt traktuję jako materiał do praktycznej nauki i pokazania, jak sprawdzam dane, obliczenia oraz ich założenia.”

Przećwicz tekst własnymi słowami. Jeśli wykonasz własną zmianę, np. analizę wrażliwości CCF, opisz ją i pokaż rezultat. Nie dodawaj twierdzenia o takiej pracy, zanim jej nie wykonasz.
