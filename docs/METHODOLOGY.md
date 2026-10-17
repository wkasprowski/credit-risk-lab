# Model methodology and assumptions

This document describes the implemented demonstrator, not a complete IFRS 9 or prudential IRB model. All customers, balances, outcomes, recoveries and dates are synthetic. Default and credit impairment are equated for this simplified experiment.

## Sources and quality

Six CSV extracts are generated with NumPy's fixed seed 42. Historical PD cohorts contain independent customers; the reporting portfolio is a separate population. Latent generator risk is not exported as a feature.

SQL checks raw-key uniqueness before joining. Snapshot versions use ROW_NUMBER partitioned by loan/date, ordered by descending ingestion_id. The newest version wins; invalid newest data are quarantined rather than silently replaced with an older observation.

Checks cover missing contracts/customers, balances, exposure signs, maturity, DPD, utilisation, DTI and flags. The default dataset has 72,012 raw snapshot rows, eight duplicate copies and four rejected records, leaving 72,000 accepted snapshots. Missing income is handled by a median fitted only on PD training data.

The SQL prior-DPD windows demonstrate feature engineering but are not extra PD predictors: matching historical training inputs are not available for those additional columns.

## PD model and leakage prevention

The target is default during the next twelve months for a non-defaulted customer at observation. Features are income, DTI, utilisation, employment years, current DPD, delinquent months over six months, and product.

Numeric imputation and standardisation are fitted inside a training pipeline. Product uses one-hot encoding with the first category omitted. No identifier, cohort, target, future default date, outcome-window end or later recovery is a PD predictor.

| Cohort | Observation period | Rows | Use |
|---|---|---:|---|
| Train | 2018–2020 | 12,000 | Preprocessing and logistic coefficients |
| Calibration | 2022 | 4,000 | Independent Platt slope/intercept |
| Test | 2024 | 4,000 | Frozen out-of-time assessment |

Customer IDs are unique across cohorts. Earlier outcome windows mature before the next cohort's first feature observation. Validation rejects future/incomplete windows and targets inconsistent with default dates. Outcomes are fully observed before the as-of date.

The full calibrated logistic model was specified before the final test. A simpler DTI/utilisation/DPD logistic model is a benchmark; it is not used to tune on test data. No class balancing is applied to distort probabilities. Platt scaling is a logistic model of training-model logits fitted on the independent calibration cohort.

Reported metrics are ROC-AUC, Gini=2*AUC−1, Brier, log loss, mean PD and observed default rate. Reliability deciles include Wilson intervals; the AUC interval uses 200 deterministic bootstrap resamples. Brier reflects more than calibration alone. Coefficient odds ratios are associations; numeric coefficients refer to one standard deviation.

PSI bins are set from training scores. Both train/test and train/current-performing PSI are recorded. The current portfolio PSI around 0.4167 warrants analysis of population and feature shifts; no automatic production-acceptance threshold is asserted.

## LGD

For each resolved workout:

~~~text
PV_net_recovery = sum((recovery_t - cost_t) / (1 + EIR)^(t/12))
LGD_raw = 1 - PV_net_recovery / EAD_at_default
LGD_target = clip(LGD_raw, 0, 1)
~~~

Each case has four recovery/cost transactions over a 24-month period. Ridge regression predicts LGD using product, collateral coverage, utilisation and EIR; predictions are clipped to [0,1].

Training: 2,400 defaults from 2017–2019, resolved by the end of 2021. Test: 900 defaults from 2022, resolved by the end of 2024. Future recovery amounts and resolution outcomes are not predictors. MAE is compared with a constant training-mean baseline. The target-clipping count is reported.

Only resolved cases are modelled. Open-workout selection bias, incomplete recovery histories and censoring are not corrected.

## Stage assignment and SICR

Ordered rules:

1. Stage 3: default_flag=1, unlikeliness-to-pay flag=1, or DPD>=90.
2. Stage 2: DPD>30, watchlist=1, or the quantitative SICR rule.
3. Stage 1 otherwise.

The standard's 30/90 DPD presumptions can be rebuttable. This demonstrator has no rebuttal process and implements the stated rules. It omits POCI, cure/probation periods and complex restructurings.

The quantitative rule compares current and origination risk over a common remaining horizon:

~~~text
PD_lifetime(p, n) = 1 - (1-p)^(n/12)
SICR if current_lifetime_PD / origin_lifetime_PD >= 2
        AND current_lifetime_PD - origin_lifetime_PD >= 0.03
~~~

The ratio and absolute thresholds are project assumptions, not mandatory IFRS numeric thresholds. Origination PD is a simulated source-system field, not a validated historical origination model. Stage 1 need not mean low absolute PD; it concerns deterioration since initial recognition.

## EAD and discounting

Instalment exposure is reconstructed from current balance, remaining months and an effective monthly rate (1+EIR)^(1/12)−1. It is measured just before the scheduled payment/default in the month.

Performing cards use drawn balance + 50% of undrawn available limit, with constant exposure and a 36-month assumed behavioural horizon. Stage 3 uses drawn exposure only, assuming further drawing is unavailable.

The historical synthetic balances are not a complete accounting amortisation system. Future exposure is reconstructed at each reporting date. Prepayments, limit changes, competing events, fees and detailed behavioural dynamics are omitted.

LGD discounts recoveries from recovery time to default time. ECL separately discounts default losses from default time to reporting time; these are different intervals.

## Monthly ECL and scenarios

~~~text
monthly_hazard_s = 1 - (1 - PD_12m_s)^(1/12)
marginal_PD_s,t = (1 - monthly_hazard_s)^(t-1) * monthly_hazard_s
ECL_s = sum_t marginal_PD_s,t * LGD_s * EAD_t / (1+EIR)^(t/12)
ECL_weighted = 0.2*ECL_optimistic + 0.6*ECL_base + 0.2*ECL_adverse
~~~

Stage 1 includes default events up to min(12, remaining months), not only recovery cash flows occurring within twelve months. Stage 2 includes defaults over remaining life. A 12% constant annual PD gives two-year lifetime PD 1−0.88²=22.56%, not 24%.

Stage 3 uses PD=1 and conditional loss = current drawn balance * scenario LGD. This is a proxy for future loss at the reporting date, not an individually timed remaining recovery model conditioned on time already in default.

| Scenario | Weight | PD odds multiplier | LGD multiplier |
|---|---:|---:|---:|
| Optimistic | 0.2 | 0.8 | 0.9 |
| Base | 0.6 | 1.0 | 1.0 |
| Adverse | 0.2 | 1.8 | 1.2 |

The probability transformation is p_s=m*p/(1-p+m*p); LGD is clipped to [0,1]. Stages are fixed across scenarios. Multipliers and weights are assumed, not estimated from unemployment, GDP or interest-rate paths. The default configuration is the supported baseline for regression verification.

## Audit and sensitivity

The engine exports monthly/scenario components for six selected contracts, two per stage. Summing weighted_contribution reconciles each selected contract to the fact table. SQL and Python reconcile at the portfolio level. The tests also check probability mass, maturity limits, exposure schedules and scenario bounds.

Sensitivity changes one assumption at a time: PD odds +20%, LGD +20%, CCF to 75%, or SICR ratio to 1.5. PD/LGD/CCF sensitivities hold stages fixed; the SICR sensitivity reassigns them.

The baseline CCF sensitivity raises weighted ECL by about 306,116.14 PLN. All results describe this generator only. Real use would require appropriate source data, definitions, macro relationships, independent model validation and governance.

## Baseline verification policy

The verification script deliberately freezes the default dataset, financial totals and preserved source hashes. Intentional model or generator changes require a fresh review and explicit baseline/provenance update; they should not be presented as the unchanged validated release.
