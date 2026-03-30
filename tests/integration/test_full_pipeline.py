"""Integration test: full pipeline from data loading through map construction."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import geopandas as gpd
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

import folium  # noqa: E402

from src.config_loader import (  # noqa: E402
    get_all_layer_configs,
    get_partner_config,
)
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
    """A GeoDataFrame mimicking merged geodata output."""
    return gpd.GeoDataFrame(
        {
            "GEOID": ["47037001700", "47037001800", "47037001900"],
            "NAME": ["17", "18", "19"],
            "NAMELSAD": ["Census Tract 17", "Census Tract 18", "Census Tract 19"],
            "DP03_0062E": [58000, 41000, 74500],
            "DP03_0119PE": [12.5, 22.3, 8.7],
            "DP05_0001E": [5000, 3000, 8000],
            "DIABETES": [14.2, 18.5, 9.1],
            "BPHIGH": [32.1, 38.5, 25.0],
            "OBESITY": [35.2, 40.1, 28.0],
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
    return gpd.GeoDataFrame(
        {
            "partner_name": ["Test Partner", "Another Partner"],
            "address": ["123 Main St", "456 Broadway"],
            "partner_type": ["school_summer", "medical_health"],
        },
        geometry=[Point(-86.78, 36.16), Point(-86.76, 36.17)],
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# Test: GEOID normalization across sources
# ---------------------------------------------------------------------------
class TestGeoidNormalization:
    def test_all_geoids_are_11_chars(self, sample_gdf):
        for geoid in sample_gdf["GEOID"]:
            assert len(str(geoid)) == 11

    def test_geoids_start_with_county_fips(self, sample_gdf):
        for geoid in sample_gdf["GEOID"]:
            assert str(geoid).startswith("47037")


# ---------------------------------------------------------------------------
# Test: layer building with YAML-driven configs
# ---------------------------------------------------------------------------
class TestLayerBuildingPipeline:
    def test_all_configured_layers_build_successfully(self, sample_gdf):
        """Every layer defined in project.yml should build without error."""
        all_layers = get_all_layer_configs()
        for layer_cfg in all_layers:
            if layer_cfg["column"] in sample_gdf.columns:
                fg, cmap = build_choropleth_layer(sample_gdf, layer_cfg)
                assert isinstance(fg, folium.FeatureGroup)

    def test_boundary_layer_builds(self, sample_gdf):
        fg = build_boundary_layer(sample_gdf)
        assert isinstance(fg, folium.FeatureGroup)

    def test_partner_markers_build(self, sample_partners_gdf):
        partner_cfg = get_partner_config()
        fg = build_partner_markers(sample_partners_gdf, partner_cfg)
        assert isinstance(fg, folium.FeatureGroup)
        markers = [c for c in fg._children.values() if isinstance(c, folium.Marker)]
        assert len(markers) == 2


# ---------------------------------------------------------------------------
# Test: full map assembly
# ---------------------------------------------------------------------------
class TestFullMapAssembly:
    def test_build_map_with_income_layer(self, sample_gdf, sample_partners_gdf):
        """Build a full map with income choropleth + partners."""
        m = folium.Map(location=[36.1627, -86.7816], zoom_start=11)

        # Add choropleth
        income_cfg = next(
            l for l in get_all_layer_configs() if l["column"] == "DP03_0062E"
        )
        fg, cmap = build_choropleth_layer(sample_gdf, income_cfg)
        fg.add_to(m)
        cmap.add_to(m)

        # Add partners
        partner_cfg = get_partner_config()
        partner_fg = build_partner_markers(sample_partners_gdf, partner_cfg)
        partner_fg.add_to(m)

        # Add LayerControl
        folium.LayerControl(collapsed=False).add_to(m)

        assert isinstance(m, folium.Map)
        html = m._repr_html_()
        assert len(html) > 0

    def test_build_map_boundaries_only(self, sample_gdf):
        """Build a map with just boundary layer, no choropleth."""
        m = folium.Map(location=[36.1627, -86.7816], zoom_start=11)
        boundary_fg = build_boundary_layer(sample_gdf)
        boundary_fg.add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)

        assert isinstance(m, folium.Map)

    def test_multiple_choropleth_layers(self, sample_gdf):
        """Build a map with multiple choropleth layers togglable via LayerControl."""
        m = folium.Map(location=[36.1627, -86.7816], zoom_start=11)

        layers_to_add = ["DP03_0062E", "DP03_0119PE", "DIABETES"]
        for col in layers_to_add:
            cfg = next(
                (l for l in get_all_layer_configs() if l["column"] == col),
                None,
            )
            if cfg and col in sample_gdf.columns:
                fg, cmap = build_choropleth_layer(sample_gdf, cfg)
                fg.add_to(m)
                cmap.add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)
        assert isinstance(m, folium.Map)


# ---------------------------------------------------------------------------
# Test: data files exist (if pipeline has been run)
# ---------------------------------------------------------------------------
class TestDataFilesExist:
    def test_tract_geojson_exists(self):
        path = Path("data/geo/tracts.geojson")
        if not path.exists():
            pytest.skip("Tract GeoJSON not generated yet")
        gdf = gpd.read_file(str(path))
        assert len(gdf) > 100

    def test_partners_geojson_exists(self):
        path = Path("data/points/partners.geojson")
        if not path.exists():
            pytest.skip("Partners GeoJSON not generated yet")
        gdf = gpd.read_file(str(path))
        assert len(gdf) > 0

    def test_parquet_files_exist(self):
        path = Path("data/choropleth/acs_tract_data.parquet")
        if not path.exists():
            pytest.skip("Parquet files not generated yet")
        df = pd.read_parquet(path)
        assert len(df) > 0
        assert "GEOID" in df.columns
