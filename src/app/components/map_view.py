"""Composant de carte des transactions comparables (theme dark)."""

import streamlit as st
import folium
from streamlit_folium import st_folium

from src.estimation.estimator import EstimationResult
from src.app.utils.css import BG_CARD, TEXT_PRIMARY, BORDER, GOLD

# Couleurs par zone (zone 3 plus claire pour visibilite sur fond sombre)
ZONE_COLORS = {1: "#D4A843", 2: "#58A6FF", 3: "#B0BAC6"}


def render_map(result: EstimationResult):
    """Affiche une carte dark avec l'adresse, les comparables et les zones."""
    if result.nb_comparables == 0:
        return

    lat = result.geocoding.latitude
    lon = result.geocoding.longitude
    has_zones = result.zone_config is not None and "zone" in result.comparables.columns

    # Carte avec tuiles sombres
    m = folium.Map(
        location=[lat, lon],
        zoom_start=14,
        tiles="CartoDB dark_matter",
    )

    # Cercles des zones concentriques (dessiner du plus grand au plus petit)
    if has_zones and result.zone_config:
        zc = result.zone_config
        zone_radii = [
            (zc.radius_3_km * 1000, ZONE_COLORS[3], f"Zone 3 ({zc.radius_2_km}-{zc.radius_3_km} km)"),
            (zc.radius_2_km * 1000, ZONE_COLORS[2], f"Zone 2 ({zc.radius_1_km}-{zc.radius_2_km} km)"),
            (zc.radius_1_km * 1000, ZONE_COLORS[1], f"Zone 1 (0-{zc.radius_1_km} km)"),
        ]
        for radius_m, color, tooltip in zone_radii:
            folium.Circle(
                location=[lat, lon],
                radius=radius_m,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.06,
                weight=1.5,
                opacity=0.5,
                tooltip=tooltip,
            ).add_to(m)

    # Marqueur de l'adresse recherchee (or)
    folium.Marker(
        [lat, lon],
        popup=f"<b>{result.geocoding.label}</b><br>Estimation: {result.prix_m2_estime:,.0f} EUR/m\u00b2",
        icon=folium.Icon(color="orange", icon="home", prefix="fa"),
    ).add_to(m)

    # Marqueurs des comparables
    comparables = result.comparables
    if "latitude" in comparables.columns and "longitude" in comparables.columns:
        for _, row in comparables.iterrows():
            if row["latitude"] and row["longitude"]:
                # Couleur par zone si disponible, sinon par rapport de prix
                if has_zones and "zone" in row.index:
                    color = ZONE_COLORS.get(int(row["zone"]), "#8B949E")
                else:
                    ratio = row["prix_m2"] / result.prix_m2_estime if result.prix_m2_estime > 0 else 1
                    if ratio > 1.1:
                        color = "#F85149"
                    elif ratio < 0.9:
                        color = "#3FB950"
                    else:
                        color = "#58A6FF"

                # Popup enrichi
                dist_str = ""
                if "distance_m" in row.index and row["distance_m"] is not None:
                    d = row["distance_m"]
                    dist_str = f"Distance: {d:.0f} m<br>" if d < 1000 else f"Distance: {d/1000:.1f} km<br>"

                zone_str = ""
                if has_zones and "zone" in row.index:
                    zone_str = f"Zone: {int(row['zone'])}<br>"

                # Adresse si disponible
                addr_str = ""
                if "adresse" in row.index and row.get("adresse"):
                    addr_str = f"{row['adresse']}<br>"

                popup_text = (
                    f"<b>{row.get('nom_commune', '')}</b><br>"
                    f"{addr_str}"
                    f"{zone_str}"
                    f"{dist_str}"
                    f"Date: {row['date_mutation']}<br>"
                    f"Prix: {row['valeur_fonciere']:,.0f} EUR<br>"
                    f"Surface: {row['surface']:.0f} m\u00b2<br>"
                    f"Prix/m\u00b2: {row['prix_m2']:,.0f} EUR"
                )

                folium.CircleMarker(
                    [row["latitude"], row["longitude"]],
                    radius=7,
                    popup=popup_text,
                    color="#FFFFFF",
                    weight=1,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.85,
                ).add_to(m)

    # Legende
    if has_zones and result.zone_config:
        zc = result.zone_config
        legend_html = f"""
        <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
             background: {BG_CARD}; padding: 12px 14px; border-radius: 8px;
             border: 1px solid {BORDER}; color: {TEXT_PRIMARY}; font-size: 13px;">
            <b style="color:{GOLD};">Legende</b><br>
            <i style="color:#D4A843;">&#9679;</i> Adresse recherchee<br>
            <i style="color:{ZONE_COLORS[1]};">&#9679;</i> Zone 1 (0-{zc.radius_1_km} km)<br>
            <i style="color:{ZONE_COLORS[2]};">&#9679;</i> Zone 2 ({zc.radius_1_km}-{zc.radius_2_km} km)<br>
            <i style="color:{ZONE_COLORS[3]};">&#9679;</i> Zone 3 ({zc.radius_2_km}-{zc.radius_3_km} km)<br>
            <span style="font-size:11px; color:{TEXT_PRIMARY}; opacity:0.6;">Cliquez sur un point pour les details</span>
        </div>
        """
    else:
        legend_html = f"""
        <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
             background: {BG_CARD}; padding: 12px 14px; border-radius: 8px;
             border: 1px solid {BORDER}; color: {TEXT_PRIMARY}; font-size: 13px;">
            <b style="color:{GOLD};">Legende</b><br>
            <i style="color:#D4A843;">&#9679;</i> Adresse recherchee<br>
            <i style="color:#F85149;">&#9679;</i> Plus cher (+10%)<br>
            <i style="color:#58A6FF;">&#9679;</i> Comparable (&plusmn;10%)<br>
            <i style="color:#3FB950;">&#9679;</i> Moins cher (-10%)
        </div>
        """
    m.get_root().html.add_child(folium.Element(legend_html))

    st_folium(m, width=700, height=450, returned_objects=[])
