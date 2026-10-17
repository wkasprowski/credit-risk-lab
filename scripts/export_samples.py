"""Export a small referentially consistent synthetic sample after a full run."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    raw, target = ROOT / "data" / "raw", ROOT / "data" / "sample"
    target.mkdir(parents=True, exist_ok=True)
    loans = pd.read_csv(raw / "loans.csv").head(30)
    ids, customers = set(loans.loan_id), set(loans.customer_id)
    samples = {
        "loans": loans,
        "borrowers": pd.read_csv(raw / "borrowers.csv").query("customer_id in @customers"),
        "snapshots": pd.read_csv(raw / "snapshots.csv").query("loan_id in @ids"),
    }
    historical = pd.read_csv(raw / "historical_pd.csv")
    samples["historical_pd"] = historical.groupby(["cohort", "default_12m"]).head(5)
    workouts = pd.read_csv(raw / "workouts.csv").groupby("cohort").head(5)
    cases = set(workouts.case_id)
    samples["workouts"] = workouts
    samples["recoveries"] = pd.read_csv(raw / "recoveries.csv").query("case_id in @cases")
    samples["fact_ecl_sample"] = pd.read_csv(ROOT / "outputs" / "latest_portfolio.csv").query("loan_id in @ids")
    for name, frame in samples.items():
        frame.to_csv(target / f"{name}.csv", index=False, float_format="%.10f")
    print("Exported synthetic samples:", {k: len(v) for k, v in samples.items()})


if __name__ == "__main__":
    main()
