"""Deterministic, fictional source systems. No actual bank/customer records.

PD cohorts are independent borrowers at observation dates, with complete
12-month outcomes. LGD records are resolved workouts with cash flows observed
for 24 months. The generator's latent risk is never exported as a feature.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit
from src.io_utils import write_csv

PRODUCTS = ["cash_loan", "secured_loan", "credit_card"]


def sample_features(n, rng, drift=0.0):
    product = rng.choice(PRODUCTS, n, p=[0.55, 0.20, 0.25])
    income = np.clip(rng.lognormal(np.log(6500), 0.40, n), 2500, 25000)
    dti = np.clip(rng.beta(2.2, 4.5, n) + drift, 0.02, 0.90)
    utilization = rng.beta(2.3, 2.0, n)
    employment_years = np.clip(rng.gamma(2.0, 2.5, n), 0, 25)
    dpd = rng.choice([0, 7, 20, 35, 60], n, p=[.79, .09, .06, .04, .02])
    delinquent_6m = np.clip(rng.poisson(0.5 + 1.2 * (dpd > 0), n), 0, 6)
    return pd.DataFrame({"income": income, "dti": dti,
                         "utilization": utilization, "employment_years": employment_years,
                         "dpd": dpd, "delinquent_6m": delinquent_6m, "product": product})


def default_probability(f, offset=0):
    z = (-4.3 + 2.4*f.dti + 1.4*f.utilization + .045*f.dpd
         + .24*f.delinquent_6m - .09*f.employment_years - .00004*f.income
         + .15*(f["product"] == "credit_card") + offset)
    return expit(z.to_numpy())


def historical_pd(config, rng):
    parts = []
    for group, count, start, end, shift in [
        ("train", config["pd_train_rows"], "2018-01-01", "2020-12-31", 0.),
        ("calibration", config["pd_calibration_rows"], "2022-01-01", "2022-12-31", .15),
        ("test", config["pd_test_rows"], "2024-01-01", "2024-12-31", .25),
    ]:
        f = sample_features(count, rng, shift*.08)
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        observation = start_ts + pd.to_timedelta(rng.integers(0, (end_ts-start_ts).days+1, count), unit="D")
        outcome_end = observation + pd.DateOffset(months=12)
        latent = rng.normal(0, .45, count)
        p = expit(np.log(default_probability(f)/(1-default_probability(f))) + shift + latent)
        target = rng.binomial(1, p)
        days = np.array((outcome_end - observation).days)
        default_offset = (rng.uniform(.001, 1., count) * days).astype(int).clip(1)
        default_date = observation + pd.to_timedelta(default_offset, unit="D")
        f.insert(0, "customer_id", [f"H-{group}-{i:05d}" for i in range(count)])
        f["observation_date"] = observation.strftime("%Y-%m-%d")
        f["outcome_end"] = outcome_end.strftime("%Y-%m-%d")
        f["default_date"] = np.where(target == 1, default_date.strftime("%Y-%m-%d"), None)
        f["default_12m"] = target
        f["cohort"] = group
        f.loc[rng.choice(count, max(1, count//50), replace=False), "income"] = np.nan
        parts.append(f)
    return pd.concat(parts, ignore_index=True)


def portfolio(config, rng):
    n = config["portfolio_loans"]
    f = sample_features(n, rng)
    f["dpd"] = 0
    f["delinquent_6m"] = 0
    customer_id = np.array([f"C-{i:05d}" for i in range(n)])
    loan_id = np.array([f"L-{i:05d}" for i in range(n)])
    borrowers = f[["income", "employment_years"]].copy()
    borrowers.insert(0, "customer_id", customer_id)
    borrowers.loc[rng.choice(n, n//50, replace=False), "income"] = np.nan
    products = f["product"].to_numpy()
    original = rng.uniform(12000, 95000, n)
    original[products == "secured_loan"] *= 2.7
    original[products == "credit_card"] = rng.uniform(4000, 24000, (products == "credit_card").sum())
    term = rng.integers(48, 85, n)
    term[products == "credit_card"] = 48
    eir = rng.uniform(.06, .19, n)
    collateral = np.where(products == "secured_loan", rng.uniform(.6, 1.3, n), 0.)
    orig_pd = np.clip(default_probability(f), .003, .75)
    origin = pd.Timestamp("2025-09-30") - pd.to_timedelta(rng.integers(30, 360, n), unit="D")
    loans = pd.DataFrame({"loan_id": loan_id, "customer_id": customer_id,
                          "product": products, "original_amount": original,
                          "origination_date": origin.strftime("%Y-%m-%d"), "eir": eir,
                          "collateral_coverage": collateral, "term_months": term,
                          "origination_pd_12m": orig_pd})
    state = rng.choice([0, 7, 20, 35, 60, 90], n, p=[.81, .07, .05, .035, .015, .02])
    default_flag = (state >= 90).astype(int)
    watch = (rng.random(n) < .012).astype(int)
    utp = np.zeros(n, dtype=int)
    default_balance = np.zeros(n)
    history = []
    delinquency_flags = []
    for t, date in enumerate(pd.date_range(end=config["report_date"], periods=12, freq="ME")):
        if t:
            new_default = (default_flag == 0) & (rng.random(n) < (.001 + .002*(state > 30)))
            default_flag[new_default] = 1
            state[new_default] = 90
            active = default_flag == 0
            jump = (rng.random(n) < .09) & active
            state[jump] = rng.choice([0, 7, 20, 35, 60], jump.sum(), p=[.56, .16, .12, .10, .06])
        remaining = np.where(products == "credit_card", 36, term-12-t)
        utilization = np.clip(f.utilization.to_numpy() + .015*t + rng.normal(0, .025, n), .02, .98)
        balance = np.where(products == "credit_card", original*utilization, original*(remaining/term))
        newly_frozen = (default_flag == 1) & (default_balance == 0)
        default_balance[newly_frozen] = balance[newly_frozen]
        balance = np.where(default_flag == 1, default_balance, balance)
        undrawn = np.where((products == "credit_card") & (default_flag == 0), original-balance, 0)
        # A qualitative unlikeliness-to-pay trigger may occur before 90 DPD.
        new_utp = (default_flag == 0) & (rng.random(n) < .0007)
        utp[new_utp] = 1
        default_flag[new_utp] = 1
        default_balance[new_utp] = balance[new_utp]
        undrawn[new_utp] = 0
        delinquency_flags.append((state > 0).astype(int))
        # A genuinely rolling count, never a function of elapsed calendar time.
        delinquent_6m = np.sum(delinquency_flags[-6:], axis=0)
        part = pd.DataFrame({"loan_id": loan_id, "report_date": date.strftime("%Y-%m-%d"),
                             "balance": balance, "undrawn": undrawn, "dpd": state,
                             "default_flag": default_flag, "utp": utp, "watchlist": watch,
                             "dti": np.clip(f.dti.to_numpy()+.004*t+rng.normal(0,.008,n),.02,.95),
                             "utilization": utilization, "delinquent_6m": delinquent_6m,
                             "remaining_months": remaining})
        history.append(part)
    snapshots = pd.concat(history, ignore_index=True)
    snapshots["ingestion_id"] = np.arange(len(snapshots))
    duplicates = snapshots.iloc[:8].copy()
    duplicates["ingestion_id"] = np.arange(len(snapshots), len(snapshots)+8)
    invalid = snapshots.tail(4).copy()
    invalid["ingestion_id"] = np.arange(len(snapshots)+8, len(snapshots)+12)
    invalid.loc[invalid.index[:3], "report_date"] = "2026-09-15"
    invalid.loc[invalid.index[0], "balance"] = -100
    invalid.loc[invalid.index[1], "balance"] = np.nan
    invalid.loc[invalid.index[2], "remaining_months"] = 0
    invalid.loc[invalid.index[3], "loan_id"] = "UNKNOWN-LOAN"
    return borrowers, loans, pd.concat([snapshots, duplicates, invalid], ignore_index=True)


def workouts(config, rng):
    defaults, cashflows = [], []
    for cohort, n, start, end in [
        ("train", config["lgd_train_rows"], "2017-01-01", "2019-12-31"),
        ("test", config["lgd_test_rows"], "2022-01-01", "2022-12-31"),
    ]:
        features = sample_features(n, rng)
        ead = rng.uniform(10000, 150000, n)
        coverage = np.where(features["product"] == "secured_loan", rng.uniform(.6,1.3,n), 0.)
        eir = rng.uniform(.06, .19, n)
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        date = start_ts + pd.to_timedelta(rng.integers(0, (end_ts-start_ts).days+1,n),unit="D")
        # Gross recoveries and workout costs are separate transactions.
        recovery_rate = np.clip(.30+.50*coverage-.06*features.utilization.to_numpy()
                                -.025*(features["product"].to_numpy()=="credit_card")+rng.normal(0,.075,n),.06,.96)
        cost_rate = rng.uniform(.015,.055,n)
        for i in range(n):
            case = f"W-{cohort}-{i:05d}"
            defaults.append({"case_id":case,"default_date":date[i].strftime("%Y-%m-%d"),
                             "resolved_date":(date[i]+pd.DateOffset(months=24)).strftime("%Y-%m-%d"),
                             "cohort":cohort,"product":features["product"].iloc[i],"ead_at_default":ead[i],
                             "collateral_coverage":coverage[i],"utilization":features.utilization.iloc[i],"eir":eir[i]})
            allocations = rng.dirichlet([1,2,2,1])
            for month, share in zip([3,6,12,24],allocations):
                cashflows.append({"case_id":case,"month_after_default":month,
                                  "recovery":ead[i]*recovery_rate[i]*share,
                                  "cost":ead[i]*cost_rate[i]*share,
                                  "cashflow_date":(date[i]+pd.DateOffset(months=month)).strftime("%Y-%m-%d")})
    return pd.DataFrame(defaults), pd.DataFrame(cashflows)


def generate(root: Path, config):
    raw = root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(config["seed"])
    hist = historical_pd(config, rng)
    borrowers, loans, snapshots = portfolio(config, rng)
    defaults, cashflows = workouts(config, rng)
    for name, df in {"historical_pd":hist,"borrowers":borrowers,"loans":loans,
                     "snapshots":snapshots,"workouts":defaults,"recoveries":cashflows}.items():
        write_csv(df,raw / f"{name}.csv",index=False,float_format="%.8f")
