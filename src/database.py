from pathlib import Path
import sqlite3
import pandas as pd
from src.io_utils import write_csv


def build_database(root: Path, config):
    output = root / "outputs"
    output.mkdir(exist_ok=True)
    db = output / ".credit_risk.build.sqlite"
    # Deterministically rebuild this project's generated database only.
    if db.exists():
        db.unlink()
    conn = sqlite3.connect(db)
    for name in ["historical_pd","borrowers","loans","snapshots","workouts","recoveries"]:
        df = pd.read_csv(root / "data" / "raw" / f"{name}.csv")
        df.to_sql(f"raw_{name}", conn, index=False, if_exists="replace")
    # Source key integrity is checked before joins can multiply rows.
    for table, key in [("raw_loans","loan_id"),("raw_borrowers","customer_id"),
                       ("raw_historical_pd","customer_id"),("raw_workouts","case_id")]:
        invalid = conn.execute(f"SELECT COUNT(*)-COUNT(DISTINCT {key}) FROM {table}").fetchone()[0]
        if invalid:
            raise ValueError(f"Duplicate or missing source key: {table}.{key}")
    conn.executescript((root / "sql" / "01_curated_views.sql").read_text(encoding="utf-8"))
    raw = conn.execute("SELECT COUNT(*) FROM raw_snapshots").fetchone()[0]
    dedup = conn.execute("SELECT COUNT(*) FROM deduplicated_snapshots").fetchone()[0]
    rejected = conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
    accepted = conn.execute("SELECT COUNT(*) FROM curated_snapshots").fetchone()[0]
    if raw-(raw-dedup)-rejected != accepted:
        raise ValueError("Source-to-curated row reconciliation failed")
    report = {"raw_snapshot_rows":raw,"duplicates_removed":raw-dedup,
              "quarantined_rows":rejected,"accepted_rows":accepted,
              "missing_income_borrowers":conn.execute("SELECT COUNT(*) FROM raw_borrowers WHERE income IS NULL").fetchone()[0]}
    report["reject_reasons"] = dict(conn.execute("SELECT reject_reason,COUNT(*) FROM quarantine GROUP BY reject_reason").fetchall())
    write_csv(pd.read_sql_query("SELECT * FROM quarantine",conn),output / "quarantine.csv",index=False)
    features = pd.read_sql_query("SELECT * FROM portfolio_features ORDER BY report_date,loan_id",conn)
    if len(features) != accepted:
        raise ValueError("Join cardinality mismatch")
    if (features.report_date > config["report_date"]).any():
        raise ValueError("A snapshot is later than the configured as-of date")
    conn.commit()
    return conn, features, report
