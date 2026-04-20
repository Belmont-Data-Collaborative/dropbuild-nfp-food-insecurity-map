"""NFP Food Insecurity Map — Streamlit Application.

Interactive food insecurity mapping tool for the Nashville Food Project
and Belmont University's BDAIC.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import logging
import streamlit as st
import streamlit.components.v1 as components

from src import config
from src.config_loader import (
    get_all_layer_configs,
    get_granularities,
    get_partner_config,
    is_layer_available_for_granularity,
)
from src.map_builder import build_map_html, _giving_matters_available


def _giving_matters_count() -> int:
    """Return the feature count in data/points/giving_matters.geojson, or 0."""
    import json
    from pathlib import Path

    path = Path("data/points/giving_matters.geojson")
    if not path.exists():
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            return len(json.load(f).get("features", []))
    except (OSError, json.JSONDecodeError):
        return 0


@st.cache_data(ttl=3600)
def _giving_matters_category_ids() -> frozenset[str]:
    """Return the set of unique category ids present in the GeoJSON."""
    import json
    from pathlib import Path

    path = Path("data/points/giving_matters.geojson")
    if not path.exists():
        return frozenset()
    try:
        with open(path, "r", encoding="utf-8") as f:
            features = json.load(f).get("features", [])
        return frozenset(
            str(f.get("properties", {}).get("category", "")).strip()
            for f in features
            if f.get("properties", {}).get("category")
        )
    except (OSError, json.JSONDecodeError):
        return frozenset()

# Configure logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _configure_page() -> None:
    """Set Streamlit page config. Must be first Streamlit call."""
    st.set_page_config(
        page_title="NFP Food Insecurity Map",
        page_icon="\U0001f5fa\ufe0f",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def _inject_custom_css() -> None:
    """Inject custom CSS for branded styling."""
    st.markdown(
        """
    <style>
    /* Hide auto-generated sidebar nav so custom nav with "Home" label is used */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* Reduce default top padding */
    .stMainBlockContainer {
        padding-top: 2.5rem !important;
    }

    /* Map page header (lightweight; the branded hero lives on Home) */
    .map-page-header {
        border-left: 4px solid #2E7D32;
        padding: 0.4rem 0 0.4rem 1rem;
        margin-bottom: 1rem;
    }
    .map-page-header h2 {
        margin: 0;
        color: #1B5E20;
        font-size: 1.5rem;
    }
    .map-page-header .breadcrumb {
        font-size: 0.85rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-top: 0.2rem;
    }

    /* Sidebar section headers */
    .sidebar-section {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #666;
        margin: 1.2rem 0 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #eee;
    }

    /* Partner legend items */
    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        font-size: 0.85rem;
    }
    .legend-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
        border: 1px solid rgba(0,0,0,0.15);
    }

    /* Map container */
    iframe {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }

    /* Data source badges */
    .source-badge {
        display: inline-block;
        background: #f0f2f6;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        color: #555;
        margin: 2px;
    }

    </style>
    """,
        unsafe_allow_html=True,
    )


def _render_page_header(granularity: str) -> None:
    """Render the simple Map page header with a breadcrumb-style subtitle.

    Per spec_updates_2.md §4.3, the branded hero lives on the Home page.
    The Map page gets just a page title + a breadcrumb that reflects the
    currently selected granularity.
    """
    granularities = get_granularities()
    label = next(
        (g["label"] for g in granularities if g["id"] == granularity),
        granularity,
    )
    st.markdown(
        f"""
        <div class="map-page-header">
            <h2>Interactive Map</h2>
            <div class="breadcrumb">Nashville MSA &middot; {label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_partner_category_selector(
    types_cfg: dict[str, dict[str, str]],
) -> tuple[str, ...]:
    """Render per-category checkboxes with a colored dot beside each label.

    The selector doubles as the legend: each checkbox row shows a colored
    dot matching the pin color for that partner type. Checking a box shows
    pins of that category on the map; unchecking hides them. If every box
    is unchecked, the whole Community Partners layer is hidden.

    Returns the tuple of partner_type ids currently selected.
    """
    total = _community_partners_total()
    if total:
        st.caption(
            f"{total:,} community partners across the MSA "
            "(NFP partners + CFMT Giving Matters organizations)."
        )

    selected: list[str] = []
    for type_id, type_info in types_cfg.items():
        color = type_info.get("color", "#CCCCCC")
        label = type_info.get("label", type_id)
        col_dot, col_cbox = st.columns([1, 10], gap="small")
        with col_dot:
            st.markdown(
                f'<div style="width:14px;height:14px;background:{color};'
                f'border-radius:50%;margin-top:0.55rem;"></div>',
                unsafe_allow_html=True,
            )
        with col_cbox:
            if st.checkbox(
                label, value=True, key=f"partner_type_{type_id}",
                label_visibility="visible",
            ):
                selected.append(type_id)
    return tuple(selected)


def _community_partners_total() -> int:
    """Return NFP partner count + Giving Matters count for the caption."""
    import json
    from pathlib import Path

    total = 0
    for path in (
        Path("data/points/partners.geojson"),
        Path("data/points/giving_matters.geojson"),
    ):
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                total += len(json.load(f).get("features", []))
        except (OSError, json.JSONDecodeError):
            pass
    return total


def _render_data_freshness() -> None:
    """Render data source badges with vintage info."""
    sources = [
        ("Census ACS", "American Community Survey 2020-2024 5-Year Estimates"),
        ("CDC PLACES", "CDC PLACES 2024 Model-Based Estimates"),
        ("Partners", "Nashville Food Project Partner Directory"),
    ]
    for name, desc in sources:
        st.markdown(
            f'<span class="source-badge">{name}</span> {desc}',
            unsafe_allow_html=True,
        )


def _render_sidebar() -> tuple[str, list[str], tuple[str, ...]]:
    """Render sidebar controls and return user selections.

    Returns:
        Tuple of (granularity, selected_layers, selected_partner_categories).
        The last tuple holds the partner_type ids to render in the unified
        Community Partners layer; empty means the layer is hidden.
    """
    with st.sidebar:
        # Custom navigation with "Home" label
        st.page_link("app.py", label="Home")
        st.page_link("pages/1_Map.py", label="Map")
        st.page_link("pages/2_About_the_Data.py", label="About the Data")

        # Geographic Level
        st.markdown(
            '<div class="sidebar-section">Geographic Level</div>',
            unsafe_allow_html=True,
        )
        granularities = get_granularities()
        granularity = st.radio(
            "Select geographic level",
            options=[g["id"] for g in granularities],
            format_func=lambda x: next(
                g["label"] for g in granularities if g["id"] == x
            ),
            horizontal=True,
            label_visibility="collapsed",
        )

        # Data Layers — single indicator selection
        st.markdown(
            '<div class="sidebar-section">Data Layers</div>',
            unsafe_allow_html=True,
        )
        all_layers = get_all_layer_configs()
        available_layers = [
            l for l in all_layers
            if is_layer_available_for_granularity(l, granularity)
        ]
        unavailable_layers = [
            l for l in all_layers
            if not is_layer_available_for_granularity(l, granularity)
        ]

        layer_options = ["None"] + [l["display_name"] for l in available_layers]
        default_idx = 0
        for i, l in enumerate(available_layers):
            if l.get("default_visible", False):
                default_idx = i + 1
                break

        selected_name = st.selectbox(
            "Select indicator to display",
            options=layer_options,
            index=default_idx,
            key=f"layer_select_{granularity}",
        )

        selected_layers: list[str] = []
        if selected_name != "None":
            for l in available_layers:
                if l["display_name"] == selected_name:
                    selected_layers.append(l["column"])
                    break

        if unavailable_layers:
            names = ", ".join(l["display_name"] for l in unavailable_layers)
            st.caption(
                f"Switch to Census Tracts to view: {names}"
            )

        # Community Partners — unified NFP + Giving Matters layer.
        # Per-category checkboxes double as the color legend.
        st.markdown(
            '<div class="sidebar-section">Community Partners</div>',
            unsafe_allow_html=True,
        )
        types_cfg = get_partner_config().get("types", {})
        selected_partner_categories = _render_partner_category_selector(types_cfg)

        # Export placeholder
        st.markdown(
            '<div class="sidebar-section">Export</div>',
            unsafe_allow_html=True,
        )
        export_placeholder = st.empty()

        # Data Sources
        st.markdown(
            '<div class="sidebar-section">Data Sources</div>',
            unsafe_allow_html=True,
        )
        _render_data_freshness()

    return granularity, selected_layers, selected_partner_categories


def _render_map(
    granularity: str,
    selected_layers: list[str],
    selected_partner_categories: tuple[str, ...],
) -> None:
    """Render the Folium map and export button."""
    with st.spinner("Building map..."):
        map_html = build_map_html(
            granularity,
            tuple(selected_layers),
            selected_partner_categories=selected_partner_categories,
        )

    components.html(map_html, height=700, scrolling=False)

    # Export button in sidebar
    with st.sidebar:
        st.download_button(
            label="\u2b07 Download Map as HTML",
            data=map_html,
            file_name="nfp_food_insecurity_map.html",
            mime="text/html",
        )


def _render_nfp_logo() -> None:
    """Render NFP logo centered at top of page."""
    import base64
    from pathlib import Path

    logo_bytes = Path("assets/NFP logo.png").read_bytes()
    b64 = base64.b64encode(logo_bytes).decode()
    st.markdown(
        f'<div style="text-align:center;padding:0.5rem 0;">'
        f'<img src="data:image/png;base64,{b64}" '
        f'style="width:550px !important;max-width:100%;" />'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_bdaic_footer() -> None:
    """Render BDAIC branding at page bottom."""
    import base64
    from pathlib import Path

    logo_bytes = Path("assets/BDAIC logo.png").read_bytes()
    b64 = base64.b64encode(logo_bytes).decode()
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;'
        f'margin-top:1.5rem;padding-top:0.8rem;border-top:1px solid #eee;">'
        f'<img src="data:image/png;base64,{b64}" style="height:40px;" />'
        f'<span style="font-size:0.85rem;color:#888;">'
        f'Built by the Belmont Data &amp; AI Collaborative</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    """Render the Map page."""
    _configure_page()
    _inject_custom_css()

    granularity, selected_layers, selected_partner_categories = _render_sidebar()

    _render_nfp_logo()
    _render_page_header(granularity)
    _render_map(granularity, selected_layers, selected_partner_categories)
    _render_bdaic_footer()


main()
