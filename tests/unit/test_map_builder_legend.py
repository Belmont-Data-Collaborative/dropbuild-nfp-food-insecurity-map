"""Unit tests for legend positioning in map_builder.py.

Verifies that choropleth legends are placed in the bottom-right corner
of the Leaflet map using native L.control({position: 'bottomright'}),
NOT branca's default topright D3/SVG rendering.

Spec requirement #46: "Display a map legend in the bottom-right corner
of the map showing the color scale and numeric range (min/max)."

See MISTAKES_DB.md G009 for rationale.
"""
from __future__ import annotations

import html as html_mod
import json
import re
import sys
from unittest.mock import MagicMock

import geopandas as gpd
import pandas as pd
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

import branca.colormap  # noqa: E402
import folium  # noqa: E402

from src.config_loader import get_all_layer_configs, get_partner_config  # noqa: E402
from src.layer_manager import build_choropleth_layer  # noqa: E402
from src.map_builder import build_map_html  # noqa: E402


def _get_inner_html(outer_html: str) -> str:
    """Extract the inner HTML from the folium iframe srcdoc.

    Works whether the output is a bare ``<iframe srcdoc="...">`` (explicit
    Figure height) or wrapped in a responsive ``<div>`` container.
    """
    start = outer_html.index('srcdoc="') + 8
    end = outer_html.index('"', start)
    return html_mod.unescape(outer_html[start:end])


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
def poverty_layer_config():
    return {
        "column": "DP03_0119PE",
        "display_name": "Poverty Rate",
        "colormap": "YlOrRd",
        "legend_name": "Poverty Rate (%)",
        "format_str": "{:.1f}%",
        "tooltip_alias": "Poverty",
        "default_visible": False,
    }


# ---------------------------------------------------------------------------
# Test: branca colormap must NOT be added to map (no topright)
# ---------------------------------------------------------------------------
class TestNoBrancaTopright:
    """Branca's cmap.add_to(m) hardcodes position: 'topright' which cannot
    be reliably overridden via DOM manipulation. It must not be used."""

    def test_no_topright_position_in_single_layer(self, sample_gdf):
        """Single layer map must not contain position: 'topright' from branca."""
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "position: 'topright'" not in inner, (
            "branca colormap must not be added via cmap.add_to(m) — "
            "it hardcodes topright and cannot be reliably moved"
        )

    def test_no_topright_position_in_multi_layer(self, sample_gdf):
        outer = build_map_html("tract", ("DP03_0062E", "DP03_0119PE"))
        inner = _get_inner_html(outer)
        assert "position: 'topright'" not in inner


# ---------------------------------------------------------------------------
# Test: single combined legend control (not one per layer)
# ---------------------------------------------------------------------------
class TestSingleCombinedLegend:
    """All layer legends must live in ONE L.control to prevent stacking/
    reflow issues where hiding one legend shifts others out of view."""

    def test_single_control_not_per_layer_loop(self, sample_gdf):
        """Legend must NOT create one L.control per layer inside a loop.
        Multiple stacked controls cause reflow when one is hidden,
        shifting other legends out of the visible map area."""
        outer = build_map_html("tract", ("DP03_0062E", "DP03_0119PE"))
        inner = _get_inner_html(outer)
        # A forEach that creates L.control inside it = one control per layer
        assert "forEach" not in inner or "L.control" not in inner.split("forEach")[1].split("}")[0], (
            "Must not create L.control inside a forEach loop — "
            "use a single control with sections inside"
        )

    def test_uses_direct_references_not_queryselector(self, sample_gdf):
        """Legend toggling must use direct JS object references, not
        querySelector which can match wrong elements."""
        outer = build_map_html("tract", ("DP03_0062E", "DP03_0119PE"))
        inner = _get_inner_html(outer)
        assert "querySelector(" not in inner, (
            "Must use direct JS references for legend toggling, "
            "not querySelector() which can match wrong elements"
        )


# ---------------------------------------------------------------------------
# Test: legend uses native L.control at bottomright
# ---------------------------------------------------------------------------
class TestBottomRightLegendControl:
    """Legends must be created as L.control({position: 'bottomright'})
    directly in the map's script section."""

    def test_bottomright_position_in_single_layer(self, sample_gdf):
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "'bottomright'" in inner, (
            "Legend must use L.control({position: 'bottomright'})"
        )

    def test_bottomright_position_in_multi_layer(self, sample_gdf):
        outer = build_map_html("tract", ("DP03_0062E", "DP03_0119PE"))
        inner = _get_inner_html(outer)
        assert "'bottomright'" in inner

    def test_legend_has_data_layer_name(self, sample_gdf):
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "data-layer-name" in inner

    def test_legend_contains_layer_display_name(self, sample_gdf):
        """Legend must show the human-readable layer name."""
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "Median Household Income" in inner

    def test_legend_contains_gradient(self, sample_gdf):
        """Legend must contain a CSS gradient for the color scale."""
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "linear-gradient" in inner

    def test_no_legend_when_no_layers(self):
        outer = build_map_html("tract", ())
        inner = _get_inner_html(outer)
        assert "data-layer-name" not in inner
        assert "'bottomright'" not in inner


# ---------------------------------------------------------------------------
# Test: legend script runs AFTER map initialization
# ---------------------------------------------------------------------------
class TestLegendScriptOrder:
    """The legend script must execute after the map variable exists.
    It must be in the script section, not in the body HTML."""

    def test_legend_script_deferred_to_domcontentloaded(self, sample_gdf):
        """The legend script must be wrapped in DOMContentLoaded so it
        runs after the map variable is initialized."""
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "DOMContentLoaded" in inner, (
            "Legend script must be deferred via DOMContentLoaded "
            "to run after map init"
        )

    def test_no_setinterval_polling(self, sample_gdf):
        """Must not use setInterval to poll for elements — unreliable."""
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "setInterval" not in inner, (
            "Legend script must not poll with setInterval — "
            "add to script section so it runs after map init"
        )


# ---------------------------------------------------------------------------
# Test: LayerControl event listeners
# ---------------------------------------------------------------------------
class TestLayerControlEvents:
    """overlayadd/overlayremove must toggle legend visibility
    when layers are toggled via the in-map LayerControl."""

    def test_overlayadd_listener(self, sample_gdf):
        outer = build_map_html("tract", ("DP03_0062E", "DP03_0119PE"))
        inner = _get_inner_html(outer)
        assert "overlayadd" in inner

    def test_overlayremove_listener(self, sample_gdf):
        outer = build_map_html("tract", ("DP03_0062E", "DP03_0119PE"))
        inner = _get_inner_html(outer)
        assert "overlayremove" in inner

    def test_uses_map_variable_directly(self, sample_gdf):
        """Must use the folium map variable name, not iterate window."""
        outer = build_map_html("tract", ("DP03_0062E",))
        inner = _get_inner_html(outer)
        assert "for (var key in window)" not in inner
        # Verify it uses the actual map variable for event binding
        map_var = re.search(r"var (map_\w+)\s*=\s*L\.map", inner).group(1)
        assert f"{map_var}.on(" in inner


# ---------------------------------------------------------------------------
# Test: selected layers have show=True
# ---------------------------------------------------------------------------
class TestSelectedLayerShowState:
    def test_non_default_selected_layer_has_show_true(
        self, sample_gdf, poverty_layer_config
    ):
        fg, _ = build_choropleth_layer(sample_gdf, poverty_layer_config, show=True)
        assert fg.show is True

    def test_show_false_when_not_overridden(self, sample_gdf, poverty_layer_config):
        fg, _ = build_choropleth_layer(sample_gdf, poverty_layer_config)
        assert fg.show is False
