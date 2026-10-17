// Name this query FactECL. Change only ProjectRoot to the extracted folder.
// CSV uses a dot decimal separator; parsing culture MUST remain en-US.
let
    ProjectRoot = "SET_PROJECT_FOLDER",
    Source = Csv.Document(
        File.Contents(ProjectRoot & "\outputs\fact_ecl.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Types = Table.TransformColumnTypes(Headers, {
        {"loan_id", type text}, {"customer_id", type text},
        {"report_date", type date}, {"product", type text},
        {"stage", Int64.Type}, {"stage_reason", type text},
        {"balance", type number}, {"undrawn", type number},
        {"eir", type number}, {"dpd", Int64.Type},
        {"pd_12m", type number}, {"pd_lifetime", type number},
        {"origination_pd_12m", type number}, {"lgd", type number},
        {"ead", type number}, {"ecl_weighted", type number},
        {"ecl_base", type number}, {"ecl_optimistic", type number},
        {"ecl_adverse", type number}, {"coverage_ratio", type number},
        {"remaining_months", Int64.Type}, {"sicr_pd_ratio", type number},
        {"sicr_absolute_increase", type number}
    }, "en-US")
in
    Types
