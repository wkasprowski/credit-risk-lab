"""Independent SQL references for all available dashboard filter combinations."""
import json
import sqlite3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
cases=[]
with sqlite3.connect(root / "outputs" / "credit_risk.sqlite") as conn:
    dates=[r[0] for r in conn.execute("SELECT DISTINCT report_date FROM fact_ecl ORDER BY report_date")]
    for date in dates:
        for product in ["all","cash_loan","secured_loan","credit_card"]:
            for stage in ["all","1","2","3"]:
                for scenario in ["weighted","base","adverse","optimistic"]:
                    where="report_date=?";args=[date]
                    if product!="all":
                        where+=" AND product=?";args.append(product)
                    if stage!="all":
                        where+=" AND stage=?";args.append(int(stage))
                    count,ead,ecl=conn.execute("SELECT COUNT(*),SUM(ead),SUM(ecl_"+scenario+") FROM fact_ecl WHERE "+where,args).fetchone()
                    top=conn.execute("SELECT loan_id FROM fact_ecl WHERE "+where+" ORDER BY ecl_"+scenario+" DESC LIMIT 10",args).fetchall()
                    cases.append(dict(date=date,product=product,stage=stage,scenario=scenario,
                                      count=count,ead=ead or 0,ecl=ecl or 0,top=[r[0] for r in top]))
(root / "outputs" / "dashboard_reference.json").write_text(json.dumps(cases),encoding="utf-8")
print(f"SQL reference cases: {len(cases)}")
