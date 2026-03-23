from __future__ import annotations

import copy

import folium
import pandas as pd

from src import config
from src.layer_manager import (
    build_choropleth_layer,
    build_partner_markers,
    build_tract_boundaries_layer,
)


def _get_layer_config(layer_id: str) -> dict | None:
    """Look up a choropleth layer config by its id."""
    for layer in config.CHOROPLETH_LAYERS:
        if layer["id"] == layer_id:
            return layer
    return None


def _get_data_for_layer(
    layer_config: dict,
    census_df: pd.DataFrame | None,
    cdc_df: pd.DataFrame | None,
) -> pd.DataFrame | None:
    """Return the appropriate DataFrame for the given layer config."""
    source = layer_config["csv_source"]
    if source == "census":
        return census_df
    elif source == "cdc_places":
        return cdc_df
    return None


def build_map(
    geojson: dict,
    census_df: pd.DataFrame | None,
    cdc_df: pd.DataFrame | None,
    geocoded_df: pd.DataFrame | None,
    selected_layer_id: str | None,
    show_partners: bool,
) -> folium.Map:
    """Build the complete Folium map.

    - Centered on config.DAVIDSON_CENTER at config.DEFAULT_ZOOM.
    - Always includes tract boundary layer.
    - Adds choropleth layer if selected_layer_id is not None.
    - Adds partner markers if show_partners is True and geocoded_df is provided.
    - Adds legend colormap to bottom-right if choropleth is active.
    - Returns a folium.Map object.
    """
    m = folium.Map(
        location=config.DAVIDSON_CENTER,
        zoom_start=config.DEFAULT_ZOOM,
        tiles="cartodbpositron",
        height=700,
    )

    colormap = None
    if selected_layer_id is not None:
        layer_config = _get_layer_config(selected_layer_id)
        if layer_config is not None:
            df = _get_data_for_layer(layer_config, census_df, cdc_df)
            if df is not None and not df.empty:
                choropleth_layer, colormap = build_choropleth_layer(
                    geojson, df, layer_config
                )
                choropleth_layer.add_to(m)
            else:
                # No data available — show plain boundaries
                build_tract_boundaries_layer(geojson).add_to(m)
        else:
            build_tract_boundaries_layer(geojson).add_to(m)
    else:
        # No choropleth — add tract boundaries with "select a layer" popup
        boundary_layer = _build_no_data_boundaries(geojson)
        boundary_layer.add_to(m)

    # Add partner markers
    if show_partners and geocoded_df is not None and not geocoded_df.empty:
        markers = build_partner_markers(geocoded_df)
        for marker in markers:
            marker.add_to(m)

    # Add legend colormap
    if colormap is not None:
        colormap.add_to(m)

    return m


def _build_no_data_boundaries(geojson: dict) -> folium.GeoJson:
    """Build tract boundary layer with 'select a layer' popup when
    no choropleth is selected."""
    geojson_copy = copy.deepcopy(geojson)
    for feature in geojson_copy.get("features", []):
        props = feature.get("properties", {})
        tract_name = props.get("NAME", props.get("GEOID", ""))
        props["_popup_html"] = (
            f"<b>Census Tract {tract_name}</b> &mdash; "
            f"Select a data layer to see values."
        )

    layer = folium.GeoJson(
        geojson_copy,
        name="Census Tract Boundaries",
        style_function=lambda feature: {
            "fillColor": "transparent",
            "color": "#666666",
            "weight": 1,
            "fillOpacity": 0,
        },
        highlight_function=lambda feature: {
            "weight": 3,
            "fillOpacity": 0.3,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NAMELSAD"],
            aliases=["Census Tract:"],
            sticky=True,
        ),
    )
    layer.add_child(
        folium.GeoJsonPopup(
            fields=["_popup_html"],
            aliases=[""],
            labels=False,
            parse_html=True,
        )
    )
    return layer
