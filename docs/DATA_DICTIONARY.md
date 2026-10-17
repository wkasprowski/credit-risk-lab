# Data dictionary

All data are synthetic. Each reporting customer has one contract. Historical modelling customers and reporting-portfolio customers are independent. Reporting values are in PLN; probabilities are decimal fractions.

| Field | Meaning |
|---|---|
| customer_id / loan_id / case_id | Fictional business keys |
| report_date | Month-end snapshot date, not a cash-flow period |
| observation_date / outcome_end | PD feature date and complete twelve-month target-window end |
| default_date / default_12m | Outcome date and binary target; excluded from PD predictors |
| income | Fictional monthly income; missing values allowed |
| dti | Monthly debt-service burden divided by income in the simulation |
| utilisation / utilization | Fraction of available/general indebtedness capacity in use |
| employment_years | Employment tenure |
| dpd | Days past due |
| delinquent_6m | Count of delinquent months over the observed rolling six-month history |
| default_flag / utp / watchlist | Simulated default, unlikeliness to pay, and early-warning flags |
| balance / undrawn | Current drawn exposure and available undrawn limit |
| eir | Assumed annual effective interest rate |
| collateral_coverage | Simulated collateral value relative to exposure |
| remaining_months | Remaining instalment or assumed behavioural horizon |
| origination_pd_12m | Simulated initial-recognition PD field |
| pd_12m / pd_lifetime | Modelled default probabilities; Stage 3 uses one |
| lgd | Predicted discounted fractional loss given default |
| ead | Exposure plus assumed further drawdown when applicable |
| stage / stage_reason | Assigned risk stage and first triggering rule |
| ecl_base / ecl_optimistic / ecl_adverse | Scenario ECL in PLN |
| ecl_weighted | Weighted ECL in PLN |
| coverage_ratio | Weighted ECL divided by EAD |
| sicr_pd_ratio / sicr_absolute_increase | Quantitative deterioration over a common remaining horizon |

The source field is spelled `utilization` in CSV/code. It is a designed synthetic risk indicator, including for instalment products; it is not an actual external credit-bureau measure.

The first reporting months have only the observed history available in the generator. A production behavioural model would need a defined full lookback and treatment of missing history.

Never sum balance/EAD across all reporting dates and present that as a single current portfolio. Use one date for cards; use separate dates for trends.

The audit file grain is contract × scenario × possible default month. Stage 3 uses month zero. `contribution` precedes scenario weighting; `weighted_contribution` includes the weight and can be summed across scenarios.
