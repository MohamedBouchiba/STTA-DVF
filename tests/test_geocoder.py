"""Tests du geocodeur."""

from unittest.mock import patch, MagicMock

import pytest

from src.estimation.geocoder import geocode, geocode_best, GeocodingResult


MOCK_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [2.3376, 48.8606]},
            "properties": {
                "label": "10 Rue de Rivoli 75001 Paris",
                "score": 0.95,
                "housenumber": "10",
                "street": "Rue de Rivoli",
                "postcode": "75001",
                "city": "Paris",
                "citycode": "75101",
                "context": "75, Paris, Ile-de-France",
            },
        }
    ],
}


@patch("src.estimation.geocoder.requests.get")
def test_geocode_returns_results(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    results = geocode("10 rue de Rivoli, Paris")

    assert len(results) == 1
    assert results[0].label == "10 Rue de Rivoli 75001 Paris"
    assert results[0].citycode == "75101"
    assert results[0].latitude == pytest.approx(48.8606)
    assert results[0].longitude == pytest.approx(2.3376)


@patch("src.estimation.geocoder.requests.get")
def test_geocode_empty_response(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"type": "FeatureCollection", "features": []}
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    results = geocode("adresse inexistante xyz123")
    assert len(results) == 0


@patch("src.estimation.geocoder.requests.get")
def test_geocode_best_min_score(mock_get):
    low_score_response = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [2.0, 48.0]},
                "properties": {
                    "label": "Resultat vague",
                    "score": 0.2,
                    "postcode": "00000",
                    "city": "Inconnue",
                    "citycode": "00000",
                    "context": "",
                },
            }
        ],
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = low_score_response
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = geocode_best("xyz", min_score=0.4)
    assert result is None


@patch("src.estimation.geocoder.requests.get")
def test_geocode_best_returns_result(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    result = geocode_best("10 rue de Rivoli, Paris")
    assert result is not None
    assert result.score >= 0.4
    assert result.citycode == "75101"
