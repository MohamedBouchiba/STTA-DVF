"""Calcul des intervalles et niveaux de confiance."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ConfidenceResult:
    """Resultat du calcul de confiance."""
    level: str           # 'high', 'medium', 'low'
    level_label: str     # Label en francais
    low_estimate: float  # Borne basse de l'intervalle
    high_estimate: float # Borne haute de l'intervalle
    nb_comparables: int
    search_level: int    # Niveau geographique utilise


def compute_confidence(
    comparables: pd.DataFrame,
    search_level: int,
    surface: float,
    adjustment: float = 1.0,
) -> ConfidenceResult:
    """
    Calcule le niveau de confiance et l'intervalle de prix.

    Args:
        comparables: DataFrame des transactions comparables.
        search_level: Niveau geographique utilise (1-4).
        surface: Surface du bien estime.
        adjustment: Facteur d'ajustement surface.

    Returns:
        ConfidenceResult.
    """
    n = len(comparables)

    # Niveau de confiance
    if n >= 30 and search_level <= 2:
        level = "high"
        level_label = "Confiance haute"
    elif n >= 10 and search_level <= 3:
        level = "medium"
        level_label = "Confiance moyenne"
    else:
        level = "low"
        level_label = "Confiance faible"

    # Intervalle base sur les quartiles des comparables
    if n > 0:
        q25 = float(np.percentile(comparables["prix_m2"], 25))
        q75 = float(np.percentile(comparables["prix_m2"], 75))
    else:
        q25 = 0
        q75 = 0

    low_estimate = q25 * surface * adjustment
    high_estimate = q75 * surface * adjustment

    return ConfidenceResult(
        level=level,
        level_label=level_label,
        low_estimate=round(low_estimate, 0),
        high_estimate=round(high_estimate, 0),
        nb_comparables=n,
        search_level=search_level,
    )
