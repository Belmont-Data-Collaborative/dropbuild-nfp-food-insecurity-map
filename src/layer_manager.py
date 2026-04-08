"""Folium map layer builders.

Builds choropleth layers, partner pin markers, and boundary layers
as named FeatureGroups for LayerControl toggling.
"""
from __future__ import annotations

import logging
from typing import Any

from dataclasses import dataclass, field

import branca.colormap
import folium
import geopandas as gpd
import numpy as np
import pandas as pd


@dataclass
class LegendInfo:
    """Legend metadata returned by layer builders for the legend control.

    For continuous layers: colors is a list of RGBA tuples, vmin/vmax are set.
    For categorical layers: categories maps value → (color_hex, label).
    """

    colors: list = field(default_factory=list)
    vmin: float = 0.0
    vmax: float = 1.0
    caption: str = ""
    categories: dict[int | str, tuple[str, str]] | None = None

logger = logging.getLogger(__name__)

# Mapping of folium.Icon preset color names to approximate hex values
_ICON_COLOR_MAP = {
    "#E41A1C": "red",
    "#377EB8": "blue",
    "#4DAF4A": "green",
    "#984EA3": "purple",
    "#FF7F00": "orange",
    "#A65628": "darkred",
    "#F781BF": "pink",
    "#999999": "gray",
}


def _hex_to_icon_color(hex_color: str) -> str:
    """Map hex color to nearest folium.Icon preset color."""
    return _ICON_COLOR_MAP.get(hex_color, "blue")


def build_partner_markers(
    partners_gdf: gpd.GeoDataFrame,
    partner_config: dict[str, Any],
) -> folium.FeatureGroup:
    """Build pin markers for partner locations as a toggleable FeatureGroup.

    Uses folium.Marker with folium.Icon (Font Awesome) for each partner.
    Each partner type gets a distinct colored pin.

    Args:
        partners_gdf: GeoDataFrame with partner_name, partner_type, geometry.
        partner_config: Partner configuration from project.yml.

    Returns:
        FeatureGroup containing all partner Markers.
    """
    fg = folium.FeatureGroup(name="NFP Partners", show=True)
    types_cfg = partner_config.get("types", {})
    fallback_color = "#CCCCCC"

    for _, row in partners_gdf.iterrows():
        if row.geometry is None:
            continue

        partner_type = row.get("partner_type", "unknown")
        type_cfg = types_cfg.get(partner_type, {})
        color = type_cfg.get("color", fallback_color)
        icon_name = type_cfg.get("icon", "map-marker")
        label = type_cfg.get("label", partner_type)

        if partner_type not in types_cfg:
            label = "Unknown Type"
            logger.warning(
                "Unrecognized partner_type '%s' for partner '%s'",
                partner_type,
                row.get("partner_name", "Unknown"),
            )

        popup_html = (
            f'<div style="min-width: 200px;">'
            f'<strong>{row.get("partner_name", "Unknown")}</strong><br>'
            f"<em>{label}</em><br>"
            f'{row.get("address", "")}'
            f"</div>"
        )

        icon_color = _hex_to_icon_color(color)

        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row.get("partner_name", ""),
            icon=folium.Icon(
                color=icon_color,
                icon_color=color,
                icon=icon_name,
                prefix="fa",
            ),
        ).add_to(fg)

    return fg


# Two-tone palette for binary LILA flag and other 0/1 categorical layers.
# Index 0 → "negative" (light gray), index 1 → "positive" (dark red).
_CATEGORICAL_TWO_TONE = ["#EEEEEE", "#B71C1C"]


def _categorical_color_for(value: Any, categories: dict[Any, str]) -> str:
    """Map a category value to a hex color from the two-tone palette."""
    keys = sorted(categories.keys(), key=lambda k: (str(type(k).__name__), k))
    try:
        idx = keys.index(value)
    except ValueError:
        return "#CCCCCC"
    if idx < len(_CATEGORICAL_TWO_TONE):
        return _CATEGORICAL_TWO_TONE[idx]
    return "#CCCCCC"


def _build_categorical_layer(
    gdf: gpd.GeoDataFrame,
    layer_config: dict[str, Any],
    *,
    visible: bool,
) -> tuple[folium.FeatureGroup, LegendInfo]:
    """Render a categorical choropleth using discrete two-tone colors."""
    col = layer_config["column"]
    display_name = layer_config["display_name"]
    categories: dict[Any, str] = dict(layer_config.get("categories", {}))

    fg = folium.FeatureGroup(name=display_name, show=visible)

    # GEOID -> raw category value
    data_lookup: dict[str, Any] = {}
    if col in gdf.columns:
        for _, row in gdf.iterrows():
            geoid = str(row.get("GEOID", "")).zfill(11)
            val = row.get(col)
            if pd.notna(val):
                # Coerce floats like 1.0 to int when keys are ints
                if isinstance(val, float) and val.is_integer():
                    val = int(val)
                data_lookup[geoid] = val

    def style_function(feature: dict) -> dict:
        geoid = str(feature.get("properties", {}).get("GEOID", "")).zfill(11)
        val = data_lookup.get(geoid)
        if val is None:
            return {
                "fillColor": "#EEEEEE",
                "color": "#666666",
                "weight": 1,
                "fillOpacity": 0.5,
            }
        return {
            "fillColor": _categorical_color_for(val, categories),
            "color": "#666666",
            "weight": 1,
            "fillOpacity": 0.7,
        }

    # Popup HTML using the human-readable category label
    geojson_data = json.loads(gdf.to_json())
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        geoid = str(props.get("GEOID", "")).zfill(11)
        tract_name = props.get("NAME", geoid)
        val = data_lookup.get(geoid)
        if val is None:
            popup_html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"Data not available for this tract."
            )
        else:
            label = categories.get(val, str(val))
            popup_html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"{display_name}: {label}"
            )
        props["_popup_html"] = popup_html

    geojson_layer = folium.GeoJson(
        geojson_data,
        name=display_name,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["NAMELSAD"] if "NAMELSAD" in gdf.columns else ["NAME"],
            aliases=["Area:"],
            sticky=True,
        ),
        highlight_function=lambda feature: {"weight": 3, "fillOpacity": 0.9},
    )
    geojson_layer.add_child(
        folium.GeoJsonPopup(
            fields=["_popup_html"],
            aliases=[""],
            labels=False,
            parse_html=True,
        )
    )
    geojson_layer.add_to(fg)

    # Build legend info: categories dict maps value -> (color_hex, label)
    legend_categories: dict[Any, tuple[str, str]] = {}
    for value, label in categories.items():
        legend_categories[value] = (_categorical_color_for(value, categories), label)

    legend = LegendInfo(
        colors=[],
        vmin=0.0,
        vmax=1.0,
        caption=layer_config.get("legend_name", display_name),
        categories=legend_categories,
    )
    return fg, legend


def build_choropleth_layer(
    gdf: gpd.GeoDataFrame,
    layer_config: dict[str, Any],
    *,
    show: bool | None = None,
) -> tuple[folium.FeatureGroup, Any]:
    """Build a choropleth FeatureGroup. Dispatches to categorical or continuous renderer.

    Returns:
        (FeatureGroup, LegendInfo)  for ``layer_type: categorical``
        (FeatureGroup, LinearColormap)  for ``layer_type: continuous`` (default)
    """
    if layer_config.get("layer_type", "continuous") == "categorical":
        visible = show if show is not None else layer_config.get("default_visible", False)
        return _build_categorical_layer(gdf, layer_config, visible=visible)
    return _build_continuous_layer(gdf, layer_config, show=show)


def _build_continuous_layer(
    gdf: gpd.GeoDataFrame,
    layer_config: dict[str, Any],
    *,
    show: bool | None = None,
) -> tuple[folium.FeatureGroup, branca.colormap.LinearColormap]:
    """Build a single choropleth layer as a toggleable FeatureGroup.

    Args:
        gdf: Merged GeoDataFrame with geometry + data columns.
        layer_config: Variable configuration from project.yml.
        show: If provided, overrides default_visible for the FeatureGroup.

    Returns:
        Tuple of (FeatureGroup, LinearColormap) for the layer.
    """
    col = layer_config["column"]
    display_name = layer_config["display_name"]
    colormap_name = layer_config.get("colormap", "YlOrRd")
    format_str = layer_config.get("format_str", "{:.1f}")
    tooltip_alias = layer_config.get("tooltip_alias", display_name)
    default_visible = layer_config.get("default_visible", False)

    visible = show if show is not None else default_visible

    fg = folium.FeatureGroup(
        name=display_name,
        show=visible,
    )

    # Get values for colormap
    if col in gdf.columns:
        values = gdf[col].dropna()
    else:
        values = pd.Series(dtype=float)

    if len(values) == 0:
        vmin, vmax = 0.0, 1.0
    else:
        vmin = float(values.min())
        vmax = float(values.max())

    # Build colormap from branca named colormaps
    colormap = _build_colormap(colormap_name, vmin, vmax, display_name)

    # Build GEOID -> value lookup
    data_lookup: dict[str, float] = {}
    if col in gdf.columns:
        for _, row in gdf.iterrows():
            geoid = str(row.get("GEOID", "")).zfill(11)
            val = row.get(col)
            if pd.notna(val):
                data_lookup[geoid] = float(val)

    def style_function(feature: dict) -> dict:
        geoid = str(feature.get("properties", {}).get("GEOID", "")).zfill(11)
        val = data_lookup.get(geoid)
        if val is not None:
            return {
                "fillColor": colormap(val),
                "color": "#666666",
                "weight": 1,
                "fillOpacity": 0.7,
            }
        return {
            "fillColor": "#EEEEEE",
            "color": "#666666",
            "weight": 1,
            "fillOpacity": 0.5,
        }

    # Build popup HTML into properties
    geojson_data = json.loads(gdf.to_json())
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        geoid = str(props.get("GEOID", "")).zfill(11)
        tract_name = props.get("NAME", geoid)
        val = data_lookup.get(geoid)
        if val is not None:
            try:
                formatted = format_str.format(val)
            except (ValueError, KeyError):
                formatted = str(val)
            popup_html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"{display_name}: {formatted}"
            )
        else:
            popup_html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"Data not available for this tract."
            )
        props["_popup_html"] = popup_html

    geojson_layer = folium.GeoJson(
        geojson_data,
        name=display_name,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["NAMELSAD"] if "NAMELSAD" in gdf.columns else ["NAME"],
            aliases=["Area:"],
            sticky=True,
        ),
        highlight_function=lambda feature: {
            "weight": 3,
            "fillOpacity": 0.9,
        },
    )

    geojson_layer.add_child(
        folium.GeoJsonPopup(
            fields=["_popup_html"],
            aliases=[""],
            labels=False,
            parse_html=True,
        )
    )

    geojson_layer.add_to(fg)
    return fg, colormap


def _build_colormap(
    name: str, vmin: float, vmax: float, caption: str
) -> branca.colormap.LinearColormap:
    """Build a LinearColormap from a named color scheme."""
    color_schemes = {
        "YlOrRd": ["#FFFFB2", "#FED976", "#FEB24C", "#FD8D3C", "#FC4E2A", "#E31A1C", "#B10026"],
        "YlGnBu": ["#FFFFCC", "#C7E9B4", "#7FCDBB", "#41B6C4", "#1D91C0", "#225EA8", "#0C2C84"],
        "Blues":  ["#EFF3FF", "#C6DBEF", "#9ECAE1", "#6BAED6", "#4292C6", "#2171B5", "#084594"],
        "Reds":   ["#FEE5D9", "#FCBBA1", "#FC9272", "#FB6A4A", "#EF3B2C", "#CB181D", "#99000D"],
        "OrRd":   ["#FEF0D9", "#FDD49E", "#FDBB84", "#FC8D59", "#EF6548", "#D7301F", "#990000"],
        "PuRd":   ["#F1EEF6", "#D4B9DA", "#C994C7", "#DF65B0", "#E7298A", "#CE1256", "#91003F"],
        "BuPu":   ["#EDF8FB", "#BFD3E6", "#9EBCDA", "#8C96C6", "#8C6BB1", "#88419D", "#6E016B"],
        "YlOrBr": ["#FFFFD4", "#FEE391", "#FEC44F", "#FE9929", "#EC7014", "#CC4C02", "#8C2D04"],
        "GnBu":   ["#F0F9E8", "#CCEBC5", "#A8DDB5", "#7BCCC4", "#4EB3D3", "#2B8CBE", "#08589E"],
        "Purples":["#F2F0F7", "#DADAEB", "#BCBDDC", "#9E9AC8", "#807DBA", "#6A51A3", "#4A1486"],
        "Greens": ["#EDF8E9", "#C7E9C0", "#A1D99B", "#74C476", "#41AB5D", "#238B45", "#005A32"],
    }
    colors = color_schemes.get(name, color_schemes["YlOrRd"])
    return branca.colormap.LinearColormap(
        colors=colors,
        vmin=vmin,
        vmax=vmax,
        caption=caption,
    )


def build_boundary_layer(
    gdf: gpd.GeoDataFrame,
) -> folium.FeatureGroup:
    """Build a boundary-only layer with 'select a layer' popups.

    Used when no choropleth is active.
    """
    fg = folium.FeatureGroup(name="Boundaries", show=True)

    geojson_data = json.loads(gdf.to_json())
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        tract_name = props.get("NAME", props.get("GEOID", ""))
        props["_popup_html"] = (
            f"<b>Census Tract {tract_name}</b> &mdash; "
            f"Select a data layer to see values."
        )

    layer = folium.GeoJson(
        geojson_data,
        name="Boundaries",
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
            fields=["NAMELSAD"] if "NAMELSAD" in geojson_data.get("features", [{}])[0].get("properties", {}) else ["NAME"],
            aliases=["Area:"],
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
    layer.add_to(fg)
    return fg


def build_giving_matters_layer(
    gdf: gpd.GeoDataFrame,
    config: dict[str, Any],
) -> folium.FeatureGroup:
    """Render Giving Matters organizations as circle markers.

    Per spec_updates_2.md §3.4, circle markers are used (not pin markers) so
    the layer visually distinguishes from NFP partner pins. Toggleable via
    LayerControl.

    Args:
        gdf: GeoDataFrame with Point geometry; expected columns may include
            ``name``, ``address``, ``category``.
        config: ``data_sources.giving_matters`` from project.yml.

    Returns:
        FeatureGroup of CircleMarkers.
    """
    layer_name = config.get("point_layer_name", "Community Partners (Giving Matters)")
    color = config.get("default_color", "#17BECF")

    fg = folium.FeatureGroup(name=layer_name, show=False)

    for _, row in gdf.iterrows():
        if row.geometry is None:
            continue

        name = row.get("name", "Community Partner")
        address = row.get("address", "")
        category = row.get("category", "")
        popup_html = (
            f'<div style="min-width: 200px;">'
            f"<strong>{name}</strong><br>"
        )
        if category:
            popup_html += f"<em>{category}</em><br>"
        if address:
            popup_html += f"{address}"
        popup_html += "</div>"

        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            weight=1,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=str(name),
        ).add_to(fg)

    return fg


def build_county_boundaries_layer(
    county_gdf: gpd.GeoDataFrame,
) -> folium.FeatureGroup:
    """Render MSA county boundaries as a reference overlay.

    Displays dashed boundary lines so they don't visually compete with
    tract-level choropleth shading. Toggleable via LayerControl.
    """
    fg = folium.FeatureGroup(name="County Boundaries", show=True)
    folium.GeoJson(
        json.loads(county_gdf.to_json()),
        style_function=lambda x: {
            "fillColor": "transparent",
            "color": "#333333",
            "weight": 2,
            "dashArray": "5,5",
        },
        tooltip=folium.GeoJsonTooltip(fields=["NAME"], aliases=["County:"]),
    ).add_to(fg)
    return fg


# Required for json.loads in build_choropleth_layer
import json
