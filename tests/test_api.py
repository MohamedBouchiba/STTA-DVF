"""Tests de l'API FastAPI STTA-DVF."""

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.schemas import VALID_SECTIONS

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health & Defaults
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_format(self):
        """Health endpoint retourne le format attendu."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "database" in data


class TestDefaults:
    def test_defaults_structure(self):
        """Defaults retourne les 7 categories de coefficients."""
        resp = client.get("/api/v1/defaults")
        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {"type", "quality", "condition", "construction", "characteristics", "floor", "zone"}
        assert expected_keys == set(data.keys())

    def test_defaults_type_coefficients(self):
        """Les coefficients de type contiennent les types attendus."""
        resp = client.get("/api/v1/defaults")
        data = resp.json()
        assert "appartement" in data["type"]
        assert "maison" in data["type"]
        assert data["type"]["appartement"] == 1.0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_missing_address(self):
        """Adresse manquante -> 422."""
        resp = client.post("/api/v1/estimate", json={
            "property_type": "appartement",
            "surface": 50,
        })
        assert resp.status_code == 422

    def test_missing_surface(self):
        """Surface manquante -> 422."""
        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
        })
        assert resp.status_code == 422

    def test_invalid_surface(self):
        """Surface <= 0 -> 422."""
        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
            "surface": 0,
        })
        assert resp.status_code == 422

    def test_missing_property_type(self):
        """Type de bien manquant -> 422."""
        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "surface": 50,
        })
        assert resp.status_code == 422

    def test_address_too_short(self):
        """Adresse trop courte -> 422."""
        resp = client.post("/api/v1/estimate", json={
            "address": "ab",
            "property_type": "appartement",
            "surface": 50,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Include filter (avec mock)
# ---------------------------------------------------------------------------

def _mock_geocode_result():
    """Cree un mock GeocodingResult."""
    geo = MagicMock()
    geo.label = "12 Rue de Rivoli, 75001 Paris"
    geo.score = 0.95
    geo.latitude = 48.856
    geo.longitude = 2.359
    geo.citycode = "75101"
    geo.city = "Paris"
    geo.postcode = "75001"
    geo.context = "75, Paris, Ile-de-France"
    return geo


def _mock_comparables_df():
    """Cree un DataFrame de comparables mock."""
    import pandas as pd
    return pd.DataFrame({
        "id_mutation": ["2024-1", "2024-2", "2024-3", "2024-4", "2024-5"],
        "date_mutation": ["2024-01-15", "2024-02-20", "2024-03-10", "2024-04-05", "2024-05-12"],
        "valeur_fonciere": [500000, 450000, 550000, 480000, 520000],
        "type_bien": ["appartement"] * 5,
        "surface": [50, 45, 55, 48, 52],
        "nb_pieces": [3, 2, 3, 2, 3],
        "prix_m2": [10000, 10000, 10000, 10000, 10000],
        "code_commune": ["75101"] * 5,
        "nom_commune": ["Paris 1er"] * 5,
        "code_departement": ["75"] * 5,
        "latitude": [48.856, 48.857, 48.855, 48.858, 48.854],
        "longitude": [2.359, 2.360, 2.358, 2.361, 2.357],
        "distance_m": [100, 200, 300, 400, 500],
        "zone": [1, 1, 2, 2, 3],
    })


def _mock_search_result(comparables_df):
    """Cree un mock ComparableSearch."""
    from src.estimation.zone_config import ZoneConfig
    search = MagicMock()
    search.comparables = comparables_df
    search.level = 1
    search.level_desc = "multi-zones (3 km)"
    search.zone_config = ZoneConfig()
    return search


class TestIncludeFilter:
    @patch("src.api.service.geocode_best")
    @patch("src.api.service.find_comparables")
    @patch("src.api.service.get_zone_stats")
    @patch("src.api.service.pd.read_sql")
    def test_include_estimation_only(self, mock_read_sql, mock_zone_stats, mock_find, mock_geocode):
        """include=['estimation'] retourne seulement la section estimation."""
        mock_geocode.return_value = _mock_geocode_result()
        mock_find.return_value = _mock_search_result(_mock_comparables_df())
        mock_zone_stats.return_value = None
        mock_read_sql.return_value = _mock_comparables_df().head(0)

        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
            "surface": 50,
            "include": ["estimation"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["estimation"] is not None
        assert data["geocoding"] is None
        assert data["adjustments"] is None
        assert data["zone_stats"] is None
        assert data["evolution"] is None
        assert data["comparables"] is None

    @patch("src.api.service.geocode_best")
    @patch("src.api.service.find_comparables")
    @patch("src.api.service.get_zone_stats")
    @patch("src.api.service.pd.read_sql")
    def test_include_all_by_default(self, mock_read_sql, mock_zone_stats, mock_find, mock_geocode):
        """include=None retourne toutes les sections."""
        mock_geocode.return_value = _mock_geocode_result()
        mock_find.return_value = _mock_search_result(_mock_comparables_df())
        mock_zone_stats.return_value = {
            "total_transactions": 100,
            "last_12m_transactions": 50,
            "median_prix_m2_12m": 10000,
            "stddev_prix_m2_12m": 2000,
            "trend_12m": 3.5,
            "data_quality_flag": "good",
        }
        import pandas as pd
        semester_df = pd.DataFrame({
            "annee": [2023, 2024], "semestre": [2, 1], "nb_transactions": [40, 50],
            "median_prix_m2": [9500, 10000], "q1_prix_m2": [7500, 8000], "q3_prix_m2": [11500, 12000],
        })
        monthly_df = pd.DataFrame({
            "annee_mois": ["2024-01"], "nb_transactions": [20],
            "median_prix_m2": [10000], "rolling_median_6m": [9800],
        })
        # 2 calls: commune (>= 2 rows so no fallback), then monthly
        mock_read_sql.side_effect = [semester_df, monthly_df]

        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
            "surface": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["geocoding"] is not None
        assert data["estimation"] is not None
        assert data["adjustments"] is not None
        assert data["zone_stats"] is not None
        assert data["evolution"] is not None
        assert data["comparables"] is not None

    @patch("src.api.service.geocode_best")
    def test_geocoding_failed(self, mock_geocode):
        """Geocodage echoue -> status geocoding_failed."""
        mock_geocode.return_value = None

        resp = client.post("/api/v1/estimate", json={
            "address": "adresse inconnue xyz",
            "property_type": "appartement",
            "surface": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "geocoding_failed"


# ---------------------------------------------------------------------------
# Estimation details (avec mock)
# ---------------------------------------------------------------------------

class TestEstimationDetails:
    @patch("src.api.service.geocode_best")
    @patch("src.api.service.find_comparables")
    @patch("src.api.service.get_zone_stats")
    @patch("src.api.service.pd.read_sql")
    def test_estimation_fields(self, mock_read_sql, mock_zone_stats, mock_find, mock_geocode):
        """La section estimation contient tous les champs attendus."""
        mock_geocode.return_value = _mock_geocode_result()
        mock_find.return_value = _mock_search_result(_mock_comparables_df())
        mock_zone_stats.return_value = None
        import pandas as pd
        mock_read_sql.return_value = pd.DataFrame()

        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
            "surface": 50,
            "include": ["estimation"],
        })
        data = resp.json()
        est = data["estimation"]
        assert "prix_m2_base" in est
        assert "prix_total_base" in est
        assert "adjustment_factor" in est
        assert "prix_m2_ajuste" in est
        assert "prix_total_ajuste" in est
        assert "total_multiplier" in est
        assert "confidence" in est
        assert "nb_comparables" in est
        assert "niveau_geo" in est
        assert est["nb_comparables"] == 5
        assert est["prix_m2_base"] > 0
        assert est["confidence"]["level"] in ("high", "medium", "low")

    @patch("src.api.service.geocode_best")
    @patch("src.api.service.find_comparables")
    @patch("src.api.service.get_zone_stats")
    @patch("src.api.service.pd.read_sql")
    def test_adjustments_with_duplex(self, mock_read_sql, mock_zone_stats, mock_find, mock_geocode):
        """Un duplex a un coefficient type != 1.0."""
        mock_geocode.return_value = _mock_geocode_result()
        mock_find.return_value = _mock_search_result(_mock_comparables_df())
        mock_zone_stats.return_value = None
        import pandas as pd
        mock_read_sql.return_value = pd.DataFrame()

        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "duplex",
            "surface": 50,
            "include": ["estimation", "adjustments"],
        })
        data = resp.json()
        assert data["estimation"]["total_multiplier"] != 1.0
        assert len(data["adjustments"]["details"]) > 0
        assert any(d["name"] == "type" for d in data["adjustments"]["details"])

    @patch("src.api.service.geocode_best")
    @patch("src.api.service.find_comparables")
    @patch("src.api.service.get_zone_stats")
    @patch("src.api.service.pd.read_sql")
    def test_zone_breakdown_present(self, mock_read_sql, mock_zone_stats, mock_find, mock_geocode):
        """Zone breakdown est present quand multi-zones est actif."""
        mock_geocode.return_value = _mock_geocode_result()
        mock_find.return_value = _mock_search_result(_mock_comparables_df())
        mock_zone_stats.return_value = None
        import pandas as pd
        mock_read_sql.return_value = pd.DataFrame()

        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
            "surface": 50,
            "include": ["estimation"],
        })
        data = resp.json()
        zb = data["estimation"]["zone_breakdown"]
        assert zb is not None
        assert "1" in zb
        assert "2" in zb
        assert "3" in zb
        assert zb["1"]["count"] > 0

    @patch("src.api.service.geocode_best")
    @patch("src.api.service.find_comparables")
    @patch("src.api.service.get_zone_stats")
    @patch("src.api.service.pd.read_sql")
    def test_zone_config_returned(self, mock_read_sql, mock_zone_stats, mock_find, mock_geocode):
        """Zone config est retournee dans la section estimation."""
        mock_geocode.return_value = _mock_geocode_result()
        mock_find.return_value = _mock_search_result(_mock_comparables_df())
        mock_zone_stats.return_value = None
        import pandas as pd
        mock_read_sql.return_value = pd.DataFrame()

        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
            "surface": 50,
            "zone_config": {"radius_1_km": 0.5, "radius_2_km": 1.5, "radius_3_km": 3.0},
            "include": ["estimation"],
        })
        data = resp.json()
        zc = data["estimation"]["zone_config"]
        assert zc is not None
        assert zc["radius_1_km"] == 1.0  # Default from ZoneConfig (search.zone_config)


# ---------------------------------------------------------------------------
# Comparables section
# ---------------------------------------------------------------------------

class TestComparables:
    @patch("src.api.service.geocode_best")
    @patch("src.api.service.find_comparables")
    @patch("src.api.service.get_zone_stats")
    @patch("src.api.service.pd.read_sql")
    def test_comparables_items(self, mock_read_sql, mock_zone_stats, mock_find, mock_geocode):
        """Les comparables contiennent les champs attendus."""
        mock_geocode.return_value = _mock_geocode_result()
        mock_find.return_value = _mock_search_result(_mock_comparables_df())
        mock_zone_stats.return_value = None
        import pandas as pd
        mock_read_sql.return_value = pd.DataFrame()

        resp = client.post("/api/v1/estimate", json={
            "address": "12 rue de Rivoli, Paris",
            "property_type": "appartement",
            "surface": 50,
            "include": ["comparables"],
        })
        data = resp.json()
        comp = data["comparables"]
        assert comp["count"] == 5
        item = comp["items"][0]
        assert "id_mutation" in item
        assert "latitude" in item
        assert "longitude" in item
        assert "distance_m" in item
        assert "zone" in item
        assert "prix_m2" in item
        assert "surface" in item


# ---------------------------------------------------------------------------
# Integration tests (real DB, skipped without DB)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIntegrationEstimate:
    def test_paris_full_estimation(self):
        """Estimation complete pour Paris, toutes sections."""
        resp = client.post("/api/v1/estimate", json={
            "address": "25 avenue des Champs-Elysees, Paris",
            "property_type": "appartement",
            "surface": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

        # Geocoding
        assert data["geocoding"] is not None
        assert data["geocoding"]["citycode"].startswith("75")
        assert data["geocoding"]["score"] > 0.5

        # Estimation
        est = data["estimation"]
        assert est is not None
        assert 5000 <= est["prix_m2_base"] <= 25000
        assert est["nb_comparables"] >= 5
        assert est["confidence"]["level"] in ("high", "medium", "low")

        # Adjustments (appartement standard -> multiplier ~1.0)
        adj = data["adjustments"]
        assert adj is not None
        assert adj["total_multiplier"] == 1.0 or abs(adj["total_multiplier"] - 1.0) < 0.01

        # Evolution
        evo = data["evolution"]
        assert evo is not None
        assert evo["source"] in ("commune", "departement")
        assert len(evo["semester"]) > 0

        # Comparables
        comp = data["comparables"]
        assert comp is not None
        assert comp["count"] >= 5

    def test_paris_duplex_adjustments(self):
        """Duplex a Paris : total_multiplier > 1.0."""
        resp = client.post("/api/v1/estimate", json={
            "address": "15 rue de la Paix, Paris",
            "property_type": "duplex",
            "surface": 80,
            "etage": 5,
            "ascenseur": True,
            "balcon": True,
            "condition": "bon_etat",
            "quality": "superieure",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["estimation"]["total_multiplier"] > 1.0
        assert data["estimation"]["prix_total_ajuste"] > data["estimation"]["prix_total_base"]

    def test_marseille_with_zone_config(self):
        """Marseille avec zone_config custom."""
        resp = client.post("/api/v1/estimate", json={
            "address": "1 rue de la Republique, Marseille",
            "property_type": "appartement",
            "surface": 65,
            "zone_config": {
                "radius_1_km": 0.5,
                "radius_2_km": 1.5,
                "radius_3_km": 4.0,
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert 1000 <= data["estimation"]["prix_m2_base"] <= 8000

    def test_include_filter_integration(self):
        """Include filter fonctionne avec vraie DB."""
        resp = client.post("/api/v1/estimate", json={
            "address": "25 avenue des Champs-Elysees, Paris",
            "property_type": "appartement",
            "surface": 50,
            "include": ["estimation", "comparables"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["estimation"] is not None
        assert data["comparables"] is not None
        assert data["geocoding"] is None
        assert data["adjustments"] is None
        assert data["zone_stats"] is None
        assert data["evolution"] is None

    def test_health_integration(self):
        """Health check avec vraie DB."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["transactions_count"] > 0
        assert data["postgis_version"] is not None
