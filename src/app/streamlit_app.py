"""Application Streamlit - Estimateur immobilier STTA-DVF (page unique, dark finance)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.estimation.estimator import estimate
from src.estimation.geocoder import geocode
from src.estimation.zone_config import ZoneConfig
from src.app.utils.css import inject_global_css, GOLD, TEXT_SECONDARY
from src.app.components.admin_panel import render_admin_panel
from src.app.components.results_panel import render_results
from src.app.components.step_characteristics import CHARACTERISTICS
from src.app.components.step_additional import PERIOD_OPTIONS, CONDITION_OPTIONS
from src.app.models.property_input import (
    PropertyInput,
    PropertyType,
    ConstructionPeriod,
    PropertyCondition,
    QualityLevel,
)


# -- Configuration de la page --
st.set_page_config(
    page_title="STTA-DVF Estimateur",
    page_icon="\U0001f3e0",
    layout="centered",
    initial_sidebar_state="auto",
)

# -- Styles CSS --
inject_global_css()

# -- Sidebar --
with st.sidebar:
    st.markdown(
        f'<div style="text-align:center; padding:1rem 0;">'
        f'<span style="color:{GOLD}; font-size:1.4rem; font-weight:800; '
        f'letter-spacing:1px;">STTA-DVF</span><br>'
        f'<span style="color:{TEXT_SECONDARY}; font-size:0.75rem;">'
        f"Estimateur immobilier</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.caption("Source : DVF Etalab (transactions notariales)")

# Admin panel (retourne overrides ou None)
admin_overrides = render_admin_panel()

# ==========================================
# EN-TETE
# ==========================================
st.markdown(
    f'<div style="text-align:center; margin-bottom:1.5rem;">'
    f'<span style="color:{GOLD}; font-size:1.8rem; font-weight:800;">'
    f"Estimateur de prix immobilier</span><br>"
    f'<span style="color:{TEXT_SECONDARY}; font-size:0.85rem;">'
    f"Transactions reelles DVF | Geocodage Geoplateforme</span>"
    f"</div>",
    unsafe_allow_html=True,
)

# ==========================================
# SECTION 1 : ADRESSE
# ==========================================
st.markdown(
    f'<div class="form-header">Adresse du bien</div>',
    unsafe_allow_html=True,
)

col_addr, col_cp = st.columns([3, 1])
with col_addr:
    address_input = st.text_input(
        "Adresse",
        placeholder="12 rue de Rivoli, Paris",
        key="input_address",
        label_visibility="collapsed",
    )
with col_cp:
    postcode_input = st.text_input(
        "Code postal",
        placeholder="75001",
        key="input_postcode",
        label_visibility="collapsed",
    )

# Recherche d'adresse
if st.button("Rechercher l'adresse", key="btn_geocode", use_container_width=True):
    if address_input.strip():
        with st.spinner("Geocodage..."):
            try:
                results = geocode(
                    address_input.strip(),
                    postcode=postcode_input.strip() or None,
                )
                if results:
                    st.session_state["geocoding_results"] = results
                    st.session_state["selected_geo_idx"] = 0
                else:
                    st.warning("Aucune adresse trouvee.")
                    st.session_state.pop("geocoding_results", None)
            except Exception as e:
                st.error(f"Erreur de geocodage : {e}")
    else:
        st.warning("Veuillez saisir une adresse.")

# Selection d'adresse
geo_result = None
if "geocoding_results" in st.session_state:
    results = st.session_state["geocoding_results"]
    labels = [f"{r.label} (score: {r.score:.2f})" for r in results]
    selected_idx = st.radio(
        "Selectionnez l'adresse",
        range(len(labels)),
        format_func=lambda i: labels[i],
        key="radio_geo",
        index=st.session_state.get("selected_geo_idx", 0),
    )
    geo_result = results[selected_idx]
    st.session_state["selected_geo_idx"] = selected_idx

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ==========================================
# SECTION 2 : TYPE DE BIEN (cartes 3x2)
# ==========================================
st.markdown(
    f'<div class="form-header">Type de bien</div>',
    unsafe_allow_html=True,
)

if "selected_type" not in st.session_state:
    st.session_state["selected_type"] = PropertyType.APPARTEMENT

property_types = list(PropertyType)
for row_start in range(0, len(property_types), 3):
    row_types = property_types[row_start : row_start + 3]
    cols = st.columns(3)
    for col, pt in zip(cols, row_types):
        with col:
            is_selected = st.session_state["selected_type"] == pt
            css_class = "type-card selected" if is_selected else "type-card"
            st.markdown(
                f'<div class="{css_class}">'
                f'<div class="card-icon">{pt.icon}</div>'
                f'<div class="card-label">{pt.label}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button(
                pt.label,
                key=f"btn_type_{pt.value}",
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                st.session_state["selected_type"] = pt
                st.rerun()

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ==========================================
# SECTION 3 : INFORMATIONS PRINCIPALES
# ==========================================
st.markdown(
    f'<div class="form-header">Informations principales</div>',
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)
with col1:
    surface = st.number_input(
        "Surface (m\u00b2)", min_value=5.0, max_value=10000.0,
        value=50.0, step=1.0, key="input_surface",
    )
    nb_sdb = st.number_input(
        "Salles de bain", min_value=0, max_value=20,
        value=1, step=1, key="input_sdb",
    )
with col2:
    nb_pieces = st.number_input(
        "Nombre de pieces", min_value=1, max_value=50,
        value=2, step=1, key="input_pieces",
    )
    etage = st.number_input(
        "Etage", min_value=0, max_value=50,
        value=0, step=1, key="input_etage",
    )

col3, col4 = st.columns(2)
with col3:
    nb_etages_imm = st.number_input(
        "Nb etages immeuble", min_value=1, max_value=60,
        value=5, step=1, key="input_nb_etages",
    )
with col4:
    has_elevator = st.checkbox("Ascenseur", key="input_ascenseur")

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ==========================================
# SECTION 4 : CARACTERISTIQUES (expander ferme)
# ==========================================
with st.expander("Caracteristiques (facultatif)", expanded=False):
    st.markdown(
        f'<div class="form-subtitle">'
        f"Ces informations permettent d'affiner l'estimation."
        f"</div>",
        unsafe_allow_html=True,
    )

    char_values = {}
    for i in range(0, len(CHARACTERISTICS), 3):
        row = CHARACTERISTICS[i : i + 3]
        cols = st.columns(3)
        for col, (key, label, icon) in zip(cols, row):
            with col:
                # Ascenseur est deja gere ci-dessus
                if key == "ascenseur":
                    char_values[key] = has_elevator
                else:
                    char_values[key] = st.checkbox(
                        f"{icon} {label}",
                        key=f"char_{key}",
                    )

# ==========================================
# SECTION 5 : COMPLEMENTS (expander ferme)
# ==========================================
with st.expander("Complements (facultatif)", expanded=False):
    st.markdown(
        f'<div class="form-subtitle">'
        f"Periode de construction, etat et qualite du bien."
        f"</div>",
        unsafe_allow_html=True,
    )

    period_labels = list(PERIOD_OPTIONS.keys())
    selected_period = st.selectbox(
        "Periode de construction", period_labels,
        index=0, key="input_period",
    )
    construction_period = PERIOD_OPTIONS[selected_period]

    cond_labels = list(CONDITION_OPTIONS.keys())
    selected_cond = st.selectbox(
        "Etat du bien", cond_labels,
        index=0, key="input_condition",
    )
    condition = CONDITION_OPTIONS[selected_cond]

    st.markdown("**Qualite du bien** *(par rapport au quartier)*")
    quality_map = {
        "Inferieure": QualityLevel.INFERIEURE,
        "Comparable": QualityLevel.COMPARABLE,
        "Superieure": QualityLevel.SUPERIEURE,
    }
    selected_quality = st.radio(
        "Qualite",
        list(quality_map.keys()),
        index=1,
        horizontal=True,
        key="input_quality",
        label_visibility="collapsed",
    )
    quality = quality_map[selected_quality]

# ==========================================
# BOUTON ESTIMER
# ==========================================
st.markdown("")
can_estimate = geo_result is not None

col_l, col_c, col_r = st.columns([1, 2, 1])
with col_c:
    estimate_clicked = st.button(
        "ESTIMER LE PRIX",
        type="primary",
        use_container_width=True,
        disabled=not can_estimate,
        key="btn_estimate",
    )

if not can_estimate:
    st.caption("Recherchez et selectionnez une adresse pour estimer le prix.")

# ==========================================
# ESTIMATION
# ==========================================
if estimate_clicked and geo_result:
    # Construire le PropertyInput
    prop = PropertyInput(
        property_type=st.session_state["selected_type"],
        surface=surface,
        nb_pieces=nb_pieces,
        nb_salles_de_bain=nb_sdb,
        etage=etage,
        nb_etages_immeuble=nb_etages_imm,
        ascenseur=has_elevator,
        balcon=char_values.get("balcon", False),
        terrasse=char_values.get("terrasse", False),
        cave=char_values.get("cave", False),
        parking=char_values.get("parking", False),
        chambre_service=char_values.get("chambre_service", False),
        vue_exceptionnelle=char_values.get("vue_exceptionnelle", False),
        parties_communes_renovees=char_values.get("parties_communes_renovees", False),
        ravalement_recent=char_values.get("ravalement_recent", False),
        construction_period=construction_period,
        condition=condition,
        quality=quality,
    )

    # Extraire zone_config des overrides admin
    zone_cfg = admin_overrides.zone_config if admin_overrides else None

    with st.spinner("Estimation en cours..."):
        result = estimate(
            address=geo_result.label,
            type_bien=prop.dvf_type_bien,
            surface=prop.surface,
            nb_pieces=prop.dvf_nb_pieces,
            postcode=geo_result.postcode,
            zone_config=zone_cfg,
        )

    if result is None:
        st.error("Impossible d'estimer le prix. Verifiez l'adresse et les parametres.")
    else:
        st.session_state["estimation_result"] = result
        st.session_state["estimation_prop"] = prop

# ==========================================
# RESULTATS
# ==========================================
if "estimation_result" in st.session_state:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    result = st.session_state["estimation_result"]
    prop = st.session_state.get("estimation_prop")

    # Detecter changement de zone_config ou donnees obsoletes -> re-estimer
    current_zone_cfg = admin_overrides.zone_config if admin_overrides else ZoneConfig()
    stored_zone_cfg = result.zone_config or ZoneConfig()
    needs_refresh = (
        current_zone_cfg != stored_zone_cfg
        or "adresse" not in result.comparables.columns
    )

    if needs_refresh and prop:
        with st.spinner("Recalcul avec les nouvelles zones..."):
            new_result = estimate(
                address=result.geocoding.label,
                type_bien=prop.dvf_type_bien,
                surface=prop.surface,
                nb_pieces=prop.dvf_nb_pieces,
                postcode=result.geocoding.postcode,
                zone_config=current_zone_cfg,
                geocoding=result.geocoding,
            )
        if new_result:
            st.session_state["estimation_result"] = new_result
            st.rerun()

    if prop:
        render_results(result, prop, overrides=admin_overrides)
    else:
        from src.app.components.estimation import render_estimation
        render_estimation(result)
