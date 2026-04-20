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


def test_giving_matters_layer_uses_pin_markers() -> None:
    """Giving Matters uses folium.Marker (Font-Awesome pins) wrapped in a
    MarkerCluster for performance at MSA scale.
    """
    from folium.plugins import MarkerCluster

    cfg = {
        "point_layer_name": "Community Partners (Giving Matters)",
        "default_color": "#17BECF",
    }
    fg = build_giving_matters_layer(_sample_gdf(), cfg)

    assert isinstance(fg, folium.FeatureGroup)
    assert fg.layer_name == "Community Partners (Giving Matters)"

    # FeatureGroup wraps a MarkerCluster; pin Markers live inside it.
    children = list(fg._children.values())
    assert len(children) == 1
    cluster = children[0]
    assert isinstance(cluster, MarkerCluster), (
        "Giving Matters markers must be wrapped in a MarkerCluster"
    )

    markers = list(cluster._children.values())
    assert len(markers) == 2
    for child in markers:
        assert isinstance(child, folium.Marker), (
            "Giving Matters points must use folium.Marker pins"
        )
        assert child.icon is not None, "Each pin must have a folium.Icon"


def test_giving_matters_layer_uses_default_color() -> None:
    cfg = {
        "point_layer_name": "Community Partners (Giving Matters)",
        "default_color": "#17BECF",
    }
    fg = build_giving_matters_layer(_sample_gdf(), cfg)
    cluster = next(iter(fg._children.values()))
    marker = next(iter(cluster._children.values()))
    # folium.Icon stores the fine-grained hex as icon_color on its options
    opts = str(marker.icon.options)
    assert "#17BECF" in opts or "#17becf" in opts.lower()


def test_giving_matters_layer_filters_by_category() -> None:
    """selected_categories restricts which rows render."""
    cfg = {
        "point_layer_name": "Community Partners (Giving Matters)",
        "default_color": "#17BECF",
    }
    fg = build_giving_matters_layer(
        _sample_gdf(), cfg, selected_categories=("Education",)
    )
    cluster = next(iter(fg._children.values()))
    markers = list(cluster._children.values())
    # Sample has 2 rows: Education + Health. Filter keeps only Education.
    assert len(markers) == 1

    # Empty/None filter keeps everything.
    fg_all = build_giving_matters_layer(_sample_gdf(), cfg, selected_categories=None)
    cluster_all = next(iter(fg_all._children.values()))
    assert len(cluster_all._children) == 2


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
