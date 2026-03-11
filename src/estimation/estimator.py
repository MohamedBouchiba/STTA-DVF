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
from src.estimation.zone_config import ZoneConfig


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

    # Multi-zones
    zone_config: ZoneConfig | None = None
    zone_breakdown: dict | None = None


def compute_surface_adjustment(user_surface: float, comparables: pd.DataFrame) -> float:
    """
    Ajustement prix/m2 en fonction de la surface.

    Les grands biens ont tendance a avoir un prix/m2 plus bas.
    Chaque doublement de surface reduit le prix/m2 d'environ 10%.
    Plafonne a +/- 20%.
    """
    if len(comparables) == 0:
        return 1.0

    surface_col = "surface" if "surface" in comparables.columns else "surface_utilisee"
    median_surface = float(comparables[surface_col].median())
    if median_surface <= 0:
        return 1.0

    ratio = user_surface / median_surface
    if ratio <= 0:
        return 1.0

    adjustment = 1 - 0.1 * math.log2(ratio)
    return max(0.8, min(1.2, adjustment))


def compute_weighted_median(
    comparables: pd.DataFrame,
    zone_config: ZoneConfig,
) -> tuple[float, dict]:
    """
    Mediane ponderee par zone.

    Calcule la mediane de prix_m2 dans chaque zone, puis
    retourne la moyenne ponderee des medianes.

    Returns:
        (prix_m2, zone_breakdown) ou zone_breakdown contient
        les medianes, counts et poids par zone.
    """
    if "zone" not in comparables.columns:
        return float(np.median(comparables["prix_m2"])), {}

    breakdown = {}
    medians = {}
    weights = {}

    for z in [1, 2, 3]:
        group = comparables[comparables["zone"] == z]
        count = len(group)
        if count > 0:
            med = float(group["prix_m2"].median())
            w = zone_config.weight_for_zone(z)
            medians[z] = med
            weights[z] = w
            breakdown[z] = {
                "count": count,
                "median_prix_m2": round(med, 2),
                "weight": w,
            }
        else:
            breakdown[z] = {"count": 0, "median_prix_m2": None, "weight": 0}

    # Redistribuer les poids proportionnellement aux zones presentes
    total_weight = sum(weights.values())
    if total_weight == 0:
        return float(np.median(comparables["prix_m2"])), breakdown

    weighted_prix_m2 = sum(
        medians[z] * weights[z] / total_weight for z in medians
    )

    # Stocker le poids effectif (normalise) dans le breakdown
    for z in breakdown:
        if breakdown[z]["count"] > 0:
            breakdown[z]["effective_weight"] = round(weights[z] / total_weight, 4)
        else:
            breakdown[z]["effective_weight"] = 0

    return weighted_prix_m2, breakdown


def get_zone_stats(code_commune: str, type_bien: str) -> dict | None:
    """Recupere les statistiques de zone depuis mart."""
    engine = get_engine()
    try:
        query = text("""
            SELECT total_transactions, last_12m_transactions,
                   median_prix_m2_12m, stddev_prix_m2_12m,
                   trend_12m, data_quality_flag
            FROM mart.zone_stats
            WHERE code_commune = :code_commune AND type_bien = :type_bien
        """)
        with engine.connect() as conn:
            result = conn.execute(query, {"code_commune": code_commune, "type_bien": type_bien})
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


def get_historical_stats(code_commune: str, code_departement: str, type_bien: str) -> pd.DataFrame:
    """Recupere l'historique des medianes par semestre."""
    engine = get_engine()
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2,
               q1_prix_m2, q3_prix_m2
        FROM mart.stats_commune
        WHERE code_commune = :code_commune AND type_bien = :type_bien
        ORDER BY annee, semestre
    """)
    df = pd.read_sql(query, engine, params={"code_commune": code_commune, "type_bien": type_bien})

    if len(df) == 0:
        query = text("""
            SELECT annee, semestre, nb_transactions, median_prix_m2,
                   q1_prix_m2, q3_prix_m2
            FROM mart.stats_departement
            WHERE code_departement = :code_departement AND type_bien = :type_bien
            ORDER BY annee, semestre
        """)
        df = pd.read_sql(query, engine, params={"code_departement": code_departement, "type_bien": type_bien})

    return df


def estimate(
    address: str,
    type_bien: str,
    surface: float,
    nb_pieces: int | None = None,
    postcode: str | None = None,
    zone_config: ZoneConfig | None = None,
    geocoding: GeocodingResult | None = None,
) -> EstimationResult | None:
    """
    Estime le prix d'un bien immobilier.

    Args:
        address: Adresse en texte libre.
        type_bien: 'maison' ou 'appartement'.
        surface: Surface en m2.
        nb_pieces: Nombre de pieces (optionnel).
        postcode: Code postal (optionnel, aide le geocodage).
        zone_config: Configuration des zones concentriques (optionnel).
        geocoding: Resultat de geocodage existant (optionnel, evite un appel API).

    Returns:
        EstimationResult ou None si le geocodage echoue.
    """
    # Etape 1 : Geocodage (reutiliser si fourni)
    if geocoding is not None:
        geo = geocoding
    else:
        geo = geocode_best(address, postcode=postcode)
        if geo is None:
            return None

    # Etape 2 : Recherche de comparables
    search = find_comparables(
        latitude=geo.latitude,
        longitude=geo.longitude,
        code_commune=geo.citycode,
        type_bien=type_bien,
        surface=surface,
        nb_pieces=nb_pieces,
        zone_config=zone_config,
    )
    comparables = search.comparables

    if len(comparables) == 0:
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
            zone_config=search.zone_config,
            zone_breakdown=None,
        )

    # Etape 3 : Mediane prix/m2 (ponderee par zone si multi-zones)
    zone_breakdown = None
    if search.zone_config and "zone" in comparables.columns:
        base_median, zone_breakdown = compute_weighted_median(comparables, search.zone_config)
    else:
        base_median = float(np.median(comparables["prix_m2"]))

    # Etape 4 : Ajustement surface
    adjustment = compute_surface_adjustment(surface, comparables)
    adjusted_prix_m2 = base_median * adjustment

    # Etape 5 : Stats zone
    zone_stats = get_zone_stats(geo.citycode, type_bien)

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
        zone_config=search.zone_config,
        zone_breakdown=zone_breakdown,
    )
