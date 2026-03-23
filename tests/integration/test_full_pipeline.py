from __future__ import annotations

"""Integration test: full pipeline from CSV load through map construction."""

import json
import os
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Mock streamlit before importing src modules
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())
sys.modules.setdefault("boto3", MagicMock())

# Mock geopy for geocoder
_geopy_mock = MagicMock()
sys.modules.setdefault("geopy", _geopy_mock)
sys.modules.setdefault("geopy.geocoders", _geopy_mock)
sys.modules.setdefault("geopy.exc", MagicMock())

import folium  # noqa: E402

from src import config  # noqa: E402
from src.data_loader import load_csv_from_file  # noqa: E402
from src.layer_manager import (  # noqa: E402
    build_choropleth_layer,
    build_partner_markers,
    build_tract_boundaries_layer,
)
from src.map_builder import build_map  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "fixtures")

# Minimal GeoJSON for test purposes
SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"GEOID": "47037001700", "NAME": "17", "NAMELSAD": "Census Tract 17"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-86.80, 36.16], [-86.78, 36.16],
                    [-86.78, 36.18], [-86.80, 36.18],
                    [-86.80, 36.16],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {"GEOID": "47037001800", "NAME": "18", "NAMELSAD": "Census Tract 18"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-86.78, 36.16], [-86.76, 36.16],
                    [-86.76, 36.18], [-86.78, 36.18],
                    [-86.78, 36.16],
                ]],
            },
        },
        {
            "type": "Feature",
            "properties": {"GEOID": "47037001900", "NAME": "19", "NAMELSAD": "Census Tract 19"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-86.76, 36.16], [-86.74, 36.16],
                    [-86.74, 36.18], [-86.76, 36.18],
                    [-86.76, 36.16],
                ]],
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# Test: data loading from fixtures
# ---------------------------------------------------------------------------
class TestDataLoading:
    def test_load_partners_fixture(self):
        path = os.path.join(FIXTURES_DIR, "sample_partners.csv")
        df = load_csv_from_file(path)
        assert len(df) == 5
        assert "partner_name" in df.columns
        assert "address" in df.columns
        assert "partner_type" in df.columns

    def test_load_census_fixture(self):
        path = os.path.join(FIXTURES_DIR, "sample_census.csv")
        df = load_csv_from_file(path)
        assert len(df) == 3
        assert "GEOID" in df.columns
        assert "poverty_rate" in df.columns

    def test_load_cdc_places_fixture(self):
        path = os.path.join(FIXTURES_DIR, "sample_cdc_places.csv")
        df = load_csv_from_file(path)
        assert len(df) == 3
        assert "GEOID" in df.columns
        assert "DIABETES_CrudePrev" in df.columns


# ---------------------------------------------------------------------------
# Test: GEOID normalization pipeline
# ---------------------------------------------------------------------------
class TestGeoidNormalization:
    def test_census_geoid_normalization(self):
        path = os.path.join(FIXTURES_DIR, "sample_census.csv")
        df = load_csv_from_file(path)
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
        assert all(len(str(g)) == 11 for g in df["GEOID"])
        assert all(str(g).startswith("47037") for g in df["GEOID"])

    def test_cdc_geoid_normalization(self):
        path = os.path.join(FIXTURES_DIR, "sample_cdc_places.csv")
        df = load_csv_from_file(path)
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
        assert all(len(str(g)) == 11 for g in df["GEOID"])

    def test_geojson_geoid_matches_csv(self):
        """GEOIDs in the test GeoJSON should match those in the census fixture."""
        path = os.path.join(FIXTURES_DIR, "sample_census.csv")
        df = load_csv_from_file(path)
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
        geojson_geoids = {
            f["properties"]["GEOID"] for f in SAMPLE_GEOJSON["features"]
        }
        csv_geoids = set(df["GEOID"])
        assert geojson_geoids == csv_geoids


# ---------------------------------------------------------------------------
# Test: layer building pipeline
# ---------------------------------------------------------------------------
class TestLayerBuildingPipeline:
    def test_tract_boundaries_layer(self):
        layer = build_tract_boundaries_layer(SAMPLE_GEOJSON)
        assert isinstance(layer, folium.GeoJson)

    def test_choropleth_layer_with_census_data(self):
        path = os.path.join(FIXTURES_DIR, "sample_census.csv")
        df = load_csv_from_file(path)
        df["GEOID"] = df["GEOID"].astype(str).str.zfill(11)
        layer_config = next(
            lc for lc in config.CHOROPLETH_LAYERS if lc["id"] == "median_income"
        )
        geojson_layer, colormap = build_choropleth_layer(
            SAMPLE_GEOJSON, df, layer_config
        )
        assert isinstance(geojson_layer, folium.GeoJson)

    def test_partner_markers_with_geocoded_data(self):
        geocoded = pd.DataFrame({
            "partner_name": ["Test Partner"],
            "address": ["123 Main St"],
            "partner_type": ["school_summer"],
            "latitude": [36.16],
            "longitude": [-86.78],
            "geocode_status": ["success"],
        })
        markers = build_partner_markers(geocoded)
        assert isinstance(markers, list)
        assert len(markers) == 1


# ---------------------------------------------------------------------------
# Test: full map assembly
# ---------------------------------------------------------------------------
class TestFullMapAssembly:
    def test_build_map_with_all_layers(self):
        census_path = os.path.join(FIXTURES_DIR, "sample_census.csv")
        cdc_path = os.path.join(FIXTURES_DIR, "sample_cdc_places.csv")
        census_df = load_csv_from_file(census_path)
        census_df["GEOID"] = census_df["GEOID"].astype(str).str.zfill(11)
        cdc_df = load_csv_from_file(cdc_path)
        cdc_df["GEOID"] = cdc_df["GEOID"].astype(str).str.zfill(11)

        geocoded = pd.DataFrame({
            "partner_name": ["Test Partner"],
            "address": ["123 Main St"],
            "partner_type": ["school_summer"],
            "latitude": [36.16],
            "longitude": [-86.78],
            "geocode_status": ["success"],
        })

        result = build_map(
            geojson=SAMPLE_GEOJSON,
            census_df=census_df,
            cdc_df=cdc_df,
            geocoded_df=geocoded,
            selected_layer_id="median_income",
            show_partners=True,
        )
        assert isinstance(result, folium.Map)

    def test_build_map_no_choropleth(self):
        result = build_map(
            geojson=SAMPLE_GEOJSON,
            census_df=None,
            cdc_df=None,
            geocoded_df=None,
            selected_layer_id=None,
            show_partners=False,
        )
        assert isinstance(result, folium.Map)

    def test_build_map_partners_only(self):
        geocoded = pd.DataFrame({
            "partner_name": ["Test"],
            "address": ["123 Main St"],
            "partner_type": ["school_summer"],
            "latitude": [36.16],
            "longitude": [-86.78],
            "geocode_status": ["success"],
        })
        result = build_map(
            geojson=SAMPLE_GEOJSON,
            census_df=None,
            cdc_df=None,
            geocoded_df=geocoded,
            selected_layer_id=None,
            show_partners=True,
        )
        assert isinstance(result, folium.Map)
