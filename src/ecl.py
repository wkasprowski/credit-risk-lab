"""Transparent educational ECL engine, not a production IFRS 9 implementation.

Monthly marginal default probabilities include survival. Workout LGD is
discounted from recovery to default; default losses are separately discounted
from default to reporting. Stage 1 limits DEFAULT EVENTS to 12 months, not
the period over which subsequent workout recoveries occur.
"""
import numpy as np
import pandas as pd


def annual_to_monthly_hazard(pd12):
    p = np.asarray(pd12,dtype=float)
    if not np.isfinite(p).all() or ((p < 0)|(p > 1)).any():
        raise ValueError("Annual PD must be a finite probability")
    return 1-np.power(1-p,1/12)


def lifetime_probability(pd12, months):
    return 1-np.power(1-np.asarray(pd12),np.asarray(months)/12)


def stress_probability(p, multiplier):
    if multiplier <= 0:
        raise ValueError("Odds multiplier must be positive")
    p = np.asarray(p,dtype=float)
    return multiplier*p/(1-p+multiplier*p)


def assign_stages(frame, config):
    out = frame.copy()
    current_lifetime = lifetime_probability(out.pd_12m,out.remaining_months)
    origin_lifetime = lifetime_probability(out.origination_pd_12m,out.remaining_months)
    ratio = current_lifetime / np.maximum(origin_lifetime,1e-8)
    increase = current_lifetime-origin_lifetime
    quantitative = (ratio >= config["sicr_lifetime_ratio"]) & (increase >= config["sicr_lifetime_absolute_increase"])
    default = (out.default_flag == 1)|(out.utp == 1)|(out.dpd >= 90)
    # >30 DPD is the IFRS 9 rebuttable SICR backstop; no rebuttals here.
    out["stage"] = np.select([default,(out.dpd > 30)|(out.watchlist == 1)|quantitative],[3,2],default=1)
    out["stage_reason"] = np.select([
        default,out.dpd>30,out.watchlist==1,quantitative],
        ["default_or_utp","dpd_over_30","watchlist","lifetime_pd_deterioration"],default="no_sicr")
    out["pd_lifetime"] = np.where(default,1.,current_lifetime)
    out["pd_12m"] = np.where(default,1.,out.pd_12m)
    out["sicr_pd_ratio"] = ratio
    out["sicr_absolute_increase"] = increase
    return out


def projected_ead(balance, undrawn, months_remaining, eir, revolving, month, ccf):
    """Exposure just BEFORE the month's scheduled payment/default.

    Amortising loans use equal instalments reconstructed from current balance;
    cards retain exposure and use a fixed educational behavioural horizon.
    The supplied annual EIR converts to an effective monthly rate.
    """
    b,u,n,r,rev = map(np.asarray,[balance,undrawn,months_remaining,eir,revolving])
    monthly = np.power(1+r,1/12)-1
    denom = 1-np.power(1+monthly,-n)
    payment = np.divide(b*monthly,denom,out=b/n,where=np.abs(monthly)>1e-10)
    k = month-1
    compound = np.power(1+monthly,k)
    annuity_factor = np.divide(compound-1,monthly,out=np.full_like(b,k,dtype=float),where=np.abs(monthly)>1e-10)
    scheduled = np.maximum(0,b*compound-payment*annuity_factor)
    return np.where(rev,b+ccf*u,scheduled)


def calculate_ecl(frame, config, detail_ids=()):
    weights = [s["weight"] for s in config["scenarios"]]
    if not np.isclose(sum(weights),1.) or any(w < 0 for w in weights):
        raise ValueError("Scenario weights must be nonnegative and sum to one")
    if not 0 <= config["ccf"] <= 1:
        raise ValueError("CCF must be between 0 and 1")
    b,u,n,eir = (frame[c].to_numpy(dtype=float) for c in ["balance","undrawn","remaining_months","eir"])
    p,lgd,stage = (frame[c].to_numpy() for c in ["pd_12m","lgd","stage"])
    if (not np.isfinite(np.column_stack([b,u,n,eir,p,lgd])).all()
        or (b < 0).any() or (u < 0).any() or (n < 1).any()
        or (eir < 0).any() or ((lgd < 0)|(lgd > 1)).any()):
        raise ValueError("Invalid input to ECL engine")
    rev = frame["product"].to_numpy() == "credit_card"
    horizon = np.where(stage == 1,np.minimum(12,n),n).astype(int)
    performing = stage < 3
    ead = np.where(performing,b+np.where(rev,config["ccf"]*u,0),b)
    weighted = np.zeros(len(frame))
    scenarios,detail = {},[]
    include = frame.loan_id.isin(detail_ids).to_numpy()
    for s in config["scenarios"]:
        ps = stress_probability(p,s["pd_odds_multiplier"])
        ls = np.clip(lgd*s["lgd_multiplier"],0,1)
        q = annual_to_monthly_hazard(ps)
        total = np.where(performing,0,b*ls)
        for ix in np.flatnonzero(include & ~performing):
            detail.append({"loan_id":frame.loan_id.iloc[ix],"report_date":frame.report_date.iloc[ix],
                           "scenario":s["name"],"month":0,"marginal_pd":1.,"projected_ead":b[ix],
                           "lgd":ls[ix],"discount":1.,"contribution":total[ix],
                           "scenario_weight":s["weight"],"weighted_contribution":total[ix]*s["weight"]})
        for month in range(1,int(n.max())+1):
            eligible = performing & (month <= horizon)
            marginal = np.power(1-q,month-1)*q
            exposure = projected_ead(b,u,n,eir,rev,month,config["ccf"])
            discount = np.power(1+eir,-month/12)
            contribution = np.where(eligible,marginal*ls*exposure*discount,0.)
            total += contribution
            for ix in np.flatnonzero(include & eligible):
                detail.append({"loan_id":frame.loan_id.iloc[ix],"report_date":frame.report_date.iloc[ix],
                               "scenario":s["name"],"month":month,"marginal_pd":marginal[ix],
                               "projected_ead":exposure[ix],"lgd":ls[ix],"discount":discount[ix],
                               "contribution":contribution[ix],"scenario_weight":s["weight"],
                               "weighted_contribution":contribution[ix]*s["weight"]})
        scenarios[s["name"]] = total
        weighted += s["weight"]*total
    if (weighted < -1e-8).any() or (weighted-ead > 1e-6).any():
        raise ValueError("ECL outside allowed educational exposure bounds")
    result = frame.copy()
    result["ead"] = ead
    result["ecl_weighted"] = weighted
    for name,values in scenarios.items():
        result[f"ecl_{name}"] = values
    result["coverage_ratio"] = np.divide(weighted,ead,out=np.zeros_like(weighted),where=ead>0)
    return result,pd.DataFrame(detail)
