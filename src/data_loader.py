"""Data loading layer for the Streamlit app.

Loads pre-built Parquet files (from pipeline output) and GeoJSON boundaries.
Supports multi-granularity (tract / zip).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import streamlit as st

from src import config
from src.config_loader import get_all_layer_configs, get_data_sources, get_granularities, get_map_display

logger = logging.getLogger(__name__)


class DataLoadError(Exception):
    """Raised when data cannot be loaded."""


class DataSchemaError(Exception):
    """Raised when loaded data is missing required columns."""


@st.cache_data(ttl=3600)
def load_geodata(granularity: str) -> gpd.GeoDataFrame:
    """Load and merge geographic boundaries with all choropleth data.

    Args:
        granularity: 'tract' or 'zip'.

    Returns:
        Merged GeoDataFrame with all metric columns.

    Raises:
        DataLoadError: If boundary file is not found.
    """
    # Find geo file for this granularity
    granularities = get_granularities()
    geo_file = None
    for g in granularities:
        if g["id"] == granularity:
            geo_file = g["geo_file"]
            break

    if geo_file is None:
        raise DataLoadError(f"Unknown granularity: {granularity}")

    geo_path = Path(geo_file)
    if not geo_path.exists():
        raise DataLoadError(f"Geographic boundary file not found: {geo_file}")

    # Load GeoJSON
    gdf = gpd.read_file(str(geo_path))

    # Simplify geometries for performance (configurable via project.yml)
    tolerance = get_map_display().get("simplify_tolerance", 0.001)
    gdf["geometry"] = gdf.geometry.simplify(tolerance, preserve_topology=True)

    # Normalize GEOIDs
    if "GEOID" in gdf.columns:
        gdf["GEOID"] = gdf["GEOID"].astype(str).str.zfill(11)

    # Load and merge each data source's parquet
    data_sources = get_data_sources()
    for source_key, source_cfg in data_sources.items():
        output_prefix = source_cfg.get("output_prefix", source_key)
        parquet_path = f"data/choropleth/{output_prefix}_{granularity}_data.parquet"

        if not Path(parquet_path).exists():
            logger.warning("Parquet not found: %s", parquet_path)
            continue

        try:
            df = pd.read_parquet(parquet_path)
            if "GEOID" in df.columns:
                df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)

            # Merge on GEOID
            data_cols = [c for c in df.columns if c != "GEOID"]
            gdf = gdf.merge(
                df[["GEOID"] + data_cols],
                on="GEOID",
                how="left",
            )
            logger.info(
                "Merged %s: %d data columns", source_key, len(data_cols)
            )
        except (FileNotFoundError, pd.errors.ParserError, OSError) as exc:
            logger.warning("Failed to load %s: %s", parquet_path, exc)

    return gdf


@st.cache_data(ttl=3600)
def load_geojson_dict(granularity: str) -> dict:
    """Load raw GeoJSON as dict for Folium layers.

    Args:
        granularity: 'tract' or 'zip'.

    Returns:
        GeoJSON dict with normalized GEOIDs.

    Raises:
        DataLoadError: If file not found.
    """
    granularities = get_granularities()
    geo_file = None
    for g in granularities:
        if g["id"] == granularity:
            geo_file = g["geo_file"]
            break

    if geo_file is None:
        raise DataLoadError(f"Unknown granularity: {granularity}")

    geo_path = Path(geo_file)
    if not geo_path.exists():
        raise DataLoadError(f"Geographic boundary file not found: {geo_file}")

    with open(geo_path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    # Normalize GEOIDs
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        if "GEOID" in props and props["GEOID"] is not None:
            props["GEOID"] = str(props["GEOID"]).zfill(11)

    return geojson
