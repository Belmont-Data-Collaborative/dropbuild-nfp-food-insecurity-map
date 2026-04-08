"""Tests for Phase 2.5: categorical layer support.

Verifies:
- config_loader.get_layer_type() reads layer_type field with "continuous" default
- config_loader.get_layer_categories() returns the categories dict for categorical layers
- layer_manager.build_choropleth_layer() renders categorical layers with discrete
  two-tone colors (#EEEEEE for 0, #B71C1C for 1) instead of a gradient
- Categorical LegendInfo has populated `categories` and empty/unused `colors`
"""
from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from src.config_loader import get_layer_categories, get_layer_type
from src.layer_manager import build_choropleth_layer

# --- Fixtures -----------------------------------------------------------------

CATEGORICAL_LAYER = {
    "column": "LILATracts_1And10",
    "display_name": "LILA Designation (1 & 10 mi)",
    "legend_name": "Low Income + Low Access",
    "format_str": "{}",
    "tooltip_alias": "LILA",
    "default_visible": False,
    "layer_type": "categorical",
    "categories": {0: "Not LILA", 1: "LILA Tract"},
}

CONTINUOUS_LAYER = {
    "column": "lapop1",
    "display_name": "Low Access Population (1 mi)",
    "colormap": "YlOrRd",
    "legend_name": "Pop Beyond 1 mi",
    "format_str": "{:,.0f}",
}


def _make_gdf() -> gpd.GeoDataFrame:
    geoms = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
        Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
    ]
    return gpd.GeoDataFrame(
        {
            "GEOID": ["47037010100", "47037010200", "47037010300"],
            "NAME": ["A", "B", "C"],
            "LILATracts_1And10": [0, 1, 1],
            "geometry": geoms,
        },
        crs="EPSG:4326",
    )


# --- config_loader ------------------------------------------------------------


def test_get_layer_type_categorical() -> None:
    assert get_layer_type(CATEGORICAL_LAYER) == "categorical"


def test_get_layer_type_default_is_continuous() -> None:
    assert get_layer_type(CONTINUOUS_LAYER) == "continuous"


def test_get_layer_type_explicit_continuous() -> None:
    cfg = {**CONTINUOUS_LAYER, "layer_type": "continuous"}
    assert get_layer_type(cfg) == "continuous"


def test_get_layer_categories_returns_dict() -> None:
    cats = get_layer_categories(CATEGORICAL_LAYER)
    assert cats == {0: "Not LILA", 1: "LILA Tract"}


def test_get_layer_categories_continuous_returns_empty() -> None:
    assert get_layer_categories(CONTINUOUS_LAYER) == {}


# --- layer_manager rendering --------------------------------------------------


def test_categorical_layer_uses_discrete_colors() -> None:
    gdf = _make_gdf()
    fg, legend = build_choropleth_layer(gdf, CATEGORICAL_LAYER)

    # Legend should carry categories metadata, not a continuous gradient
    assert legend.categories is not None
    assert 0 in legend.categories and 1 in legend.categories
    color_0, label_0 = legend.categories[0]
    color_1, label_1 = legend.categories[1]
    assert color_0.upper() == "#EEEEEE"
    assert color_1.upper() == "#B71C1C"
    assert label_0 == "Not LILA"
    assert label_1 == "LILA Tract"


def test_categorical_layer_style_function_assigns_category_colors() -> None:
    gdf = _make_gdf()
    fg, _legend = build_choropleth_layer(gdf, CATEGORICAL_LAYER)

    # Drill into the GeoJson child of the FeatureGroup
    geojson_child = next(
        c for c in fg._children.values() if isinstance(c, __import__("folium").GeoJson)
    )
    style_fn = geojson_child.style_function

    feat_0 = {"properties": {"GEOID": "47037010100"}}
    feat_1 = {"properties": {"GEOID": "47037010200"}}
    assert style_fn(feat_0)["fillColor"].upper() == "#EEEEEE"
    assert style_fn(feat_1)["fillColor"].upper() == "#B71C1C"


def test_continuous_layer_still_returns_branca_colormap() -> None:
    import branca.colormap

    gdf = _make_gdf()
    cfg = {**CONTINUOUS_LAYER, "column": "LILATracts_1And10"}
    _fg, cmap = build_choropleth_layer(gdf, cfg)
    # Continuous path: returns a branca LinearColormap, not a LegendInfo
    assert isinstance(cmap, branca.colormap.LinearColormap)
