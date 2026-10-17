# Verification report

Verified on 2026-10-17 from the selected existing archive and a clean Python virtual environment. This report describes executed checks, not a plan.

## Input inventory and protection

The selected archive contained 59 files and about 66.26 MB unpacked: source code, two SQL scripts, tests, six synthetic source extracts, a SQLite database, model/evaluation exports, HTML, charts, PDF and Polish documentation. An independent hash-checked backup was made before changes. The original archive was not modified. The alternative project was not used.

The original unpacked copy passed 26 Python tests and 768 Node/SQL filter checks. Its SQLite integrity was OK, with 72,000 fact rows and 12 dates. Those results were then regenerated rather than trusted as final evidence.

## Clean Python environment

Python 3.12.14, Linux x86_64. A new venv was created without system site-packages; dependencies were downloaded and installed from the original pinned direct requirements. The installed transitive versions were recorded in requirements.lock.txt. pip check reported no broken requirements. The exact environment is in environment.txt.

A fresh run started without full raw data or outputs, generated six source CSVs, built the SQL layers/database, fitted the models and calculated every reporting snapshot. The source generator was then run again with seed 42: all six CSV SHA-256 values matched exactly. Timestamps/PDF metadata are not claimed to be byte-identical.

## Executed checks

| Check | Result |
|---|---|
| Full pipeline | PASS; source generation through dashboard and PDF |
| Python financial/integration tests | 26 passed |
| SQLite integrity_check | OK |
| Fact population | 72,000 rows, 12 dates, 6,000 loans |
| Source quality | 72,012 raw - 8 duplicate - 4 rejected = 72,000 accepted |
| SQL/Python latest EAD and ECL | Agree within 0.000001 PLN |
| Six loan-level ECL audits | Agree with monthly/scenario component sums |
| Node/SQL dashboard logic | All 768 combinations passed |
| Actual Chromium dashboard | All 768 combinations passed, including top-ten rankings |
| CSV download | PASS |
| JavaScript exceptions / external requests | 0 / 0 |
| Desktop / mobile | 1440x1050 and 390x844; no horizontal page overflow |
| Deterministic generator | All six raw CSV hashes reproduced |
| Original numeric and SQL code | Five Python modules and two original SQL scripts unchanged |

The real browser was Chromium 153.0.8010.0 with Playwright 1.62.1. It opened the actual HTML using file://, without a server or account. Screenshots are genuine browser captures. The default Playwright browser download returned a broken archive; a separate Chromium binary was installed from a published package and used only for verification. That binary and its dependencies are not included in the repository.

## Actual baseline results

| Measure | Result |
|---|---:|
| Reporting date | 2026-09-30 |
| EAD | 240,431,995.01346758 PLN |
| Weighted ECL, Python | 35,710,382.24321605 PLN |
| Weighted ECL, SQL | 35,710,382.24321606 PLN |
| Weighted ECL rounded | **35,710,382.24 PLN** |
| Coverage | 14.8525916% |
| Stage 1 / 2 / 3 contracts | 3,385 / 2,363 / 252 |
| PD test AUC / Gini | 0.7425854531 / 0.4851709061 |
| PD Brier / log loss | 0.0639609900 / 0.2377561454 |
| PD mean / observed defaults | 7.393839% / 7.675000% |
| LGD MAE / mean baseline MAE | 0.0548399373 / 0.1408252006 |

The earlier ECL, test count and filter-count claims were confirmed; no numerical correction was necessary. Presentation, structure and documentation were cleaned.

## Limits of verification and unfinished work

The Python execution was Linux-only. Windows instructions are supplied but not claimed as a Windows runtime test. Power BI Desktop/M/DAX was not run: there is no PBIX. Browser checks cover this dashboard and reference dataset, not every browser version. No GitHub publication or GitHub account operation was performed.

Financial limitations remain: synthetic outcomes, constant hazard, assumed scenario/CCF/SICR parameters, fixed stages across scenarios, resolved-only LGD, simplified card life and Stage 3 proxy. Current-performing score PSI versus training is about 0.4167. These points prevent a production-validity claim.

## Recruiter readiness

**Suitable to show as an educational portfolio**, with the stated synthetic-data and model limitations. It demonstrates executable SQL/Python work and a working HTML report. It does not establish commercial experience, regulatory compliance or readiness for real lending/financial reporting decisions. The presenter should understand the code and be able to reproduce and explain a calculation.

## Reproduce

Run the Windows/Linux README installation, then:

~~~powershell
python scripts/verify_project.py
~~~

For the real-browser check, install the optional package.json dependencies and Chromium (or select Edge), then use --browser. Node is optional for the financial pipeline. Running verification regenerates full data in ignored folders; do not add those to Git. Machine-readable evidence is in verification.json, metrics.json and the test/pipeline logs.

## Release packaging checks

The candidate public ZIP was extracted into another empty directory and verified again: full generation, SQL/database build, deterministic raw CSVs, models, 26 Python tests, 768 Node logic cases and 768 real-browser cases all passed. Optional Node dependencies were also installed with npm ci and the browser test passed against that installation.

Text pattern scanning and manual review found no target-institution references, personal name, private workspace/user paths or common credential-key patterns in public files. This is a scoped release review, not a guarantee against every possible secret format. The public package excludes full raw data, the database, environments, caches, Node modules and temporary files. No PBIX or Git history is included.
