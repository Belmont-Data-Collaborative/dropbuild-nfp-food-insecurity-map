"""About the Data page — methodology, sources, vintage, limitations.

Per spec_updates_2.md §4.4. Reference documentation for every dataset shown
on the Map page, plus the Nashville MSA geographic coverage and the LILA
2010\u219220 tract crosswalk methodology.
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import logging
from datetime import datetime
from pathlib import Path

import streamlit as st

from src import config
from src.config_loader import get_geography

logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def _configure_page() -> None:
    st.set_page_config(
        page_title="About the Data \u2014 NFP Food Insecurity Map",
        page_icon="\U0001f4d6",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def _inject_custom_css() -> None:
    st.markdown(
        """
    <style>
    /* Hide auto-generated sidebar nav so custom nav with "Home" label is used */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* Reduce default top padding */
    .stMainBlockContainer {
        padding-top: 0 !important;
    }

    .docs-header {
        border-left: 4px solid #2E7D32;
        padding: 0.4rem 0 0.4rem 1rem;
        margin-bottom: 1rem;
    }
    .docs-header h2 { margin: 0; color: #1B5E20; font-size: 1.5rem; }
    .docs-header .breadcrumb {
        font-size: 0.85rem; color: #666;
        text-transform: uppercase; letter-spacing: 0.04em;
        margin-top: 0.2rem;
    }
    .docs-section { max-width: 900px; }
    .freshness {
        color: #888; font-size: 0.82rem; text-align: right;
        margin-top: 1.5rem; padding-top: 0.5rem;
        border-top: 1px solid #eee;
    }

    </style>
    """,
        unsafe_allow_html=True,
    )


def _last_pipeline_run() -> str:
    parquet_dir = Path("data/choropleth")
    if not parquet_dir.exists():
        return "unknown"
    files = list(parquet_dir.glob("*.parquet"))
    if not files:
        return "unknown"
    return datetime.fromtimestamp(
        max(f.stat().st_mtime for f in files)
    ).strftime("%Y-%m-%d")


def _render_header() -> None:
    st.markdown(
        """
        <div class="docs-header">
            <h2>About the Data</h2>
            <div class="breadcrumb">Methodology &middot; Sources &middot; Limitations</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_overview() -> None:
    st.markdown(
        """
        This tool combines public datasets on income, poverty, health, and food
        access with the Nashville Food Project's partner directory to support
        strategic decisions about where food insecurity is concentrated and where
        NFP should consider growing its partner network. Each data source on the
        map is documented below, including its vintage, geographic granularity,
        and known limitations.
        """
    )


def _render_data_sources() -> None:
    st.subheader("Data Sources")

    with st.expander("Census ACS (American Community Survey)"):
        st.markdown(
            """
            - **What it measures:** household income, poverty rate, total population
            - **Vintage:** 2020\u20132024 5-Year Estimates
            - **Geography:** Census tract and ZIP code (ZCTA)
            - **Source:** U.S. Census Bureau via data.census.gov
            - **Update frequency:** Annual rolling 5-year estimates
            """
        )

    with st.expander("CDC PLACES (Health Indicators)"):
        st.markdown(
            """
            - **What it measures:** diabetes, hypertension, and obesity prevalence
            - **Vintage:** 2024 model-based estimates
            - **Geography:** Census tract and ZIP code (ZCTA)
            - **Source:** CDC PLACES (places.cdc.gov)
            - **Methodology note:** Model-based small-area estimates derived from
              BRFSS survey data \u2014 not direct measurements. Values should be
              interpreted as estimates with uncertainty.
            """
        )

    with st.expander("USDA Food Access Research Atlas (LILA)"):
        st.markdown(
            """
            - **What it measures:** Low Income, Low Access to supermarkets
            - **Vintage:** Based on **2019 ACS** data and **2010 Census tract boundaries**
            - **Geography:** Census tract only (not available at ZIP level)
            - **Source:** USDA Economic Research Service
            """
        )
        st.markdown("**Boundary conversion methodology**")
        st.markdown(
            """
            The original LILA data uses 2010 Census tract boundaries, which differ
            from the 2020 boundaries used by this tool's map. BDAIC converted LILA
            estimates from 2010 to 2020 tract boundaries using the U.S. Census
            Bureau's official **2010-to-2020 Census Tract Relationship File**.

            - **Binary LILA designation flags** (e.g. *LILA Tracts 1 & 10 mi*) use a
              conservative approach: a 2020 tract is flagged as LILA if **any**
              contributing 2010 tract was designated LILA.
            - **Population counts** (e.g. *Low Access Population*) use **area-weighted
              apportionment** \u2014 each 2010 tract's count is multiplied by the
              fraction of its land area falling inside the 2020 tract, then summed.
            - **Rates and percentages** use **area-weighted averages**.
            - Tiny intersection slivers (\u003c1% of the 2010 tract's area) are
              filtered out to remove boundary noise.
            - 2020 tracts with no 2010 LILA match are shown as missing data.

            **Why this matters:** Census tracts are redrawn every decade. Between
            2010 and 2020 some tracts were split, merged, or had boundary
            adjustments. The crosswalk accounts for these changes, but LILA values
            on the map are *modeled approximations on 2020 geography*, not direct
            measurements. Treat them as estimates rather than exact figures.
            """
        )

    with st.expander("NFP Partner Locations"):
        st.markdown(
            """
            - **What it shows:** geocoded locations of Nashville Food Project partner
              organizations
            - **Categories:** 8 partner types (school/summer, medical/health,
              transitional housing, senior services, community development,
              homeless outreach, workforce development, after-school)
            - **Source:** Nashville Food Project partner directory
            - **Update process:** addresses are geocoded via Nominatim and cached
              in S3; geocoding accuracy depends on the address quality of source
              records, so some locations may be approximate.
            """
        )

    with st.expander("Giving Matters (Community Foundation of Middle Tennessee)"):
        st.markdown(
            """
            - **What it shows:** nonprofit and community organization locations from
              the CFMT Giving Matters database
            - **Source:** Community Foundation of Middle Tennessee
            - **Status:** **Integration pending** \u2014 data not yet received from CFMT.
              The pipeline is wired and will activate automatically once the
              dataset is uploaded to S3 and the column mapping is finalized.
            """
        )


def _render_geographic_coverage() -> None:
    st.subheader("Geographic Coverage")
    geo = get_geography()
    msa_name = geo.get("msa_name", "Nashville MSA")
    counties = geo.get("msa_counties", [])
    st.markdown(
        f"""
        The map covers the **{msa_name} Metropolitan Statistical Area** as defined
        by the U.S. Office of Management and Budget. This consists of
        **{len(counties)} counties** in Tennessee:
        """
    )
    cols = st.columns(2)
    half = (len(counties) + 1) // 2
    for i, county in enumerate(counties):
        target = cols[0] if i < half else cols[1]
        target.markdown(f"- {county.get('name', county.get('fips', ''))}")
    st.caption(
        "Note: not every dataset covers every tract. LILA in particular may "
        "have missing values for tracts that did not exist in 2010 boundaries."
    )


def _render_limitations() -> None:
    st.subheader("Limitations and Caveats")
    st.markdown(
        """
        - **Data vintage varies** across sources (2019 LILA, 2020\u20132024 ACS,
          2024 CDC PLACES). Year-over-year comparisons across sources should be
          made carefully.
        - **LILA uses older tract boundaries** than the other datasets and is
          presented as a modeled approximation on 2020 geography.
        - **Geocoding accuracy** depends on the quality of source addresses; some
          partner locations may be approximate.
        - **Correlation does not imply causation.** Overlaying poverty, health, and
          food-access indicators highlights co-occurrence \u2014 not causal links.
        - This tool is designed for **strategic planning**, not granular
          individual-level assessment.
        """
    )


def _render_technical_details() -> None:
    st.subheader("Technical Details")
    st.markdown(
        """
        - **Data pipeline:** Python ETL producing Parquet files (one per source
          \u00d7 granularity) plus GeoJSON boundaries.
        - **Map rendering:** Folium (Leaflet.js) embedded in Streamlit via
          `streamlit-folium`.
        - **Tile layer:** CartoDB Positron.
        - **Repository / questions:** contact the BDAIC team at Belmont University.
        """
    )


def _render_nfp_logo() -> None:
    """Render NFP logo centered at top of page."""
    import base64

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


def _render_custom_nav() -> None:
    """Render custom sidebar navigation with 'Home' instead of 'app'."""
    with st.sidebar:
        st.page_link("app.py", label="Home")
        st.page_link("pages/1_Map.py", label="Map")
        st.page_link("pages/2_About_the_Data.py", label="About the Data")


def main() -> None:
    _configure_page()
    _inject_custom_css()
    _render_custom_nav()
    _render_nfp_logo()
    _render_header()
    with st.container():
        _render_overview()
        st.divider()
        _render_data_sources()
        st.divider()
        _render_geographic_coverage()
        st.divider()
        _render_limitations()
        st.divider()
        _render_technical_details()
        st.markdown(
            f'<div class="freshness">Pipeline last run: {_last_pipeline_run()}</div>',
            unsafe_allow_html=True,
        )
    _render_bdaic_footer()


main()
