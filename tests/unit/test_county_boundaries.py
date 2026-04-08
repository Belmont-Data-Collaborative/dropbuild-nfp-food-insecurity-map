"""Unit tests for spec_updates_2.md §6.2 — county boundary layer.

Verifies that build_county_boundaries_layer produces a toggleable
FeatureGroup with dashed boundary lines that can be turned on/off via
LayerControl. The layer ships visible by default per spec §1.4.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

# Mock streamlit before importing src modules
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())
sys.modules.setdefault("boto3", MagicMock())

import folium  # noqa: E402

from src.layer_manager import build_county_boundaries_layer  # noqa: E402


@pytest.fixture
def county_gdf():
    return gpd.GeoDataFrame(
        {
            "NAME": ["Davidson County", "Williamson County"],
            "COUNTYFP": ["037", "187"],
        },
        geometry=[
            Polygon([(-86.9, 36.0), (-86.7, 36.0), (-86.7, 36.2), (-86.9, 36.2)]),
            Polygon([(-86.9, 35.8), (-86.7, 35.8), (-86.7, 36.0), (-86.9, 36.0)]),
        ],
        crs="EPSG:4326",
    )


def test_returns_feature_group(county_gdf):
    fg = build_county_boundaries_layer(county_gdf)
    assert isinstance(fg, folium.FeatureGroup)


def test_feature_group_name(county_gdf):
    fg = build_county_boundaries_layer(county_gdf)
    assert fg.layer_name == "County Boundaries"


def test_feature_group_shown_by_default(county_gdf):
    fg = build_county_boundaries_layer(county_gdf)
    assert fg.show is True


def test_geojson_uses_dashed_style(county_gdf):
    """Per spec §1.4, county boundaries render as dashed lines so they don't
    visually compete with tract-level choropleth shading."""
    fg = build_county_boundaries_layer(county_gdf)
    geojson_child = next(
        c for c in fg._children.values() if isinstance(c, folium.GeoJson)
    )
    style = geojson_child.style_function({})
    assert style.get("dashArray") == "5,5"
    assert style.get("fillColor") == "transparent"
