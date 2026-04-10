"""Regression test: every continuous choropleth layer must use a distinct
colormap so users can tell layers apart at a glance.

Categorical layers are excluded from the uniqueness check (they use the
discrete two-tone palette and don't share the gradient namespace).
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# Mock streamlit before importing src
_st_mock = MagicMock()
_st_mock.cache_data = lambda f=None, **kw: f if f else lambda g: g
_st_mock.cache_resource = lambda f=None, **kw: f if f else lambda g: g
_st_mock.secrets = {}
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("streamlit_folium", MagicMock())

from src.config_loader import get_all_layer_configs, get_layer_type  # noqa: E402
from src.layer_manager import _build_colormap  # noqa: E402


def _continuous_layers() -> list[dict]:
    return [
        layer for layer in get_all_layer_configs()
        if get_layer_type(layer) != "categorical"
    ]


def test_every_continuous_layer_has_unique_colormap() -> None:
    layers = _continuous_layers()
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for layer in layers:
        cmap = layer.get("colormap", "YlOrRd")
        if cmap in seen:
            duplicates.append(
                f"{layer['display_name']!r} reuses {cmap} (also {seen[cmap]!r})"
            )
        else:
            seen[cmap] = layer["display_name"]
    assert not duplicates, "Duplicate colormaps:\n  " + "\n  ".join(duplicates)


def test_every_colormap_is_registered_in_layer_manager() -> None:
    """Each colormap referenced in project.yml must be defined in
    layer_manager._build_colormap (otherwise it falls back to YlOrRd silently
    and we lose the uniqueness guarantee)."""
    for layer in _continuous_layers():
        name = layer.get("colormap", "YlOrRd")
        cmap = _build_colormap(name, 0.0, 1.0, "test")
        # Build a known reference and compare hex colors. If the requested
        # name is not registered, _build_colormap silently falls back to YlOrRd.
        ylorrd = _build_colormap("YlOrRd", 0.0, 1.0, "test")
        if name != "YlOrRd":
            assert cmap.colors != ylorrd.colors, (
                f"Colormap {name!r} (used by {layer['display_name']!r}) "
                f"is not registered in _build_colormap — silently falling "
                f"back to YlOrRd."
            )
