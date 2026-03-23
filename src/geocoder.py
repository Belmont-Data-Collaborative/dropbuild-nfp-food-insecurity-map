from __future__ import annotations

import io
import logging
import os
import time

import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim

from src import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class GeocodingError(Exception):
    """Fatal initialization errors only. NEVER raised for individual address failures."""


# ---------------------------------------------------------------------------
# Geolocator
# ---------------------------------------------------------------------------
@st.cache_resource
def get_nominatim_geolocator() -> Nominatim:
    """Create and cache a Nominatim geolocator instance."""
    return Nominatim(user_agent="nfp_food_insecurity_map")


# ---------------------------------------------------------------------------
# Cache loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_geocode_cache(bucket: str | None = None) -> pd.DataFrame:
    """Load geocode cache from S3 or local mock file.
    Returns empty DataFrame if cache does not exist."""
    if config.USE_MOCK_DATA:
        cache_path = os.path.join(
            config.MOCK_DATA_DIR, "mock_geocode_cache.csv"
        )
        if os.path.exists(cache_path):
            try:
                return pd.read_csv(cache_path)
            except Exception:
                pass
        return pd.DataFrame(
            columns=["address", "latitude", "longitude"]
        )

    # S3 mode
    effective_bucket = bucket or config.AWS_BUCKET_NAME
    try:
        from src.data_loader import get_s3_client

        client = get_s3_client()
        response = client.get_object(
            Bucket=effective_bucket, Key=config.S3_GEOCODE_CACHE_KEY
        )
        body = response["Body"].read()
        return pd.read_csv(io.BytesIO(body))
    except Exception:
        return pd.DataFrame(
            columns=["address", "latitude", "longitude"]
        )


def _save_geocode_cache(cache_df: pd.DataFrame) -> None:
    """Write updated geocode cache to S3. Skip in mock mode.
    Failures are logged — app continues."""
    if config.USE_MOCK_DATA:
        return
    try:
        from src.data_loader import get_s3_client

        client = get_s3_client()
        csv_buffer = io.StringIO()
        cache_df.to_csv(csv_buffer, index=False)
        client.put_object(
            Bucket=config.AWS_BUCKET_NAME,
            Key=config.S3_GEOCODE_CACHE_KEY,
            Body=csv_buffer.getvalue().encode("utf-8"),
        )
    except Exception as exc:
        logger.warning("Failed to write geocode cache to S3: %s", exc)


# ---------------------------------------------------------------------------
# Main geocoding function
# ---------------------------------------------------------------------------
@st.cache_data
def geocode_partners(partners_df: pd.DataFrame) -> pd.DataFrame:
    """Geocode partner addresses.

    Returns DataFrame with columns:
        partner_name, address, latitude, longitude, geocode_status.

    - Checks cache first for each address.
    - Calls Nominatim for uncached addresses (max 1 req/sec).
    - Appends ', Davidson County, TN, USA' to each address query.
    - NEVER raises for individual address failures.
    - Writes updated cache to S3 (skipped in mock mode).
    """
    geolocator = get_nominatim_geolocator()
    cache_df = load_geocode_cache()

    # Build address -> (lat, lon) lookup from cache
    cache_lookup: dict[str, tuple[float, float]] = {}
    for _, row in cache_df.iterrows():
        addr = str(row.get("address", ""))
        lat = row.get("latitude")
        lon = row.get("longitude")
        if addr and pd.notna(lat) and pd.notna(lon):
            cache_lookup[addr] = (float(lat), float(lon))

    results: list[dict] = []
    new_cache_entries: list[dict] = []

    for _, partner in partners_df.iterrows():
        name = partner.get("partner_name", "")
        address = partner.get("address", "")

        # Blank/NaN address — skip geocoding
        if pd.isna(address) or str(address).strip() == "":
            results.append(
                {
                    "partner_name": name,
                    "address": address if pd.notna(address) else "",
                    "latitude": float("nan"),
                    "longitude": float("nan"),
                    "geocode_status": "failed",
                }
            )
            continue

        address_str = str(address).strip()

        # Check cache
        if address_str in cache_lookup:
            lat, lon = cache_lookup[address_str]
            results.append(
                {
                    "partner_name": name,
                    "address": address_str,
                    "latitude": lat,
                    "longitude": lon,
                    "geocode_status": "success",
                }
            )
            continue

        # Nominatim geocode — never raise on individual failures
        try:
            query = f"{address_str}, Davidson County, TN, USA"
            time.sleep(1)  # Rate limit: max 1 req/sec
            location = geolocator.geocode(query, timeout=10)
            if location is not None:
                lat = location.latitude
                lon = location.longitude
                results.append(
                    {
                        "partner_name": name,
                        "address": address_str,
                        "latitude": lat,
                        "longitude": lon,
                        "geocode_status": "success",
                    }
                )
                cache_lookup[address_str] = (lat, lon)
                new_cache_entries.append(
                    {
                        "address": address_str,
                        "latitude": lat,
                        "longitude": lon,
                    }
                )
            else:
                results.append(
                    {
                        "partner_name": name,
                        "address": address_str,
                        "latitude": float("nan"),
                        "longitude": float("nan"),
                        "geocode_status": "failed",
                    }
                )
        except Exception as exc:
            logger.warning(
                "Geocoding failed for '%s': %s", address_str, exc
            )
            results.append(
                {
                    "partner_name": name,
                    "address": address_str,
                    "latitude": float("nan"),
                    "longitude": float("nan"),
                    "geocode_status": "failed",
                }
            )

    # Update cache with new entries
    if new_cache_entries:
        new_df = pd.DataFrame(new_cache_entries)
        updated_cache = pd.concat([cache_df, new_df], ignore_index=True)
        _save_geocode_cache(updated_cache)

    return pd.DataFrame(results)
