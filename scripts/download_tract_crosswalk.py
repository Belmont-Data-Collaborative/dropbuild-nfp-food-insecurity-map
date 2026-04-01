"""Download Census Bureau 2010-to-2020 Tract Relationship File and upload to S3.

Standalone script — no imports from src/.

Downloads the national pipe-delimited relationship file, filters to
Tennessee (state FIPS 47), and uploads to S3 as CSV.

Usage:
    python scripts/download_tract_crosswalk.py
"""
from __future__ import annotations

import io
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

# Census Bureau 2020-to-2010 Census Tract Relationship File
# National pipe-delimited file inside a ZIP archive
CROSSWALK_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_natl.txt"

REQUIRED_COLUMNS = [
    "GEOID_TRACT_20", "GEOID_TRACT_10",
    "AREALAND_PART", "AREALAND_TRACT_20", "AREALAND_TRACT_10",
]


def load_config() -> dict:
    config_path = os.environ.get("PROJECT_CONFIG", "project.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    config = load_config()
    lila_cfg = config["data_sources"]["usda_lila"]
    bucket = lila_cfg["s3_bucket"]
    s3_key = lila_cfg["crosswalk_key"]
    state_fips = config["geography"]["state_fips"]

    print(f"Downloading Census tract crosswalk from {CROSSWALK_URL}...")
    resp = requests.get(CROSSWALK_URL, timeout=180)
    resp.raise_for_status()
    print(f"  Downloaded {len(resp.content):,} bytes")

    # Parse pipe-delimited file
    df = pd.read_csv(io.BytesIO(resp.content), sep="|", low_memory=False)
    print(f"  Loaded {len(df):,} rows (national)")

    # Validate columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        print(f"  ERROR: Missing expected columns: {missing}")
        print(f"  Available columns: {sorted(df.columns.tolist())}")
        sys.exit(1)

    # Filter to Tennessee using the 2020 tract GEOID
    df["GEOID_TRACT_20"] = df["GEOID_TRACT_20"].astype(str).str.zfill(11)
    df["GEOID_TRACT_10"] = df["GEOID_TRACT_10"].astype(str).str.zfill(11)
    tn_mask = df["GEOID_TRACT_20"].str[:2] == state_fips
    df_tn = df[tn_mask].copy()
    print(f"  Filtered to state {state_fips}: {len(df_tn):,} rows")

    if len(df_tn) == 0:
        print("  ERROR: No rows for Tennessee. Check state_fips config.")
        sys.exit(1)

    # Save locally as CSV for manual S3 upload
    local_dir = Path("data/source/usda_lila")
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / "tract_2010_to_2020_tn.csv"
    df_tn.to_csv(local_path, index=False)
    print(f"  Saved locally to {local_path}")

    # Log provenance and manual upload instructions
    now = datetime.now(timezone.utc).isoformat()
    print(f"\nProvenance:")
    print(f"  Source URL: {CROSSWALK_URL}")
    print(f"  Download date: {now}")
    print(f"  Local path: {local_path}")
    print(f"  Rows (TN only): {len(df_tn):,}")
    print(f"  Unique 2020 tracts: {df_tn['GEOID_TRACT_20'].nunique():,}")
    print(f"  Unique 2010 tracts: {df_tn['GEOID_TRACT_10'].nunique():,}")
    print(f"\nManual S3 upload command:")
    print(f"  aws s3 cp {local_path} s3://{bucket}/{s3_key}")


if __name__ == "__main__":
    main()
