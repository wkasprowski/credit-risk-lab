-- Run each query in DB Browser for SQLite, against outputs/credit_risk.sqlite.

-- Latest portfolio by product and stage; reconcile to the dashboard.
SELECT product, stage, COUNT(*) AS contracts,
 ROUND(SUM(ead),2) AS exposure_pln,
 ROUND(SUM(ecl_weighted),2) AS ecl_pln,
 ROUND(SUM(ecl_weighted)/NULLIF(SUM(ead),0),6) AS coverage_ratio
FROM fact_ecl
WHERE report_date=(SELECT MAX(report_date) FROM fact_ecl)
GROUP BY product, stage ORDER BY product, stage;

-- Stage migration using a window function, latest vs previous month.
WITH migration AS (
 SELECT loan_id, report_date, stage,
   LAG(stage) OVER(PARTITION BY loan_id ORDER BY report_date) AS prior_stage
 FROM fact_ecl
)
SELECT prior_stage, stage AS current_stage, COUNT(*) AS contracts
FROM migration
WHERE report_date=(SELECT MAX(report_date) FROM fact_ecl)
  AND prior_stage IS NOT NULL
GROUP BY prior_stage,stage;

-- Data quality report: no quiet removal of bad records.
SELECT reject_reason, COUNT(*) AS rejected FROM quarantine GROUP BY reject_reason;

-- Highest expected losses among performing, deteriorated loans.
SELECT loan_id,product,dpd,pd_12m,lgd,ead,ecl_weighted,stage_reason
FROM fact_ecl
WHERE report_date=(SELECT MAX(report_date) FROM fact_ecl) AND stage=2
ORDER BY ecl_weighted DESC LIMIT 20;

-- Quarterly exposure-weighted probability of default (performing only).
SELECT report_date,
 SUM(pd_12m*ead)/NULLIF(SUM(ead),0) AS weighted_pd
FROM fact_ecl WHERE stage < 3
GROUP BY report_date ORDER BY report_date;
