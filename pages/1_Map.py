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


def _render_partner_legend() -> None:
    """Render partner type legend with colored dots."""
    partner_cfg = get_partner_config()
    for type_key, type_info in partner_cfg["types"].items():
        st.markdown(
            f'<div class="legend-item">'
            f'<span class="legend-dot" style="background-color: '
            f'{type_info["color"]};"></span>'
            f'{type_info["label"]}'
            f"</div>",
            unsafe_allow_html=True,
        )


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


def _render_sidebar() -> tuple[str, bool, list[str], bool]:
    """Render sidebar controls and return user selections.

    Returns:
        Tuple of (granularity, show_partners, selected_layers, show_giving_matters).
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

        # Partner Locations
        st.markdown(
            '<div class="sidebar-section">Partner Locations</div>',
            unsafe_allow_html=True,
        )
        show_partners = st.checkbox("Show NFP Partners", value=True)

        if show_partners:
            _render_partner_legend()

        # Community Partners (Giving Matters) — only when data is available
        show_giving_matters = False
        if _giving_matters_available():
            st.markdown(
                '<div class="sidebar-section">Community Partners</div>',
                unsafe_allow_html=True,
            )
            show_giving_matters = st.checkbox(
                "Show Giving Matters Partners",
                value=False,
            )
            if show_giving_matters:
                gm_count = _giving_matters_count()
                if gm_count:
                    st.caption(
                        f"{gm_count:,} organizations from CFMT Giving Matters, "
                        "colored by NFP partner category."
                    )
                else:
                    st.caption("Organizations from CFMT Giving Matters database")

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

    return granularity, show_partners, selected_layers, show_giving_matters


def _render_map(
    granularity: str,
    show_partners: bool,
    selected_layers: list[str],
    show_giving_matters: bool,
) -> None:
    """Render the Folium map and export button."""
    with st.spinner("Building map..."):
        map_html = build_map_html(
            granularity,
            show_partners,
            tuple(selected_layers),
            show_giving_matters=show_giving_matters,
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

    granularity, show_partners, selected_layers, show_giving_matters = _render_sidebar()

    _render_nfp_logo()
    _render_page_header(granularity)
    _render_map(granularity, show_partners, selected_layers, show_giving_matters)
    _render_bdaic_footer()


main()
