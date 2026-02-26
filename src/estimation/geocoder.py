"""Geocodage d'adresses via l'API Geoplateforme (ex-BAN)."""

from dataclasses import dataclass

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import GEOCODING_API_URL


@dataclass
class GeocodingResult:
    """Resultat d'un geocodage."""
    label: str
    score: float
    latitude: float
    longitude: float
    housenumber: str | None
    street: str | None
    postcode: str
    city: str
    citycode: str  # Code INSEE
    context: str   # ex: "75, Paris, Ile-de-France"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def geocode(address: str, limit: int = 5, postcode: str | None = None) -> list[GeocodingResult]:
    """
    Geocode une adresse via l'API Geoplateforme.

    Args:
        address: Adresse en texte libre.
        limit: Nombre max de resultats.
        postcode: Code postal pour affiner (optionnel).

    Returns:
        Liste de resultats ordonnee par score decroissant.
    """
    params = {
        "q": address,
        "limit": limit,
        "type": "housenumber",
    }
    if postcode:
        params["postcode"] = postcode

    resp = requests.get(GEOCODING_API_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0])

        results.append(GeocodingResult(
            label=props.get("label", ""),
            score=props.get("score", 0),
            latitude=coords[1],
            longitude=coords[0],
            housenumber=props.get("housenumber"),
            street=props.get("street"),
            postcode=props.get("postcode", ""),
            city=props.get("city", ""),
            citycode=props.get("citycode", ""),
            context=props.get("context", ""),
        ))

    return results


def geocode_best(address: str, postcode: str | None = None, min_score: float = 0.4) -> GeocodingResult | None:
    """
    Retourne le meilleur resultat de geocodage, ou None si score insuffisant.

    Args:
        address: Adresse en texte libre.
        postcode: Code postal (optionnel).
        min_score: Score minimum acceptable (0 a 1).

    Returns:
        Le meilleur resultat ou None.
    """
    results = geocode(address, limit=1, postcode=postcode)
    if not results:
        return None
    best = results[0]
    if best.score < min_score:
        return None
    return best
