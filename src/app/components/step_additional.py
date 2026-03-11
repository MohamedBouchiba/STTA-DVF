"""Etape 5 : Complements d'information (periode, etat, qualite)."""

import streamlit as st

from src.app.models.property_input import (
    ConstructionPeriod,
    PropertyCondition,
    QualityLevel,
)

PERIOD_OPTIONS: dict[str, ConstructionPeriod] = {
    "-- Ne sais pas --": ConstructionPeriod.UNKNOWN,
    "Avant 1850": ConstructionPeriod.AVANT_1850,
    "1850 - 1913 (Haussmannien)": ConstructionPeriod.P1850_1913,
    "1914 - 1947": ConstructionPeriod.P1914_1947,
    "1948 - 1969": ConstructionPeriod.P1948_1969,
    "1970 - 1989": ConstructionPeriod.P1970_1989,
    "1990 - 2005": ConstructionPeriod.P1990_2005,
    "Apres 2005": ConstructionPeriod.APRES_2005,
}

CONDITION_OPTIONS: dict[str, PropertyCondition] = {
    "Standard": PropertyCondition.STANDARD,
    "A renover": PropertyCondition.A_RENOVER,
    "Bon etat": PropertyCondition.BON_ETAT,
    "Refait a neuf": PropertyCondition.REFAIT_A_NEUF,
}


def _find_index(options: dict, value) -> int:
    """Trouve l'index d'une valeur dans un dict ordonne."""
    for i, v in enumerate(options.values()):
        if v == value:
            return i
    return 0


def render_step_additional() -> bool:
    """
    Affiche les complements d'information.

    Returns:
        True (toujours, tout est optionnel).
    """
    st.markdown(
        '<div class="form-header">Precisions concernant votre bien</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="form-subtitle">'
        "Ces details optionnels permettent d'ajuster l'estimation. "
        "Vous pouvez passer cette etape si vous ne les connaissez pas."
        "</div>",
        unsafe_allow_html=True,
    )

    # Periode de construction
    current_period = st.session_state.wizard_data.get(
        "construction_period", ConstructionPeriod.UNKNOWN
    )
    period_labels = list(PERIOD_OPTIONS.keys())

    selected_period = st.selectbox(
        "Periode de construction",
        period_labels,
        index=_find_index(PERIOD_OPTIONS, current_period),
        key="wiz_construction_period",
    )
    st.session_state.wizard_data["construction_period"] = PERIOD_OPTIONS[
        selected_period
    ]

    st.markdown("")

    # Etat du bien
    current_cond = st.session_state.wizard_data.get(
        "condition", PropertyCondition.STANDARD
    )
    cond_labels = list(CONDITION_OPTIONS.keys())

    selected_cond = st.selectbox(
        "Etat du bien",
        cond_labels,
        index=_find_index(CONDITION_OPTIONS, current_cond),
        key="wiz_condition",
    )
    st.session_state.wizard_data["condition"] = CONDITION_OPTIONS[selected_cond]

    st.markdown("---")

    # Qualite - 3 boutons
    st.markdown(
        "**Qualite de l'appartement**  \n"
        "*Par rapport aux autres biens du quartier*"
    )

    quality_options = [
        (QualityLevel.INFERIEURE, "Inferieure"),
        (QualityLevel.COMPARABLE, "Comparable"),
        (QualityLevel.SUPERIEURE, "Superieure"),
    ]
    current_quality = st.session_state.wizard_data.get(
        "quality", QualityLevel.COMPARABLE
    )

    cols = st.columns(3)
    for col, (qval, qlabel) in zip(cols, quality_options):
        with col:
            is_sel = current_quality == qval
            if st.button(
                qlabel,
                key=f"btn_quality_{qval.value}",
                type="primary" if is_sel else "secondary",
                use_container_width=True,
            ):
                st.session_state.wizard_data["quality"] = qval
                st.rerun()

    return True
