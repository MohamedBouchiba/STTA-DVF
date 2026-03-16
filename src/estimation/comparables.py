"""Recherche de transactions comparables."""

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text

from src.config import MIN_COMPARABLES
from src.db import get_engine
from src.estimation.zone_config import ZoneConfig


@dataclass
class ComparableSearch:
    """Parametres et resultats d'une recherche de comparables."""
    latitude: float
    longitude: float
    code_commune: str
    code_departement: str
    type_bien: str
    surface: float | None
    nb_pieces: int | None
    level: int           # Niveau de fallback utilise (1-4)
    level_desc: str      # Description du niveau
    comparables: pd.DataFrame
    zone_config: ZoneConfig | None = None


def find_comparables(
    latitude: float,
    longitude: float,
    code_commune: str,
    type_bien: str,
    surface: float | None = None,
    nb_pieces: int | None = None,
    min_comparables: int | None = None,
    zone_config: ZoneConfig | None = None,
) -> ComparableSearch:
    """
    Recherche des transactions comparables avec fallback hierarchique.

    Si zone_config est fourni, utilise 3 zones concentriques exclusives
    avec distance et zone assignees. Sinon, fallback classique.

    Niveaux de fallback :
        1. Multi-zones (R1/R2/R3 km), 24 derniers mois
        2. Meme commune, 24 mois
        3. Meme commune, 48 mois
        4. Meme departement, 24 mois
    """
    if min_comparables is None:
        min_comparables = MIN_COMPARABLES
    if zone_config is None:
        zone_config = ZoneConfig()

    engine = get_engine()
    code_departement = code_commune[:2] if len(code_commune) >= 2 else code_commune

    # Colonnes de base
    cols = """
        t.id_mutation, t.date_mutation, t.valeur_fonciere, t.type_bien,
        t.surface, t.nb_pieces, t.prix_m2,
        t.code_commune, t.nom_commune, t.code_departement,
        t.adresse, t.code_postal,
        t.latitude, t.longitude
    """

    # Filtres optionnels de surface
    surface_filter = ""
    if surface:
        surface_filter = f"AND t.surface BETWEEN {surface * 0.5} AND {surface * 2.0}"

    r1, r2, r3 = zone_config.radii_meters

    params = {
        "lat": latitude,
        "lon": longitude,
        "code_commune": code_commune,
        "code_departement": code_departement,
        "type_bien": type_bien,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "max_comp": zone_config.max_comparables,
    }

    # ---- Level 1 : Multi-zones (3 zones concentriques) ----
    query_zones = f"""
        SELECT {cols},
               ST_Distance(
                   t.geom::geography,
                   ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
               ) AS distance_m,
               CASE
                   WHEN ST_DWithin(t.geom::geography,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :r1) THEN 1
                   WHEN ST_DWithin(t.geom::geography,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :r2) THEN 2
                   ELSE 3
               END AS zone
        FROM core.transactions t
        WHERE t.type_bien = :type_bien
          AND NOT t.is_outlier
          AND t.geom IS NOT NULL
          AND ST_DWithin(
              t.geom::geography,
              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
              :r3
          )
          AND t.date_mutation >= CURRENT_DATE - INTERVAL '24 months'
          {surface_filter}
        ORDER BY distance_m
        LIMIT :max_comp
    """

    df = pd.read_sql(text(query_zones), engine, params=params)

    if len(df) >= min_comparables:
        desc_parts = []
        for z in [1, 2, 3]:
            n = len(df[df["zone"] == z])
            if n > 0:
                if z == 1:
                    desc_parts.append(f"zone 1 (0-{zone_config.radius_1_km} km): {n}")
                elif z == 2:
                    desc_parts.append(f"zone 2 ({zone_config.radius_1_km}-{zone_config.radius_2_km} km): {n}")
                else:
                    desc_parts.append(f"zone 3 ({zone_config.radius_2_km}-{zone_config.radius_3_km} km): {n}")

        return ComparableSearch(
            latitude=latitude,
            longitude=longitude,
            code_commune=code_commune,
            code_departement=code_departement,
            type_bien=type_bien,
            surface=surface,
            nb_pieces=nb_pieces,
            level=1,
            level_desc=", ".join(desc_parts) if desc_parts else f"multi-zones ({zone_config.radius_3_km} km)",
            comparables=df,
            zone_config=zone_config,
        )

    # ---- Fallback levels 2-4 (sans zones) ----
    fallback_levels = [
        {
            "level": 2,
            "desc": "commune, 24 derniers mois",
            "where": """
                t.code_commune = :code_commune
                AND t.date_mutation >= CURRENT_DATE - INTERVAL '24 months'
            """,
        },
        {
            "level": 3,
            "desc": "commune, 48 derniers mois",
            "where": """
                t.code_commune = :code_commune
                AND t.date_mutation >= CURRENT_DATE - INTERVAL '48 months'
            """,
        },
        {
            "level": 4,
            "desc": "departement, 24 derniers mois",
            "where": """
                t.code_departement = :code_departement
                AND t.date_mutation >= CURRENT_DATE - INTERVAL '24 months'
            """,
        },
    ]

    # Ajouter distance_m pour les fallbacks aussi
    fallback_cols = f"""
        {cols},
        CASE WHEN t.geom IS NOT NULL THEN
            ST_Distance(
                t.geom::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
        ELSE NULL END AS distance_m
    """

    for lvl in fallback_levels:
        query = f"""
            SELECT {fallback_cols}
            FROM core.transactions t
            WHERE t.type_bien = :type_bien
              AND NOT t.is_outlier
              AND {lvl['where']}
              {surface_filter}
            ORDER BY t.date_mutation DESC
            LIMIT :max_comp
        """

        df = pd.read_sql(text(query), engine, params=params)

        if len(df) >= min_comparables:
            return ComparableSearch(
                latitude=latitude,
                longitude=longitude,
                code_commune=code_commune,
                code_departement=code_departement,
                type_bien=type_bien,
                surface=surface,
                nb_pieces=nb_pieces,
                level=lvl["level"],
                level_desc=lvl["desc"],
                comparables=df,
                zone_config=None,
            )

    # Pas assez de comparables meme au dernier niveau
    return ComparableSearch(
        latitude=latitude,
        longitude=longitude,
        code_commune=code_commune,
        code_departement=code_departement,
        type_bien=type_bien,
        surface=surface,
        nb_pieces=nb_pieces,
        level=4,
        level_desc="departement, 24 derniers mois (donnees insuffisantes)",
        comparables=df,
        zone_config=None,
    )
