"""Geocoding module — used by the pipeline, not by the Streamlit app directly.

The app loads pre-geocoded GeoJSON from data/points/partners.geojson.
This module is kept for pipeline imports and backward compatibility.
"""
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


class GeocodingError(Exception):
    """Fatal initialization errors only. NEVER raised for individual address failures."""


@st.cache_resource
def get_nominatim_geolocator() -> Nominatim:
    """Create and cache a Nominatim geolocator instance."""
    return Nominatim(user_agent="nfp_food_insecurity_map")


@st.cache_data
def load_geocode_cache(bucket: str | None = None) -> pd.DataFrame:
    """Load geocode cache from local mock file.

    Returns empty DataFrame if cache does not exist.
    """
    if config.USE_MOCK_DATA:
        cache_path = os.path.join(
            config.MOCK_DATA_DIR, "mock_geocode_cache.csv"
        )
        if os.path.exists(cache_path):
            try:
                return pd.read_csv(cache_path)
            except Exception:
                pass
        return pd.DataFrame(columns=["address", "latitude", "longitude"])

    # Non-mock mode — return empty (pipeline handles S3 cache)
    return pd.DataFrame(columns=["address", "latitude", "longitude"])


@st.cache_data
def geocode_partners(partners_df: pd.DataFrame) -> pd.DataFrame:
    """Geocode partner addresses.

    Returns DataFrame with columns:
        partner_name, address, latitude, longitude, geocode_status.

    NEVER raises for individual address failures.
    """
    geolocator = get_nominatim_geolocator()
    cache_df = load_geocode_cache()

    cache_lookup: dict[str, tuple[float, float]] = {}
    for _, row in cache_df.iterrows():
        addr = str(row.get("address", ""))
        lat = row.get("latitude")
        lon = row.get("longitude")
        if addr and pd.notna(lat) and pd.notna(lon):
            cache_lookup[addr] = (float(lat), float(lon))

    results: list[dict] = []

    for _, partner in partners_df.iterrows():
        name = partner.get("partner_name", "")
        address = partner.get("address", "")

        if pd.isna(address) or str(address).strip() == "":
            results.append({
                "partner_name": name,
                "address": address if pd.notna(address) else "",
                "latitude": float("nan"),
                "longitude": float("nan"),
                "geocode_status": "failed",
            })
            continue

        address_str = str(address).strip()

        if address_str in cache_lookup:
            lat, lon = cache_lookup[address_str]
            results.append({
                "partner_name": name,
                "address": address_str,
                "latitude": lat,
                "longitude": lon,
                "geocode_status": "success",
            })
            continue

        try:
            query = f"{address_str}, Davidson County, TN, USA"
            time.sleep(1)
            location = geolocator.geocode(query, timeout=10)
            if location is not None:
                results.append({
                    "partner_name": name,
                    "address": address_str,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "geocode_status": "success",
                })
            else:
                results.append({
                    "partner_name": name,
                    "address": address_str,
                    "latitude": float("nan"),
                    "longitude": float("nan"),
                    "geocode_status": "failed",
                })
        except Exception as exc:
            logger.warning("Geocoding failed for '%s': %s", address_str, exc)
            results.append({
                "partner_name": name,
                "address": address_str,
                "latitude": float("nan"),
                "longitude": float("nan"),
                "geocode_status": "failed",
            })

    return pd.DataFrame(results)
