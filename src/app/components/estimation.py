"""Composant d'affichage du resultat d'estimation."""

import streamlit as st

from src.estimation.estimator import EstimationResult
from src.app.utils.formatting import (
    format_price,
    format_price_m2,
    format_percentage,
    confidence_color,
)


def render_estimation(result: EstimationResult):
    """Affiche le resultat d'une estimation."""
    if result.nb_comparables == 0:
        st.error("Estimation impossible : aucune transaction comparable trouvee dans la zone.")
        return

    # Prix estime principal
    st.subheader("Estimation de prix")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Prix estime",
            value=format_price(result.prix_total_estime),
        )
    with col2:
        st.metric(
            label="Prix au m\u00b2",
            value=format_price_m2(result.prix_m2_estime),
        )
    with col3:
        color = confidence_color(result.confidence.level)
        st.markdown(
            f'<div style="text-align:center; padding:10px;">'
            f'<span style="color:{color}; font-size:1.5em; font-weight:bold;">'
            f'{result.confidence.level_label}'
            f'</span></div>',
            unsafe_allow_html=True,
        )

    # Intervalle de confiance
    st.info(
        f"Fourchette estimee : **{format_price(result.confidence.low_estimate)}** "
        f"- **{format_price(result.confidence.high_estimate)}**"
    )

    # Details
    with st.expander("Details de l'estimation", expanded=False):
        st.write(f"- **Adresse geocodee** : {result.geocoding.label}")
        st.write(f"- **Code INSEE** : {result.geocoding.citycode}")
        st.write(f"- **Perimetre** : {result.niveau_geo}")
        st.write(f"- **Comparables utilises** : {result.nb_comparables}")
        st.write(f"- **Ajustement surface** : {result.adjustment_factor:.2%}")

        if result.zone_stats:
            st.write("---")
            st.write("**Statistiques de zone :**")
            zs = result.zone_stats
            st.write(f"- Transactions totales : {zs['total_transactions']}")
            st.write(f"- Transactions 12 derniers mois : {zs['last_12m_transactions']}")
            if zs["median_prix_m2_12m"]:
                st.write(f"- Mediane prix/m\u00b2 (12 mois) : {format_price_m2(zs['median_prix_m2_12m'])}")
            st.write(f"- Tendance 12 mois : {format_percentage(zs['trend_12m'])}")
            st.write(f"- Qualite donnees : {zs['data_quality_flag']}")

    # Tableau des comparables
    if len(result.comparables) > 0:
        with st.expander(f"Transactions comparables ({result.nb_comparables})", expanded=False):
            display_df = result.comparables[
                ["datemut", "valeurfonc", "surface_utilisee", "nb_pieces", "prix_m2", "libcommune"]
            ].copy()
            display_df.columns = ["Date", "Prix", "Surface", "Pieces", "Prix/m\u00b2", "Commune"]
            display_df["Date"] = display_df["Date"].astype(str)
            display_df["Prix"] = display_df["Prix"].apply(lambda x: f"{x:,.0f} EUR".replace(",", " "))
            display_df["Surface"] = display_df["Surface"].apply(lambda x: f"{x:.0f} m\u00b2")
            display_df["Prix/m\u00b2"] = display_df["Prix/m\u00b2"].apply(lambda x: f"{x:,.0f} EUR".replace(",", " "))
            st.dataframe(display_df, use_container_width=True, hide_index=True)
