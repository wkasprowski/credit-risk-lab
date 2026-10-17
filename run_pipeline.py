"""One command rebuilds source data, SQL marts, models, ECL and reports."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
from datetime import datetime, timezone

# Keep CPU use predictable on Windows and small development machines.
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
import numpy as np
import pandas as pd
import sklearn
from src.synthetic import generate
from src.database import build_database
from src.models import train_pd, train_lgd, score_psi
from src.ecl import assign_stages, calculate_ecl, stress_probability
from src.io_utils import write_csv


def run(root, config_path=None):
    config_path = config_path or root / "config.json"
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    print("1/6 Generate synthetic source systems",flush=True)
    generate(root,config)
    print("2/6 SQL deduplication, data quality and feature joins",flush=True)
    conn,features,quality = build_database(root,config)
    output = root / "outputs"
    try:
        print("3/6 Train and independently evaluate PD/LGD",flush=True)
        predict_pd,pd_metrics,train_scores = train_pd(conn,config,output)
        predict_lgd,lgd_metrics = train_lgd(conn,config,output)
        # Models now hold everything in memory; avoid a long-lived write
        # connection while numeric work and file exports are performed.
        conn.close()
        features["pd_12m"] = predict_pd(features)
        features["lgd"] = predict_lgd(features)
        staged = assign_stages(features,config)
        latest = staged[staged.report_date==config["report_date"]]
        pd_metrics["score_psi_train_vs_current_performing"] = score_psi(train_scores,latest.loc[latest.stage<3,"pd_12m"])
        print("4/6 Monthly scenario-weighted expected credit losses",flush=True)
        fact,_ = calculate_ecl(staged,config)
        latest = fact[fact.report_date==config["report_date"]].copy()
        audit_ids = latest.sort_values("ecl_weighted",ascending=False).groupby("stage").head(2).loan_id.tolist()
        _,audit = calculate_ecl(latest[latest.loan_id.isin(audit_ids)],config,detail_ids=audit_ids)
        write_csv(audit,output / "ecl_calculation_audit.csv",index=False)
        audit_sums = audit.groupby("loan_id").weighted_contribution.sum()
        expected = latest.set_index("loan_id").loc[audit_sums.index,"ecl_weighted"]
        if not np.allclose(audit_sums,expected,atol=1e-6):
            raise ValueError("Loan-level calculation audit does not reconcile")
        columns = ["loan_id","report_date","customer_id","product","balance","undrawn","eir",
                   "dpd","stage","stage_reason","pd_12m","pd_lifetime","origination_pd_12m",
                   "lgd","ead","ecl_weighted","ecl_base","ecl_optimistic","ecl_adverse","coverage_ratio",
                   "remaining_months","sicr_pd_ratio","sicr_absolute_increase"]
        fact = fact[columns]
        import sqlite3
        conn = sqlite3.connect(output / ".credit_risk.build.sqlite")
        fact.to_sql("fact_ecl",conn,index=False,if_exists="replace")
        conn.execute("CREATE UNIQUE INDEX idx_fact_key ON fact_ecl(loan_id,report_date)")
        write_csv(fact,output / "fact_ecl.csv",index=False,float_format="%.10f")
        write_csv(latest[columns],output / "latest_portfolio.csv",index=False,float_format="%.10f")
        aggregate = fact.groupby(["report_date","product","stage"],as_index=False).agg(
            loans=("loan_id","size"),ead=("ead","sum"),ecl_weighted=("ecl_weighted","sum"),
            ecl_base=("ecl_base","sum"),ecl_optimistic=("ecl_optimistic","sum"),ecl_adverse=("ecl_adverse","sum"))
        write_csv(aggregate,output / "portfolio_aggregates.csv",index=False)
        sql_ecl = conn.execute("SELECT SUM(ecl_weighted) FROM fact_ecl WHERE report_date=?",(config["report_date"],)).fetchone()[0]
        python_ecl = float(latest.ecl_weighted.sum())
        if not np.isclose(sql_ecl,python_ecl,atol=1e-6,rtol=1e-12):
            raise ValueError("SQL/Python monetary reconciliation failed")
        migration = pd.read_sql_query("""WITH x AS (
            SELECT loan_id,report_date,stage,LAG(stage) OVER(PARTITION BY loan_id ORDER BY report_date) AS prior_stage
            FROM fact_ecl)
            SELECT prior_stage,stage,COUNT(*) AS loans FROM x
            WHERE report_date=? AND prior_stage IS NOT NULL GROUP BY prior_stage,stage""",conn,params=(config["report_date"],))
        write_csv(migration,output / "stage_migration.csv",index=False)
        if int(migration.loans.sum()) != len(latest):
            raise ValueError("Stage migration population mismatch")
        # Sensitivities change one assumption at a time, using the same portfolio.
        sensitivities = []
        for name in ["reference","pd_odds_20pct_up","lgd_20pct_up","ccf_75pct","sicr_ratio_1_5"]:
            working,local = latest.copy(),dict(config)
            if name == "pd_odds_20pct_up":
                working.loc[working.stage<3,"pd_12m"] = stress_probability(working.loc[working.stage<3,"pd_12m"],1.2)
            elif name == "lgd_20pct_up":
                working["lgd"] = (working.lgd*1.2).clip(0,1)
            elif name == "ccf_75pct":
                local["ccf"] = .75
            elif name == "sicr_ratio_1_5":
                local["sicr_lifetime_ratio"] = 1.5
                working = assign_stages(working,local)
            calculated,_ = calculate_ecl(working,local)
            sensitivities.append({"assumption":name,"ecl_pln":float(calculated.ecl_weighted.sum()),
                                  "stage2_loans":int((calculated.stage==2).sum())})
        sensitivity = pd.DataFrame(sensitivities)
        sensitivity["delta_pln"] = sensitivity.ecl_pln-python_ecl
        sensitivity["delta_pct"] = sensitivity.delta_pln/python_ecl
        write_csv(sensitivity,output / "sensitivity.csv",index=False)
        totals = {"report_date":config["report_date"],"portfolio_loans":len(latest),
                  "ead_pln":float(latest.ead.sum()),"drawn_balance_pln":float(latest.balance.sum()),
                  "ecl_weighted_pln":python_ecl,"coverage_ratio":python_ecl/float(latest.ead.sum()),
                  "ecl_base_pln":float(latest.ecl_base.sum()),"ecl_adverse_pln":float(latest.ecl_adverse.sum()),
                  "ecl_optimistic_pln":float(latest.ecl_optimistic.sum()),
                  "stage_counts":{str(k):int(v) for k,v in latest.stage.value_counts().sort_index().items()}}
        summary = {"totals":totals,"pd":pd_metrics,"lgd":lgd_metrics,"data_quality":quality,
                   "reconciliation":{"sql_ecl_pln":sql_ecl,"python_ecl_pln":python_ecl,
                                     "audit_loans":len(audit_ids),"sql_python_agree":True,"loan_audit_agrees":True},
                   "config":config,"data_type":"SYNTHETIC"}
        (output / "metrics.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
        conn.commit()
        conn.close()
        os.replace(output / ".credit_risk.build.sqlite",output / "credit_risk.sqlite")
        print("5/6 Offline dashboard, charts and recruiter report",flush=True)
        from src.reporting import create_reports
        create_reports(root,fact,latest,summary)
        print("6/6 Reproducibility manifest",flush=True)
        files = [config_path,*sorted((root / "data" / "raw").glob("*.csv")),*sorted((root / "src").glob("*.py")),
                 *sorted((root / "sql").glob("*.sql")),root / "run_pipeline.py"]
        manifest = {"generated_at_utc":datetime.now(timezone.utc).isoformat(),"python":platform.python_version(),
                    "numpy":np.__version__,"pandas":pd.__version__,"scikit_learn":sklearn.__version__,
                    "seed":config["seed"],"input_and_source_sha256":{
                        str(Path(p).relative_to(root)) if Path(p).is_relative_to(root) else str(p):
                        hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}}
        (output / "run_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print(f"DONE | loans={len(latest):,} | ECL={python_ecl:,.2f} PLN | AUC={pd_metrics['full_calibrated']['roc_auc']:.3f}",flush=True)
        return summary
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,help="Optional JSON configuration")
    args = parser.parse_args()
    run(Path(__file__).resolve().parent,args.config)
