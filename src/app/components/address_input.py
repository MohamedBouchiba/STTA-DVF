"""Composant de saisie d'adresse avec geocodage."""

import streamlit as st

from src.estimation.geocoder import geocode, GeocodingResult


def render_address_input() -> GeocodingResult | None:
    """
    Affiche le formulaire de saisie d'adresse et retourne le resultat geocode.

    Returns:
        GeocodingResult si une adresse est validee, None sinon.
    """
    st.subheader("Adresse du bien")

    col1, col2 = st.columns([3, 1])
    with col1:
        address = st.text_input(
            "Adresse",
            placeholder="Ex: 10 rue de Rivoli, Paris",
            key="address_input",
        )
    with col2:
        postcode = st.text_input(
            "Code postal (optionnel)",
            placeholder="75001",
            key="postcode_input",
            max_chars=5,
        )

    if st.button("Rechercher l'adresse", type="primary", key="btn_geocode"):
        if not address:
            st.warning("Veuillez saisir une adresse.")
            return None

        with st.spinner("Geocodage en cours..."):
            results = geocode(
                address,
                limit=5,
                postcode=postcode if postcode else None,
            )

        if not results:
            st.error("Aucune adresse trouvee. Verifiez votre saisie.")
            return None

        st.session_state["geocoding_results"] = results
        st.session_state["selected_address_idx"] = 0

    # Afficher les resultats de geocodage
    if "geocoding_results" in st.session_state:
        results = st.session_state["geocoding_results"]

        options = [f"{r.label} (score: {r.score:.2f})" for r in results]
        selected = st.radio(
            "Confirmez l'adresse :",
            options,
            index=st.session_state.get("selected_address_idx", 0),
            key="address_select",
        )

        idx = options.index(selected)
        st.session_state["selected_address_idx"] = idx
        chosen = results[idx]

        st.success(f"Adresse selectionnee : **{chosen.label}** (INSEE: {chosen.citycode})")
        return chosen

    return None
