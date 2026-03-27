"""Partner data loader for the Streamlit app.

Loads pre-built partner GeoJSON from pipeline output.
Falls back to mock CSV data in local development mode.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

from src import config

logger = logging.getLogger(__name__)

PARTNERS_GEOJSON_PATH = "data/points/partners.geojson"


@st.cache_data(ttl=3600)
def load_partners() -> gpd.GeoDataFrame:
    """Load partner locations from GeoJSON (pipeline output).

    In mock mode, falls back to mock CSV + geocode cache if GeoJSON
    doesn't exist.

    Returns:
        GeoDataFrame with partner_name, partner_type, address, geometry.
    """
    geojson_path = Path(PARTNERS_GEOJSON_PATH)

    if geojson_path.exists():
        gdf = gpd.read_file(str(geojson_path))
        logger.info("Loaded %d partners from %s", len(gdf), geojson_path)
        return gdf

    # Fallback: load from mock CSVs
    if config.USE_MOCK_DATA:
        logger.info("GeoJSON not found, falling back to mock CSV data")
        return _load_from_mock_csv()

    raise FileNotFoundError(
        f"Partner GeoJSON not found: {geojson_path}. "
        "Run 'python -m pipeline --step partners' first."
    )


def _load_from_mock_csv() -> gpd.GeoDataFrame:
    """Load partners from mock CSV + geocode cache as fallback."""
    partners_path = os.path.join(config.MOCK_DATA_DIR, "mock_nfp_partners.csv")
    cache_path = os.path.join(config.MOCK_DATA_DIR, "mock_geocode_cache.csv")

    if not os.path.exists(partners_path):
        raise FileNotFoundError(f"Mock partner file not found: {partners_path}")

    partners_df = pd.read_csv(partners_path)

    if os.path.exists(cache_path):
        cache_df = pd.read_csv(cache_path)
        # Merge coordinates
        partners_df = partners_df.merge(
            cache_df[["address", "latitude", "longitude"]],
            on="address",
            how="left",
        )
    else:
        partners_df["latitude"] = float("nan")
        partners_df["longitude"] = float("nan")

    # Filter to geocoded partners
    valid = partners_df.dropna(subset=["latitude", "longitude"])

    gdf = gpd.GeoDataFrame(
        valid,
        geometry=gpd.points_from_xy(valid["longitude"], valid["latitude"]),
        crs="EPSG:4326",
    )

    logger.info("Loaded %d partners from mock CSV", len(gdf))
    return gdf
