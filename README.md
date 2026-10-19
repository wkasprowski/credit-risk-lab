# Credit Risk Lab

An educational project that uses **Python, SQL and SQLite** to explore a simplified credit-risk workflow on synthetic data.

[Methodology](docs/METHODOLOGY.md) · [Data dictionary](docs/DATA_DICTIONARY.md) · [Sources](docs/SOURCES.md)

The project generates a fictional retail-loan portfolio, prepares an analytical database, estimates PD and LGD, calculates scenario-weighted ECL and presents the results in an offline HTML dashboard.

> All records are synthetic. This repository is not a production banking model, a complete IFRS 9 implementation or work performed for a financial institution.

![Dashboard overview](screenshots/dashboard-overview.png)

## What the project contains

- 6,000 fictional contracts observed across 12 month-end snapshots;
- 72,000 contract-month records after deduplication and quality checks;
- SQL views and queries for cleaning, joining and analysing the portfolio;
- Python modules for synthetic-data generation, PD/LGD modelling and ECL calculation;
- an offline HTML dashboard with date, product, stage and scenario filters;
- automated tests and reconciliation of selected SQL and Python totals;
- example Power Query M and DAX files for a manual Power BI build.

## Main workflow

1. Generate deterministic synthetic source files.
2. Load them into SQLite and validate source keys.
3. Deduplicate monthly snapshots and quarantine invalid records.
4. Fit simplified PD and LGD models on separated time periods.
5. Assign risk stages and calculate monthly, discounted ECL under three scenarios.
6. Export analytical results and rebuild the HTML dashboard.

More detail about the assumptions is available in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Technology

- Python 3.12
- pandas, NumPy, SciPy and scikit-learn
- SQLite and SQL
- HTML, CSS and JavaScript
- unittest; optional Node.js and Playwright dashboard checks

## Run on Windows

Open PowerShell in the repository directory and run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe run_pipeline.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The pipeline creates the full synthetic inputs and analytical outputs in ignored directories. Small example files remain in `data/sample/` so the structure can be inspected without running the pipeline.

To view the prepared dashboard without installing anything, open `dashboard/index.html` in a browser.

## Example SQL analysis

```sql
SELECT product,
       stage,
       COUNT(*) AS contracts,
       ROUND(SUM(ead), 2) AS ead_pln,
       ROUND(SUM(ecl_weighted), 2) AS ecl_pln
FROM fact_ecl
WHERE report_date = '2026-09-30'
GROUP BY product, stage
ORDER BY product, stage;
```

The main queries are in:

- `sql/01_curated_views.sql` — cleaning, deduplication and analytical views;
- `sql/02_analysis.sql` — portfolio summaries, migrations and high-loss contracts;
- `sql/03_validation.sql` — integrity and reconciliation checks.

## Baseline result

For the default configuration and reporting date `2026-09-30`:

| Measure | Result |
|---|---:|
| Contracts | 6,000 |
| Contract-month records | 72,000 |
| EAD | 240,431,995.01 PLN |
| Scenario-weighted ECL | 35,710,382.24 PLN |
| PD test ROC-AUC | 0.7426 |
| LGD test MAE | 0.0548 |

These values describe generated data only. They do not demonstrate performance on real borrowers.

## Repository structure

```text
src/          Python modules
sql/          SQL preparation, analysis and validation
tests/        Python and dashboard checks
data/sample/  small synthetic examples
dashboard/    offline HTML dashboard
docs/         methodology, dictionary, sources and Power BI guide
reports/      saved verification outputs
screenshots/  dashboard previews
```

## Limitations

- The dataset and outcomes are generated rather than observed.
- PD lifetime curves, macroeconomic scenarios, SICR thresholds and CCF are simplified assumptions.
- LGD is trained on resolved workouts and does not model censoring of open cases.
- Stage 3 and behavioural life for revolving products are simplified.
- There is no completed `.pbix` file and no production deployment or regulatory validation.

## Development note

The implementation and documentation were developed with AI-assisted tooling as part of an educational portfolio project. The repository demonstrates a reproducible technical workflow, not commercial banking experience.

MIT licensed.
