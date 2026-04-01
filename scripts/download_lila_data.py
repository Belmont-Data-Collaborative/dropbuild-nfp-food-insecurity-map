"""Download USDA Food Access Research Atlas (LILA) data and upload to S3.

Standalone script — no imports from src/.

Usage:
    python scripts/download_lila_data.py
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd
import requests
import yaml

# USDA ERS Food Access Research Atlas download URL
# Data is published as Excel (.xlsx). We convert to CSV for S3 upload.
LILA_URL = "https://www.ers.usda.gov/media/5626/food-access-research-atlas-data-download-2019.xlsx"

EXPECTED_COLUMNS = [
    "CensusTract", "LILATracts_1And10", "LILATracts_halfAnd10",
    "LILATracts_1And20", "lapop1", "lalowi1", "PovertyRate",
    "MedianFamilyIncome",
]


def load_config() -> dict:
    config_path = os.environ.get("PROJECT_CONFIG", "project.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    config = load_config()
    lila_cfg = config["data_sources"]["usda_lila"]
    bucket = lila_cfg["s3_bucket"]
    s3_key = lila_cfg["source_key"]

    print(f"Downloading LILA data from {LILA_URL}...")
    resp = requests.get(LILA_URL, timeout=180)
    resp.raise_for_status()
    print(f"  Downloaded {len(resp.content):,} bytes")

    # Read Excel — the data is in the first sheet or a sheet named
    # "Food Access Research Atlas"
    xls = pd.ExcelFile(io.BytesIO(resp.content))
    print(f"  Sheet names: {xls.sheet_names}")
    # Use the sheet with the most rows (the data sheet, not variable defs)
    best_sheet = None
    best_rows = 0
    for sheet in xls.sheet_names:
        df_tmp = pd.read_excel(xls, sheet_name=sheet, nrows=5)
        if "CensusTract" in df_tmp.columns:
            best_sheet = sheet
            break
        if len(df_tmp.columns) > best_rows:
            best_rows = len(df_tmp.columns)
            best_sheet = sheet
    if best_sheet is None:
        best_sheet = xls.sheet_names[0]

    print(f"  Reading sheet: {best_sheet}")
    df = pd.read_excel(xls, sheet_name=best_sheet)
    print(f"  Loaded {len(df):,} rows, {len(df.columns)} columns")

    # Validate expected columns
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        print(f"  WARNING: Missing expected columns: {missing}")
        print(f"  Available columns (first 30): {sorted(df.columns.tolist())[:30]}")
        # Don't exit — column names may differ slightly between vintages
        # (see spec open_questions: "Exact LILA CSV column names may differ")

    found = [c for c in EXPECTED_COLUMNS if c in df.columns]
    print(f"  Found {len(found)}/{len(EXPECTED_COLUMNS)} expected columns: {found}")

    # Save locally as CSV for manual S3 upload
    local_dir = Path("data/source/usda_lila")
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / "food_access_research_atlas.csv"
    df.to_csv(local_path, index=False)
    print(f"  Saved locally to {local_path}")

    # Log provenance and manual upload instructions
    now = datetime.now(timezone.utc).isoformat()
    print(f"\nProvenance:")
    print(f"  Source URL: {LILA_URL}")
    print(f"  Download date: {now}")
    print(f"  Local path: {local_path}")
    print(f"  Rows: {len(df):,}")
    print(f"\nManual S3 upload command:")
    print(f"  aws s3 cp {local_path} s3://{bucket}/{s3_key}")


if __name__ == "__main__":
    main()
