-- SQLite 3.25+; raw tables are loaded from six simulated source systems.
-- Deduplication is explicit: the most recent ingestion wins.
CREATE VIEW deduplicated_snapshots AS
WITH ranked AS (
  SELECT s.*, ROW_NUMBER() OVER (
    PARTITION BY loan_id, report_date ORDER BY ingestion_id DESC
  ) AS row_rank
  FROM raw_snapshots s
)
SELECT * FROM ranked WHERE row_rank = 1;

CREATE VIEW classified_snapshots AS
SELECT s.*,
 CASE
   WHEN l.loan_id IS NULL THEN 'missing_contract'
   WHEN b.customer_id IS NULL THEN 'missing_borrower'
   WHEN balance IS NULL THEN 'missing_balance'
   WHEN balance < 0 OR undrawn < 0 THEN 'negative_exposure'
   WHEN remaining_months IS NULL OR remaining_months < 1 OR remaining_months > 120 THEN 'invalid_maturity'
   WHEN dpd IS NULL OR dpd < 0 THEN 'invalid_dpd'
   WHEN dti IS NULL OR dti < 0 OR dti > 1 THEN 'invalid_dti'
   WHEN utilization IS NULL OR utilization < 0 OR utilization > 1 THEN 'invalid_utilization'
   WHEN default_flag NOT IN (0,1) OR utp NOT IN (0,1) OR watchlist NOT IN (0,1)
        OR default_flag IS NULL OR utp IS NULL OR watchlist IS NULL THEN 'invalid_flags'
   WHEN undrawn IS NULL OR delinquent_6m IS NULL OR delinquent_6m < 0 THEN 'missing_feature'
   WHEN report_date <> date(report_date, 'start of month', '+1 month', '-1 day') THEN 'not_month_end'
   ELSE NULL
 END AS reject_reason
FROM deduplicated_snapshots s
LEFT JOIN raw_loans l ON s.loan_id = l.loan_id
LEFT JOIN raw_borrowers b ON l.customer_id = b.customer_id;

CREATE VIEW quarantine AS
SELECT * FROM classified_snapshots WHERE reject_reason IS NOT NULL;

CREATE TABLE curated_snapshots (
 loan_id TEXT NOT NULL, report_date TEXT NOT NULL,
 balance REAL NOT NULL CHECK (balance >= 0), undrawn REAL NOT NULL CHECK (undrawn >= 0),
 dpd INTEGER NOT NULL CHECK(dpd >= 0), default_flag INTEGER NOT NULL, utp INTEGER NOT NULL,
 watchlist INTEGER NOT NULL, dti REAL NOT NULL, utilization REAL NOT NULL,
 delinquent_6m INTEGER NOT NULL, remaining_months INTEGER NOT NULL,
 PRIMARY KEY(loan_id, report_date)
);
INSERT INTO curated_snapshots
SELECT loan_id, report_date, balance, undrawn, dpd, default_flag, utp,
       watchlist, dti, utilization, delinquent_6m, remaining_months
FROM classified_snapshots WHERE reject_reason IS NULL;
CREATE INDEX idx_curated_date ON curated_snapshots(report_date);

CREATE VIEW portfolio_features AS
SELECT s.*, l.customer_id, l.product, l.eir, l.collateral_coverage,
       l.origination_pd_12m, l.origination_date, b.income, b.employment_years,
       LAG(s.dpd) OVER (PARTITION BY s.loan_id ORDER BY s.report_date) AS prior_dpd,
       MAX(s.dpd) OVER (PARTITION BY s.loan_id ORDER BY s.report_date
                       ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS max_dpd_3_snapshots
FROM curated_snapshots s
JOIN raw_loans l ON s.loan_id=l.loan_id
JOIN raw_borrowers b ON l.customer_id=b.customer_id;

-- Feature whitelist excludes labels, future outcomes and synthetic latent risk.
CREATE VIEW pd_observations AS
SELECT customer_id, observation_date, outcome_end, default_date, cohort,
       income, dti, utilization, employment_years, dpd, delinquent_6m,
       product, default_12m
FROM raw_historical_pd;
