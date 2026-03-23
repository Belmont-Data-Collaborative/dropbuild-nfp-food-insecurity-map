from __future__ import annotations

"""Unit tests for src/layer_manager.py."""

import json
import os
import sys
from unittest.mock import MagicMock

import numpy as np
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

import folium  # noqa: E402
import branca.colormap  # noqa: E402

from src.layer_manager import (  # noqa: E402
    build_choropleth_layer,
    build_partner_markers,
    build_tract_boundaries_layer,
)
from src import config  # noqa: E402


# ---------------------------------------------------------------------------
# Shared test GeoJSON fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_geojson():
    """A minimal GeoJSON FeatureCollection for Davidson County tracts."""
    return {
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


@pytest.fixture
def sample_census_df():
    return pd.DataFrame({
        "GEOID": ["47037001700", "47037001800", "47037001900"],
        "poverty_rate": [12.5, 22.3, 8.7],
        "median_household_income": [58000, 41000, 74500],
        "data_vintage": [
            "ACS 2022 5-Year Estimates",
            "ACS 2022 5-Year Estimates",
            "ACS 2022 5-Year Estimates",
        ],
    })


@pytest.fixture
def sample_geocoded_df():
    return pd.DataFrame({
        "partner_name": [
            "East Nashville Community Center",
            "Antioch Food Pantry",
            "Bordeaux Senior Services",
        ],
        "address": [
            "1234 Gallatin Ave Nashville TN 37206",
            "456 Nolensville Pike Nashville TN 37211",
            "789 Clarksville Pike Nashville TN 37208",
        ],
        "partner_type": ["community_development", "school_summer", "senior_services"],
        "latitude": [36.1823, 36.0894, 36.1950],
        "longitude": [-86.7429, -86.7143, -86.8210],
        "geocode_status": ["success", "success", "success"],
    })


# ---------------------------------------------------------------------------
# Test: build_tract_boundaries_layer
# ---------------------------------------------------------------------------
class TestBuildTractBoundariesLayer:
    def test_returns_geojson_object(self, sample_geojson):
        result = build_tract_boundaries_layer(sample_geojson)
        assert isinstance(result, folium.GeoJson), (
            "build_tract_boundaries_layer must return a folium.GeoJson, not a tuple"
        )

    def test_not_a_tuple(self, sample_geojson):
        result = build_tract_boundaries_layer(sample_geojson)
        assert not isinstance(result, tuple), (
            "build_tract_boundaries_layer must return a single GeoJson, NOT a tuple"
        )


# ---------------------------------------------------------------------------
# Test: build_choropleth_layer
# ---------------------------------------------------------------------------
class TestBuildChoroplethLayer:
    def _get_median_income_config(self):
        for layer in config.CHOROPLETH_LAYERS:
            if layer["id"] == "median_income":
                return layer
        pytest.skip("median_income layer not found in CHOROPLETH_LAYERS")

    def test_returns_tuple(self, sample_geojson, sample_census_df):
        layer_config = self._get_median_income_config()
        result = build_choropleth_layer(sample_geojson, sample_census_df, layer_config)
        assert isinstance(result, tuple), "build_choropleth_layer must return a tuple"
        assert len(result) == 2, "build_choropleth_layer must return a 2-tuple"

    def test_tuple_contains_geojson_and_colormap(self, sample_geojson, sample_census_df):
        layer_config = self._get_median_income_config()
        geojson_layer, colormap = build_choropleth_layer(
            sample_geojson, sample_census_df, layer_config
        )
        assert isinstance(geojson_layer, folium.GeoJson)
        assert isinstance(colormap, branca.colormap.LinearColormap)


# ---------------------------------------------------------------------------
# Test: build_partner_markers
# ---------------------------------------------------------------------------
class TestBuildPartnerMarkers:
    def test_returns_list(self, sample_geocoded_df):
        result = build_partner_markers(sample_geocoded_df)
        assert isinstance(result, list)

    def test_returns_circle_markers(self, sample_geocoded_df):
        result = build_partner_markers(sample_geocoded_df)
        for marker in result:
            assert isinstance(marker, folium.CircleMarker)

    def test_correct_count(self, sample_geocoded_df):
        result = build_partner_markers(sample_geocoded_df)
        assert len(result) == len(sample_geocoded_df)

    def test_unknown_partner_type_uses_fallback_color(self):
        """Partners with unrecognized partner_type should use FALLBACK_COLOR."""
        df = pd.DataFrame({
            "partner_name": ["Unknown Partner"],
            "address": ["123 Fake St"],
            "partner_type": ["nonexistent_type"],
            "latitude": [36.16],
            "longitude": [-86.78],
            "geocode_status": ["success"],
        })
        result = build_partner_markers(df)
        assert len(result) == 1
        marker = result[0]
        # CircleMarker options should have FALLBACK_COLOR
        assert isinstance(marker, folium.CircleMarker)

    def test_empty_dataframe(self):
        """build_partner_markers should handle empty DataFrame."""
        df = pd.DataFrame(
            columns=["partner_name", "address", "partner_type", "latitude", "longitude", "geocode_status"]
        )
        result = build_partner_markers(df)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_skips_failed_geocodes(self):
        """Partners with NaN lat/lon should not produce markers."""
        df = pd.DataFrame({
            "partner_name": ["Failed Partner"],
            "address": [""],
            "partner_type": ["school_summer"],
            "latitude": [np.nan],
            "longitude": [np.nan],
            "geocode_status": ["failed"],
        })
        result = build_partner_markers(df)
        # Failed geocodes should be skipped
        assert len(result) == 0
