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
    codinsee: str
    coddep: str
    type_bien: str
    surface: float | None
    nb_pieces: int | None
    level: int           # Niveau de fallback utilise (1-4)
    level_desc: str      # Description du niveau
    comparables: pd.DataFrame


def find_comparables(
    latitude: float,
    longitude: float,
    codinsee: str,
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
        codinsee: Code INSEE de la commune.
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
    coddep = codinsee[:2] if len(codinsee) >= 2 else codinsee

    # Colonnes a selectionner
    cols = """
        t.idmutation, t.datemut, t.valeurfonc, t.type_bien,
        t.surface_utilisee, t.nb_pieces, t.prix_m2,
        t.codinsee, t.libcommune, t.coddep,
        g.latitude, g.longitude
    """

    # Filtres optionnels de surface
    surface_filter = ""
    if surface:
        surface_filter = f"AND t.surface_utilisee BETWEEN {surface * 0.5} AND {surface * 2.0}"

    # Niveaux de recherche
    levels = [
        {
            "level": 1,
            "desc": "1 km, 24 derniers mois",
            "where": f"""
                g.geom IS NOT NULL
                AND ST_DWithin(
                    g.geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    1000
                )
                AND t.datemut >= CURRENT_DATE - INTERVAL '24 months'
            """,
        },
        {
            "level": 2,
            "desc": "commune, 24 derniers mois",
            "where": """
                t.codinsee = :codinsee
                AND t.datemut >= CURRENT_DATE - INTERVAL '24 months'
            """,
        },
        {
            "level": 3,
            "desc": "commune, 48 derniers mois",
            "where": """
                t.codinsee = :codinsee
                AND t.datemut >= CURRENT_DATE - INTERVAL '48 months'
            """,
        },
        {
            "level": 4,
            "desc": "departement, 24 derniers mois",
            "where": """
                t.coddep = :coddep
                AND t.datemut >= CURRENT_DATE - INTERVAL '24 months'
            """,
        },
    ]

    params = {
        "lat": latitude,
        "lon": longitude,
        "codinsee": codinsee,
        "coddep": coddep,
        "type_bien": type_bien,
    }

    for lvl in levels:
        query = f"""
            SELECT {cols}
            FROM core.transactions t
            JOIN core.geo g ON g.idmutation = t.idmutation
            WHERE t.type_bien = :type_bien
              AND t.quality_score & 1 = 0
              AND {lvl['where']}
              {surface_filter}
            ORDER BY t.datemut DESC
            LIMIT 500
        """

        df = pd.read_sql(text(query), engine, params=params)

        if len(df) >= min_comparables:
            return ComparableSearch(
                latitude=latitude,
                longitude=longitude,
                codinsee=codinsee,
                coddep=coddep,
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
        codinsee=codinsee,
        coddep=coddep,
        type_bien=type_bien,
        surface=surface,
        nb_pieces=nb_pieces,
        level=4,
        level_desc="departement, 24 derniers mois (donnees insuffisantes)",
        comparables=df,
    )
