"""Unit tests for the unified Community Partners layer.

Covers changes made on 2026-04-20 to src/layer_manager.py:

1. ``_hex_to_icon_color`` gained mappings for ``#2E7D32`` (community_meals,
   darkgreen) and ``#607D8B`` (other, cadetblue) so the two newest NFP
   partner types pick up valid Leaflet Awesome preset colors instead of
   falling back to ``blue``.

2. ``build_partner_markers`` now accepts a ``selected_categories`` filter
   that restricts which rows render (matching the filter added to
   ``build_giving_matters_layer`` earlier).

3. ``build_community_partners_layer`` is a new helper that merges NFP
   partners + Giving Matters organizations into ONE
   ``folium.FeatureGroup`` containing ONE ``MarkerCluster``. It replaces
   the previous two-layer flow (separate "NFP Partners" and "Community
   Partners (Giving Matters)" LayerControl entries).

4. ``_make_pin_marker`` is the shared pin-building helper both sources
   route through so the visual output is identical.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import geopandas as gpd
import pytest
from shapely.geometry import Point

# Streamlit isn't needed for these tests but layer_manager imports
# side-effect modules that indirectly pull it in. Mock before import.
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kwargs: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())
sys.modules.setdefault("boto3", MagicMock())

import folium  # noqa: E402
from folium.plugins import MarkerCluster  # noqa: E402

from src.layer_manager import (  # noqa: E402
    _hex_to_icon_color,
    _make_pin_marker,
    build_community_partners_layer,
    build_partner_markers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def nfp_gdf():
    """3 NFP partners across 3 partner types."""
    return gpd.GeoDataFrame(
        {
            "partner_name": ["Alpha NFP", "Beta NFP", "Gamma NFP"],
            "address": ["1 Main St", "2 Main St", "3 Main St"],
            "partner_type": ["community_meals", "school_summer", "senior_services"],
        },
        geometry=[Point(-86.78, 36.16), Point(-86.79, 36.17), Point(-86.80, 36.18)],
        crs="EPSG:4326",
    )


@pytest.fixture
def gm_gdf():
    """4 Giving Matters orgs across 3 partner types (note: `category` col)."""
    return gpd.GeoDataFrame(
        {
            "name": ["GM One", "GM Two", "GM Three", "GM Four"],
            "address": ["10 Oak", "20 Oak", "30 Oak", "40 Oak"],
            "category": ["community_meals", "community_meals", "other", "after_school"],
        },
        geometry=[
            Point(-86.70, 36.10),
            Point(-86.71, 36.11),
            Point(-86.72, 36.12),
            Point(-86.73, 36.13),
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def partner_config():
    """Minimal partner config covering the types used in fixtures."""
    return {
        "types": {
            "school_summer": {
                "label": "School & Summer Programs",
                "color": "#E41A1C", "icon": "graduation-cap",
            },
            "community_meals": {
                "label": "Community Meals",
                "color": "#2E7D32", "icon": "utensils",
            },
            "senior_services": {
                "label": "Senior Services",
                "color": "#984EA3", "icon": "user",
            },
            "after_school": {
                "label": "After-School Programs",
                "color": "#999999", "icon": "child",
            },
            "other": {
                "label": "Other",
                "color": "#607D8B", "icon": "circle",
            },
        },
    }


@pytest.fixture
def gm_config():
    return {
        "point_layer_name": "Community Partners (Giving Matters)",
        "default_color": "#17BECF",
    }


# ---------------------------------------------------------------------------
# _hex_to_icon_color — new mappings for community_meals + other
# ---------------------------------------------------------------------------
class TestHexToIconColorMap:
    def test_community_meals_maps_to_darkgreen(self):
        """#2E7D32 (community_meals) must use a valid Awesome preset."""
        assert _hex_to_icon_color("#2E7D32") == "darkgreen"

    def test_other_maps_to_cadetblue(self):
        """#607D8B (the new 'other' category) must not fall back to blue."""
        assert _hex_to_icon_color("#607D8B") == "cadetblue"

    def test_existing_mappings_preserved(self):
        """Regression: pre-existing NFP colors still resolve correctly."""
        assert _hex_to_icon_color("#E41A1C") == "red"
        assert _hex_to_icon_color("#377EB8") == "blue"
        assert _hex_to_icon_color("#4DAF4A") == "green"
        assert _hex_to_icon_color("#984EA3") == "purple"
        assert _hex_to_icon_color("#FF7F00") == "orange"
        assert _hex_to_icon_color("#A65628") == "darkred"
        assert _hex_to_icon_color("#F781BF") == "pink"
        assert _hex_to_icon_color("#999999") == "gray"

    def test_unknown_hex_falls_back_to_blue(self):
        """Sentinel: unrecognized hex → blue fallback (unchanged behavior)."""
        assert _hex_to_icon_color("#123456") == "blue"
        assert _hex_to_icon_color("") == "blue"


# ---------------------------------------------------------------------------
# _make_pin_marker — shared helper used by both NFP + Giving Matters paths
# ---------------------------------------------------------------------------
class TestMakePinMarker:
    def test_returns_folium_marker(self):
        m = _make_pin_marker(
            lat=36.16, lon=-86.78,
            name="Test Org", address="123 Main St",
            category_id="community_meals",
            category_label="Community Meals",
            color="#2E7D32", icon_name="utensils",
        )
        assert isinstance(m, folium.Marker)
        assert m.location == [36.16, -86.78]

    def test_icon_has_hex_color_and_preset(self):
        """Icon stores the exact hex in icon_color and the preset in color."""
        m = _make_pin_marker(
            lat=36.16, lon=-86.78,
            name="X", address="Y",
            category_id="other",
            category_label="Other",
            color="#607D8B", icon_name="circle",
        )
        assert isinstance(m.icon, folium.Icon)
        opts = str(m.icon.options)
        # Hex preserved for fill color
        assert "#607D8B" in opts or "#607d8b" in opts.lower()
        # Preset mapped via _hex_to_icon_color
        assert "cadetblue" in opts.lower()

    def test_popup_contains_name_label_and_address(self):
        m = _make_pin_marker(
            lat=0, lon=0,
            name="Second Harvest", address="123 Charity Ln",
            category_id="community_meals",
            category_label="Community Meals",
            color="#2E7D32", icon_name="utensils",
        )
        # Attach to a throwaway map and render to HTML so the popup string
        # survives end-to-end through folium's template chain.
        m.add_to(folium.Map())
        html = m.get_root().render()
        assert "Second Harvest" in html
        assert "Community Meals" in html
        assert "123 Charity Ln" in html


# ---------------------------------------------------------------------------
# build_partner_markers — selected_categories filter
# ---------------------------------------------------------------------------
class TestBuildPartnerMarkersFilter:
    def test_none_filter_keeps_all(self, nfp_gdf, partner_config):
        fg = build_partner_markers(nfp_gdf, partner_config, selected_categories=None)
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 3

    def test_empty_filter_keeps_all(self, nfp_gdf, partner_config):
        """Empty tuple is treated as 'no filter' — matches giving_matters semantics."""
        fg = build_partner_markers(nfp_gdf, partner_config, selected_categories=())
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 3

    def test_single_category_filter(self, nfp_gdf, partner_config):
        fg = build_partner_markers(
            nfp_gdf, partner_config, selected_categories=("community_meals",),
        )
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 1

    def test_multi_category_filter(self, nfp_gdf, partner_config):
        fg = build_partner_markers(
            nfp_gdf, partner_config,
            selected_categories=("community_meals", "school_summer"),
        )
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 2

    def test_unmatched_category_returns_no_markers(self, nfp_gdf, partner_config):
        """Filter that matches zero rows → empty FeatureGroup."""
        fg = build_partner_markers(
            nfp_gdf, partner_config, selected_categories=("homeless_outreach",),
        )
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 0


# ---------------------------------------------------------------------------
# build_community_partners_layer — unified NFP + Giving Matters layer
# ---------------------------------------------------------------------------
class TestBuildCommunityPartnersLayer:
    def test_returns_feature_group_named_community_partners(
        self, nfp_gdf, gm_gdf, partner_config, gm_config,
    ):
        fg = build_community_partners_layer(
            nfp_gdf, gm_gdf, partner_config, gm_config,
        )
        assert isinstance(fg, folium.FeatureGroup)
        assert fg.layer_name == "Community Partners"

    def test_wraps_markers_in_single_marker_cluster(
        self, nfp_gdf, gm_gdf, partner_config, gm_config,
    ):
        fg = build_community_partners_layer(
            nfp_gdf, gm_gdf, partner_config, gm_config,
        )
        children = list(fg._children.values())
        # Exactly ONE MarkerCluster — no second FG, no loose markers
        assert len(children) == 1
        assert isinstance(children[0], MarkerCluster)

    def test_merges_both_sources_without_filter(
        self, nfp_gdf, gm_gdf, partner_config, gm_config,
    ):
        """No filter => 3 NFP + 4 GM = 7 pins in the cluster."""
        fg = build_community_partners_layer(
            nfp_gdf, gm_gdf, partner_config, gm_config,
        )
        cluster = next(iter(fg._children.values()))
        markers = list(cluster._children.values())
        assert len(markers) == 7
        for m in markers:
            assert isinstance(m, folium.Marker)

    def test_filter_applies_to_both_sources(
        self, nfp_gdf, gm_gdf, partner_config, gm_config,
    ):
        """'community_meals' filter: 1 NFP + 2 GM = 3 pins."""
        fg = build_community_partners_layer(
            nfp_gdf, gm_gdf, partner_config, gm_config,
            selected_categories=("community_meals",),
        )
        cluster = next(iter(fg._children.values()))
        assert len(cluster._children) == 3

    def test_empty_selected_categories_is_no_filter(
        self, nfp_gdf, gm_gdf, partner_config, gm_config,
    ):
        """Empty tuple == None — render everything."""
        fg = build_community_partners_layer(
            nfp_gdf, gm_gdf, partner_config, gm_config,
            selected_categories=(),
        )
        cluster = next(iter(fg._children.values()))
        assert len(cluster._children) == 7

    def test_handles_missing_nfp_source(
        self, gm_gdf, partner_config, gm_config,
    ):
        """When partners geojson is absent, still render Giving Matters."""
        fg = build_community_partners_layer(
            None, gm_gdf, partner_config, gm_config,
        )
        cluster = next(iter(fg._children.values()))
        assert len(cluster._children) == 4  # 4 GM rows, no NFP

    def test_handles_missing_giving_matters_source(
        self, nfp_gdf, partner_config, gm_config,
    ):
        """When giving_matters.geojson is absent, still render NFP partners."""
        fg = build_community_partners_layer(
            nfp_gdf, None, partner_config, gm_config,
        )
        cluster = next(iter(fg._children.values()))
        assert len(cluster._children) == 3  # 3 NFP rows, no GM

    def test_handles_both_sources_missing(self, partner_config, gm_config):
        """When both sources are missing, the cluster is empty but the FG exists."""
        fg = build_community_partners_layer(
            None, None, partner_config, gm_config,
        )
        cluster = next(iter(fg._children.values()))
        assert len(cluster._children) == 0

    def test_category_coloring_shared_across_sources(
        self, nfp_gdf, gm_gdf, partner_config, gm_config,
    ):
        """A community_meals NFP pin and a community_meals GM pin share
        the same hex color (#2E7D32) — sources render identically."""
        fg = build_community_partners_layer(
            nfp_gdf, gm_gdf, partner_config, gm_config,
            selected_categories=("community_meals",),
        )
        cluster = next(iter(fg._children.values()))
        markers = list(cluster._children.values())
        colors = [str(m.icon.options).lower() for m in markers]
        for opts in colors:
            assert "#2e7d32" in opts

    def test_gm_default_color_applies_when_type_unknown(self, partner_config):
        """Giving Matters row with unrecognized category uses gm_config.default_color."""
        gm_orphan = gpd.GeoDataFrame(
            {"name": ["Orphan"], "address": ["x"], "category": ["not_a_real_type"]},
            geometry=[Point(-86.78, 36.16)],
            crs="EPSG:4326",
        )
        gm_config = {"default_color": "#17BECF"}
        fg = build_community_partners_layer(
            None, gm_orphan, partner_config, gm_config,
        )
        cluster = next(iter(fg._children.values()))
        marker = next(iter(cluster._children.values()))
        opts = str(marker.icon.options).lower()
        assert "#17becf" in opts
