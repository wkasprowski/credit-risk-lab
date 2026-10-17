# Changes made for the public portfolio release

This release starts from the selected existing Credit Risk Lab archive. It is not a replacement project.

## Preserved

- Original PD/LGD modelling, calibration and temporal validation code.
- Original financial ECL engine and deterministic synthetic generator.
- Original database loader and the two original SQL scripts.
- The 26 original financial/integration tests.
- Baseline configuration and scenario assumptions.
- The dashboard's original aggregation and top-loss selection logic.

Core source hashes are compared with the input archive in the verification record. Numerical results are independently reproduced rather than copied from old statements.

## Cleaned and reorganised

- Removed institution-specific recruitment references and job-ad links.
- Removed the personal name from report metadata, report text and dashboard footer.
- Replaced time-sensitive application advice with general portfolio documentation.
- Created an English main README and a shorter Polish README.
- Moved the dashboard template to dashboard/template.html and the generated preview to dashboard/index.html; updated its checker and Windows launcher.
- Translated the dashboard presentation to English and used English numeric display formatting.
- Added a narrow-screen layout so long monetary cards do not overflow.
- Replaced the fixed example Power Query project path with a required SET_PROJECT_FOLDER placeholder.
- Added MIT licensing, a comprehensive .gitignore and optional locked browser-test dependencies.

## Added

- Small referentially consistent synthetic samples and their export script.
- Complete methodology, data dictionary, source references and manual Power BI guide.
- A standalone verification script, an extra SQL validation script and a real-browser checker.
- Real dashboard screenshots, measured verification results and reproducibility information.
- Manual publication commands, repository description/topics, truthful CV bullets and interview preparation.

## Excluded from the public release

- Full raw CSVs and the approximately 33 MB SQLite database.
- Large full fact-table exports and redundant copies of generated results.
- Personal recruitment notes and the old personalised PDF.
- Python environments/caches, Node dependencies, temporary downloads, build files and private audit paths.
- Any Git history, credentials, account configuration or fabricated PBIX file.

The full dataset and analytical outputs are recreated by run_pipeline.py. The small public preview, sample and verification snapshots intentionally remain.

## Unfinished scope

No Power BI Desktop execution or PBIX exists. No production deployment, external validation or institution affiliation is claimed. GitHub publication remains a manual user action.
