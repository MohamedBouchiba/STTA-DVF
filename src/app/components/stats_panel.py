"""Composant de statistiques locales du marche (Plotly dark theme)."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import text

from src.db import get_engine
from src.estimation.estimator import EstimationResult
from src.app.utils.formatting import format_price_m2, format_percentage
from src.app.utils.css import get_plotly_dark_theme, GOLD, GOLD_MUTED


def _get_historical_data(code_commune: str, code_departement: str, type_bien: str) -> pd.DataFrame:
    """Recupere l'historique des medianes par semestre."""
    engine = get_engine()

    # Niveau commune
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2,
               q1_prix_m2, q3_prix_m2
        FROM mart.stats_commune
        WHERE code_commune = :code_commune AND type_bien = :type_bien
        ORDER BY annee, semestre
    """)
    df = pd.read_sql(query, engine, params={"code_commune": code_commune, "type_bien": type_bien})

    if len(df) < 2:
        # Fallback departement
        query = text("""
            SELECT annee, semestre, nb_transactions, median_prix_m2,
                   q1_prix_m2, q3_prix_m2
            FROM mart.stats_departement
            WHERE code_departement = :code_departement AND type_bien = :type_bien
            ORDER BY annee, semestre
        """)
        df = pd.read_sql(query, engine, params={"code_departement": code_departement, "type_bien": type_bien})
        if len(df) > 0:
            df["source"] = "departement"
        return df

    df["source"] = "commune"
    return df


def render_stats_chart(result: EstimationResult):
    """Affiche le graphique Plotly d'evolution des prix."""
    if result.nb_comparables == 0:
        return

    code_commune = result.geocoding.citycode
    code_departement = code_commune[:2] if len(code_commune) >= 2 else code_commune
    type_bien = result.comparables["type_bien"].iloc[0] if len(result.comparables) > 0 else "appartement"

    hist = _get_historical_data(code_commune, code_departement, type_bien)

    if len(hist) == 0:
        st.caption("Pas de donnees historiques disponibles.")
        return

    hist["periode"] = hist["annee"].astype(str) + "-S" + hist["semestre"].astype(str)

    theme = get_plotly_dark_theme()

    fig = go.Figure()

    # Barres des medianes
    fig.add_trace(go.Bar(
        x=hist["periode"],
        y=hist["median_prix_m2"],
        marker_color=GOLD,
        marker_line_color=GOLD_MUTED,
        marker_line_width=1,
        opacity=0.85,
        name="Mediane prix/m\u00b2",
        hovertemplate="%{x}<br>%{y:,.0f} EUR/m\u00b2<extra></extra>",
    ))

    # Fourchette IQR si disponible
    if "q1_prix_m2" in hist.columns and "q3_prix_m2" in hist.columns:
        has_iqr = hist["q1_prix_m2"].notna().any()
        if has_iqr:
            fig.add_trace(go.Scatter(
                x=hist["periode"],
                y=hist["q3_prix_m2"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=hist["periode"],
                y=hist["q1_prix_m2"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(212,168,67,0.1)",
                showlegend=False,
                hoverinfo="skip",
            ))

    fig.update_layout(
        **theme,
        title=None,
        xaxis_title=None,
        yaxis_title="Prix/m\u00b2 (EUR)",
        showlegend=False,
        height=350,
        bargap=0.15,
        margin=dict(l=50, r=20, t=20, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)

    source = hist["source"].iloc[0] if "source" in hist.columns else "commune"
    st.caption(f"Mediane prix/m\u00b2 par semestre (source: {source})")


def render_stats_metrics(result: EstimationResult):
    """Affiche les metriques de zone."""
    if not result.zone_stats:
        return

    zs = result.zone_stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Transactions (12 mois)",
            zs["last_12m_transactions"] or 0,
        )
    with col2:
        if zs["median_prix_m2_12m"]:
            st.metric(
                "Mediane prix/m\u00b2",
                format_price_m2(zs["median_prix_m2_12m"]),
            )
    with col3:
        st.metric(
            "Tendance 12 mois",
            format_percentage(zs["trend_12m"]),
        )
