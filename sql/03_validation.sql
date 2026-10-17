-- Independent checks after python run_pipeline.py; SQLite.
PRAGMA integrity_check;

-- 72,000 observations, 12 report dates and 6,000 synthetic loans.
SELECT COUNT(*) AS rows, COUNT(DISTINCT report_date) AS report_dates,
       COUNT(DISTINCT loan_id) AS loans
FROM fact_ecl;

-- Expected: zero duplicate primary business keys.
SELECT loan_id, report_date, COUNT(*) AS copies
FROM fact_ecl GROUP BY loan_id, report_date HAVING COUNT(*) > 1;

-- Reconcile the latest snapshot, never sum twelve monthly balances as one.
SELECT COUNT(*) AS contracts, SUM(ead) AS ead_pln,
       SUM(ecl_weighted) AS weighted_ecl_pln
FROM fact_ecl
WHERE report_date = (SELECT MAX(report_date) FROM fact_ecl);

-- Expected: zero invalid or unordered expected-loss rows.
SELECT COUNT(*) AS invalid_rows
FROM fact_ecl
WHERE ecl_weighted < 0 OR ecl_weighted > ead + 0.000001
   OR ecl_adverse + 0.000001 < ecl_base
   OR ecl_base + 0.000001 < ecl_optimistic;
