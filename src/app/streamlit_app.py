"""Application Streamlit - Estimateur immobilier STTA-DVF."""

import streamlit as st

from src.estimation.estimator import estimate
from src.app.components.address_input import render_address_input
from src.app.components.property_form import render_property_form
from src.app.components.estimation import render_estimation
from src.app.components.map_view import render_map
from src.app.components.stats_panel import render_stats_panel


# -- Configuration de la page --
st.set_page_config(
    page_title="STTA-DVF Estimateur",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -- Sidebar --
with st.sidebar:
    st.title("STTA-DVF")
    st.markdown("**Estimateur immobilier**")
    st.markdown("Base sur les donnees DVF+ (Cerema)")
    st.markdown("---")
    st.markdown(
        "Methode : mediane locale des transactions\n"
        "comparables avec ajustement surface\n"
        "et correction de tendance."
    )
    st.markdown("---")
    st.caption("Source : DVF+ open-data (Cerema/DGALN)")
    st.caption("Geocodage : API Geoplateforme")

# -- Contenu principal --
st.title("Estimateur de prix immobilier")
st.markdown("Estimez le prix d'un bien a partir des transactions reelles enregistrees par les notaires.")

# Deux colonnes : formulaire | resultats
col_form, col_results = st.columns([2, 3])

with col_form:
    # Saisie adresse
    geocoding_result = render_address_input()

    # Saisie caracteristiques
    st.markdown("---")
    property_input = render_property_form()

    # Bouton estimation
    st.markdown("---")
    estimate_clicked = st.button(
        "Estimer le prix",
        type="primary",
        use_container_width=True,
        key="btn_estimate",
        disabled=(geocoding_result is None),
    )

with col_results:
    if estimate_clicked and geocoding_result and property_input:
        with st.spinner("Estimation en cours..."):
            result = estimate(
                address=geocoding_result.label,
                type_bien=property_input.type_bien,
                surface=property_input.surface,
                nb_pieces=property_input.nb_pieces,
                postcode=geocoding_result.postcode,
            )

        if result is None:
            st.error("Impossible d'estimer le prix. Verifiez l'adresse.")
        else:
            # Stocker en session pour persister entre les reruns
            st.session_state["estimation_result"] = result

    # Afficher le resultat (meme apres rerun)
    if "estimation_result" in st.session_state:
        result = st.session_state["estimation_result"]
        render_estimation(result)
        render_map(result)
        render_stats_panel(result)
