"""Composant de carte des transactions comparables."""

import streamlit as st
import folium
from streamlit_folium import st_folium

from src.estimation.estimator import EstimationResult


def render_map(result: EstimationResult):
    """Affiche une carte avec l'adresse et les comparables."""
    if result.nb_comparables == 0:
        return

    st.subheader("Carte des transactions comparables")

    lat = result.geocoding.latitude
    lon = result.geocoding.longitude

    # Creer la carte centree sur l'adresse
    m = folium.Map(location=[lat, lon], zoom_start=14)

    # Marqueur de l'adresse recherchee
    folium.Marker(
        [lat, lon],
        popup=f"<b>{result.geocoding.label}</b><br>Estimation: {result.prix_m2_estime:,.0f} EUR/m\u00b2",
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(m)

    # Marqueurs des comparables
    comparables = result.comparables
    if "latitude" in comparables.columns and "longitude" in comparables.columns:
        for _, row in comparables.iterrows():
            if row["latitude"] and row["longitude"]:
                # Couleur par prix/m2 relatif
                ratio = row["prix_m2"] / result.prix_m2_estime if result.prix_m2_estime > 0 else 1
                if ratio > 1.1:
                    color = "darkred"
                elif ratio < 0.9:
                    color = "darkgreen"
                else:
                    color = "blue"

                popup_text = (
                    f"<b>{row.get('libcommune', '')}</b><br>"
                    f"Date: {row['datemut']}<br>"
                    f"Prix: {row['valeurfonc']:,.0f} EUR<br>"
                    f"Surface: {row['surface_utilisee']:.0f} m\u00b2<br>"
                    f"Prix/m\u00b2: {row['prix_m2']:,.0f} EUR"
                )

                folium.CircleMarker(
                    [row["latitude"], row["longitude"]],
                    radius=6,
                    popup=popup_text,
                    color=color,
                    fill=True,
                    fill_opacity=0.7,
                ).add_to(m)

    # Legende
    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
         background: white; padding: 10px; border-radius: 5px; border: 1px solid #ccc;">
        <b>Legende</b><br>
        <i style="color:red;">&#9679;</i> Adresse recherchee<br>
        <i style="color:darkred;">&#9679;</i> Plus cher (+10%)<br>
        <i style="color:blue;">&#9679;</i> Comparable (&plusmn;10%)<br>
        <i style="color:darkgreen;">&#9679;</i> Moins cher (-10%)
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, width=700, height=450, returned_objects=[])
