"""Composant de statistiques locales du marche."""

import streamlit as st
import pandas as pd
from sqlalchemy import text

from src.db import get_engine
from src.estimation.estimator import EstimationResult
from src.app.utils.formatting import format_price_m2, format_percentage


def _get_historical_data(codinsee: str, coddep: str, type_bien: str) -> pd.DataFrame:
    """Recupere l'historique des medianes par semestre."""
    engine = get_engine()

    # Niveau commune
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2,
               q1_prix_m2, q3_prix_m2
        FROM mart.prix_m2_commune
        WHERE codinsee = :codinsee AND type_bien = :type_bien
        ORDER BY annee, semestre
    """)
    df = pd.read_sql(query, engine, params={"codinsee": codinsee, "type_bien": type_bien})

    if len(df) < 2:
        # Fallback departement
        query = text("""
            SELECT annee, semestre, nb_transactions, median_prix_m2,
                   q1_prix_m2, q3_prix_m2
            FROM mart.prix_m2_departement
            WHERE coddep = :coddep AND type_bien = :type_bien
            ORDER BY annee, semestre
        """)
        df = pd.read_sql(query, engine, params={"coddep": coddep, "type_bien": type_bien})
        if len(df) > 0:
            df["source"] = "departement"
        return df

    df["source"] = "commune"
    return df


def render_stats_panel(result: EstimationResult):
    """Affiche les statistiques du marche local."""
    if result.nb_comparables == 0:
        return

    st.subheader("Statistiques du marche local")

    codinsee = result.geocoding.citycode
    coddep = codinsee[:2] if len(codinsee) >= 2 else codinsee
    type_bien = result.comparables["type_bien"].iloc[0] if len(result.comparables) > 0 else "appartement"

    # Historique
    hist = _get_historical_data(codinsee, coddep, type_bien)

    if len(hist) > 0:
        # Graphique d'evolution
        hist["periode"] = hist["annee"].astype(str) + "-S" + hist["semestre"].astype(str)

        st.bar_chart(
            hist.set_index("periode")["median_prix_m2"],
            use_container_width=True,
        )

        source = hist["source"].iloc[0] if "source" in hist.columns else "commune"
        st.caption(f"Mediane prix/m\u00b2 par semestre (source: {source})")

    # Stats zone
    if result.zone_stats:
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
