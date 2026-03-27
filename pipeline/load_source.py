"""Generic S3/local data loader for pipeline steps.

Handles S3 prefix-based discovery, local loading, GEOID normalization,
county-level filtering, Census sentinel replacement, and Parquet output.
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any

import boto3
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def get_s3_client() -> boto3.client:
    """Create a boto3 S3 client."""
    return boto3.client("s3")


def load_from_s3_prefix(
    bucket: str,
    prefix: str,
) -> pd.DataFrame:
    """Discover and load the latest CSV/Parquet file under an S3 prefix.

    Args:
        bucket: S3 bucket name.
        prefix: S3 key prefix to search under.

    Returns:
        DataFrame loaded from the discovered file.

    Raises:
        FileNotFoundError: If no files found under prefix.
    """
    client = get_s3_client()
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    contents = response.get("Contents", [])

    if not contents:
        raise FileNotFoundError(
            f"No files found under s3://{bucket}/{prefix}"
        )

    # Sort by last modified, pick newest
    contents.sort(key=lambda x: x["LastModified"], reverse=True)

    for obj in contents:
        key = obj["Key"]
        if key.endswith(".parquet"):
            return _load_parquet_from_s3(client, bucket, key)
        if key.endswith(".csv"):
            return _load_csv_from_s3(client, bucket, key)

    raise FileNotFoundError(
        f"No CSV or Parquet files found under s3://{bucket}/{prefix}"
    )


def load_from_s3_key(bucket: str, key: str) -> pd.DataFrame:
    """Load a specific file from S3 by key."""
    client = get_s3_client()
    if key.endswith(".parquet"):
        return _load_parquet_from_s3(client, bucket, key)
    return _load_csv_from_s3(client, bucket, key)


def load_from_local(path: str) -> pd.DataFrame:
    """Load a CSV or Parquet file from local disk."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if p.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _load_csv_from_s3(
    client: boto3.client, bucket: str, key: str
) -> pd.DataFrame:
    """Load CSV from S3."""
    logger.info("Loading CSV from s3://%s/%s", bucket, key)
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    return pd.read_csv(io.BytesIO(body))


def _load_parquet_from_s3(
    client: boto3.client, bucket: str, key: str
) -> pd.DataFrame:
    """Load Parquet from S3."""
    logger.info("Loading Parquet from s3://%s/%s", bucket, key)
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    return pd.read_parquet(io.BytesIO(body))


def normalize_geoid(df: pd.DataFrame, geoid_col: str = "GEOID") -> pd.DataFrame:
    """Normalize GEOID column to 11-character zero-filled strings."""
    if geoid_col in df.columns:
        df[geoid_col] = df[geoid_col].astype(str).str.zfill(11)
    return df


def filter_by_county(
    df: pd.DataFrame,
    state_fips: str,
    county_fips: str,
    geoid_col: str = "GEOID",
) -> pd.DataFrame:
    """Filter DataFrame to rows matching state+county FIPS prefix."""
    prefix = state_fips + county_fips
    mask = df[geoid_col].astype(str).str.startswith(prefix)
    filtered = df[mask].copy()
    logger.info(
        "Filtered %d -> %d rows for county FIPS %s",
        len(df), len(filtered), prefix,
    )
    return filtered


def replace_census_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    """Replace Census sentinel values (negative numbers) with NaN."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df.loc[df[col] < 0, col] = np.nan
    return df


def apply_filters(
    df: pd.DataFrame, filters: list[dict[str, Any]]
) -> pd.DataFrame:
    """Apply row-level filters from config."""
    for f in filters:
        col = f["column"]
        val = f["value"]
        if col in df.columns:
            df = df[df[col] == val].copy()
            logger.info("Filtered on %s == %s: %d rows", col, val, len(df))
    return df


def save_parquet(df: pd.DataFrame, output_path: str) -> None:
    """Save DataFrame as Parquet file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Saved %d rows to %s", len(df), output_path)


def process_data_source(
    source_key: str,
    source_config: dict[str, Any],
    geography: dict[str, Any],
    granularity: str,
) -> pd.DataFrame | None:
    """Process a single data source for a given granularity.

    Loads from S3, normalizes GEOIDs, filters by county, replaces sentinels,
    applies row-level filters, and saves as Parquet.

    Args:
        source_key: Config key (e.g., 'census_acs').
        source_config: Source configuration dict from project.yml.
        geography: Geography configuration dict.
        granularity: 'tract' or 'zip'.

    Returns:
        Processed DataFrame, or None if loading fails.
    """
    bucket = source_config["s3_bucket"]
    prefix = source_config["s3_prefix"].get(granularity)
    if not prefix:
        logger.warning("No prefix for %s/%s", source_key, granularity)
        return None

    geoid_col = source_config.get("geoid_column", "GEOID")
    output_prefix = source_config.get("output_prefix", source_key)

    try:
        df = load_from_s3_prefix(bucket, prefix)
    except FileNotFoundError:
        logger.error("No data found for %s/%s", source_key, granularity)
        return None

    # Rename geoid column to standard GEOID
    if geoid_col != "GEOID" and geoid_col in df.columns:
        df = df.rename(columns={geoid_col: "GEOID"})

    df = normalize_geoid(df)
    df = filter_by_county(
        df, geography["state_fips"], geography["county_fips"]
    )
    df = replace_census_sentinels(df)

    # Apply any row-level filters
    filters = source_config.get("filters", [])
    if filters:
        df = apply_filters(df, filters)

    # Keep only GEOID + variable columns
    var_columns = [v["column"] for v in source_config.get("variables", [])]
    keep_cols = ["GEOID"] + [c for c in var_columns if c in df.columns]
    df = df[keep_cols].copy()

    output_path = f"data/choropleth/{output_prefix}_{granularity}_data.parquet"
    save_parquet(df, output_path)

    return df
