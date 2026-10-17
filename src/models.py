import json
import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from src.io_utils import write_csv

PD_NUMERIC = ["income","dti","utilization","employment_years","dpd","delinquent_6m"]
PD_FEATURES = PD_NUMERIC + ["product"]
LGD_NUMERIC = ["collateral_coverage","utilization","eir"]
LGD_FEATURES = LGD_NUMERIC + ["product"]


def preprocessing(numeric, categorical):
    parts = [("num", Pipeline([("impute",SimpleImputer(strategy="median")),
                               ("scale",StandardScaler())]),numeric)]
    if categorical:
        parts.append(("cat",OneHotEncoder(handle_unknown="ignore",drop="first",sparse_output=False),categorical))
    return ColumnTransformer(parts, remainder="drop", verbose_feature_names_out=False)


def validate_pd_cohorts(df, asof):
    obs, end = pd.to_datetime(df.observation_date), pd.to_datetime(df.outcome_end)
    if (end > pd.Timestamp(asof)).any() or (end <= obs).any():
        raise ValueError("Incomplete or invalid 12-month performance window")
    if not (end == obs + pd.DateOffset(months=12)).all():
        raise ValueError("Outcome window must cover 12 months")
    if df.customer_id.duplicated().any() or df.customer_id.isna().any():
        raise ValueError("Borrowers must not cross train/calibration/test cohorts")
    if not df.default_12m.isin([0,1]).all():
        raise ValueError("Invalid binary target")
    event = pd.to_datetime(df.default_date)
    positives = df.default_12m == 1
    if (event[positives].isna().any() or
        not ((event[positives] > obs[positives]) & (event[positives] <= end[positives])).all()
        or event[~positives].notna().any()):
        raise ValueError("Default date inconsistent with target/performance window")
    train, cal, test = (df[df.cohort == s] for s in ["train","calibration","test"])
    if any(d.empty or d.default_12m.nunique() != 2 for d in [train,cal,test]):
        raise ValueError("Every cohort must contain positive and negative outcomes")
    # Purged temporal split: all prior cohort outcomes mature before the next
    # cohort's first feature observation. No overlapping label windows.
    if not (train.outcome_end.max() < cal.observation_date.min()
            and cal.outcome_end.max() < test.observation_date.min()):
        raise ValueError("Overlapping temporal feature/outcome windows")


def score_psi(reference, comparison, bins=10):
    edges = np.unique(np.quantile(reference,np.linspace(0,1,bins+1)))
    if len(edges) < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    a = np.histogram(reference,bins=edges)[0].astype(float)
    b = np.histogram(comparison,bins=edges)[0].astype(float)
    a = np.maximum(a / max(1,a.sum()),1e-6)
    b = np.maximum(b / max(1,b.sum()),1e-6)
    return float(np.sum((b-a)*np.log(b/a)))


def probability_metrics(y,p):
    auc = float(roc_auc_score(y,p))
    return {"roc_auc":auc,"gini":2*auc-1,"brier":float(brier_score_loss(y,p)),
            "log_loss":float(log_loss(y,p)),"mean_pd":float(np.mean(p)),
            "observed_default_rate":float(np.mean(y)),"rows":len(y)}


def export_linear(model, numeric, directory, filename, extra=None):
    prep, fitted = model.named_steps["prep"], model.named_steps["model"]
    transform = prep.named_transformers_["num"]
    out = {"feature_names":prep.get_feature_names_out().tolist(),
           "numeric_features":numeric,"medians":transform.named_steps["impute"].statistics_.tolist(),
           "means":transform.named_steps["scale"].mean_.tolist(),
           "standard_deviations":transform.named_steps["scale"].scale_.tolist(),
           "coefficients":np.ravel(fitted.coef_).tolist(),
           "intercept":float(np.ravel(fitted.intercept_)[0]),
           "categorical_encoding":"product, first category dropped"}
    if "cat" in prep.named_transformers_:
        out["categories"] = [x.tolist() for x in prep.named_transformers_["cat"].categories_]
    if extra:
        out.update(extra)
    directory.mkdir(exist_ok=True)
    (directory / filename).write_text(json.dumps(out,indent=2),encoding="utf-8")


def train_pd(conn, config, output):
    df = pd.read_sql_query("SELECT * FROM pd_observations ORDER BY observation_date,customer_id",conn)
    validate_pd_cohorts(df,config["report_date"])
    train, cal, test = (df[df.cohort == s].copy() for s in ["train","calibration","test"])
    full = Pipeline([("prep",preprocessing(PD_NUMERIC,["product"])),
                     ("model",LogisticRegression(C=1.,max_iter=1500,tol=1e-8,random_state=config["seed"]))])
    baseline_features = ["dti","utilization","dpd"]
    baseline = Pipeline([("prep",preprocessing(baseline_features,[])),
                         ("model",LogisticRegression(C=1.,max_iter=1500,tol=1e-8))])
    full.fit(train[PD_FEATURES],train.default_12m)
    baseline.fit(train[baseline_features],train.default_12m)
    # Explicit Platt scaling on an independent, later cohort.
    calibrator = LogisticRegression(C=1e6,max_iter=1500,tol=1e-9)
    calibrator.fit(full.decision_function(cal[PD_FEATURES]).reshape(-1,1),cal.default_12m)
    if calibrator.coef_[0,0] <= 0:
        raise ValueError("Calibration unexpectedly reverses score ordering")
    def predict(frame):
        return calibrator.predict_proba(full.decision_function(frame[PD_FEATURES]).reshape(-1,1))[:,1]
    p = predict(test)
    metrics = {
        "baseline_3_features":probability_metrics(test.default_12m,baseline.predict_proba(test[baseline_features])[:,1]),
        "full_uncalibrated":probability_metrics(test.default_12m,full.predict_proba(test[PD_FEATURES])[:,1]),
        "full_calibrated":probability_metrics(test.default_12m,p),
        "score_psi_train_vs_test":score_psi(predict(train),p),
        "split":{s:{"rows":len(d),"observation_start":d.observation_date.min(),
                    "observation_end":d.observation_date.max(),"labels_mature_by":d.outcome_end.max()}
                 for s,d in [("train",train),("calibration",cal),("test",test)]},
        "selection_policy":"Full calibrated logistic model specified before opening out-of-time test. No test-set tuning."
    }
    rng = np.random.default_rng(config["seed"]+71)
    y = test.default_12m.to_numpy()
    boot = []
    for _ in range(200):
        idx = rng.integers(0,len(y),len(y))
        if np.unique(y[idx]).size == 2:
            boot.append(roc_auc_score(y[idx],p[idx]))
    metrics["auc_bootstrap_95ci"] = np.quantile(boot,[.025,.975]).tolist()
    preds = test[["customer_id","observation_date","default_12m"]].copy()
    preds["pd_12m"] = p
    write_csv(preds,output / "pd_test_predictions.csv",index=False)
    preds["bin"] = pd.qcut(preds.pd_12m,10,labels=False,duplicates="drop")+1
    bins = preds.groupby("bin").agg(rows=("pd_12m","size"),mean_pd=("pd_12m","mean"),
                                   observed_rate=("default_12m","mean"),defaults=("default_12m","sum")).reset_index()
    z = 1.96
    denom = 1+z*z/bins.rows
    center = (bins.observed_rate+z*z/(2*bins.rows))/denom
    half = z*np.sqrt(bins.observed_rate*(1-bins.observed_rate)/bins.rows+z*z/(4*bins.rows**2))/denom
    bins["wilson_low"],bins["wilson_high"] = center-half,center+half
    write_csv(bins,output / "pd_calibration_bins.csv",index=False)
    names = full.named_steps["prep"].get_feature_names_out()
    coef = full.named_steps["model"].coef_[0]
    write_csv(pd.DataFrame({"feature":names,"coefficient":coef,"odds_ratio":np.exp(coef)}),output / "pd_coefficients.csv",index=False)
    export_linear(full,PD_NUMERIC,output / "models","pd_model.json",{
        "calibration_slope":float(calibrator.coef_[0,0]),
        "calibration_intercept":float(calibrator.intercept_[0]),"purpose":"12-month behavioural default probability"})
    return predict, metrics, predict(train)


def discounted_workout_lgd(defaults, cashflows):
    if defaults.case_id.duplicated().any():
        raise ValueError("Duplicate workout key")
    merged = cashflows.merge(defaults[["case_id","ead_at_default","eir"]],on="case_id",validate="many_to_one")
    if len(merged) != len(cashflows) or (merged.ead_at_default <= 0).any():
        raise ValueError("Unmatched recovery transaction or invalid default exposure")
    merged["pv_net_recovery"] = (merged.recovery-merged.cost)/(1+merged.eir)**(merged.month_after_default/12)
    pv = merged.groupby("case_id").pv_net_recovery.sum()
    out = defaults.copy()
    out["pv_net_recovery"] = out.case_id.map(pv).fillna(0)
    out["lgd_unbounded"] = 1-out.pv_net_recovery/out.ead_at_default
    out["lgd_target"] = out.lgd_unbounded.clip(0,1)
    return out


def train_lgd(conn, config, output):
    defaults = pd.read_sql_query("SELECT * FROM raw_workouts",conn)
    cashflows = pd.read_sql_query("SELECT * FROM raw_recoveries",conn)
    if ((defaults.resolved_date > config["report_date"]).any()
        or (cashflows.cashflow_date > config["report_date"]).any()):
        raise ValueError("Future or unresolved workout outcomes")
    df = discounted_workout_lgd(defaults,cashflows)
    train,test = df[df.cohort=="train"],df[df.cohort=="test"]
    if train.resolved_date.max() >= test.default_date.min():
        raise ValueError("LGD outcome windows overlap test observation dates")
    model = Pipeline([("prep",preprocessing(LGD_NUMERIC,["product"])),("model",Ridge(alpha=5.))])
    model.fit(train[LGD_FEATURES],train.lgd_target)
    def predict(frame):
        return np.clip(model.predict(frame[LGD_FEATURES]),0,1)
    pred = predict(test)
    metrics = {"mae":float(mean_absolute_error(test.lgd_target,pred)),
               "constant_mean_baseline_mae":float(mean_absolute_error(test.lgd_target,np.repeat(train.lgd_target.mean(),len(test)))),
               "mean_predicted":float(np.mean(pred)),"mean_observed":float(test.lgd_target.mean()),
               "train_rows":len(train),"test_rows":len(test),
               "target_clipped_rows":int((df.lgd_unbounded != df.lgd_target).sum()),
               "train_resolved_by":train.resolved_date.max(),"test_default_start":test.default_date.min(),
               "all_resolved_by":df.resolved_date.max()}
    write_csv(df,output / "lgd_workout_targets.csv",index=False)
    test_out = test[["case_id","lgd_target"]].copy()
    test_out["predicted_lgd"] = pred
    write_csv(test_out,output / "lgd_test_predictions.csv",index=False)
    export_linear(model,LGD_NUMERIC,output / "models","lgd_model.json",{
        "prediction_clip":[0,1],"target":"1 - discounted net recoveries / EAD at default"})
    return predict,metrics
