"""Regression test: ZIP-granularity GeoJsons must not contain GeometryCollection.

Folium's GeoJsonTooltip / GeoJsonPopup do not render GeometryCollection
features, which causes a runtime JS error that breaks the LayerControl
(and the visible CartoDB Positron basemap) at ZIP granularity.

The fix in src.data_loader.load_geodata() must convert any GeometryCollection
into a MultiPolygon by extracting only the (Multi)Polygon members.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import geopandas as gpd
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiPolygon,
    Point,
    Polygon,
)

# Mock streamlit before importing src
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kw: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kw: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())

from src.data_loader import _coerce_to_polygonal  # noqa: E402


def test_geometry_collection_with_polygon_becomes_multipolygon() -> None:
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    line = LineString([(0, 0), (2, 2)])
    point = Point(3, 3)
    gc = GeometryCollection([poly, line, point])

    result = _coerce_to_polygonal(gc)
    assert result is not None
    assert result.geom_type in ("Polygon", "MultiPolygon")


def test_geometry_collection_with_multiple_polygons() -> None:
    p1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    p2 = Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    line = LineString([(0, 0), (5, 5)])
    gc = GeometryCollection([p1, line, p2])

    result = _coerce_to_polygonal(gc)
    assert result.geom_type == "MultiPolygon"
    assert len(list(result.geoms)) == 2


def test_geometry_collection_with_only_lines_returns_none() -> None:
    gc = GeometryCollection([LineString([(0, 0), (1, 1)])])
    assert _coerce_to_polygonal(gc) is None


def test_polygon_passthrough_unchanged() -> None:
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert _coerce_to_polygonal(poly) is poly


def test_load_geodata_zip_has_no_geometry_collections(monkeypatch) -> None:
    """End-to-end: after load_geodata('zip'), no feature should be a
    GeometryCollection."""
    from pathlib import Path

    if not Path("data/geo/zipcodes.geojson").exists():
        import pytest
        pytest.skip("zipcodes.geojson not present in this environment")

    from src.data_loader import load_geodata

    gdf = load_geodata("zip")
    bad = [g for g in gdf.geometry if g is not None and g.geom_type == "GeometryCollection"]
    assert bad == [], (
        f"{len(bad)} GeometryCollection features remain in the ZIP gdf — "
        f"Folium tooltips will fail and break LayerControl."
    )
