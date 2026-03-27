"""Generate mock Parquet files from existing mock CSVs for local development.

STANDALONE script — NO imports from src/ modules.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


def main() -> None:
    mock_dir = Path("data/mock")
    choropleth_dir = Path("data/choropleth")
    choropleth_dir.mkdir(parents=True, exist_ok=True)

    # Census ACS mock -> parquet (tract only for mock)
    census_path = mock_dir / "mock_census_tract_data.csv"
    if census_path.exists():
        df = pd.read_csv(census_path)
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)

        # Rename columns to match project.yml variable names
        rename_map = {
            "median_household_income": "DP03_0062E",
            "poverty_rate": "DP03_0119PE",
        }
        df_out = df[["GEOID"]].copy()
        for old_name, new_name in rename_map.items():
            if old_name in df.columns:
                df_out[new_name] = df[old_name]

        # Add a population column (mock)
        import numpy as np
        rng = np.random.default_rng(42)
        df_out["DP05_0001E"] = rng.integers(1000, 15000, size=len(df_out))

        df_out.to_parquet(choropleth_dir / "acs_tract_data.parquet", index=False)
        print(f"Saved {len(df_out)} rows to acs_tract_data.parquet")

        # Also create a zip-level version (just copy tract for mock)
        df_out.to_parquet(choropleth_dir / "acs_zipcode_data.parquet", index=False)
        print(f"Saved {len(df_out)} rows to acs_zipcode_data.parquet")
    else:
        print(f"WARNING: {census_path} not found")

    # CDC PLACES mock -> parquet
    cdc_path = mock_dir / "mock_cdc_places_data.csv"
    if cdc_path.exists():
        df = pd.read_csv(cdc_path)
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)

        df_out = df[["GEOID"]].copy()
        if "DIABETES_CrudePrev" in df.columns:
            df_out["DIABETES_CrudePrev"] = df["DIABETES_CrudePrev"]

        # Add mock hypertension and obesity columns
        rng = np.random.default_rng(43)
        df_out["HIGHBP_CrudePrev"] = np.round(rng.uniform(20, 45, size=len(df_out)), 1)
        df_out["OBESITY_CrudePrev"] = np.round(rng.uniform(25, 42, size=len(df_out)), 1)

        df_out.to_parquet(choropleth_dir / "health_lila_tract_data.parquet", index=False)
        print(f"Saved {len(df_out)} rows to health_lila_tract_data.parquet")

        df_out.to_parquet(choropleth_dir / "health_lila_zipcode_data.parquet", index=False)
        print(f"Saved {len(df_out)} rows to health_lila_zipcode_data.parquet")
    else:
        print(f"WARNING: {cdc_path} not found")

    print("\nSUCCESS: Mock parquet files generated")


if __name__ == "__main__":
    main()
