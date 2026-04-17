"""Giving Matters pipeline step.

Per spec_updates_2.md §3.3:

1. Returns None immediately when ``enabled: false`` in project.yml.
2. Returns None gracefully if the S3 key does not exist (data not yet
   received from CFMT).
3. Otherwise loads the CSV, validates required columns, geocodes addresses
   via Nominatim (with a local/S3 cache), validates coordinates fall within
   the Nashville MSA bounding box, and writes
   ``data/points/giving_matters.geojson``.

Supports both S3 (production) and local mock CSV (development) loading,
mirroring the pattern in :mod:`pipeline.process_partners`.
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

# Nashville MSA bounding box — generous, covers all 14 OMB counties.
MSA_BBOX = {
    "min_lat": 35.40,
    "max_lat": 36.75,
    "min_lon": -87.80,
    "max_lon": -85.75,
}

OUTPUT_GEOJSON = Path("data/points/giving_matters.geojson")
DEFAULT_LOCAL_CSV = "giving_matters.csv"
DEFAULT_LOCAL_CACHE = "giving_matters_geocode_cache.csv"


def _validate_msa_coords(lat: float, lon: float) -> bool:
    """Return True if (lat, lon) falls inside the Nashville MSA bbox."""
    return (
        MSA_BBOX["min_lat"] <= lat <= MSA_BBOX["max_lat"]
        and MSA_BBOX["min_lon"] <= lon <= MSA_BBOX["max_lon"]
    )


def _load_csv(
    source_config: dict[str, Any],
    use_mock: bool,
    mock_dir: str,
) -> pd.DataFrame | None:
    """Load the Giving Matters CSV from S3 or the local mock directory."""
    if use_mock:
        path = os.path.join(mock_dir, DEFAULT_LOCAL_CSV)
        if not os.path.exists(path):
            logger.warning("Mock Giving Matters CSV not found at %s — skipping", path)
            return None
        logger.info("Loading Giving Matters data from %s", path)
        return pd.read_csv(path)

    bucket = source_config.get("s3_bucket")
    s3_key = source_config.get("s3_key")
    if not bucket or not s3_key:
        logger.warning("giving_matters: missing s3_bucket or s3_key — skipping")
        return None

    s3 = boto3.client("s3")
    logger.info("Loading Giving Matters data from s3://%s/%s", bucket, s3_key)
    try:
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404", "NoSuchBucket"}:
            logger.warning(
                "Giving Matters data not yet available at s3://%s/%s — skipping",
                bucket, s3_key,
            )
            return None
        logger.error("Failed to load Giving Matters data: %s", exc)
        return None
    except BotoCoreError as exc:
        logger.error("Failed to load Giving Matters data: %s", exc)
        return None

    return pd.read_csv(io.BytesIO(obj["Body"].read()), low_memory=False)


def _load_geocode_cache(
    source_config: dict[str, Any],
    use_mock: bool,
    mock_dir: str,
) -> pd.DataFrame:
    """Load the geocode cache from S3 or local mock directory."""
    columns = ["address", "latitude", "longitude"]
    if use_mock:
        path = os.path.join(mock_dir, DEFAULT_LOCAL_CACHE)
        if os.path.exists(path):
            return pd.read_csv(path)
        return pd.DataFrame(columns=columns)

    bucket = source_config.get("s3_bucket")
    key = source_config.get("geocode_cache_key")
    if not bucket or not key:
        return pd.DataFrame(columns=columns)
    try:
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        return pd.read_csv(io.BytesIO(obj["Body"].read()))
    except (ClientError, BotoCoreError, pd.errors.ParserError) as exc:
        logger.info("No existing Giving Matters geocode cache: %s", exc)
        return pd.DataFrame(columns=columns)


def _save_geocode_cache(
    cache_df: pd.DataFrame,
    source_config: dict[str, Any],
    use_mock: bool,
    mock_dir: str,
) -> None:
    """Persist the geocode cache. S3 in production, local file in mock mode."""
    if use_mock:
        Path(mock_dir).mkdir(parents=True, exist_ok=True)
        path = os.path.join(mock_dir, DEFAULT_LOCAL_CACHE)
        cache_df.to_csv(path, index=False)
        logger.info("Geocode cache saved to %s", path)
        return

    bucket = source_config.get("s3_bucket")
    key = source_config.get("geocode_cache_key")
    if not bucket or not key:
        logger.warning("No S3 target for Giving Matters cache — skipping save")
        return
    try:
        s3 = boto3.client("s3")
        buffer = io.StringIO()
        cache_df.to_csv(buffer, index=False)
        s3.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue().encode("utf-8"))
        logger.info("Geocode cache saved to s3://%s/%s", bucket, key)
    except (ClientError, BotoCoreError) as exc:
        logger.warning("Failed to write Giving Matters geocode cache to S3: %s", exc)


def _build_query(row: pd.Series) -> str | None:
    """Build a Nominatim query string from a row.

    Uses the full ``address`` column when available, appending city/state
    when the address lacks them. Falls back to ``city, county, TN`` for
    P.O. Box entries with no street address.
    """
    address = str(row.get("address") or "").strip()
    city = str(row.get("city") or "").strip()
    county = str(row.get("county") or "").strip()
    state = str(row.get("state") or "Tennessee").strip() or "Tennessee"

    is_po_box = address.upper().startswith(("P.O.", "PO BOX", "P O BOX"))

    if address and not is_po_box:
        # Some addresses include city/state ("333 Welshwood Dr, Nashville, TN");
        # others are bare ("306 Jackson St"). Append any context tokens that
        # aren't already present so Nominatim can resolve bare street names.
        addr_upper = address.upper()
        suffix_parts: list[str] = []
        if city and city.upper() not in addr_upper:
            suffix_parts.append(city)
        if "TN" not in addr_upper and "TENNESSEE" not in addr_upper:
            suffix_parts.append(state)
        if "USA" not in addr_upper and "UNITED STATES" not in addr_upper:
            suffix_parts.append("USA")
        if suffix_parts:
            return f"{address}, " + ", ".join(suffix_parts)
        return address

    # P.O. Box or missing address — fall back to city-level geocoding.
    parts = [p for p in (city, f"{county} County" if county else "", state, "USA") if p]
    return ", ".join(parts) if parts else None


def _geocode_rows(
    df: pd.DataFrame,
    source_config: dict[str, Any],
    use_mock: bool,
    mock_dir: str,
) -> pd.DataFrame:
    """Geocode each row via Nominatim with cache. Returns df with lat/lon/status."""
    geolocator = Nominatim(user_agent="nfp_food_insecurity_map_giving_matters")
    cache_df = _load_geocode_cache(source_config, use_mock, mock_dir)

    cache_lookup: dict[str, tuple[float, float]] = {}
    for _, row in cache_df.iterrows():
        addr = str(row.get("address", ""))
        lat = row.get("latitude")
        lon = row.get("longitude")
        if addr and pd.notna(lat) and pd.notna(lon):
            cache_lookup[addr] = (float(lat), float(lon))

    new_cache: list[dict] = []
    latitudes: list[float] = []
    longitudes: list[float] = []
    statuses: list[str] = []
    success = 0
    failed = 0
    nan = float("nan")

    total = len(df)
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        query = _build_query(row)
        if not query:
            latitudes.append(nan)
            longitudes.append(nan)
            statuses.append("failed")
            failed += 1
            continue

        if query in cache_lookup:
            lat, lon = cache_lookup[query]
            if _validate_msa_coords(lat, lon):
                latitudes.append(lat)
                longitudes.append(lon)
                statuses.append("success")
                success += 1
            else:
                latitudes.append(nan)
                longitudes.append(nan)
                statuses.append("failed")
                failed += 1
            continue

        try:
            time.sleep(1.0)  # Nominatim rate limit: 1 req/sec
            location = geolocator.geocode(query, timeout=10)
        except (GeocoderTimedOut, GeocoderUnavailable, GeocoderServiceError,
                ValueError) as exc:
            logger.warning("Geocoding failed for '%s': %s", query, exc)
            latitudes.append(nan)
            longitudes.append(nan)
            statuses.append("failed")
            failed += 1
            continue

        if location is None:
            latitudes.append(nan)
            longitudes.append(nan)
            statuses.append("failed")
            failed += 1
            continue

        lat, lon = float(location.latitude), float(location.longitude)
        if not _validate_msa_coords(lat, lon):
            latitudes.append(nan)
            longitudes.append(nan)
            statuses.append("failed")
            failed += 1
            continue

        cache_lookup[query] = (lat, lon)
        new_cache.append({"address": query, "latitude": lat, "longitude": lon})
        latitudes.append(lat)
        longitudes.append(lon)
        statuses.append("success")
        success += 1

        if i % 50 == 0 or i == total:
            logger.info(
                "Giving Matters geocoding: %d/%d (%d succeeded, %d failed)",
                i, total, success, failed,
            )

    df = df.copy()
    df["latitude"] = latitudes
    df["longitude"] = longitudes
    df["geocode_status"] = statuses

    if new_cache:
        updated = pd.concat(
            [cache_df, pd.DataFrame(new_cache)], ignore_index=True
        ).drop_duplicates(subset=["address"], keep="last")
        _save_geocode_cache(updated, source_config, use_mock, mock_dir)

    logger.info(
        "Giving Matters: %d/%d geocoded successfully (%d failed)",
        success, total, failed,
    )
    return df


def _to_geojson(df: pd.DataFrame, output_path: Path) -> int:
    """Convert a geocoded DataFrame to GeoJSON and save. Returns feature count."""
    features = []
    for _, row in df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")
        if pd.isna(lat) or pd.isna(lon):
            continue
        props = {
            "name": str(row.get("partner_name") or "").strip(),
            "address": str(row.get("address") or "").strip(),
            "category": str(row.get("partner_type") or "other").strip(),
            "county": str(row.get("county") or "").strip(),
        }
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": props,
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)
    logger.info("Wrote %d Giving Matters features to %s", len(features), output_path)
    return len(features)


def process_giving_matters(
    source_config: dict[str, Any],
    use_mock: bool = False,
    mock_dir: str = "data/mock/",
) -> pd.DataFrame | None:
    """Run the Giving Matters pipeline step.

    Args:
        source_config: ``data_sources.giving_matters`` from project.yml.
        use_mock: When True, load from ``data/mock/giving_matters.csv`` instead of S3.
        mock_dir: Mock data directory (default ``data/mock/``).

    Returns:
        DataFrame of geocoded organizations, or None when the step was
        skipped (disabled in config, missing S3 key, schema mismatch, etc.).
    """
    if not source_config.get("enabled", False):
        logger.info("Giving Matters integration is disabled — skipping")
        return None

    df = _load_csv(source_config, use_mock, mock_dir)
    if df is None:
        return None
    logger.info("Loaded %d Giving Matters rows", len(df))

    # Column mapping: required_columns in project.yml maps canonical names
    # (name_column, address_column, category_column) to the CSV's own
    # column names. We rename to canonical (partner_name/address/partner_type)
    # for internal processing.
    required = source_config.get("required_columns", {}) or {}
    missing = [c for c in required.values() if c and c not in df.columns]
    if missing:
        logger.error("Giving Matters: missing required columns: %s", missing)
        return None

    rename_map: dict[str, str] = {}
    if required.get("name_column"):
        rename_map[required["name_column"]] = "partner_name"
    if required.get("address_column"):
        rename_map[required["address_column"]] = "address"
    if required.get("category_column"):
        rename_map[required["category_column"]] = "partner_type"
    if rename_map:
        df = df.rename(columns=rename_map)

    for col in ("partner_name", "address", "partner_type", "city", "county", "state"):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()

    df = _geocode_rows(df, source_config, use_mock, mock_dir)
    _to_geojson(df, OUTPUT_GEOJSON)
    return df
