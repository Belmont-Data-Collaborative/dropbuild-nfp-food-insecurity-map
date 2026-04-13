"""NFP Food Insecurity Map — Home Page (multi-page app entry point).

Per spec_updates_2.md §4.2, this is the cover/landing page for the
multi-page Streamlit application. Map functionality lives in pages/1_Map.py.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import json
import logging
from datetime import datetime
from pathlib import Path

import streamlit as st

from src import config
from src.config_loader import (
    get_all_layer_configs,
    get_geography,
    get_project,
)

# Configure logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _configure_page() -> None:
    """Set Streamlit page config. Must be the first Streamlit call."""
    st.set_page_config(
        page_title="NFP Food Insecurity Map",
        page_icon="\U0001f5fa\ufe0f",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def _inject_custom_css() -> None:
    """Inject custom CSS for the branded landing page."""
    st.markdown(
        """
    <style>
    /* Hide auto-generated sidebar nav so custom nav with "Home" label is used */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* NFP logo text fallback */
    .nfp-logo-text {
        text-align: center;
        padding: 0.3rem 0 0.5rem;
    }
    .nfp-logo-text span {
        font-size: 1.3rem;
        font-weight: 700;
        color: #2E7D32;
    }

    .home-hero {
        background: linear-gradient(135deg, #2E7D32, #1B5E20);
        color: white;
        padding: 2.5rem 2rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .home-hero h1 {
        margin: 0;
        font-size: 2.4rem;
        font-weight: 700;
    }
    .home-hero p.subtitle {
        margin: 0.5rem 0 0;
        opacity: 0.92;
        font-size: 1.1rem;
    }
    .home-description {
        font-size: 1.05rem;
        line-height: 1.6;
        color: #333;
        max-width: 900px;
        margin: 0 auto 1.5rem;
        text-align: center;
    }
    .nav-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-left: 4px solid #2E7D32;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .nav-card h3 { margin: 0 0 0.4rem; color: #1B5E20; font-size: 1.15rem; }
    .nav-card p  { margin: 0; color: #555; font-size: 0.92rem; }
    .stats-bar {
        background: #f7f9f7;
        border: 1px solid #e0e8e0;
        border-radius: 8px;
        padding: 1rem 1.5rem;
        margin: 1.5rem 0;
        text-align: center;
        font-size: 0.95rem;
        color: #444;
    }
    .stats-bar strong { color: #1B5E20; }
    .branding-row {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 0.5rem;
        margin: 1.5rem 0 0.5rem;
        color: #888;
        font-size: 0.82rem;
    }
    .branding-row img { height: 28px; width: auto; }
    .freshness {
        text-align: center;
        font-size: 0.82rem;
        color: #888;
        margin-top: 0.5rem;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _gather_key_stats() -> dict[str, int | str]:
    """Compute dynamic stats for the landing-page summary bar."""
    geo = get_geography()
    counties = len(geo.get("msa_counties", [])) or 1

    tracts = 0
    tracts_path = Path("data/geo/tracts.geojson")
    if tracts_path.exists():
        try:
            with open(tracts_path, "r", encoding="utf-8") as f:
                tracts = len(json.load(f).get("features", []))
        except (OSError, json.JSONDecodeError):
            tracts = 0

    indicators = len(get_all_layer_configs())

    partners = 0
    partners_path = Path("data/points/partners.geojson")
    if partners_path.exists():
        try:
            with open(partners_path, "r", encoding="utf-8") as f:
                partners = len(json.load(f).get("features", []))
        except (OSError, json.JSONDecodeError):
            partners = 0

    return {
        "counties": counties,
        "tracts": tracts,
        "indicators": indicators,
        "partners": partners,
    }


def _last_pipeline_run() -> str:
    """Return the most recent mtime among the choropleth parquet outputs."""
    parquet_dir = Path("data/choropleth")
    if not parquet_dir.exists():
        return "unknown"
    files = list(parquet_dir.glob("*.parquet"))
    if not files:
        return "unknown"
    latest = max(f.stat().st_mtime for f in files)
    return datetime.fromtimestamp(latest).strftime("%Y-%m-%d")


def _render_nfp_logo() -> None:
    """Render NFP logo at top of page. Uses image if available, else text."""
    logo_path = Path("assets/nfp_logo.png")
    if logo_path.exists():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(str(logo_path), width=250)
    else:
        st.markdown(
            '<div class="nfp-logo-text">'
            "<span>Nashville Food Project</span></div>",
            unsafe_allow_html=True,
        )


def _render_hero() -> None:
    project = get_project()
    st.markdown(
        f"""
        <div class="home-hero">
            <h1>{project['name']}</h1>
            <p class="subtitle">A strategic planning tool for the Nashville Food Project</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_description() -> None:
    st.markdown(
        """
        <div class="home-description">
            This interactive mapping tool helps the Nashville Food Project and
            its partners understand where food insecurity is concentrated across
            the 14-county Nashville metropolitan area. It overlays Census income
            and poverty data, CDC health indicators, USDA food-access measures,
            and existing NFP partner locations to support data-informed decisions
            about where to grow the partner network.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_stats_bar() -> None:
    stats = _gather_key_stats()
    st.markdown(
        f"""
        <div class="stats-bar">
            Covering <strong>{stats['counties']}</strong> counties &middot;
            <strong>{stats['tracts']:,}</strong> census tracts &middot;
            <strong>{stats['indicators']}</strong> data indicators &middot;
            <strong>{stats['partners']}</strong> NFP partner locations
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_nav_cards() -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="nav-card">
                <h3>\U0001f5fa\ufe0f  Interactive Map</h3>
                <p>Explore food insecurity indicators across the Nashville MSA
                with toggleable layers, partner locations, and choropleth views
                at tract or ZIP-code granularity.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            st.page_link("pages/1_Map.py", label="Open the Map", icon="\u27a1\ufe0f")
        except Exception:
            st.caption("Open the **Map** page from the sidebar.")

    with col2:
        st.markdown(
            """
            <div class="nav-card">
                <h3>\U0001f4d6  About the Data</h3>
                <p>Methodology, vintage dates, and source documentation for every
                dataset shown on the map &mdash; including the LILA 2010\u219220 tract
                conversion and known limitations.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            st.page_link(
                "pages/2_About_the_Data.py",
                label="View Data Documentation",
                icon="\u27a1\ufe0f",
            )
        except Exception:
            st.caption("Open the **About the Data** page from the sidebar.")


def _render_branding_and_freshness() -> None:
    bdaic_logo = Path("assets/bdaic_logo.png")
    logo_html = ""
    if bdaic_logo.exists():
        logo_html = f'<img src="app/static/{bdaic_logo.name}" alt="BDAIC">'
    st.markdown(
        f"""
        <div class="branding-row">
            {logo_html}
            <span>Built by the Belmont Data & AI Collaborative</span>
        </div>
        <div class="freshness">Data last updated: {_last_pipeline_run()}</div>
        """,
        unsafe_allow_html=True,
    )


def _render_custom_nav() -> None:
    """Render custom sidebar navigation with 'Home' instead of 'app'."""
    with st.sidebar:
        st.page_link("app.py", label="Home")
        st.page_link("pages/1_Map.py", label="Map")
        st.page_link("pages/2_About_the_Data.py", label="About the Data")


def main() -> None:
    """Render the Home page."""
    _configure_page()
    _inject_custom_css()
    _render_custom_nav()
    _render_nfp_logo()
    _render_hero()
    _render_description()
    _render_stats_bar()
    _render_nav_cards()
    _render_branding_and_freshness()


if __name__ == "__main__":
    main()
else:
    # Streamlit executes the script top-to-bottom; call main() unconditionally.
    main()
