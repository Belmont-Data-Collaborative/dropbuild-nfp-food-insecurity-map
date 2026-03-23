from __future__ import annotations

import io
import json
import os
from pathlib import Path

import boto3
import pandas as pd
import streamlit as st

from src import config


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class DataLoadError(Exception):
    """Raised when data cannot be loaded (S3 error, file missing)."""


class DataSchemaError(Exception):
    """Raised when loaded data is missing required columns."""


# ---------------------------------------------------------------------------
# S3 client
# ---------------------------------------------------------------------------
@st.cache_resource
def get_s3_client() -> boto3.client:
    """Create and cache a boto3 S3 client."""
    return boto3.client("s3")


# ---------------------------------------------------------------------------
# Low-level loaders
# ---------------------------------------------------------------------------
@st.cache_data
def load_csv_from_s3(bucket: str, key: str) -> pd.DataFrame:
    """Load a CSV from S3 into a DataFrame. Raises DataLoadError on failure."""
    try:
        client = get_s3_client()
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        return pd.read_csv(io.BytesIO(body))
    except Exception as exc:
        raise DataLoadError(
            f"Failed to load s3://{bucket}/{key}: {exc}"
        ) from exc


@st.cache_data
def load_csv_from_file(path: str) -> pd.DataFrame:
    """Load a CSV from local disk into a DataFrame. Raises DataLoadError on failure."""
    try:
        return pd.read_csv(path)
    except Exception as exc:
        raise DataLoadError(f"Failed to load file {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Helper: validate required columns
# ---------------------------------------------------------------------------
def _validate_columns(
    df: pd.DataFrame, required: list[str], source_name: str
) -> None:
    """Raise DataSchemaError if any required columns are missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataSchemaError(
            f"{source_name} is missing required columns: {missing}"
        )


# ---------------------------------------------------------------------------
# High-level loaders
# ---------------------------------------------------------------------------
@st.cache_data
def load_partners_data() -> pd.DataFrame:
    """Load partners CSV (from S3 or mock). Validates required columns."""
    if config.USE_MOCK_DATA:
        path = os.path.join(config.MOCK_DATA_DIR, "mock_nfp_partners.csv")
        df = load_csv_from_file(path)
    else:
        df = load_csv_from_s3(config.AWS_BUCKET_NAME, config.S3_PARTNERS_KEY)
    _validate_columns(df, config.PARTNERS_CSV_COLUMNS, "Partners CSV")
    return df


@st.cache_data
def load_census_data() -> pd.DataFrame:
    """Load census CSV (from S3 or mock). Normalizes GEOID with zfill(11)."""
    if config.USE_MOCK_DATA:
        path = os.path.join(
            config.MOCK_DATA_DIR, "mock_census_tract_data.csv"
        )
        df = load_csv_from_file(path)
    else:
        df = load_csv_from_s3(config.AWS_BUCKET_NAME, config.S3_CENSUS_KEY)
    _validate_columns(df, config.CENSUS_CSV_COLUMNS, "Census CSV")
    df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
    return df


@st.cache_data
def load_cdc_places_data() -> pd.DataFrame:
    """Load CDC PLACES CSV (from S3 or mock). Normalizes GEOID with zfill(11)."""
    if config.USE_MOCK_DATA:
        path = os.path.join(
            config.MOCK_DATA_DIR, "mock_cdc_places_data.csv"
        )
        df = load_csv_from_file(path)
    else:
        df = load_csv_from_s3(
            config.AWS_BUCKET_NAME, config.S3_CDC_PLACES_KEY
        )
    _validate_columns(df, config.CDC_PLACES_CSV_COLUMNS, "CDC PLACES CSV")
    df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
    return df


@st.cache_data
def load_geojson() -> dict:
    """Load GeoJSON from disk. Normalizes feature GEOID properties to 11 chars.
    Raises DataLoadError if file is missing."""
    geojson_path = Path(config.GEOJSON_PATH)
    if not geojson_path.exists():
        raise DataLoadError(
            f"GeoJSON file not found: {config.GEOJSON_PATH}"
        )
    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)
    except Exception as exc:
        raise DataLoadError(
            f"Failed to read GeoJSON: {exc}"
        ) from exc

    # Normalize GEOID properties to 11 characters
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        if "GEOID" in props and props["GEOID"] is not None:
            props["GEOID"] = str(props["GEOID"]).zfill(11)

    return geojson
