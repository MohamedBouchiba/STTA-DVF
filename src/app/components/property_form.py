"""Composant de saisie des caracteristiques du bien."""

from dataclasses import dataclass

import streamlit as st


@dataclass
class PropertyInput:
    """Donnees saisies par l'utilisateur."""
    type_bien: str
    surface: float
    nb_pieces: int | None


def render_property_form() -> PropertyInput | None:
    """
    Affiche le formulaire de caracteristiques du bien.

    Returns:
        PropertyInput si le formulaire est soumis, None sinon.
    """
    st.subheader("Caracteristiques du bien")

    type_bien = st.radio(
        "Type de bien",
        ["Appartement", "Maison"],
        horizontal=True,
        key="type_bien",
    )

    col1, col2 = st.columns(2)
    with col1:
        surface = st.number_input(
            "Surface (m\u00b2)",
            min_value=9.0,
            max_value=1000.0,
            value=50.0,
            step=1.0,
            key="surface",
        )
    with col2:
        nb_pieces = st.number_input(
            "Nombre de pieces (optionnel)",
            min_value=0,
            max_value=15,
            value=0,
            step=1,
            key="nb_pieces",
            help="Laisser a 0 pour ne pas filtrer.",
        )

    return PropertyInput(
        type_bien="appartement" if type_bien == "Appartement" else "maison",
        surface=surface,
        nb_pieces=nb_pieces if nb_pieces > 0 else None,
    )
