"""Tests for Phase 2 app-side LILA wiring.

Verifies:
- config_loader.is_layer_available_for_granularity() returns False for LILA at zip
  and True at tract; returns True for census/health at both granularities
- map_builder._add_bottom_right_legends accepts mixed continuous + categorical
  legend dicts and emits discrete swatches for categorical layers in HTML
"""
from __future__ import annotations

import folium
import geopandas as gpd
from shapely.geometry import Polygon

from src.config_loader import is_layer_available_for_granularity
from src.layer_manager import LegendInfo
from src.map_builder import _add_bottom_right_legends


# --- is_layer_available_for_granularity ---------------------------------------


def test_lila_layer_not_available_at_zip() -> None:
    layer = {
        "column": "LILATracts_1And10",
        "source_key": "usda_lila",
    }
    assert is_layer_available_for_granularity(layer, "zip") is False


def test_lila_layer_available_at_tract() -> None:
    layer = {
        "column": "LILATracts_1And10",
        "source_key": "usda_lila",
    }
    assert is_layer_available_for_granularity(layer, "tract") is True


def test_census_layer_available_at_both_granularities() -> None:
    layer = {"column": "DP03_0062E", "source_key": "census_acs"}
    assert is_layer_available_for_granularity(layer, "tract") is True
    assert is_layer_available_for_granularity(layer, "zip") is True


def test_health_layer_available_at_both_granularities() -> None:
    layer = {"column": "DIABETES", "source_key": "health_lila"}
    assert is_layer_available_for_granularity(layer, "tract") is True
    assert is_layer_available_for_granularity(layer, "zip") is True


# --- legend rendering ---------------------------------------------------------


def test_legends_handle_categorical_legendinfo() -> None:
    """_add_bottom_right_legends should accept LegendInfo for categorical
    layers and emit a discrete swatch (not a gradient) into the JS payload."""
    m = folium.Map(location=[36.0, -86.6], zoom_start=9)

    legend = LegendInfo(
        colors=[],
        vmin=0.0,
        vmax=1.0,
        caption="LILA",
        categories={
            0: ("#EEEEEE", "Not LILA"),
            1: ("#B71C1C", "LILA Tract"),
        },
    )

    layer_cfg = {
        "column": "LILATracts_1And10",
        "display_name": "LILA Designation (1 & 10 mi)",
        "layer_type": "categorical",
        "categories": {0: "Not LILA", 1: "LILA Tract"},
    }

    _add_bottom_right_legends(
        m,
        {"LILA Designation (1 & 10 mi)": legend},
        [layer_cfg],
    )

    html = m.get_root().render()
    # Categorical swatch hex colors must appear in the rendered legend JS
    assert "#B71C1C" in html or "#b71c1c" in html
    assert "#EEEEEE" in html or "#eeeeee" in html
    # Category labels must appear
    assert "Not LILA" in html
    assert "LILA Tract" in html
