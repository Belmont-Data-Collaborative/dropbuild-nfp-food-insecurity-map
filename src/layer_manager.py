from __future__ import annotations

import warnings

import branca.colormap
import folium
import numpy as np
import pandas as pd

from src import config


def build_tract_boundaries_layer(geojson: dict) -> folium.GeoJson:
    """Build a Folium GeoJSON layer for census tract boundaries.
    Returns a single GeoJson object (NOT a tuple)."""
    return folium.GeoJson(
        geojson,
        name="Census Tract Boundaries",
        style_function=lambda feature: {
            "fillColor": "transparent",
            "color": "#666666",
            "weight": 1,
            "fillOpacity": 0,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NAMELSAD"],
            aliases=["Census Tract:"],
            sticky=True,
        ),
    )


def build_choropleth_layer(
    geojson: dict,
    df: pd.DataFrame,
    layer_config: dict,
) -> tuple[folium.GeoJson, branca.colormap.LinearColormap]:
    """Build a choropleth GeoJSON layer with YlOrRd color scale.
    Returns a 2-tuple: (GeoJson layer, LinearColormap legend).

    - Lighter = lower value, darker/redder = higher value.
    - Tracts missing from df render in neutral gray #EEEEEE.
    - Popup shows: 'Census Tract [number]', formatted value, data vintage.
    - When no data: popup shows 'Data not available for this tract.'
    """
    col = layer_config["csv_column"]
    fmt = layer_config["format_string"]
    vintage_key = layer_config["data_vintage_key"]
    display_name = layer_config["display_name"]

    # Build GEOID -> row lookup
    data_lookup: dict[str, dict] = {}
    for _, row in df.iterrows():
        geoid = str(row.get("GEOID", "")).zfill(11)
        val = row.get(col)
        vintage = row.get(vintage_key, "")
        if pd.notna(val):
            data_lookup[geoid] = {"value": float(val), "vintage": vintage}

    # Compute min/max for colormap
    values = [d["value"] for d in data_lookup.values()]
    if values:
        vmin = min(values)
        vmax = max(values)
    else:
        vmin, vmax = 0.0, 1.0

    # Create colormap
    colormap = branca.colormap.LinearColormap(
        colors=["#FFFFB2", "#FED976", "#FEB24C", "#FD8D3C", "#FC4E2A", "#E31A1C", "#B10026"],
        vmin=vmin,
        vmax=vmax,
        caption=f"{display_name}",
    )

    def style_function(feature: dict) -> dict:
        geoid = str(feature.get("properties", {}).get("GEOID", "")).zfill(11)
        entry = data_lookup.get(geoid)
        if entry is not None:
            return {
                "fillColor": colormap(entry["value"]),
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

    def popup_function(feature: dict) -> folium.Popup:
        props = feature.get("properties", {})
        geoid = str(props.get("GEOID", "")).zfill(11)
        tract_name = props.get("NAME", geoid)
        entry = data_lookup.get(geoid)
        if entry is not None:
            formatted_value = fmt.format(value=entry["value"])
            html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"{display_name}: {formatted_value}<br>"
                f"<i>{entry['vintage']}</i>"
            )
        else:
            html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"Data not available for this tract."
            )
        return folium.Popup(html, max_width=250)

    # Build GeoJSON layer with popups
    geojson_layer = folium.GeoJson(
        geojson,
        name=display_name,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["NAMELSAD"],
            aliases=["Census Tract:"],
            sticky=True,
        ),
    )

    # Add popups to each feature
    for feature in geojson_layer.data.get("features", []):
        popup = popup_function(feature)
        # We'll handle popups via the highlight_function + popup in GeoJson
        # Instead, use a different approach: add child popup to the GeoJson
        pass

    # Rebuild with popup callback using GeoJsonPopup approach
    # Use a custom approach: iterate features and build popup HTML
    geojson_layer = folium.GeoJson(
        geojson,
        name=display_name,
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["NAMELSAD"],
            aliases=["Census Tract:"],
            sticky=True,
        ),
        highlight_function=lambda feature: {
            "weight": 3,
            "fillOpacity": 0.9,
        },
    )

    # Inject popup HTML into features' properties for GeoJsonPopup
    for feature in geojson_layer.data.get("features", []):
        props = feature.get("properties", {})
        geoid = str(props.get("GEOID", "")).zfill(11)
        tract_name = props.get("NAME", geoid)
        entry = data_lookup.get(geoid)
        if entry is not None:
            formatted_value = fmt.format(value=entry["value"])
            popup_html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"{display_name}: {formatted_value}<br>"
                f"<i>{entry['vintage']}</i>"
            )
        else:
            popup_html = (
                f"<b>Census Tract {tract_name}</b><br>"
                f"Data not available for this tract."
            )
        props["_popup_html"] = popup_html

    geojson_layer.add_child(
        folium.GeoJsonPopup(
            fields=["_popup_html"],
            aliases=[""],
            labels=False,
            parse_html=True,
        )
    )

    return geojson_layer, colormap


def build_partner_markers(
    geocoded_df: pd.DataFrame,
) -> list[folium.CircleMarker]:
    """Build CircleMarker objects for geocoded partners.
    Returns a list of CircleMarker objects.

    - Colors from config.PARTNER_TYPE_COLORS.
    - Unrecognized types use config.FALLBACK_COLOR with label 'Unknown Type'.
    - Popup: organization name, display label, 'Nashville Food Project Partner'.
    - Console warning for unrecognized partner_type values.
    """
    markers: list[folium.CircleMarker] = []

    for _, row in geocoded_df.iterrows():
        lat = row.get("latitude")
        lon = row.get("longitude")

        # Skip rows without valid coordinates
        if pd.isna(lat) or pd.isna(lon):
            continue

        name = row.get("partner_name", "Unknown")
        partner_type = row.get("partner_type", "")
        geocode_status = row.get("geocode_status", "")

        if geocode_status != "success":
            continue

        # Determine color and label
        if partner_type in config.PARTNER_TYPE_COLORS:
            color = config.PARTNER_TYPE_COLORS[partner_type]
            label = config.PARTNER_TYPE_LABELS.get(
                partner_type, "Unknown Type"
            )
        else:
            color = config.FALLBACK_COLOR
            label = "Unknown Type"
            warnings.warn(
                f"Unrecognized partner_type '{partner_type}' "
                f"for partner '{name}'",
                stacklevel=2,
            )

        popup_html = (
            f"<b>{name}</b><br>"
            f"{label}<br>"
            f"<i>Nashville Food Project Partner</i>"
        )

        marker = folium.CircleMarker(
            location=[float(lat), float(lon)],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            weight=2,
            popup=folium.Popup(popup_html, max_width=250),
        )
        markers.append(marker)

    return markers
