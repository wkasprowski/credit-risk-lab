# Build a Power BI report from the project

**Status:** no PBIX file exists in this release. The screenshots and preview are HTML. The supplied M/DAX has not been executed in Power BI Desktop; complete the checks below before claiming a Power BI implementation.

The following steps use the full generated data. The small sample files will not reproduce headline portfolio totals.

## 1 Generate the source data

From the project directory, run the pipeline using the Windows instructions in README. Confirm that `outputs/fact_ecl.csv` exists and has 72,000 rows. Do not use the 30-row sample as the full model.

Install [Power BI Desktop](https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop). This procedure creates a local report; it does not require publishing to Power BI Service.

## 2 Import through Power Query

1. Create a blank Power BI Desktop report.
2. Choose Transform data, then create a Blank Query.
3. Open Advanced Editor.
4. Paste all of `powerbi/import_fact_ecl.m`.
5. Replace the `SET_PROJECT_FOLDER` string with the path to your local repository directory. This is a required user-supplied path, not a path embedded in the project.
6. Name the query exactly **FactECL**.
7. Keep CSV delimiter comma, UTF-8 encoding and parsing culture **en-US**. The numbers use decimal points regardless of Windows locale.
8. Close and Apply.

Expected columns include report_date, loan_id, product, stage, pd_12m, lgd, ead, ecl_weighted and the three scenario ECL columns. Check that report_date is Date; stage/DPD/maturity are whole numbers; amounts and probabilities are decimal numbers.

Expected grain: one loan and reporting date. Twelve monthly observations of one loan are twelve rows, not twelve different loans.

## 3 Create the semantic model

The file `powerbi/measures.dax` contains multiple definitions. **Create each measure separately** using Modeling → New measure. Do not paste the entire file into one measure.

Create:

- EAD PLN and Drawn Balance PLN
- ECL Weighted PLN, ECL Base PLN, ECL Adverse PLN and ECL Optimistic PLN
- Coverage Ratio and Loan Count
- PD Performing Weighted and Adverse Uplift

Create **Calendar as a calculated table**, using Modeling → New table:

~~~dax
Calendar =
CALENDAR(MIN(FactECL[report_date]), MAX(FactECL[report_date]))
~~~

Relate Calendar[Date] (one) to FactECL[report_date] (many), single-direction filtering. Mark Calendar as a date table using its Date field.

The one-to-many relationship must not accidentally become many-to-many. No loan-level table with one row per month should be treated as a unique loan dimension.

## 4 Apply formats

| Item | Format |
|---|---|
| Monetary measures | PLN, two decimal places; million display units for cards |
| Coverage Ratio, PD Performing Weighted, Adverse Uplift | Percentage |
| FactECL[pd_12m], FactECL[lgd] | Percentage, not a sum of percentages |
| Loan Count | Whole number |
| Calendar[Date] | Date |

PD Performing Weighted excludes Stage 3 and weights by EAD. A simple average or a SUM of PD is a different quantity.

## 5 Build one report page

Use a 16:9 page and a clear layout. Suggested colours: navy #11243B, teal #147D75, orange #DC8046.

| Visual | Fields |
|---|---|
| Single-select slicer | Calendar[Date] |
| Product slicer | FactECL[product] |
| Stage slicer | FactECL[stage] |
| Four cards | Loan Count, EAD PLN, ECL Weighted PLN, Coverage Ratio |
| Stage columns | stage and ECL Weighted PLN |
| Scenario trend | Calendar[Date], ECL Base PLN, ECL Adverse PLN |
| Segment matrix | product, stage; Loan Count, EAD PLN, ECL Weighted PLN |
| Top-loss table | loan_id, stage, dpd, pd_12m, lgd, ead, ecl_weighted |
| Text | Synthetic data. Educational ECL demonstrator. |

Select **2026-09-30** on the date slicer. To display the whole history in the trend, use Edit interactions and disable the single-date slicer's effect on that trend. Keep product and stage interactions active. Cards and the top-loss table should still receive the selected reporting date.

Set a Top N filter of 10 for the contract table using ECL Weighted PLN. Do not rank by PD and label the table as highest monetary loss.

## 6 Reconcile to the independently checked baseline

With all products/stages and date 2026-09-30:

| Measure | Expected |
|---|---:|
| Loan Count | 6,000 |
| EAD PLN | 240,431,995.01 |
| ECL Weighted PLN | 35,710,382.24 |
| ECL Base PLN | 33,457,505.16 |
| ECL Adverse PLN | 50,767,593.01 |
| Coverage Ratio | about 14.8526% |

Then select credit_card and Stage 2. Match amounts and contract count with the same date/product/stage in the HTML dashboard. In HTML, use the weighted scenario to compare with ECL Weighted PLN.

Use `sql/02_analysis.sql` for an additional database comparison.

## 7 Resolve common mismatches

| Symptom | Check |
|---|---|
| CSV appears as one column | CSV delimiter must be comma |
| Amounts become text or change scale | Numeric parsing culture en-US and decimal column type |
| Amounts look much larger than the baseline | More than one reporting date is included |
| Loan Count is 6,000 but EAD is inflated | DISTINCTCOUNT can hide multi-date balance aggregation |
| Trend shows one point | Disable the single-date slicer's interaction with the trend |
| Measures fail to parse | Query name must be FactECL; create definitions separately; distinguish table from measure |
| PD differs from the HTML card | Exclude Stage 3 and use EAD weighting |

## 8 Save the actual report

Save as `Credit_Risk_Lab.pbix` only after building and validating it. Record Power BI Desktop version, source refresh date and your reconciliation results in your own notes. No placeholder PBIX is provided.

Only then add completed Power BI work to the portfolio description. Until then, describe this repository as a Python/SQL project with an HTML dashboard and Power BI preparation materials.
