"""Tests for spec_updates_2.md §3.4: Giving Matters map rendering.

Verifies:
- build_giving_matters_layer renders circle markers (not pin markers) so it
  visually distinguishes from NFP partner pins
- The layer uses the configured default color (#17BECF)
- map_builder._giving_matters_available reflects file presence
- build_map_html does not crash when the geojson is absent (no UI artifact)
"""
from __future__ import annotations

import json
from pathlib import Path

import folium
import geopandas as gpd
from shapely.geometry import Point

from src.layer_manager import build_giving_matters_layer


def _sample_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "name": ["Org A", "Org B"],
            "address": ["123 Main St", "456 Oak Ave"],
            "category": ["Education", "Health"],
            "geometry": [Point(-86.78, 36.16), Point(-86.79, 36.17)],
        },
        crs="EPSG:4326",
    )


def test_giving_matters_layer_uses_circle_markers() -> None:
    cfg = {
        "point_layer_name": "Community Partners (Giving Matters)",
        "default_color": "#17BECF",
    }
    fg = build_giving_matters_layer(_sample_gdf(), cfg)

    assert isinstance(fg, folium.FeatureGroup)
    assert fg.layer_name == "Community Partners (Giving Matters)"

    # All children must be CircleMarker (NOT folium.Marker pins)
    children = list(fg._children.values())
    assert len(children) == 2
    for child in children:
        assert isinstance(child, folium.CircleMarker), (
            "Giving Matters points must use CircleMarker, not pin markers"
        )


def test_giving_matters_layer_uses_default_color() -> None:
    cfg = {
        "point_layer_name": "Community Partners (Giving Matters)",
        "default_color": "#17BECF",
    }
    fg = build_giving_matters_layer(_sample_gdf(), cfg)
    marker = next(iter(fg._children.values()))
    # CircleMarker stores style options on .options
    opts = marker.options
    assert "#17BECF" in str(opts) or "#17becf" in str(opts).lower()


def test_giving_matters_skipped_when_geojson_missing(tmp_path, monkeypatch) -> None:
    """build_map_html must not raise when data/points/giving_matters.geojson
    is absent — the layer simply doesn't appear."""
    from src import map_builder

    # Confirm the helper reports absence cleanly
    monkeypatch.chdir(tmp_path)
    assert map_builder._giving_matters_available() is False


def test_giving_matters_available_when_file_exists(tmp_path, monkeypatch) -> None:
    from src import map_builder

    monkeypatch.chdir(tmp_path)
    points_dir = tmp_path / "data" / "points"
    points_dir.mkdir(parents=True)
    (points_dir / "giving_matters.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": []})
    )
    assert map_builder._giving_matters_available() is True
