"""Estimateur de prix immobilier base sur la mediane locale."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.db import get_engine
from src.estimation.geocoder import GeocodingResult, geocode_best
from src.estimation.comparables import find_comparables
from src.estimation.confidence import compute_confidence, ConfidenceResult


@dataclass
class EstimationResult:
    """Resultat complet d'une estimation."""
    # Adresse geocodee
    geocoding: GeocodingResult

    # Estimation
    prix_m2_estime: float
    prix_total_estime: float

    # Confiance
    confidence: ConfidenceResult

    # Details
    niveau_geo: str
    nb_comparables: int
    adjustment_factor: float
    comparables: pd.DataFrame

    # Stats zone
    zone_stats: dict | None


def _compute_surface_adjustment(user_surface: float, comparables: pd.DataFrame) -> float:
    """
    Ajustement prix/m2 en fonction de la surface.

    Les grands biens ont tendance a avoir un prix/m2 plus bas.
    Chaque doublement de surface reduit le prix/m2 d'environ 10%.
    Plafonne a +/- 20%.

    Args:
        user_surface: Surface du bien a estimer.
        comparables: DataFrame des comparables.

    Returns:
        Facteur d'ajustement (ex: 0.95 = -5%).
    """
    if len(comparables) == 0:
        return 1.0

    median_surface = float(comparables["surface_utilisee"].median())
    if median_surface <= 0:
        return 1.0

    ratio = user_surface / median_surface
    if ratio <= 0:
        return 1.0

    # log2(ratio) * -0.1 : chaque doublement = -10%
    adjustment = 1 - 0.1 * math.log2(ratio)
    return max(0.8, min(1.2, adjustment))


def _get_zone_stats(codinsee: str, type_bien: str) -> dict | None:
    """Recupere les statistiques de zone depuis mart."""
    engine = get_engine()
    try:
        query = text("""
            SELECT total_transactions, last_12m_transactions,
                   median_prix_m2_12m, stddev_prix_m2_12m,
                   trend_12m, data_quality_flag
            FROM mart.zone_stats
            WHERE codinsee = :codinsee AND type_bien = :type_bien
        """)
        with engine.connect() as conn:
            result = conn.execute(query, {"codinsee": codinsee, "type_bien": type_bien})
            row = result.fetchone()
            if row:
                return {
                    "total_transactions": row[0],
                    "last_12m_transactions": row[1],
                    "median_prix_m2_12m": float(row[2]) if row[2] else None,
                    "stddev_prix_m2_12m": float(row[3]) if row[3] else None,
                    "trend_12m": float(row[4]) if row[4] else None,
                    "data_quality_flag": row[5],
                }
    except Exception:
        pass
    return None


def _get_historical_stats(codinsee: str, coddep: str, type_bien: str) -> pd.DataFrame:
    """Recupere l'historique des medianes par semestre."""
    engine = get_engine()
    # D'abord essayer au niveau commune
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2,
               q1_prix_m2, q3_prix_m2
        FROM mart.prix_m2_commune
        WHERE codinsee = :codinsee AND type_bien = :type_bien
        ORDER BY annee, semestre
    """)
    df = pd.read_sql(query, engine, params={"codinsee": codinsee, "type_bien": type_bien})

    if len(df) == 0:
        # Fallback departement
        query = text("""
            SELECT annee, semestre, nb_transactions, median_prix_m2,
                   q1_prix_m2, q3_prix_m2
            FROM mart.prix_m2_departement
            WHERE coddep = :coddep AND type_bien = :type_bien
            ORDER BY annee, semestre
        """)
        df = pd.read_sql(query, engine, params={"coddep": coddep, "type_bien": type_bien})

    return df


def estimate(
    address: str,
    type_bien: str,
    surface: float,
    nb_pieces: int | None = None,
    postcode: str | None = None,
) -> EstimationResult | None:
    """
    Estime le prix d'un bien immobilier.

    Args:
        address: Adresse en texte libre.
        type_bien: 'maison' ou 'appartement'.
        surface: Surface en m2.
        nb_pieces: Nombre de pieces (optionnel).
        postcode: Code postal (optionnel, aide le geocodage).

    Returns:
        EstimationResult ou None si le geocodage echoue.
    """
    # Etape 1 : Geocodage
    geo = geocode_best(address, postcode=postcode)
    if geo is None:
        return None

    # Etape 2 : Recherche de comparables
    search = find_comparables(
        latitude=geo.latitude,
        longitude=geo.longitude,
        codinsee=geo.citycode,
        type_bien=type_bien,
        surface=surface,
        nb_pieces=nb_pieces,
    )
    comparables = search.comparables

    if len(comparables) == 0:
        # Aucun comparable, estimation impossible
        return EstimationResult(
            geocoding=geo,
            prix_m2_estime=0,
            prix_total_estime=0,
            confidence=ConfidenceResult(
                level="low",
                level_label="Pas de donnees",
                low_estimate=0,
                high_estimate=0,
                nb_comparables=0,
                search_level=4,
            ),
            niveau_geo=search.level_desc,
            nb_comparables=0,
            adjustment_factor=1.0,
            comparables=comparables,
            zone_stats=None,
        )

    # Etape 3 : Mediane prix/m2
    base_median = float(np.median(comparables["prix_m2"]))

    # Etape 4 : Ajustement surface
    adjustment = _compute_surface_adjustment(surface, comparables)
    adjusted_prix_m2 = base_median * adjustment

    # Etape 5 : Correction tendance (si disponible)
    zone_stats = _get_zone_stats(geo.citycode, type_bien)
    # La correction tendance est deja refletee dans les comparables recents,
    # donc on ne l'applique pas en double. Elle sert pour l'affichage.

    # Etape 6 : Prix total
    prix_total = adjusted_prix_m2 * surface

    # Etape 7 : Confiance
    confidence = compute_confidence(
        comparables=comparables,
        search_level=search.level,
        surface=surface,
        adjustment=adjustment,
    )

    return EstimationResult(
        geocoding=geo,
        prix_m2_estime=round(adjusted_prix_m2, 2),
        prix_total_estime=round(prix_total, 0),
        confidence=confidence,
        niveau_geo=search.level_desc,
        nb_comparables=len(comparables),
        adjustment_factor=round(adjustment, 4),
        comparables=comparables,
        zone_stats=zone_stats,
    )
