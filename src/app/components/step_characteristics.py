"""Etape 4 : Caracteristiques optionnelles du bien (checkboxes)."""

import streamlit as st

CHARACTERISTICS = [
    ("ascenseur", "Ascenseur", "\U0001f6d7"),
    ("balcon", "Balcon", "\U0001f33f"),
    ("terrasse", "Terrasse", "\u2600\ufe0f"),
    ("cave", "Cave", "\U0001f511"),
    ("parking", "Places de parking", "\U0001f17f\ufe0f"),
    ("chambre_service", "Chambre de service", "\U0001f6cf\ufe0f"),
    ("vue_exceptionnelle", "Vue exceptionnelle", "\U0001f305"),
    ("parties_communes_renovees", "Parties communes renovees", "\U0001f527"),
    ("ravalement_recent", "Ravalement de facade", "\U0001f3d7\ufe0f"),
]


def render_step_characteristics() -> bool:
    """
    Affiche les checkboxes de caracteristiques en grille 3x3.

    Returns:
        True (toujours, tout est optionnel).
    """
    st.markdown(
        '<div class="form-header">Caracteristiques du bien</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="form-subtitle">'
        "Ces informations sont facultatives et permettent d'affiner l'estimation."
        "</div>",
        unsafe_allow_html=True,
    )

    for i in range(0, len(CHARACTERISTICS), 3):
        row = CHARACTERISTICS[i : i + 3]
        cols = st.columns(3)
        for col, (key, label, icon) in zip(cols, row):
            with col:
                current = st.session_state.wizard_data.get(key, False)
                val = st.checkbox(
                    f"{icon} {label}",
                    value=current,
                    key=f"wiz_{key}",
                )
                st.session_state.wizard_data[key] = val

    # Compter les caracteristiques cochees
    count = sum(
        1
        for key, _, _ in CHARACTERISTICS
        if st.session_state.wizard_data.get(key, False)
    )
    if count > 0:
        st.caption(f"{count} caracteristique(s) selectionnee(s)")

    return True
