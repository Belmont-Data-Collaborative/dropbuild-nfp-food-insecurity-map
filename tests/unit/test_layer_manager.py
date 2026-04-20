"""Unit tests for src/layer_manager.py — pins, FeatureGroups, choropleth."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, Polygon

# Mock streamlit before importing src modules
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())
sys.modules.setdefault("boto3", MagicMock())

import branca.colormap  # noqa: E402
import folium  # noqa: E402

from src.config_loader import get_partner_config  # noqa: E402
from src.layer_manager import (  # noqa: E402
    build_boundary_layer,
    build_choropleth_layer,
    build_partner_markers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_gdf():
    """A GeoDataFrame with 3 Davidson County tracts and mock data columns."""
    return gpd.GeoDataFrame(
        {
            "GEOID": ["47037001700", "47037001800", "47037001900"],
            "NAME": ["17", "18", "19"],
            "NAMELSAD": ["Census Tract 17", "Census Tract 18", "Census Tract 19"],
            "DP03_0062E": [58000, 41000, 74500],
            "DP03_0119PE": [12.5, 22.3, 8.7],
            "DP05_0001E": [5000, 3000, 8000],
        },
        geometry=[
            Polygon([(-86.80, 36.16), (-86.78, 36.16), (-86.78, 36.18), (-86.80, 36.18)]),
            Polygon([(-86.78, 36.16), (-86.76, 36.16), (-86.76, 36.18), (-86.78, 36.18)]),
            Polygon([(-86.76, 36.16), (-86.74, 36.16), (-86.74, 36.18), (-86.76, 36.18)]),
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def sample_partners_gdf():
    """A GeoDataFrame with 3 partner locations."""
    return gpd.GeoDataFrame(
        {
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
        },
        geometry=[
            Point(-86.7429, 36.1823),
            Point(-86.7143, 36.0894),
            Point(-86.8210, 36.1950),
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def income_layer_config():
    """Layer config for Median Household Income."""
    return {
        "column": "DP03_0062E",
        "display_name": "Median Household Income",
        "colormap": "YlGnBu",
        "legend_name": "Median Household Income ($)",
        "format_str": "${:,.0f}",
        "tooltip_alias": "Income",
        "default_visible": True,
    }


# ---------------------------------------------------------------------------
# Test: build_partner_markers — pins, not dots
# ---------------------------------------------------------------------------
class TestBuildPartnerMarkers:
    def test_returns_feature_group(self, sample_partners_gdf):
        partner_cfg = get_partner_config()
        result = build_partner_markers(sample_partners_gdf, partner_cfg)
        assert isinstance(result, folium.FeatureGroup)

    def test_feature_group_name(self, sample_partners_gdf):
        partner_cfg = get_partner_config()
        fg = build_partner_markers(sample_partners_gdf, partner_cfg)
        assert fg.layer_name == "Community Partners"

    def test_markers_are_pins_not_circles(self, sample_partners_gdf):
        partner_cfg = get_partner_config()
        fg = build_partner_markers(sample_partners_gdf, partner_cfg)
        children = list(fg._children.values())
        for child in children:
            assert isinstance(child, folium.Marker), (
                f"Expected folium.Marker (pin), got {type(child).__name__}"
            )

    def test_correct_marker_count(self, sample_partners_gdf):
        partner_cfg = get_partner_config()
        fg = build_partner_markers(sample_partners_gdf, partner_cfg)
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 3

    def test_unknown_partner_type_handled(self):
        gdf = gpd.GeoDataFrame(
            {
                "partner_name": ["Unknown Partner"],
                "address": ["123 Fake St"],
                "partner_type": ["nonexistent_type"],
            },
            geometry=[Point(-86.78, 36.16)],
            crs="EPSG:4326",
        )
        partner_cfg = get_partner_config()
        fg = build_partner_markers(gdf, partner_cfg)
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 1

    def test_empty_gdf_returns_empty_group(self):
        gdf = gpd.GeoDataFrame(
            columns=["partner_name", "address", "partner_type", "geometry"],
        )
        partner_cfg = get_partner_config()
        fg = build_partner_markers(gdf, partner_cfg)
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 0


# ---------------------------------------------------------------------------
# Test: build_choropleth_layer — FeatureGroups
# ---------------------------------------------------------------------------
class TestBuildChoroplethLayer:
    def test_returns_tuple(self, sample_gdf, income_layer_config):
        result = build_choropleth_layer(sample_gdf, income_layer_config)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_feature_group_and_colormap(self, sample_gdf, income_layer_config):
        fg, cmap = build_choropleth_layer(sample_gdf, income_layer_config)
        assert isinstance(fg, folium.FeatureGroup)
        assert isinstance(cmap, branca.colormap.LinearColormap)

    def test_feature_group_name_matches_display(self, sample_gdf, income_layer_config):
        fg, _ = build_choropleth_layer(sample_gdf, income_layer_config)
        assert fg.layer_name == "Median Household Income"


# ---------------------------------------------------------------------------
# Test: build_boundary_layer
# ---------------------------------------------------------------------------
class TestBuildBoundaryLayer:
    def test_returns_feature_group(self, sample_gdf):
        fg = build_boundary_layer(sample_gdf)
        assert isinstance(fg, folium.FeatureGroup)
