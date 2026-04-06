"""Tests du moteur d'appreciation et de l'endpoint API."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.estimation.appreciation import (
    _compute_cagr,
    _compute_cagr_regression,
    _haversine_km,
    _compute_proximity_adjustment,
    _surface_segment,
    _construction_period_key,
    compute_appreciation,
    DPE_ADJUSTMENT,
    CONSTRUCTION_ADJUSTMENT,
    COPRO_ADJUSTMENT,
    MIN_SEM_TRANSACTIONS,
    PARIS_CENTER_LAT,
    PARIS_CENTER_LON,
    GPE_BONUS,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests : fonctions utilitaires
# ---------------------------------------------------------------------------

class TestComputeCagr:
    def test_positive_growth(self):
        assert _compute_cagr(100, 110, 1.0) == 10.0

    def test_negative_growth(self):
        result = _compute_cagr(100, 90, 1.0)
        assert result is not None
        assert result < 0

    def test_zero_years(self):
        assert _compute_cagr(100, 110, 0) is None

    def test_zero_first_value(self):
        assert _compute_cagr(0, 110, 1.0) is None

    def test_multi_year(self):
        # 100 -> 121 in 2 years = 10%/an
        result = _compute_cagr(100, 121, 2.0)
        assert result is not None
        assert abs(result - 10.0) < 0.1

    def test_fractional_years(self):
        result = _compute_cagr(100, 105, 0.5)
        assert result is not None
        assert result > 0


class TestSurfaceSegment:
    def test_petit(self):
        key, label = _surface_segment(30)
        assert key == "petit"
        assert "< 40" in label

    def test_moyen(self):
        key, label = _surface_segment(55)
        assert key == "moyen"
        assert "40-80" in label

    def test_grand(self):
        key, label = _surface_segment(100)
        assert key == "grand"
        assert "> 80" in label

    def test_boundary_40(self):
        key, _ = _surface_segment(40)
        assert key == "moyen"

    def test_boundary_80(self):
        key, _ = _surface_segment(80)
        assert key == "moyen"


class TestConstructionPeriodKey:
    def test_none(self):
        assert _construction_period_key(None) is None

    def test_haussmannien(self):
        assert _construction_period_key(1840) == "avant_1850"

    def test_belle_epoque(self):
        assert _construction_period_key(1900) == "1850_1913"

    def test_entre_guerres(self):
        assert _construction_period_key(1930) == "1914_1947"

    def test_grands_ensembles(self):
        assert _construction_period_key(1960) == "1948_1969"

    def test_moderne(self):
        assert _construction_period_key(1980) == "1970_1989"

    def test_recent(self):
        assert _construction_period_key(2000) == "1990_2005"

    def test_post_rt2005(self):
        assert _construction_period_key(2020) == "apres_2005"


class TestConstants:
    def test_dpe_adjustment_all_classes(self):
        assert set(DPE_ADJUSTMENT.keys()) == {"A", "B", "C", "D", "E", "F", "G"}
        assert DPE_ADJUSTMENT["A"] > 0
        assert DPE_ADJUSTMENT["D"] == 0
        assert DPE_ADJUSTMENT["G"] < 0

    def test_dpe_monotonic(self):
        """A > B > C > D > E > F > G."""
        classes = ["A", "B", "C", "D", "E", "F", "G"]
        for i in range(len(classes) - 1):
            assert DPE_ADJUSTMENT[classes[i]] >= DPE_ADJUSTMENT[classes[i + 1]]


class TestComputeCagrRegression:
    def test_steady_growth(self):
        """Donnees monotones croissantes -> CAGR positif."""
        df = _make_semester_df()
        cagr = _compute_cagr_regression(df)
        assert cagr is not None
        assert cagr > 0

    def test_too_few_semesters(self):
        """Moins de 2 semestres valides -> None."""
        df = pd.DataFrame({
            "annee": [2024], "semestre": [1],
            "nb_transactions": [50], "median_prix_m2": [5000],
            "q1_prix_m2": [4500], "q3_prix_m2": [5500],
        })
        assert _compute_cagr_regression(df) is None

    def test_filters_low_transactions(self):
        """Semestres avec trop peu de transactions sont exclus."""
        df = _make_semester_df()
        # Mettre tous les semestres sauf le dernier a nb_transactions=2
        df.loc[:8, "nb_transactions"] = 2
        # Un seul semestre valide -> None
        assert _compute_cagr_regression(df) is None

    def test_two_valid_semesters(self):
        """Exactement 2 semestres valides -> resultat."""
        df = pd.DataFrame({
            "annee": [2023, 2024], "semestre": [1, 1],
            "nb_transactions": [30, 40],
            "median_prix_m2": [5000, 5200],
            "q1_prix_m2": [4500, 4700], "q3_prix_m2": [5500, 5700],
        })
        cagr = _compute_cagr_regression(df)
        assert cagr is not None
        assert cagr > 0  # prix en hausse

    def test_declining_market(self):
        """Prix en baisse -> CAGR negatif."""
        rows = []
        for i, (annee, sem) in enumerate([
            (2020, 1), (2020, 2), (2021, 1), (2021, 2),
            (2022, 1), (2022, 2),
        ]):
            rows.append({
                "annee": annee, "semestre": sem,
                "nb_transactions": 50,
                "median_prix_m2": 6000 - i * 100,
                "q1_prix_m2": 5500 - i * 100,
                "q3_prix_m2": 6500 - i * 100,
            })
        df = pd.DataFrame(rows)
        cagr = _compute_cagr_regression(df)
        assert cagr is not None
        assert cagr < 0

    def test_noisy_endpoint_robustness(self):
        """Un dernier semestre aberrant ne domine pas la regression."""
        df = _make_semester_df()
        # Corrompre le dernier semestre avec un spike
        df.loc[df.index[-1], "median_prix_m2"] = 8000
        cagr_noisy = _compute_cagr_regression(df)

        # L'ancien first/last donnerait (8000/5000)^(1/4.5)-1 = ~10.8%
        # La regression doit etre beaucoup plus moderee
        assert cagr_noisy is not None
        assert cagr_noisy < 8.0

    def test_custom_decay_rate(self):
        """decay_rate=1.0 (pas de decay) doit aussi fonctionner."""
        df = _make_semester_df()
        cagr_default = _compute_cagr_regression(df, decay_rate=0.85)
        cagr_no_decay = _compute_cagr_regression(df, decay_rate=1.0)
        assert cagr_default is not None
        assert cagr_no_decay is not None
        # Les deux doivent etre positifs et proches
        assert abs(cagr_default - cagr_no_decay) < 1.0


class TestHaversineKm:
    def test_same_point(self):
        assert _haversine_km(48.85, 2.35, 48.85, 2.35) == 0.0

    def test_paris_saint_denis(self):
        # Saint-Denis ~9km au nord de Paris centre
        dist = _haversine_km(48.9362, 2.3574, PARIS_CENTER_LAT, PARIS_CENTER_LON)
        assert 8.0 < dist < 10.0

    def test_paris_melun(self):
        # Melun ~45km au sud-est de Paris
        dist = _haversine_km(48.5421, 2.6553, PARIS_CENTER_LAT, PARIS_CENTER_LON)
        assert 35.0 < dist < 55.0


class TestProximityAdjustment:
    def test_paris_intramuros(self):
        """Paris centre (< 3km) -> pas de bonus."""
        prox, gpe = _compute_proximity_adjustment(48.8606, 2.3376, "75")
        assert prox == 0.0
        assert gpe == 0.0

    def test_petite_couronne_93(self):
        """Saint-Denis (93, ~9km) -> bonus proximite + GPE."""
        prox, gpe = _compute_proximity_adjustment(48.9362, 2.3574, "93")
        assert prox > 0
        assert gpe == GPE_BONUS

    def test_grande_couronne_77(self):
        """Melun (77, ~45km) -> pas de bonus (trop loin)."""
        prox, gpe = _compute_proximity_adjustment(48.5421, 2.6553, "77")
        assert prox == 0.0
        assert gpe == 0.0

    def test_hors_idf_13(self):
        """Marseille (13) -> aucun bonus."""
        prox, gpe = _compute_proximity_adjustment(43.2965, 5.3698, "13")
        assert prox == 0.0
        assert gpe == 0.0

    def test_no_coordinates(self):
        """Sans coordonnees -> aucun bonus."""
        prox, gpe = _compute_proximity_adjustment(None, None, "93")
        assert prox == 0.0
        assert gpe == 0.0

    def test_petite_couronne_92(self):
        """Boulogne (92, ~8km) -> bonus proximite + GPE."""
        prox, gpe = _compute_proximity_adjustment(48.8397, 2.2399, "92")
        assert prox > 0
        assert gpe == GPE_BONUS

    def test_grande_couronne_with_bonus(self):
        """Versailles (78, ~17km) -> bonus proximite, pas de GPE."""
        prox, gpe = _compute_proximity_adjustment(48.8014, 2.1301, "78")
        assert prox > 0
        assert gpe == 0.0


# ---------------------------------------------------------------------------
# Unit tests : compute_appreciation (mocke)
# ---------------------------------------------------------------------------

def _make_semester_df():
    """Cree un DataFrame semestriel simule (5 ans, 10 semestres)."""
    rows = []
    base = 5000
    for i, (annee, sem) in enumerate([
        (2020, 1), (2020, 2), (2021, 1), (2021, 2),
        (2022, 1), (2022, 2), (2023, 1), (2023, 2),
        (2024, 1), (2024, 2),
    ]):
        rows.append({
            "annee": annee,
            "semestre": sem,
            "nb_transactions": 50 + i * 5,
            "median_prix_m2": base + i * 50,
            "q1_prix_m2": base + i * 50 - 500,
            "q3_prix_m2": base + i * 50 + 500,
        })
    return pd.DataFrame(rows)


def _make_dept_semester_df():
    rows = []
    base = 4500
    for i, (annee, sem) in enumerate([
        (2020, 1), (2020, 2), (2021, 1), (2021, 2),
        (2022, 1), (2022, 2), (2023, 1), (2023, 2),
        (2024, 1), (2024, 2),
    ]):
        rows.append({
            "annee": annee,
            "semestre": sem,
            "nb_transactions": 200 + i * 10,
            "median_prix_m2": base + i * 40,
        })
    return pd.DataFrame(rows)


def _make_zone_stats():
    return {
        "total_transactions": 500,
        "last_12m_transactions": 80,
        "median_prix_m2_12m": 5400.0,
        "stddev_prix_m2_12m": 700.0,
        "trend_12m": 2.0,
        "data_quality_flag": "good",
    }


class TestComputeAppreciation:
    @patch("src.estimation.appreciation._get_segment_cagr")
    @patch("src.estimation.appreciation._get_zone_stats")
    @patch("src.estimation.appreciation._get_dept_semester_data")
    @patch("src.estimation.appreciation._get_semester_data")
    def test_basic_computation(self, mock_sem, mock_dept, mock_zone, mock_seg):
        mock_sem.return_value = (_make_semester_df(), "commune")
        mock_dept.return_value = _make_dept_semester_df()
        mock_zone.return_value = _make_zone_stats()
        mock_seg.return_value = 2.1

        result = compute_appreciation(
            code_commune="75111",
            type_bien="appartement",
            surface=55,
            prix_achat=350000,
            latitude=48.86,
            longitude=2.38,
        )

        assert result.historique.cagr_total_pct is not None
        assert result.historique.nb_semestres == 10
        assert result.historique.source == "commune"
        assert result.historique.benchmark_departement is not None
        assert result.historique.segment_surface is not None
        assert result.historique.segment_surface.tranche == "moyen"

        assert result.appreciation.taux_final_pct is not None
        assert "pessimiste" in result.appreciation.scenarios
        assert "pragmatique" in result.appreciation.scenarios
        assert "optimiste" in result.appreciation.scenarios

        pess = result.appreciation.scenarios["pessimiste"].taux_pct
        pragmatique = result.appreciation.scenarios["pragmatique"].taux_pct
        opti = result.appreciation.scenarios["optimiste"].taux_pct
        assert pess < pragmatique < opti

        assert result.projection.prix_achat == 350000
        assert result.projection.horizon_annees == 5
        assert len(result.projection.annees) == 5
        assert result.projection.annees[0].annee == 1
        assert result.projection.annees[-1].annee == 5

        assert len(result.risques) > 0
        assert result.confidence.level in ("high", "medium", "low")
        assert 0 <= result.confidence.score <= 100

    @patch("src.estimation.appreciation._get_segment_cagr")
    @patch("src.estimation.appreciation._get_zone_stats")
    @patch("src.estimation.appreciation._get_dept_semester_data")
    @patch("src.estimation.appreciation._get_semester_data")
    def test_dpe_adjustment(self, mock_sem, mock_dept, mock_zone, mock_seg):
        mock_sem.return_value = (_make_semester_df(), "commune")
        mock_dept.return_value = _make_dept_semester_df()
        mock_zone.return_value = _make_zone_stats()
        mock_seg.return_value = None

        # Sans DPE
        result_no_dpe = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000,
            latitude=48.86, longitude=2.38,
        )

        # Avec DPE G
        result_g = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000, dpe_classe="G",
            latitude=48.86, longitude=2.38,
        )

        # Avec DPE A
        result_a = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000, dpe_classe="A",
            latitude=48.86, longitude=2.38,
        )

        assert result_g.appreciation.taux_final_pct < result_no_dpe.appreciation.taux_final_pct
        assert result_a.appreciation.taux_final_pct > result_no_dpe.appreciation.taux_final_pct
        assert "dpe" in result_g.appreciation.ajustements
        assert "dpe" in result_a.appreciation.ajustements

    @patch("src.estimation.appreciation._get_segment_cagr")
    @patch("src.estimation.appreciation._get_zone_stats")
    @patch("src.estimation.appreciation._get_dept_semester_data")
    @patch("src.estimation.appreciation._get_semester_data")
    def test_construction_adjustment(self, mock_sem, mock_dept, mock_zone, mock_seg):
        mock_sem.return_value = (_make_semester_df(), "commune")
        mock_dept.return_value = _make_dept_semester_df()
        mock_zone.return_value = _make_zone_stats()
        mock_seg.return_value = None

        # Haussmannien (bonus)
        result_old = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000, annee_construction=1880,
            latitude=48.86, longitude=2.38,
        )

        # Grands ensembles (malus)
        result_60s = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000, annee_construction=1965,
            latitude=48.86, longitude=2.38,
        )

        assert result_old.appreciation.taux_final_pct > result_60s.appreciation.taux_final_pct
        assert "construction" in result_old.appreciation.ajustements
        assert "construction" in result_60s.appreciation.ajustements

    @patch("src.estimation.appreciation._get_segment_cagr")
    @patch("src.estimation.appreciation._get_zone_stats")
    @patch("src.estimation.appreciation._get_dept_semester_data")
    @patch("src.estimation.appreciation._get_semester_data")
    def test_horizon_custom(self, mock_sem, mock_dept, mock_zone, mock_seg):
        mock_sem.return_value = (_make_semester_df(), "commune")
        mock_dept.return_value = _make_dept_semester_df()
        mock_zone.return_value = _make_zone_stats()
        mock_seg.return_value = None

        result = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000, horizon_annees=10,
            latitude=48.86, longitude=2.38,
        )

        assert result.projection.horizon_annees == 10
        assert len(result.projection.annees) == 10

    @patch("src.estimation.appreciation._get_segment_cagr")
    @patch("src.estimation.appreciation._get_zone_stats")
    @patch("src.estimation.appreciation._get_dept_semester_data")
    @patch("src.estimation.appreciation._get_semester_data")
    def test_fallback_departement(self, mock_sem, mock_dept, mock_zone, mock_seg):
        # Retourner peu de donnees commune -> fallback
        mock_sem.return_value = (pd.DataFrame(columns=[
            "annee", "semestre", "nb_transactions", "median_prix_m2",
            "q1_prix_m2", "q3_prix_m2",
        ]), "departement")
        mock_dept.return_value = _make_dept_semester_df()
        mock_zone.return_value = None
        mock_seg.return_value = None

        result = compute_appreciation(
            code_commune="23001", type_bien="maison",
            surface=100, prix_achat=150000,
            latitude=46.17, longitude=1.87,
        )

        assert result.historique.source == "departement"
        assert result.confidence.level in ("high", "medium", "low")

    @patch("src.estimation.appreciation._get_segment_cagr")
    @patch("src.estimation.appreciation._get_zone_stats")
    @patch("src.estimation.appreciation._get_dept_semester_data")
    @patch("src.estimation.appreciation._get_semester_data")
    def test_projection_values_increase(self, mock_sem, mock_dept, mock_zone, mock_seg):
        """Les projections augmentent d'annee en annee (quand taux > 0)."""
        mock_sem.return_value = (_make_semester_df(), "commune")
        mock_dept.return_value = _make_dept_semester_df()
        mock_zone.return_value = _make_zone_stats()
        mock_seg.return_value = None

        result = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000,
        )

        # Le scenario base devrait etre positif avec nos donnees
        if result.appreciation.taux_final_pct > 0:
            for i in range(len(result.projection.annees) - 1):
                assert result.projection.annees[i + 1].pragmatique > result.projection.annees[i].pragmatique

    @patch("src.estimation.appreciation._get_segment_cagr")
    @patch("src.estimation.appreciation._get_zone_stats")
    @patch("src.estimation.appreciation._get_dept_semester_data")
    @patch("src.estimation.appreciation._get_semester_data")
    def test_risques_dpe_g(self, mock_sem, mock_dept, mock_zone, mock_seg):
        mock_sem.return_value = (_make_semester_df(), "commune")
        mock_dept.return_value = _make_dept_semester_df()
        mock_zone.return_value = _make_zone_stats()
        mock_seg.return_value = None

        result = compute_appreciation(
            code_commune="75111", type_bien="appartement",
            surface=55, prix_achat=350000, dpe_classe="G",
            latitude=48.86, longitude=2.38,
        )

        dpe_risks = [r for r in result.risques if r.facteur == "dpe"]
        assert len(dpe_risks) == 1
        assert dpe_risks[0].impact == "eleve"


# ---------------------------------------------------------------------------
# Tests API endpoint (mocke)
# ---------------------------------------------------------------------------

def _mock_geocode_appreciation():
    geo = MagicMock()
    geo.label = "15 Rue Oberkampf, 75011 Paris"
    geo.score = 0.92
    geo.latitude = 48.8606
    geo.longitude = 2.3808
    geo.citycode = "75111"
    geo.city = "Paris 11e Arrondissement"
    geo.postcode = "75011"
    geo.context = "75, Paris, Ile-de-France"
    return geo


class TestAppreciationEndpoint:
    @patch("src.api.service.compute_appreciation")
    @patch("src.api.service.geocode_best")
    def test_success(self, mock_geocode, mock_compute):
        from src.estimation.appreciation import (
            AppreciationResult, Historique, Appreciation, Projection,
            Risque, Confidence, BenchmarkDept, SegmentSurface,
            Volatilite, Volume, Scenario, ProjectionAnnee,
        )

        mock_geocode.return_value = _mock_geocode_appreciation()
        mock_compute.return_value = AppreciationResult(
            historique=Historique(
                cagr_total_pct=2.5, cagr_3ans_pct=1.8, trend_12m_pct=1.0,
                periode_analyse="2020-S1 a 2024-S2", nb_semestres=10,
                source="commune",
                benchmark_departement=BenchmarkDept(cagr_dept_pct=2.0, surperformance_pct=0.5),
                segment_surface=SegmentSurface(tranche="moyen", label="moyen (40-80 m2)", cagr_segment_pct=2.3),
                volatilite=Volatilite(coefficient_variation=0.12, classification="stable"),
                volume=Volume(total_transactions=500, last_12m_transactions=80, tendance_volume="stable"),
            ),
            appreciation=Appreciation(
                taux_annuel_estime_pct=2.1, ajustements={},
                taux_final_pct=2.1, methode="weighted_loglinear_regression",
                scenarios={
                    "pessimiste": Scenario(taux_pct=0.5, label="Marche en ralentissement"),
                    "pragmatique": Scenario(taux_pct=2.1, label="Tendance historique maintenue"),
                    "optimiste": Scenario(taux_pct=3.7, label="Acceleration du marche"),
                },
            ),
            projection=Projection(
                prix_achat=350000, horizon_annees=5, taux_inflation_pct=2.0,
                annees=[
                    ProjectionAnnee(annee=1, pessimiste=351750, pragmatique=357350, optimiste=362950),
                    ProjectionAnnee(annee=2, pessimiste=353509, pragmatique=364852, optimiste=376381),
                    ProjectionAnnee(annee=3, pessimiste=355277, pragmatique=372512, optimiste=390309),
                    ProjectionAnnee(annee=4, pessimiste=357053, pragmatique=380334, optimiste=404750),
                    ProjectionAnnee(annee=5, pessimiste=358838, pragmatique=388321, optimiste=419722),
                ],
                plus_value_estimee={"pessimiste": 8838, "pragmatique": 38321, "optimiste": 69722},
                rendement_annualise_nominal_pct={"pessimiste": 0.5, "pragmatique": 2.1, "optimiste": 3.7},
                rendement_annualise_reel_pct={"pessimiste": -1.5, "pragmatique": 0.1, "optimiste": 1.7},
            ),
            risques=[
                Risque(facteur="volatilite", impact="faible", detail="CV 0.12 — marche stable"),
                Risque(facteur="liquidite", impact="faible", detail="80 transactions/an — marche liquide"),
            ],
            confidence=Confidence(level="high", score=85, detail="10 semestres, 500 transactions, donnees communales"),
        )

        resp = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
            "type_bien": "appartement",
            "surface": 55,
            "prix_achat": 350000,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["geocoding"]["commune"] == "Paris 11e Arrondissement"
        assert data["geocoding"]["code_commune"] == "75111"
        assert data["historique"]["cagr_total_pct"] == 2.5
        assert data["appreciation"]["taux_final_pct"] == 2.1
        assert len(data["projection"]["annees"]) == 5
        assert len(data["risques"]) == 2
        assert data["confidence"]["level"] == "high"

    @patch("src.api.service.geocode_best")
    def test_geocoding_failed(self, mock_geocode):
        mock_geocode.return_value = None

        resp = client.post("/api/v1/appreciation", json={
            "address": "adresse inconnue xyz",
            "type_bien": "appartement",
            "surface": 55,
            "prix_achat": 350000,
        })

        data = resp.json()
        assert data["status"] == "geocoding_failed"

    def test_missing_required_fields(self):
        resp = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
        })
        assert resp.status_code == 422

    def test_invalid_surface(self):
        resp = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
            "type_bien": "appartement",
            "surface": 0,
            "prix_achat": 350000,
        })
        assert resp.status_code == 422

    def test_invalid_dpe(self):
        resp = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
            "type_bien": "appartement",
            "surface": 55,
            "prix_achat": 350000,
            "dpe_classe": "X",
        })
        assert resp.status_code == 422

    @patch("src.api.service.compute_appreciation")
    @patch("src.api.service.geocode_best")
    def test_with_all_optional_params(self, mock_geocode, mock_compute):
        from src.estimation.appreciation import (
            AppreciationResult, Historique, Appreciation, Projection,
            Risque, Confidence, SegmentSurface, Volatilite, Volume,
            Scenario, ProjectionAnnee,
        )

        mock_geocode.return_value = _mock_geocode_appreciation()
        mock_compute.return_value = AppreciationResult(
            historique=Historique(
                cagr_total_pct=2.0, cagr_3ans_pct=1.5, trend_12m_pct=1.0,
                periode_analyse="2020-S1 a 2024-S2", nb_semestres=10,
                source="commune", benchmark_departement=None,
                segment_surface=SegmentSurface(tranche="moyen", label="moyen", cagr_segment_pct=None),
                volatilite=Volatilite(coefficient_variation=0.1, classification="stable"),
                volume=Volume(total_transactions=100, last_12m_transactions=20, tendance_volume="stable"),
            ),
            appreciation=Appreciation(
                taux_annuel_estime_pct=1.5, ajustements={"dpe": -0.8, "construction": -0.05},
                taux_final_pct=0.65, methode="weighted_loglinear_regression",
                scenarios={
                    "pessimiste": Scenario(taux_pct=-2.0, label="Marche en ralentissement"),
                    "pragmatique": Scenario(taux_pct=-0.15, label="Tendance historique maintenue"),
                    "optimiste": Scenario(taux_pct=1.7, label="Acceleration du marche"),
                },
            ),
            projection=Projection(
                prix_achat=200000, horizon_annees=10, taux_inflation_pct=2.0,
                annees=[ProjectionAnnee(annee=i, pessimiste=200000-i*2000, pragmatique=200000-i*300, optimiste=200000+i*3000) for i in range(1, 11)],
                plus_value_estimee={"pessimiste": -20000, "pragmatique": -3000, "optimiste": 30000},
                rendement_annualise_nominal_pct={"pessimiste": -2.0, "pragmatique": -0.15, "optimiste": 1.7},
                rendement_annualise_reel_pct={"pessimiste": -4.0, "pragmatique": -2.15, "optimiste": -0.3},
            ),
            risques=[
                Risque(facteur="dpe", impact="eleve", detail="DPE G — deja interdit en location"),
            ],
            confidence=Confidence(level="medium", score=55, detail="donnees communales"),
        )

        resp = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
            "type_bien": "appartement",
            "surface": 55,
            "prix_achat": 200000,
            "postcode": "75011",
            "dpe_classe": "G",
            "nb_pieces": 3,
            "annee_construction": 1965,
            "condition": "a_renover",
            "usage_prevu": "investissement_locatif",
            "dpe_valeur": 450,
            "ges_classe": "E",
            "nb_chambres": 2,
            "etat_copropriete": "en_difficulte",
            "zone_tendue": True,
            "etage": 3,
            "nb_etages_immeuble": 6,
            "ascenseur": True,
            "balcon": True,
            "terrasse": False,
            "cave": True,
            "parking": False,
            "horizon_annees": 10,
            "taux_inflation": 2.5,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["projection"]["annees"]) == 10
        assert data["appreciation"]["ajustements"]["dpe"] == -0.8


# ---------------------------------------------------------------------------
# Integration tests (real DB, skipped without DB)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIntegrationAppreciation:
    def test_paris_appreciation(self):
        """Appreciation complete pour Paris 11e."""
        resp = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
            "type_bien": "appartement",
            "surface": 55,
            "prix_achat": 350000,
            "postcode": "75011",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

        # Geocoding
        assert data["geocoding"]["code_commune"].startswith("75")

        # Historique
        h = data["historique"]
        assert h["cagr_total_pct"] is not None
        assert h["nb_semestres"] >= 4
        assert h["source"] in ("commune", "departement")

        # Appreciation
        a = data["appreciation"]
        assert a["taux_final_pct"] is not None
        assert a["methode"] == "weighted_loglinear_regression"
        assert a["scenarios"]["pessimiste"]["taux_pct"] < a["scenarios"]["pragmatique"]["taux_pct"]
        assert a["scenarios"]["pragmatique"]["taux_pct"] < a["scenarios"]["optimiste"]["taux_pct"]

        # Projection
        p = data["projection"]
        assert p["prix_achat"] == 350000
        assert len(p["annees"]) == 5

        # Risques et confiance
        assert len(data["risques"]) > 0
        assert data["confidence"]["level"] in ("high", "medium", "low")

    def test_paris_with_dpe(self):
        """DPE G penalise le taux vs sans DPE."""
        resp_no_dpe = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
            "type_bien": "appartement",
            "surface": 55,
            "prix_achat": 350000,
        })
        resp_dpe_g = client.post("/api/v1/appreciation", json={
            "address": "15 rue Oberkampf, Paris",
            "type_bien": "appartement",
            "surface": 55,
            "prix_achat": 350000,
            "dpe_classe": "G",
        })
        assert resp_no_dpe.status_code == 200
        assert resp_dpe_g.status_code == 200

        data_no = resp_no_dpe.json()
        data_g = resp_dpe_g.json()
        if data_no["status"] == "ok" and data_g["status"] == "ok":
            assert data_g["appreciation"]["taux_final_pct"] < data_no["appreciation"]["taux_final_pct"]

    def test_marseille_appreciation(self):
        """Appreciation pour Marseille 1er."""
        resp = client.post("/api/v1/appreciation", json={
            "address": "1 rue de la Republique, Marseille",
            "type_bien": "appartement",
            "surface": 65,
            "prix_achat": 200000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["geocoding"]["departement"] == "13"

    def test_maison_idf(self):
        """Appreciation maison en IDF (77)."""
        resp = client.post("/api/v1/appreciation", json={
            "address": "10 rue de la Mairie, Melun",
            "type_bien": "maison",
            "surface": 120,
            "prix_achat": 280000,
            "annee_construction": 1990,
            "dpe_classe": "D",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
