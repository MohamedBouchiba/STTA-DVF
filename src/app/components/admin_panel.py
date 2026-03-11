"""Panneau d'administration : coefficients d'ajustement editables."""

import streamlit as st

from src.app.models.adjustments import (
    get_default_coefficients,
    CoefficientOverrides,
    FloorParams,
)
from src.estimation.zone_config import ZoneConfig

TYPE_LABELS = {
    "appartement": "Appartement", "maison": "Maison", "duplex": "Duplex",
    "triplex": "Triplex", "loft": "Loft / Atelier",
    "hotel_particulier": "Hotel Particulier",
}
QUALITY_LABELS = {
    "inferieure": "Inferieure", "comparable": "Comparable", "superieure": "Superieure",
}
CONDITION_LABELS = {
    "a_renover": "A renover", "standard": "Standard",
    "bon_etat": "Bon etat", "refait_a_neuf": "Refait a neuf",
}
CONSTRUCTION_LABELS = {
    "unknown": "Non renseigne", "avant_1850": "Avant 1850",
    "1850_1913": "1850-1913", "1914_1947": "1914-1947",
    "1948_1969": "1948-1969", "1970_1989": "1970-1989",
    "1990_2005": "1990-2005", "apres_2005": "Apres 2005",
}
CHARACTERISTIC_LABELS = {
    "ascenseur": "Ascenseur", "balcon": "Balcon", "terrasse": "Terrasse",
    "cave": "Cave", "parking": "Parking", "chambre_service": "Chambre service",
    "vue_exceptionnelle": "Vue except.", "parties_communes_renovees": "Parties comm.",
    "ravalement_recent": "Ravalement",
}
FLOOR_PARAM_LABELS = {
    "ground_floor_discount": ("Decote RDC", 0.0, 0.20),
    "elevator_bonus_per_floor": ("Bonus/etage (asc.)", 0.0, 0.05),
    "no_elevator_penalty_per_floor": ("Penalite/etage", 0.0, 0.10),
    "last_floor_bonus": ("Bonus dernier etage", 0.0, 0.10),
    "max_elevator_bonus": ("Max bonus asc.", 0.0, 0.15),
    "max_no_elevator_penalty": ("Max penalite", 0.0, 0.30),
}


def _init_admin_state():
    if "admin_overrides" not in st.session_state:
        st.session_state["admin_overrides"] = get_default_coefficients()


def _render_group(group_key: str, label_map: dict, min_val: float, max_val: float):
    current = st.session_state["admin_overrides"][group_key]
    for key in current:
        display_label = label_map.get(key, key)
        current[key] = st.slider(
            display_label, min_value=min_val, max_value=max_val,
            value=float(current.get(key, 1.0)), step=0.01,
            key=f"admin_{group_key}_{key}", format="%.2f",
        )


def render_admin_panel() -> CoefficientOverrides | None:
    """Affiche le panneau admin dans la sidebar. Retourne overrides ou None."""
    with st.sidebar:
        st.markdown("---")
        admin_on = st.toggle("\U0001f512 Mode Admin", key="admin_toggle", value=False)

        if not admin_on:
            if "admin_overrides" in st.session_state:
                del st.session_state["admin_overrides"]
            return None

        _init_admin_state()
        st.markdown("### Coefficients")
        st.caption("Ajustez les parametres de l'algorithme")

        if st.button("\U0001f504 Reinitialiser", key="admin_reset", use_container_width=True):
            st.session_state["admin_overrides"] = get_default_coefficients()
            st.rerun()

        with st.expander("Type de bien", expanded=False):
            _render_group("type", TYPE_LABELS, 0.80, 1.30)
        with st.expander("Qualite", expanded=False):
            _render_group("quality", QUALITY_LABELS, 0.70, 1.30)
        with st.expander("Etat du bien", expanded=False):
            _render_group("condition", CONDITION_LABELS, 0.70, 1.30)
        with st.expander("Construction", expanded=False):
            _render_group("construction", CONSTRUCTION_LABELS, 0.80, 1.20)
        with st.expander("Caracteristiques", expanded=False):
            _render_group("characteristics", CHARACTERISTIC_LABELS, 0.0, 0.15)
        with st.expander("Parametres etage", expanded=False):
            defaults = get_default_coefficients()["floor"]
            current_floor = st.session_state["admin_overrides"]["floor"]
            for key, (label, min_v, max_v) in FLOOR_PARAM_LABELS.items():
                current_floor[key] = st.slider(
                    label, min_value=min_v, max_value=max_v,
                    value=float(current_floor.get(key, defaults[key])),
                    step=0.01, key=f"admin_floor_{key}", format="%.2f",
                )

        with st.expander("Zones de recherche", expanded=False):
            zone_defaults = get_default_coefficients()["zone"]
            current_zone = st.session_state["admin_overrides"]["zone"]

            st.caption("Rayons des zones concentriques (km)")
            r1 = st.slider(
                "Zone 1 : 0 a R1", min_value=0.5, max_value=3.0,
                value=float(current_zone.get("radius_1_km", zone_defaults["radius_1_km"])),
                step=0.1, key="admin_zone_r1", format="%.1f km",
            )
            r2 = st.slider(
                "Zone 2 : R1 a R2", min_value=1.0, max_value=5.0,
                value=float(current_zone.get("radius_2_km", zone_defaults["radius_2_km"])),
                step=0.1, key="admin_zone_r2", format="%.1f km",
            )
            r3 = st.slider(
                "Zone 3 : R2 a R3", min_value=2.0, max_value=10.0,
                value=float(current_zone.get("radius_3_km", zone_defaults["radius_3_km"])),
                step=0.1, key="admin_zone_r3", format="%.1f km",
            )

            # Validation : R1 < R2 < R3
            if r1 >= r2:
                r2 = r1 + 0.1
            if r2 >= r3:
                r3 = r2 + 0.1

            st.caption("Poids par zone (normalises automatiquement)")
            w1 = st.slider(
                "Poids zone 1", min_value=0.0, max_value=1.0,
                value=float(current_zone.get("weight_1", zone_defaults["weight_1"])),
                step=0.05, key="admin_zone_w1", format="%.2f",
            )
            w2 = st.slider(
                "Poids zone 2", min_value=0.0, max_value=1.0,
                value=float(current_zone.get("weight_2", zone_defaults["weight_2"])),
                step=0.05, key="admin_zone_w2", format="%.2f",
            )
            w3 = st.slider(
                "Poids zone 3", min_value=0.0, max_value=1.0,
                value=float(current_zone.get("weight_3", zone_defaults["weight_3"])),
                step=0.05, key="admin_zone_w3", format="%.2f",
            )

            total_w = w1 + w2 + w3
            if total_w > 0:
                st.caption(f"Poids effectifs : {w1/total_w:.0%} / {w2/total_w:.0%} / {w3/total_w:.0%}")
            else:
                st.warning("Au moins un poids doit etre > 0")

            current_zone.update({
                "radius_1_km": r1, "radius_2_km": r2, "radius_3_km": r3,
                "weight_1": w1, "weight_2": w2, "weight_3": w3,
            })

        ov = st.session_state["admin_overrides"]
        zone_dict = ov["zone"]
        return CoefficientOverrides(
            type_coefficients=ov["type"],
            quality_coefficients=ov["quality"],
            condition_coefficients=ov["condition"],
            construction_coefficients=ov["construction"],
            characteristic_adjustments=ov["characteristics"],
            floor_params=FloorParams(**ov["floor"]),
            zone_config=ZoneConfig(
                radius_1_km=zone_dict["radius_1_km"],
                radius_2_km=zone_dict["radius_2_km"],
                radius_3_km=zone_dict["radius_3_km"],
                weight_1=zone_dict["weight_1"],
                weight_2=zone_dict["weight_2"],
                weight_3=zone_dict["weight_3"],
            ),
        )
