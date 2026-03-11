"""Composant d'affichage du resultat d'estimation (dark theme, style pro)."""

import streamlit as st

from src.estimation.estimator import EstimationResult
from src.app.utils.formatting import (
    format_price,
    format_price_m2,
    format_percentage,
    confidence_color,
)
from src.app.utils.css import TEXT_SECONDARY


def render_estimation(result: EstimationResult):
    """Affiche le resultat d'une estimation (sans ajustements)."""
    if result.nb_comparables == 0:
        st.error("Estimation impossible : aucune transaction comparable trouvee dans la zone.")
        return

    # Prix estime principal
    color = confidence_color(result.confidence.level)
    bg_map = {"high": "rgba(63,185,80,0.15)", "medium": "rgba(212,168,67,0.15)", "low": "rgba(248,81,73,0.15)"}
    bg_pill = bg_map.get(result.confidence.level, "rgba(139,148,158,0.15)")

    st.markdown(
        f'<div class="result-card">'
        f'<div class="result-price">{format_price(result.prix_total_estime)}</div>'
        f'<div class="result-price-m2">soit {format_price_m2(result.prix_m2_estime)}</div>'
        f'<div class="result-confidence" style="color:{color}; background:{bg_pill}; border:1px solid {color};">'
        f"Confiance {result.confidence.level_label}"
        f"</div>"
        f'<div style="margin-top:0.8rem; font-size:0.8rem; color:{TEXT_SECONDARY};">'
        f"{result.nb_comparables} transactions comparables &middot; {result.niveau_geo}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Fourchette
    st.markdown(
        f'<div class="result-range">'
        f"Fourchette estimee : <b>{format_price(result.confidence.low_estimate)}</b>"
        f" &ndash; <b>{format_price(result.confidence.high_estimate)}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Synthese
    rows = (
        f'<div class="summary-row">'
        f'<span class="summary-label">Adresse</span>'
        f'<span class="summary-value">{result.geocoding.label}</span></div>'
        f'<div class="summary-row">'
        f'<span class="summary-label">Comparables</span>'
        f'<span class="summary-value">{result.nb_comparables}</span></div>'
        f'<div class="summary-row">'
        f'<span class="summary-label">Perimetre</span>'
        f'<span class="summary-value">{result.niveau_geo}</span></div>'
        f'<div class="summary-row">'
        f'<span class="summary-label">Ajustement surface</span>'
        f'<span class="summary-value">{result.adjustment_factor:.2%}</span></div>'
    )

    if result.zone_stats and result.zone_stats.get("median_prix_m2_12m"):
        zs = result.zone_stats
        rows += (
            f'<div class="summary-row">'
            f'<span class="summary-label">Mediane zone (12 mois)</span>'
            f'<span class="summary-value">{format_price_m2(zs["median_prix_m2_12m"])}</span></div>'
            f'<div class="summary-row">'
            f'<span class="summary-label">Tendance 12 mois</span>'
            f'<span class="summary-value">{format_percentage(zs["trend_12m"])}</span></div>'
        )

    st.markdown(
        f'<div class="result-summary">'
        f'<div class="summary-title">Synthese de l\'estimation</div>'
        f"{rows}"
        f"</div>",
        unsafe_allow_html=True,
    )
