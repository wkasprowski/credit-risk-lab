# Validation report

This file records the checks completed for the current baseline of Credit Risk Lab.

## Environment

- Python 3.12.14 on Linux x86_64
- clean virtual environment without system site packages
- dependencies installed from `requirements.lock.txt`
- SQLite integrity check: OK

The Windows commands in the README were prepared for Python 3.12 but were not executed as part of this validation. Power BI Desktop was not tested and the repository does not contain a `.pbix` file.

## Checks

| Check | Result |
|---|---|
| Full pipeline | PASS |
| Python financial and integration tests | 26 passed |
| Fact table | 72,000 rows, 12 dates and 6,000 contracts |
| Source reconciliation | 72,012 input rows − 8 duplicates − 4 rejected = 72,000 accepted |
| SQL and Python EAD/ECL totals | difference below 0.000001 PLN |
| Selected loan-level ECL audits | component sums matched |
| Dashboard logic against SQL references | 768 filter combinations matched |
| Browser-rendered dashboard | 768 filter combinations matched |
| JavaScript errors and external requests | 0 / 0 |
| Deterministic generator | all six source CSV hashes reproduced |

## Baseline output

Reporting date: `2026-09-30`

| Measure | Result |
|---|---:|
| EAD | 240,431,995.01 PLN |
| Scenario-weighted ECL | 35,710,382.24 PLN |
| ECL / EAD | 14.8526% |
| Stage 1 / 2 / 3 contracts | 3,385 / 2,363 / 252 |
| PD test ROC-AUC | 0.742585 |
| PD test Brier score | 0.063961 |
| LGD test MAE | 0.054840 |

## Reproduce the checks

After installing the Python dependencies and running the pipeline:

```powershell
.\.venv\Scripts\python.exe scripts/verify_project.py
```

Optional dashboard checks require Node.js. The browser check additionally requires Playwright and Chromium or Microsoft Edge.

## Known limitations

- All inputs and outcomes are synthetic.
- Monthly hazard, scenarios, CCF values and SICR thresholds are assumptions.
- LGD uses resolved workouts and does not correct for censoring of open cases.
- Stage 3 and revolving-product life are simplified.
- Current-performing score PSI versus training is approximately 0.4167 and would require investigation in a real modelling process.
- The project has not undergone independent model validation or regulatory review.
