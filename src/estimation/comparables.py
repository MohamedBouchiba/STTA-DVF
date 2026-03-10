"""Recherche de transactions comparables."""

from dataclasses import dataclass

import pandas as pd
from sqlalchemy import text

from src.config import MIN_COMPARABLES
from src.db import get_engine


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


def find_comparables(
    latitude: float,
    longitude: float,
    code_commune: str,
    type_bien: str,
    surface: float | None = None,
    nb_pieces: int | None = None,
    min_comparables: int | None = None,
) -> ComparableSearch:
    """
    Recherche des transactions comparables avec fallback hierarchique.

    Niveaux de fallback :
        1. Rayon 1km, 24 derniers mois
        2. Meme commune, 24 mois
        3. Meme commune, 48 mois
        4. Meme departement, 24 mois

    Args:
        latitude: Latitude du bien.
        longitude: Longitude du bien.
        code_commune: Code INSEE de la commune.
        type_bien: 'maison' ou 'appartement'.
        surface: Surface du bien (pour filtrer les comparables proches).
        nb_pieces: Nombre de pieces (optionnel).
        min_comparables: Nombre minimum de comparables requis.

    Returns:
        ComparableSearch avec les resultats.
    """
    if min_comparables is None:
        min_comparables = MIN_COMPARABLES

    engine = get_engine()
    code_departement = code_commune[:2] if len(code_commune) >= 2 else code_commune

    # Colonnes a selectionner (geo integre dans core.transactions)
    cols = """
        t.id_mutation, t.date_mutation, t.valeur_fonciere, t.type_bien,
        t.surface, t.nb_pieces, t.prix_m2,
        t.code_commune, t.nom_commune, t.code_departement,
        t.latitude, t.longitude
    """

    # Filtres optionnels de surface
    surface_filter = ""
    if surface:
        surface_filter = f"AND t.surface BETWEEN {surface * 0.5} AND {surface * 2.0}"

    # Niveaux de recherche
    levels = [
        {
            "level": 1,
            "desc": "1 km, 24 derniers mois",
            "where": """
                t.geom IS NOT NULL
                AND ST_DWithin(
                    t.geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    1000
                )
                AND t.date_mutation >= CURRENT_DATE - INTERVAL '24 months'
            """,
        },
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

    params = {
        "lat": latitude,
        "lon": longitude,
        "code_commune": code_commune,
        "code_departement": code_departement,
        "type_bien": type_bien,
    }

    df = pd.DataFrame()

    for lvl in levels:
        query = f"""
            SELECT {cols}
            FROM core.transactions t
            WHERE t.type_bien = :type_bien
              AND NOT t.is_outlier
              AND {lvl['where']}
              {surface_filter}
            ORDER BY t.date_mutation DESC
            LIMIT 500
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
            )

    # Si meme le dernier niveau n'a pas assez, retourner ce qu'on a
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
    )
