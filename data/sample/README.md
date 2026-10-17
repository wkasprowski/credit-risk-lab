# Small synthetic sample

These CSVs are a readable extract from the deterministic baseline, **not real customer data** and not enough data to train/evaluate the models.

- 30 reporting loans and their matching borrowers/snapshots.
- A stratified slice of each historical PD cohort and target class.
- Ten resolved workout cases and their matching recovery transactions.
- The latest ECL rows for the selected reporting loans.

Field definitions: [data dictionary](../../docs/DATA_DICTIONARY.md).

Run `python run_pipeline.py` to generate the full dataset and results. Run `python scripts/export_samples.py` afterwards to regenerate this inspection sample.

Do not compare sample totals with full-portfolio headline numbers.

The baseline export contains 30 borrowers, 30 loans, 368 raw snapshot rows (including eight duplicate-version examples), 30 stratified historical PD rows, ten workouts, 40 recoveries, and 30 latest fact rows.
