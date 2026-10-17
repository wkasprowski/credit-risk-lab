"""Rebuild and verify the baseline without requiring an external data source."""
import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(label, args, timeout=120):
    print(label, flush=True)
    completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    if completed.returncode:
        print(completed.stdout + completed.stderr, flush=True)
        raise RuntimeError(f"{label} failed with exit code {completed.returncode}")
    return completed.stdout + completed.stderr


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(browser=False):
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    pipeline_log = command("Rebuilding all synthetic data, SQL, models and reports",
                           [sys.executable, "run_pipeline.py"])
    (reports / "pipeline-log.txt").write_text(pipeline_log, encoding="utf-8")
    raw = ROOT / "data" / "raw"
    first_hashes = {p.name: digest(p) for p in sorted(raw.glob("*.csv"))}

    # Check the generator independently by recreating its inputs from seed 42.
    sys.path.insert(0, str(ROOT))
    from src.synthetic import generate
    config = json.loads((ROOT / "config.json").read_text())
    print("Checking deterministic generation", flush=True)
    generate(ROOT, config)
    second_hashes = {p.name: digest(p) for p in sorted(raw.glob("*.csv"))}
    assert first_hashes == second_hashes, "Generated CSVs are not deterministic"

    test_log = command("Running Python financial and integration tests",
                       [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    assert "Ran 26 tests" in test_log and "\nOK\n" in test_log
    (reports / "python-tests.txt").write_text(test_log, encoding="utf-8")
    metrics = json.loads((ROOT / "outputs" / "metrics.json").read_text())
    totals, pd_metrics, lgd = metrics["totals"], metrics["pd"]["full_calibrated"], metrics["lgd"]
    expectations = {
        "ead_pln": 240431995.01346758,
        "ecl_weighted_pln": 35710382.24321605,
        "ecl_base_pln": 33457505.155268215,
        "ecl_adverse_pln": 50767593.01376754,
    }
    for field, expected in expectations.items():
        assert math.isclose(totals[field], expected, rel_tol=0, abs_tol=0.01), field
    assert math.isclose(pd_metrics["roc_auc"], 0.7425854530668551, abs_tol=1e-10)
    assert math.isclose(pd_metrics["brier"], 0.06396098998129329, abs_tol=1e-10)
    assert math.isclose(lgd["mae"], 0.05483993728395957, abs_tol=1e-10)

    print("Checking SQLite and independent monetary totals", flush=True)
    db = ROOT / "outputs" / "credit_risk.sqlite"
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
        rows, months, loans = conn.execute(
            "SELECT COUNT(*),COUNT(DISTINCT report_date),COUNT(DISTINCT loan_id) FROM fact_ecl"
        ).fetchone()
        assert (rows, months, loans) == (72000, 12, 6000)
        count, ead, ecl = conn.execute(
            "SELECT COUNT(*),SUM(ead),SUM(ecl_weighted) FROM fact_ecl WHERE report_date=?",
            (config["report_date"],)
        ).fetchone()
        assert count == 6000
        assert abs(ecl - totals["ecl_weighted_pln"]) < 1e-6
        assert abs(ead - totals["ead_pln"]) < 1e-6

    command("Exporting independent SQL dashboard references",
            [sys.executable, "tests/export_dashboard_cases.py"])
    node = shutil.which("node")
    dashboard_status = {"status": "not run", "reason": "Node.js is not installed"}
    if node:
        command("Checking dashboard logic against SQL", [node, "tests/check_dashboard.cjs"])
        dashboard_status = json.loads((ROOT / "outputs" / "dashboard_checks.json").read_text())
        assert dashboard_status["independent_sql_filter_cases"] == 768
    if browser:
        if not node:
            raise RuntimeError("--browser requires Node.js and optional Playwright dependencies")
        command("Checking the dashboard in real Chromium",
                [node, "tests/check_dashboard_browser.cjs"], timeout=150)
        browser_status = json.loads((ROOT / "outputs" / "browser_checks.json").read_text())
    else:
        browser_status = {"status": "not requested; run with --browser"}

    provenance = json.loads((ROOT / "docs" / "PROVENANCE.json").read_text())
    core = {name: digest(ROOT / name) for name in provenance["original_core_sha256"]}
    assert core == provenance["original_core_sha256"], "A preserved numerical/SQL source has changed"
    command("Exporting the small synthetic inspection sample",
            [sys.executable, "scripts/export_samples.py"])
    pip_check = command("Checking dependency consistency", [sys.executable, "-m", "pip", "check"])
    environment = command("Recording installed dependency versions", [sys.executable, "-m", "pip", "freeze"])
    (reports / "environment.txt").write_text(environment, encoding="utf-8")
    (reports / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    result = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "isolated_python_environment": sys.prefix != sys.base_prefix,
        "pip_check": pip_check.strip(),
        "python_tests": 26,
        "database_integrity": integrity,
        "fact_rows": rows, "report_dates": months, "contracts": loans,
        "latest_ead_sql": ead, "latest_ecl_sql": ecl,
        "latest_ecl_python": totals["ecl_weighted_pln"],
        "pd_roc_auc": pd_metrics["roc_auc"], "pd_brier": pd_metrics["brier"],
        "lgd_mae": lgd["mae"],
        "generator_deterministic": first_hashes == second_hashes,
        "raw_csv_sha256": second_hashes,
        "core_source_unchanged": True,
        "core_source_sha256": core,
        "dashboard_logic": dashboard_status,
        "browser": browser_status,
        "power_bi_desktop_tested": False,
        "windows_execution_tested": False,
        "synthetic_data_only": True,
    }
    (reports / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"VERIFIED: {rows:,} rows, ECL {ecl:,.2f} PLN, 26 Python tests", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true", help="Also run optional Playwright browser tests")
    args = parser.parse_args()
    verify(args.browser)
