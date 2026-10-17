"""Financial identities, leakage guards and end-to-end reconciliations."""
import json
import sqlite3
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from src.ecl import (annual_to_monthly_hazard,lifetime_probability,assign_stages,
                     calculate_ecl,projected_ead)
from src.models import discounted_workout_lgd,validate_pd_cohorts,PD_FEATURES

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config.json").read_text())


def one_loan(**changes):
    values = dict(loan_id="TEST",report_date="2026-09-30",product="credit_card",
                  balance=10000.,undrawn=0.,remaining_months=24, eir=0.,
                  pd_12m=.12,lgd=.5,stage=1,origination_pd_12m=.12,
                  dpd=0,watchlist=0,default_flag=0,utp=0)
    values.update(changes)
    return pd.DataFrame([values])


class FinancialIdentities(unittest.TestCase):
    def test_monthly_marginal_probabilities_sum_to_annual_pd(self):
        p=.12
        q=float(annual_to_monthly_hazard(p))
        self.assertAlmostEqual(sum((1-q)**(m-1)*q for m in range(1,13)),p,places=12)

    def test_two_year_survival_probability(self):
        self.assertAlmostEqual(float(lifetime_probability(.12,24)),1-.88**2,places=12)

    def test_stage1_constant_exposure_equals_pd_lgd_ead(self):
        f,_=calculate_ecl(one_loan(),{**CONFIG,"scenarios":[dict(name="base",weight=1,pd_odds_multiplier=1,lgd_multiplier=1)]})
        self.assertAlmostEqual(f.ecl_weighted.iloc[0],600.,places=8)

    def test_stage2_covers_defaults_after_twelve_months(self):
        f,_=calculate_ecl(one_loan(stage=2),{**CONFIG,"scenarios":[dict(name="base",weight=1,pd_odds_multiplier=1,lgd_multiplier=1)]})
        self.assertAlmostEqual(f.ecl_weighted.iloc[0],(1-.88**2)*5000,places=8)

    def test_short_maturity_limits_stage1_to_remaining_life(self):
        f,_=calculate_ecl(one_loan(remaining_months=6),{**CONFIG,"scenarios":[dict(name="base",weight=1,pd_odds_multiplier=1,lgd_multiplier=1)]})
        self.assertAlmostEqual(f.ecl_weighted.iloc[0],(1-.88**.5)*5000,places=8)

    def test_stage3_excludes_undrawn_and_does_not_rediscout_workout_lgd(self):
        f,_=calculate_ecl(one_loan(stage=3,pd_12m=1,undrawn=9000,eir=.1),
                         {**CONFIG,"scenarios":[dict(name="base",weight=1,pd_odds_multiplier=1,lgd_multiplier=1)]})
        self.assertEqual(f.ead.iloc[0],10000)
        self.assertEqual(f.ecl_weighted.iloc[0],5000)

    def test_zero_pd_produces_zero_expected_loss(self):
        f,_=calculate_ecl(one_loan(pd_12m=0),CONFIG)
        self.assertEqual(f.ecl_weighted.iloc[0],0)

    def test_discounted_net_recovery_hand_example(self):
        defaults=pd.DataFrame([dict(case_id="X",ead_at_default=100.,eir=.1)])
        recoveries=pd.DataFrame([dict(case_id="X",month_after_default=24,recovery=60.,cost=10.)])
        out=discounted_workout_lgd(defaults,recoveries)
        self.assertAlmostEqual(out.lgd_target.iloc[0],1-50/(1.1**2)/100,places=12)

    def test_zero_interest_equal_principal_amortisation(self):
        ead=projected_ead(np.array([12000.]),np.array([0.]),np.array([12.]),
                          np.array([0.]),np.array([False]),12,.5)
        self.assertAlmostEqual(ead[0],1000.,places=9)

    def test_positive_interest_last_installment_balance(self):
        eir=.12;monthly=(1+eir)**(1/12)-1
        payment=12000*monthly/(1-(1+monthly)**-12)
        ead=projected_ead(np.array([12000.]),np.array([0.]),np.array([12.]),
                          np.array([eir]),np.array([False]),12,.5)
        self.assertAlmostEqual(ead[0],payment/(1+monthly),places=8)

    def test_thirty_dpd_is_not_the_over_thirty_backstop(self):
        frame=pd.concat([one_loan(dpd=30),one_loan(dpd=31),one_loan(dpd=90)],ignore_index=True)
        self.assertEqual(assign_stages(frame,CONFIG).stage.tolist(),[1,2,3])

    def test_unlikeliness_to_pay_defaults_without_arrears(self):
        self.assertEqual(assign_stages(one_loan(utp=1),CONFIG).stage.iloc[0],3)

    def test_quantitative_sicr_uses_lifetime_risk(self):
        self.assertEqual(assign_stages(one_loan(pd_12m=.08,origination_pd_12m=.02),CONFIG).stage.iloc[0],2)

    def test_invalid_scenario_weights_fail(self):
        broken={**CONFIG,"scenarios":[dict(name="base",weight=.8,pd_odds_multiplier=1,lgd_multiplier=1)]}
        with self.assertRaises(ValueError):
            calculate_ecl(one_loan(),broken)

    def test_invalid_pd_fails(self):
        with self.assertRaises(ValueError):
            annual_to_monthly_hazard(1.1)

    def test_null_ecl_input_fails(self):
        with self.assertRaises(ValueError):
            calculate_ecl(one_loan(balance=np.nan),CONFIG)


class PipelineEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output=ROOT / "outputs"
        if not (cls.output / "metrics.json").exists():
            raise RuntimeError("Run python run_pipeline.py before integration tests")
        cls.metrics=json.loads((cls.output / "metrics.json").read_text())
        cls.fact=pd.read_csv(cls.output / "fact_ecl.csv")
        cls.historical=pd.read_csv(ROOT / "data" / "raw" / "historical_pd.csv")

    def test_row_reconciliation(self):
        q=self.metrics["data_quality"]
        self.assertEqual(q["raw_snapshot_rows"]-q["duplicates_removed"]-q["quarantined_rows"],q["accepted_rows"])
        self.assertEqual(q["duplicates_removed"],8)
        self.assertEqual(q["quarantined_rows"],4)

    def test_six_month_delinquency_is_reconstructed_from_observed_history(self):
        with sqlite3.connect(self.output / "credit_risk.sqlite") as conn:
            df=pd.read_sql_query("""
              SELECT c.loan_id,c.report_date,d.delinquent_6m,
               SUM(CASE WHEN c.dpd>0 THEN 1 ELSE 0 END) OVER(
                 PARTITION BY c.loan_id ORDER BY c.report_date
                 ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) AS expected
              FROM curated_snapshots c JOIN deduplicated_snapshots d
              ON c.loan_id=d.loan_id AND c.report_date=d.report_date
            """,conn)
        np.testing.assert_array_equal(df.delinquent_6m,df.expected)

    def test_population_is_unique_and_complete_each_month(self):
        self.assertFalse(self.fact.duplicated(["loan_id","report_date"]).any())
        self.assertEqual(self.fact.report_date.nunique(),12)
        self.assertTrue((self.fact.groupby("report_date").size()==CONFIG["portfolio_loans"]).all())

    def test_scenario_ordering_and_convex_combination(self):
        f=self.fact
        self.assertTrue((f.ecl_adverse+1e-6>=f.ecl_base).all())
        self.assertTrue((f.ecl_base+1e-6>=f.ecl_optimistic).all())
        expected=.2*f.ecl_optimistic+.6*f.ecl_base+.2*f.ecl_adverse
        np.testing.assert_allclose(f.ecl_weighted,expected,atol=1e-6,rtol=1e-12)

    def test_stage3_probabilities_and_exposure(self):
        f=self.fact[self.fact.stage==3]
        self.assertTrue((f.pd_12m==1).all())
        np.testing.assert_allclose(f.ead,f.balance)

    def test_loan_level_audit_reconciles_to_latest_fact(self):
        detail=pd.read_csv(self.output / "ecl_calculation_audit.csv")
        amount=detail.groupby("loan_id").weighted_contribution.sum()
        latest=self.fact[self.fact.report_date==CONFIG["report_date"]].set_index("loan_id")
        np.testing.assert_allclose(amount,latest.loc[amount.index,"ecl_weighted"],atol=1e-6,rtol=1e-12)

    def test_sql_and_csv_totals_reconcile(self):
        with sqlite3.connect(self.output / "credit_risk.sqlite") as conn:
            actual=conn.execute("SELECT SUM(ecl_weighted) FROM fact_ecl WHERE report_date=?",(CONFIG["report_date"],)).fetchone()[0]
        expected=self.fact.loc[self.fact.report_date==CONFIG["report_date"],"ecl_weighted"].sum()
        self.assertAlmostEqual(actual,expected,places=5)

    def test_purged_temporal_split_and_feature_whitelist(self):
        validate_pd_cohorts(self.historical,CONFIG["report_date"])
        self.assertFalse(set(PD_FEATURES)&{"default_12m","outcome_end","default_date","cohort","customer_id"})

    def test_future_outcome_is_rejected(self):
        bad=self.historical.copy()
        bad.loc[bad.index[0],"outcome_end"]="2027-01-01"
        with self.assertRaises(ValueError):
            validate_pd_cohorts(bad,CONFIG["report_date"])

    def test_duplicate_borrower_is_rejected(self):
        bad=self.historical.copy()
        bad.loc[bad.index[-1],"customer_id"]=bad.customer_id.iloc[0]
        with self.assertRaises(ValueError):
            validate_pd_cohorts(bad,CONFIG["report_date"])


if __name__=="__main__":
    unittest.main()
