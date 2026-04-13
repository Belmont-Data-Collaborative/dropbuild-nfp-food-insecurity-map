"""Map assembly module.

Builds a complete Folium map with choropleth layers, partner markers,
and LayerControl. Returns cached HTML string.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import folium
import geopandas as gpd
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
    build_county_boundaries_layer,
    build_giving_matters_layer,
    build_partner_markers,
)
from src.partner_loader import load_partners

logger = logging.getLogger(__name__)

_GIVING_MATTERS_GEOJSON = Path("data/points/giving_matters.geojson")


def _giving_matters_available() -> bool:
    """Return True if data/points/giving_matters.geojson exists.

    The path is resolved relative to the current working directory so the
    Streamlit app and tests both pick up the live file.
    """
    return Path("data/points/giving_matters.geojson").exists()


@st.cache_data(ttl=3600)
def build_map_html(
    granularity: str,
    show_partners: bool,
    selected_layers: tuple[str, ...],
    show_giving_matters: bool = False,
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

    # Fit map to MSA boundary if available
    msa_boundary_path = Path("data/geo/msa_boundary.geojson")
    if msa_boundary_path.exists():
        try:
            msa_gdf = gpd.read_file(str(msa_boundary_path))
            bounds = msa_gdf.total_bounds  # [minx, miny, maxx, maxy]
            m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        except Exception:
            logger.warning("Could not fit map to MSA boundary")

    # Add county boundaries overlay (dashed lines, toggleable)
    county_boundaries_path = Path("data/geo/county_boundaries.geojson")
    if county_boundaries_path.exists():
        try:
            county_gdf = gpd.read_file(str(county_boundaries_path))
            county_fg = build_county_boundaries_layer(county_gdf)
            county_fg.add_to(m)
        except Exception:
            logger.warning("Could not load county boundaries")

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
            fg, cmap = build_choropleth_layer(gdf, layer_cfg, show=True)
            fg.add_to(m)
            colormaps[layer_cfg["display_name"]] = cmap
            has_active_layer = True

    # If no choropleth active, show plain boundaries
    if not has_active_layer:
        boundary_fg = build_boundary_layer(gdf)
        boundary_fg.add_to(m)

    # Giving Matters circle markers (only when enabled by sidebar AND geojson exists)
    if show_giving_matters and _giving_matters_available():
        try:
            from src.config_loader import get_data_sources

            gm_cfg = get_data_sources().get("giving_matters", {})
            gm_gdf = gpd.read_file(str(_GIVING_MATTERS_GEOJSON))
            gm_fg = build_giving_matters_layer(gm_gdf, gm_cfg)
            gm_fg.add_to(m)
        except (FileNotFoundError, ValueError, OSError) as exc:
            logger.warning("Could not render Giving Matters layer: %s", exc)

    # Partner markers
    partner_cfg_for_legend: dict | None = None
    if show_partners:
        try:
            partners_gdf = load_partners()
            partner_cfg = get_partner_config()
            partner_fg = build_partner_markers(partners_gdf, partner_cfg)
            partner_fg.add_to(m)
            partner_cfg_for_legend = partner_cfg
        except FileNotFoundError:
            logger.warning("Partner data not available")

    # Partner type legend on the map (always visible even when sidebar is
    # collapsed). Placed at bottomleft to avoid colliding with the
    # choropleth legend at bottomright.
    if show_partners and partner_cfg_for_legend:
        _add_partner_type_legend(m, partner_cfg_for_legend)

    # LayerControl — pinned to topleft so it never collides with the
    # bottom-right legend stack when many overlays are active.
    folium.LayerControl(position="topleft", collapsed=False).add_to(m)

    # Add legends at bottom-right (do NOT use cmap.add_to(m) — branca
    # hardcodes position: 'topright' and uses D3/SVG that breaks when
    # the DOM element is moved. See MISTAKES_DB.md G009.)
    if colormaps:
        _add_bottom_right_legends(m, colormaps, all_layers)

    return m._repr_html_()


def _rgba_to_hex(rgba: tuple) -> str:
    """Convert an RGBA tuple (0-1 floats) to a hex color string."""
    r, g, b = int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def _add_bottom_right_legends(
    m: folium.Map,
    colormaps: dict[str, Any],
    all_layer_configs: list[dict[str, Any]],
) -> None:
    """Create a single combined legend control at bottomright.

    Uses ONE L.control containing all layer legend sections. Each section
    is toggled via direct JS object reference when the in-map LayerControl
    fires overlayadd/overlayremove. This avoids:
    - Branca's hardcoded topright + D3/SVG (see G009)
    - Multiple stacked controls that reflow when one is hidden,
      shifting other legends out of the visible map area
    - querySelector matching issues

    See MISTAKES_DB.md G009 for rationale.
    """
    import json

    import branca.element

    map_var = m.get_name()

    # Build config lookup by display_name for format strings
    cfg_by_name: dict[str, dict] = {}
    for cfg in all_layer_configs:
        cfg_by_name[cfg["display_name"]] = cfg

    # Build legend data for each layer. Two shapes:
    #   continuous  -> {"kind": "continuous", "colors": [...], "vmin", "vmax"}
    #   categorical -> {"kind": "categorical", "swatches": [{"color","label"}]}
    from src.layer_manager import LegendInfo

    legends_data = []
    for name, legend in colormaps.items():
        layer_cfg = cfg_by_name.get(name, {})
        fmt = layer_cfg.get("format_str", "{:.1f}")

        if isinstance(legend, LegendInfo) and legend.categories is not None:
            swatches = [
                {"color": color, "label": label}
                for _value, (color, label) in legend.categories.items()
            ]
            legends_data.append({
                "kind": "categorical",
                "name": name,
                "swatches": swatches,
            })
            continue

        # Continuous (branca LinearColormap)
        hex_colors = [_rgba_to_hex(c) for c in legend.colors]
        try:
            vmin_label = fmt.format(legend.vmin)
            vmax_label = fmt.format(legend.vmax)
        except (ValueError, KeyError):
            vmin_label = str(legend.vmin)
            vmax_label = str(legend.vmax)

        legends_data.append({
            "kind": "continuous",
            "name": name,
            "colors": hex_colors,
            "vmin": vmin_label,
            "vmax": vmax_label,
        })

    legends_json = json.dumps(legends_data)

    js = f"""
    (function() {{
        var legendsData = {legends_json};

        // Single combined control — all layer sections in one div.
        var ctrl = L.control({{position: 'bottomright'}});
        // Direct references: layerName -> section DOM element.
        var sections = {{}};

        ctrl.onAdd = function() {{
            var container = L.DomUtil.create('div', 'info nfp-legend');
            container.style.backgroundColor = 'white';
            container.style.padding = '8px 12px';
            container.style.borderRadius = '5px';
            container.style.boxShadow = '0 0 15px rgba(0,0,0,0.2)';
            container.style.lineHeight = '1.4';
            container.style.fontSize = '12px';
            container.style.minWidth = '160px';
            container.style.maxHeight = '400px';
            container.style.overflowY = 'auto';

            for (var i = 0; i < legendsData.length; i++) {{
                var ld = legendsData[i];
                var section = document.createElement('div');
                section.setAttribute('data-layer-name', ld.name);
                if (i > 0) {{
                    section.style.marginTop = '8px';
                    section.style.paddingTop = '8px';
                    section.style.borderTop = '1px solid #eee';
                }}

                if (ld.kind === 'categorical') {{
                    var swatchHtml = '';
                    for (var j = 0; j < ld.swatches.length; j++) {{
                        var sw = ld.swatches[j];
                        swatchHtml +=
                            '<div style="display:flex;align-items:center;' +
                                'gap:6px;margin:2px 0;">' +
                                '<span style="display:inline-block;width:14px;' +
                                    'height:14px;background:' + sw.color + ';' +
                                    'border:1px solid #ccc;' +
                                    'border-radius:2px;"></span>' +
                                '<span>' + sw.label + '</span>' +
                            '</div>';
                    }}
                    section.innerHTML =
                        '<div style="font-weight:600;margin-bottom:4px;">' +
                            ld.name + '</div>' + swatchHtml;
                }} else {{
                    var gradient = ld.colors.join(', ');
                    section.innerHTML =
                        '<div style="font-weight:600;margin-bottom:4px;">' +
                            ld.name + '</div>' +
                        '<div style="display:flex;align-items:center;gap:5px;">' +
                            '<span style="white-space:nowrap;">' + ld.vmin +
                            '</span>' +
                            '<div style="flex:1;height:14px;' +
                                'background:linear-gradient(to right,' +
                                gradient + ');' +
                                'border:1px solid #ccc;border-radius:2px;' +
                                'min-width:100px;"></div>' +
                            '<span style="white-space:nowrap;">' + ld.vmax +
                            '</span>' +
                        '</div>';
                }}

                container.appendChild(section);
                // Store direct reference — no querySelector needed.
                sections[ld.name] = section;
            }}

            return container;
        }};
        ctrl.addTo({map_var});

        // Toggle individual sections when layers are toggled via the
        // in-map LayerControl (overlayadd / overlayremove).
        {map_var}.on('overlayadd', function(e) {{
            if (sections[e.name]) sections[e.name].style.display = '';
        }});
        {map_var}.on('overlayremove', function(e) {{
            if (sections[e.name]) sections[e.name].style.display = 'none';
        }});
    }})();
    """

    # Wrap in DOMContentLoaded so it runs after all map init scripts.
    # m.get_root().script renders our child before the map's own script
    # children, so the map variable doesn't exist yet at parse time.
    wrapped = f"document.addEventListener('DOMContentLoaded', function() {{{js}}});"
    m.get_root().script.add_child(branca.element.Element(wrapped))


def _add_partner_type_legend(
    m: folium.Map,
    partner_config: dict[str, Any],
) -> None:
    """Add partner type color legend to the map at bottomleft.

    This legend is always visible on the map regardless of whether the
    Streamlit sidebar is open or closed.  Uses the same DOMContentLoaded
    pattern as ``_add_bottom_right_legends`` (see MISTAKES_DB.md G009).
    """
    import json

    import branca.element

    map_var = m.get_name()
    types = partner_config.get("types", {})

    legend_items = [
        {"color": info["color"], "label": info["label"]}
        for info in types.values()
    ]
    items_json = json.dumps(legend_items)

    js = f"""
    (function() {{
        var items = {items_json};
        var ctrl = L.control({{position: 'bottomleft'}});
        ctrl.onAdd = function() {{
            var div = L.DomUtil.create('div', 'info nfp-partner-legend');
            div.style.backgroundColor = 'white';
            div.style.padding = '8px 12px';
            div.style.borderRadius = '5px';
            div.style.boxShadow = '0 0 15px rgba(0,0,0,0.2)';
            div.style.lineHeight = '1.4';
            div.style.fontSize = '12px';
            div.style.minWidth = '140px';
            div.style.maxHeight = '300px';
            div.style.overflowY = 'auto';

            var html = '<div style="font-weight:600;margin-bottom:6px;">' +
                       'NFP Partner Types</div>';
            for (var i = 0; i < items.length; i++) {{
                html +=
                    '<div style="display:flex;align-items:center;' +
                        'gap:6px;margin:3px 0;">' +
                    '<span style="display:inline-block;width:12px;' +
                        'height:12px;border-radius:50%;background:' +
                        items[i].color + ';border:1px solid ' +
                        'rgba(0,0,0,0.15);flex-shrink:0;"></span>' +
                    '<span>' + items[i].label + '</span></div>';
            }}
            div.innerHTML = html;
            return div;
        }};
        ctrl.addTo({map_var});
    }})();
    """

    wrapped = f"document.addEventListener('DOMContentLoaded', function() {{{js}}});"
    m.get_root().script.add_child(branca.element.Element(wrapped))


def _error_map_html(geo: dict, map_cfg: dict, error_msg: str) -> str:
    """Return a basic map with an error overlay."""
    m = folium.Map(
        location=geo["map_center"],
        zoom_start=geo["default_zoom"],
        tiles=map_cfg["tiles"],
        attr=map_cfg["tile_attribution"],
    )
    return m._repr_html_()
