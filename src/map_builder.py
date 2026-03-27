"""Map assembly module.

Builds a complete Folium map with choropleth layers, partner markers,
and LayerControl. Returns cached HTML string.
"""
from __future__ import annotations

import logging
from typing import Any

import folium
import streamlit as st

from src.config_loader import (
    get_all_layer_configs,
    get_geography,
    get_map_display,
    get_partner_config,
)
from src.data_loader import DataLoadError, load_geodata
from src.layer_manager import (
    build_boundary_layer,
    build_choropleth_layer,
    build_partner_markers,
)
from src.partner_loader import load_partners

logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600)
def build_map_html(
    granularity: str,
    show_partners: bool,
    selected_layers: tuple[str, ...],
) -> str:
    """Build a complete Folium map and return its HTML string.

    Cached by (granularity, show_partners, selected_layers).

    Args:
        granularity: 'tract' or 'zip'.
        show_partners: Whether to show partner markers.
        selected_layers: Tuple of selected layer column names.

    Returns:
        HTML string of the rendered map.
    """
    geo = get_geography()
    map_cfg = get_map_display()

    m = folium.Map(
        location=geo["map_center"],
        zoom_start=geo["default_zoom"],
        tiles=map_cfg["tiles"],
        attr=map_cfg["tile_attribution"],
        min_zoom=map_cfg["min_zoom"],
        max_zoom=map_cfg["max_zoom"],
    )

    # Load merged geodata
    try:
        gdf = load_geodata(granularity)
    except DataLoadError as exc:
        logger.error("Failed to load geodata: %s", exc)
        return _error_map_html(geo, map_cfg, str(exc))

    # Build choropleth layers
    colormaps = {}
    all_layers = get_all_layer_configs()
    has_active_layer = False

    for layer_cfg in all_layers:
        if layer_cfg["column"] in selected_layers:
            fg, cmap = build_choropleth_layer(gdf, layer_cfg)
            fg.add_to(m)
            colormaps[layer_cfg["display_name"]] = cmap
            has_active_layer = True

    # If no choropleth active, show plain boundaries
    if not has_active_layer:
        boundary_fg = build_boundary_layer(gdf)
        boundary_fg.add_to(m)

    # Partner markers
    if show_partners:
        try:
            partners_gdf = load_partners()
            partner_cfg = get_partner_config()
            partner_fg = build_partner_markers(partners_gdf, partner_cfg)
            partner_fg.add_to(m)
        except FileNotFoundError:
            logger.warning("Partner data not available")

    # LayerControl
    folium.LayerControl(collapsed=False).add_to(m)

    # Add colormaps as legends
    for name, cmap in colormaps.items():
        cmap.caption = name
        cmap.add_to(m)

    return m._repr_html_()


def _error_map_html(geo: dict, map_cfg: dict, error_msg: str) -> str:
    """Return a basic map with an error overlay."""
    m = folium.Map(
        location=geo["map_center"],
        zoom_start=geo["default_zoom"],
        tiles=map_cfg["tiles"],
        attr=map_cfg["tile_attribution"],
    )
    return m._repr_html_()
