# Ręczna publikacja repozytorium na GitHubie

Repozytorium nie zostało automatycznie opublikowane. Poniższe czynności wykonujesz sam. Paczka nie zawiera historii Git ani sztucznych commitów.

## Proponowany opis repozytorium

Reproducible Python and SQL credit-risk analytics on synthetic data: PD/LGD modelling, scenario-weighted ECL, data-quality checks and an HTML dashboard.

## Proponowane GitHub Topics

python, sql, sqlite, data-analysis, credit-risk, risk-modeling, synthetic-data, data-quality, pd, lgd, ead, ecl, ifrs9, portfolio-project

Nie dodawaj topics sugerujących ukończone Power BI, VBA, R lub SAS.

## Przygotuj narzędzia i repozytorium

1. Zainstaluj Git i otwórz terminal w katalogu **credit-risk-lab**.
2. Na GitHubie wybierz New repository i nazwę **credit-risk-lab**.
3. Wklej opis i wybierz Public.
4. Utwórz **puste** repozytorium: nie dodawaj tam kolejnego README, licencji ani .gitignore. Te pliki są już w paczce.
5. Zastąp **YOUR_USERNAME** w adresie poniżej swoim loginem. To jedyny placeholder w komendzie adresu.

## Utwórz prawdziwy pierwszy commit

~~~powershell
git --version
git init -b main
git add .
git status --short
git diff --cached --stat
~~~

Sprawdź przygotowany zestaw plików. Pełne dane, outputs, baza, środowisko Python i node_modules powinny być ignorowane. README, dokumentacja, małe próbki, dashboard, zrzuty i kod powinny zostać dodane.

Jeżeli Git prosi o tożsamość autora, skonfiguruj ją zgodnie ze swoim profilem. Nie dołączaj plików z ustawieniami konta ani poświadczeniami do projektu.

Proponowana treść rzeczywistego pierwszego commita:

~~~text
Add reproducible SQL and Python credit-risk portfolio project
~~~

Wykonaj:

~~~powershell
git commit -m "Add reproducible SQL and Python credit-risk portfolio project"
git remote add origin https://github.com/YOUR_USERNAME/credit-risk-lab.git
git remote -v
git push -u origin main
~~~

Uwierzytelnianie obsłuż przez zwykły mechanizm Git/GitHub, bez wstawiania tokenów do adresu repozytorium lub plików projektu.

## Po wysłaniu

1. Sprawdź, czy główna strona pokazuje angielski README i obraz dashboardu.
2. Otwórz README_PL i odnośniki do dokumentacji.
3. Ustaw Topics w sekcji About.
4. Sprawdź widoczność repozytorium bez zalogowania.
5. Dashboard HTML nie uruchamia się jako aplikacja wewnątrz podglądu kodu GitHuba. Rekruter może pobrać repozytorium i otworzyć dashboard/index.html. Zrzuty są widoczne bez pobierania.
6. Opcjonalne GitHub Pages jest osobnym przyszłym krokiem; nie jest skonfigurowane ani wdrożone w tej paczce.

Nie trzeba tworzyć kilku commitów udających wcześniejszą pracę. Kolejne commity powinny odpowiadać rzeczywistym poprawkom.

Źródło komend: [GitHub Docs](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).
