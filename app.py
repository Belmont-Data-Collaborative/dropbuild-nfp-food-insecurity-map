from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src import config
from src.data_loader import (
    DataLoadError,
    DataSchemaError,
    load_cdc_places_data,
    load_census_data,
    load_geojson,
    load_partners_data,
)
from src.geocoder import GeocodingError, geocode_partners
from src.map_builder import build_map


def main() -> None:
    st.set_page_config(
        page_title="NFP Food Insecurity Map",
        page_icon="🗺️",
        layout="wide",
    )

    # -----------------------------------------------------------------------
    # Sidebar
    # -----------------------------------------------------------------------
    with st.sidebar:
        # Section 1: Title and description
        st.title("Nashville Food Project \u2014 Food Insecurity Map")
        st.write(
            "An interactive mapping tool to visualize food insecurity "
            "across Davidson County, Tennessee. "
            "Explore census tract data overlaid with NFP partner locations "
            "to identify areas of greatest need."
        )

        st.divider()

        # Section 2: Data Layers
        st.subheader("Data Layers")
        show_partners = st.checkbox(
            "Show NFP Partner Locations",
            value=True,
            key="show_partners",
        )

        layer_options = ["None"] + [
            layer["display_name"] for layer in config.CHOROPLETH_LAYERS
        ]
        # Default to Median Household Income (Census)
        default_layer = next(
            (
                layer["display_name"]
                for layer in config.CHOROPLETH_LAYERS
                if layer["id"] == config.DEFAULT_CHOROPLETH_LAYER
            ),
            "None",
        )
        default_index = (
            layer_options.index(default_layer)
            if default_layer in layer_options
            else 0
        )
        selected_layer_name = st.selectbox(
            "Background Data Layer",
            options=layer_options,
            index=default_index,
            key="selected_layer",
        )

        st.divider()

        # Section 3: Partner Type Legend
        st.subheader("Partner Type Legend")
        for ptype, label in config.PARTNER_TYPE_LABELS.items():
            color = config.PARTNER_TYPE_COLORS.get(
                ptype, config.FALLBACK_COLOR
            )
            st.markdown(
                f'<span style="display:inline-block;width:14px;height:14px;'
                f"background-color:{color};border-radius:50%;"
                f'margin-right:8px;vertical-align:middle;"></span>'
                f"<span>{label}</span>",
                unsafe_allow_html=True,
            )

        st.divider()

        # Section 4: Export
        st.subheader("Export")
        # Placeholder — map HTML will be set after map is built
        export_placeholder = st.empty()

        st.divider()

        # Section 5: Data Sources
        st.subheader("Data Sources")
        data_freshness_placeholder = st.empty()

    # -----------------------------------------------------------------------
    # Resolve selected layer id
    # -----------------------------------------------------------------------
    selected_layer_id: str | None = None
    selected_layer_config: dict | None = None
    if selected_layer_name != "None":
        for layer in config.CHOROPLETH_LAYERS:
            if layer["display_name"] == selected_layer_name:
                selected_layer_id = layer["id"]
                selected_layer_config = layer
                break

    # -----------------------------------------------------------------------
    # Data freshness notice
    # -----------------------------------------------------------------------
    freshness_parts: list[str] = []
    if show_partners:
        freshness_parts.append("**NFP Partners**: Updated at runtime")
    if selected_layer_config is not None:
        source = selected_layer_config["csv_source"]
        if source == "census":
            freshness_parts.append(
                "**Census Data**: ACS 2022 5-Year Estimates"
            )
        elif source == "cdc_places":
            freshness_parts.append("**CDC PLACES**: CDC PLACES 2022")
    if not freshness_parts:
        freshness_parts.append("Select a data layer to see source details.")
    data_freshness_placeholder.markdown("\n\n".join(freshness_parts))

    # -----------------------------------------------------------------------
    # Load data
    # -----------------------------------------------------------------------
    geojson = None
    census_df = None
    cdc_df = None
    partners_df = None
    geocoded_df = None

    try:
        with st.spinner("Loading map boundaries..."):
            geojson = load_geojson()
    except DataLoadError:
        st.error(config.ERROR_DATA_LOAD)
        st.stop()

    try:
        with st.spinner("Loading census data..."):
            census_df = load_census_data()
    except (DataLoadError, DataSchemaError) as exc:
        if isinstance(exc, DataSchemaError):
            st.error(str(exc))
        else:
            st.error(config.ERROR_DATA_LOAD)
        st.stop()

    try:
        with st.spinner("Loading CDC PLACES data..."):
            cdc_df = load_cdc_places_data()
    except (DataLoadError, DataSchemaError) as exc:
        if isinstance(exc, DataSchemaError):
            st.error(str(exc))
        else:
            st.error(config.ERROR_DATA_LOAD)
        st.stop()

    # Check for zero GEOID matches
    if census_df is not None and geojson is not None:
        geojson_geoids = {
            str(f["properties"].get("GEOID", "")).zfill(11)
            for f in geojson.get("features", [])
        }
        census_geoids = set(census_df["GEOID"].astype(str))
        if len(geojson_geoids & census_geoids) == 0:
            st.warning(config.WARNING_NO_GEOID_MATCH)

    # Load and geocode partners
    if show_partners:
        try:
            with st.spinner("Loading partner data..."):
                partners_df = load_partners_data()
        except DataLoadError:
            st.error(config.ERROR_DATA_LOAD)
            st.stop()
        except DataSchemaError as exc:
            # Extract column name from exception
            st.error(str(exc))
            st.stop()

        try:
            with st.spinner("Geocoding partner addresses..."):
                geocoded_df = geocode_partners(partners_df)
        except GeocodingError:
            st.error(config.ERROR_DATA_LOAD)
            st.stop()

        # Merge partner_type into geocoded_df for marker coloring
        if geocoded_df is not None and partners_df is not None:
            if "partner_type" not in geocoded_df.columns:
                # Merge partner_type from original partners_df
                type_map = partners_df[
                    ["partner_name", "partner_type"]
                ].drop_duplicates(subset=["partner_name"])
                geocoded_df = geocoded_df.merge(
                    type_map, on="partner_name", how="left"
                )

        # Check for geocoding failures
        if geocoded_df is not None:
            failed_count = (
                geocoded_df["geocode_status"] == "failed"
            ).sum()
            if failed_count > 0:
                st.warning(
                    config.WARNING_GEOCODE_FAILURES.format(
                        count=failed_count
                    )
                )

    # -----------------------------------------------------------------------
    # Build and render map
    # -----------------------------------------------------------------------
    folium_map = build_map(
        geojson=geojson,
        census_df=census_df,
        cdc_df=cdc_df,
        geocoded_df=geocoded_df,
        selected_layer_id=selected_layer_id,
        show_partners=show_partners,
    )

    st_folium(folium_map, width=None, height=700, returned_objects=[])

    # -----------------------------------------------------------------------
    # Export button (HTML download — PNG is impossible in pure Streamlit)
    # -----------------------------------------------------------------------
    map_html = folium_map._repr_html_()
    with export_placeholder:
        st.download_button(
            label="\u2b07 Download Map as PNG",
            data=map_html,
            file_name="nfp_food_insecurity_map.html",
            mime="text/html",
        )


if __name__ == "__main__":
    main()
