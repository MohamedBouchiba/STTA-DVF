"""Tests d'integration approfondis sur la base Supabase.

Valide l'integrite des donnees chargees par le pipeline ETL:
- core.transactions : comptages, contraintes, coherence
- mart.stats_commune / stats_departement : coherence avec core
- mart.zone_stats : tendances, qualite
- mart.indices_temporels : couverture temporelle, rolling median
- Estimation end-to-end : geocodage + comparables + estimation
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from sqlalchemy import text

from src.db import get_engine

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def engine():
    """Engine SQLAlchemy connecte a Supabase."""
    return get_engine()


@pytest.fixture(scope="module")
def conn(engine):
    """Connexion reutilisable pour les tests."""
    with engine.connect() as connection:
        yield connection


def _scalar(conn, sql, params=None):
    return conn.execute(text(sql), params or {}).scalar()


def _df(engine, sql, params=None):
    return pd.read_sql(text(sql), engine, params=params or {})


# ============================================================
# 1. CORE.TRANSACTIONS — Comptages et contraintes
# ============================================================

class TestCoreTransactions:

    def test_total_count_reasonable(self, conn):
        """Au moins 500k transactions chargees (9 depts x 6 ans)."""
        total = _scalar(conn, "SELECT COUNT(*) FROM core.transactions")
        assert total >= 500_000, f"Seulement {total} transactions, attendu >= 500k"

    def test_no_null_required_fields(self, conn):
        """Aucun champ NOT NULL ne doit etre NULL."""
        for col in ["id_mutation", "date_mutation", "annee", "mois",
                     "valeur_fonciere", "type_bien", "surface",
                     "code_departement", "code_commune", "prix_m2"]:
            n = _scalar(conn, f"SELECT COUNT(*) FROM core.transactions WHERE {col} IS NULL")
            assert n == 0, f"{n} lignes avec {col} NULL"

    def test_prix_m2_positive(self, conn):
        """Tous les prix/m2 doivent etre > 0 (check constraint)."""
        n = _scalar(conn, "SELECT COUNT(*) FROM core.transactions WHERE prix_m2 <= 0")
        assert n == 0, f"{n} transactions avec prix_m2 <= 0"

    def test_surface_positive(self, conn):
        """Toutes les surfaces > 0."""
        n = _scalar(conn, "SELECT COUNT(*) FROM core.transactions WHERE surface <= 0")
        assert n == 0, f"{n} transactions avec surface <= 0"

    def test_valeur_fonciere_min_100(self, conn):
        """Valeur fonciere >= 100 (filtre des ventes symboliques)."""
        n = _scalar(conn, "SELECT COUNT(*) FROM core.transactions WHERE valeur_fonciere < 100")
        assert n == 0, f"{n} transactions avec valeur_fonciere < 100"

    def test_type_bien_values(self, conn):
        """Seuls 'maison' et 'appartement' autoises."""
        types = conn.execute(text(
            "SELECT DISTINCT type_bien FROM core.transactions ORDER BY type_bien"
        )).fetchall()
        type_set = {r[0] for r in types}
        assert type_set == {"appartement", "maison"}, f"Types inattendus: {type_set}"

    def test_annee_range(self, conn):
        """Annees entre 2020 et 2025."""
        min_y = _scalar(conn, "SELECT MIN(annee) FROM core.transactions")
        max_y = _scalar(conn, "SELECT MAX(annee) FROM core.transactions")
        assert min_y >= 2020, f"Annee min = {min_y}, attendu >= 2020"
        assert max_y <= 2025, f"Annee max = {max_y}, attendu <= 2025"

    def test_mois_range(self, conn):
        """Mois entre 1 et 12."""
        min_m = _scalar(conn, "SELECT MIN(mois) FROM core.transactions")
        max_m = _scalar(conn, "SELECT MAX(mois) FROM core.transactions")
        assert min_m >= 1 and max_m <= 12, f"Mois hors range: [{min_m}, {max_m}]"

    def test_all_departments_present(self, conn):
        """Les 9 departements attendus sont presents."""
        expected = {"13", "75", "77", "78", "91", "92", "93", "94", "95"}
        rows = conn.execute(text(
            "SELECT DISTINCT code_departement FROM core.transactions"
        )).fetchall()
        actual = {r[0] for r in rows}
        assert expected == actual, f"Departements manquants: {expected - actual}, extra: {actual - expected}"

    def test_all_years_present(self, conn):
        """Les 6 annees (2020-2025) sont presentes."""
        expected = {2020, 2021, 2022, 2023, 2024, 2025}
        rows = conn.execute(text(
            "SELECT DISTINCT annee FROM core.transactions ORDER BY annee"
        )).fetchall()
        actual = {r[0] for r in rows}
        assert expected == actual, f"Annees manquantes: {expected - actual}"

    def test_annee_matches_date(self, conn):
        """L'annee correspond a EXTRACT(YEAR FROM date_mutation)."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM core.transactions
            WHERE annee != EXTRACT(YEAR FROM date_mutation)::INTEGER
        """)
        assert n == 0, f"{n} lignes ou annee != year(date_mutation)"

    def test_mois_matches_date(self, conn):
        """Le mois correspond a EXTRACT(MONTH FROM date_mutation)."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM core.transactions
            WHERE mois != EXTRACT(MONTH FROM date_mutation)::INTEGER
        """)
        assert n == 0, f"{n} lignes ou mois != month(date_mutation)"

    def test_prix_m2_equals_ratio(self, conn):
        """prix_m2 = valeur_fonciere / surface (tolerance 0.01)."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM core.transactions
            WHERE ABS(prix_m2 - valeur_fonciere / surface) > 0.01
        """)
        assert n == 0, f"{n} lignes ou prix_m2 != valeur_fonciere/surface"

    def test_code_commune_starts_with_dept(self, conn):
        """code_commune commence par code_departement."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM core.transactions
            WHERE code_commune NOT LIKE code_departement || '%'
        """)
        assert n == 0, f"{n} lignes ou code_commune ne commence pas par code_departement"

    def test_no_duplicate_id_mutation(self, conn):
        """Chaque id_mutation est unique (ventes mono-bien)."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM (
                SELECT id_mutation FROM core.transactions
                GROUP BY id_mutation HAVING COUNT(*) > 1
            ) dupes
        """)
        assert n == 0, f"{n} id_mutation en double"

    def test_geolocalisation_rate_above_95(self, conn):
        """Plus de 95% des transactions sont geolocalisees."""
        total = _scalar(conn, "SELECT COUNT(*) FROM core.transactions")
        geo = _scalar(conn, "SELECT COUNT(*) FROM core.transactions WHERE geom IS NOT NULL")
        pct = 100 * geo / total
        assert pct >= 95, f"Taux geolocalisation = {pct:.1f}%, attendu >= 95%"

    def test_outlier_rate_reasonable(self, conn):
        """Taux d'outliers entre 1% et 15%."""
        total = _scalar(conn, "SELECT COUNT(*) FROM core.transactions")
        outliers = _scalar(conn, "SELECT COUNT(*) FROM core.transactions WHERE is_outlier")
        pct = 100 * outliers / total
        assert 1 <= pct <= 15, f"Taux outliers = {pct:.1f}%, attendu entre 1% et 15%"


# ============================================================
# 2. PRIX / M2 — Plausibilite par departement
# ============================================================

class TestPrixPlausibility:

    def test_paris_median_appart(self, engine):
        """Mediane appart Paris 75 entre 7000 et 15000 EUR/m2."""
        df = _df(engine, """
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS med
            FROM core.transactions
            WHERE code_departement = '75' AND type_bien = 'appartement' AND NOT is_outlier
        """)
        med = float(df["med"].iloc[0])
        assert 7000 <= med <= 15000, f"Mediane Paris appart = {med:.0f}, hors [7000, 15000]"

    def test_marseille_median_appart(self, engine):
        """Mediane appart Marseille 13 entre 1500 et 6000 EUR/m2."""
        df = _df(engine, """
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS med
            FROM core.transactions
            WHERE code_departement = '13' AND type_bien = 'appartement' AND NOT is_outlier
        """)
        med = float(df["med"].iloc[0])
        assert 1500 <= med <= 6000, f"Mediane Marseille appart = {med:.0f}, hors [1500, 6000]"

    def test_hauts_de_seine_higher_than_seine_saint_denis(self, engine):
        """Mediane 92 (HdS) > mediane 93 (SSD) pour les apparts."""
        df = _df(engine, """
            SELECT code_departement,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS med
            FROM core.transactions
            WHERE code_departement IN ('92', '93') AND type_bien = 'appartement' AND NOT is_outlier
            GROUP BY code_departement
        """)
        meds = dict(zip(df["code_departement"], df["med"]))
        assert meds["92"] > meds["93"], (
            f"HdS ({meds['92']:.0f}) devrait etre > SSD ({meds['93']:.0f})"
        )

    def test_paris_higher_than_all_suburbs(self, engine):
        """Mediane appart Paris 75 > toutes les autres."""
        df = _df(engine, """
            SELECT code_departement,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS med
            FROM core.transactions
            WHERE type_bien = 'appartement' AND NOT is_outlier
            GROUP BY code_departement
        """)
        meds = dict(zip(df["code_departement"], df["med"]))
        paris = meds["75"]
        for dep, med in meds.items():
            if dep != "75":
                assert paris > med, (
                    f"Paris ({paris:.0f}) devrait etre > dept {dep} ({med:.0f})"
                )

    def test_surface_range_reasonable(self, conn):
        """Surface entre 9 et 10000 m2 (filtre du pipeline)."""
        min_s = _scalar(conn, "SELECT MIN(surface) FROM core.transactions")
        max_s = _scalar(conn, "SELECT MAX(surface) FROM core.transactions")
        assert min_s >= 9, f"Surface min = {min_s}, attendu >= 9"
        assert max_s <= 10000, f"Surface max = {max_s}, attendu <= 10000"

    def test_prix_m2_not_extreme(self, conn):
        """Aucune transaction non-outlier avec prix_m2 > 100k."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM core.transactions
            WHERE NOT is_outlier AND prix_m2 > 100000
        """)
        assert n == 0, f"{n} transactions non-outlier avec prix_m2 > 100k"


# ============================================================
# 3. MART.STATS_COMMUNE — Coherence avec core
# ============================================================

class TestMartStatsCommune:

    def test_not_empty(self, conn):
        """Au moins 10k lignes dans stats_commune."""
        n = _scalar(conn, "SELECT COUNT(*) FROM mart.stats_commune")
        assert n >= 10_000, f"Seulement {n} lignes dans stats_commune"

    def test_semestre_values(self, conn):
        """Semestre = 1 ou 2."""
        sems = conn.execute(text(
            "SELECT DISTINCT semestre FROM mart.stats_commune ORDER BY semestre"
        )).fetchall()
        assert {r[0] for r in sems} == {1, 2}, f"Semestres inattendus: {sems}"

    def test_nb_transactions_positive(self, conn):
        """Toutes les lignes ont nb_transactions > 0."""
        n = _scalar(conn, "SELECT COUNT(*) FROM mart.stats_commune WHERE nb_transactions <= 0")
        assert n == 0, f"{n} lignes avec nb_transactions <= 0"

    def test_median_between_q1_q3(self, conn):
        """Mediane entre Q1 et Q3 pour toutes les lignes."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM mart.stats_commune
            WHERE median_prix_m2 < q1_prix_m2 OR median_prix_m2 > q3_prix_m2
        """)
        assert n == 0, f"{n} lignes ou median pas entre Q1 et Q3"

    def test_q1_less_than_q3(self, conn):
        """Q1 <= Q3 pour toutes les lignes."""
        n = _scalar(conn, "SELECT COUNT(*) FROM mart.stats_commune WHERE q1_prix_m2 > q3_prix_m2")
        assert n == 0, f"{n} lignes ou Q1 > Q3"

    def test_total_transactions_matches_core(self, engine):
        """Somme nb_transactions dans stats_commune = count core hors outliers."""
        mart_total = _df(engine, "SELECT SUM(nb_transactions) AS s FROM mart.stats_commune")["s"].iloc[0]
        core_total = _df(engine, "SELECT COUNT(*) AS c FROM core.transactions WHERE NOT is_outlier")["c"].iloc[0]
        assert mart_total == core_total, (
            f"Mart total = {mart_total}, core hors outliers = {core_total}"
        )

    def test_spot_check_paris_15e_2024_s1(self, engine):
        """Verification ponctuelle : Paris 15e (75115) appart 2024 S1 coherent."""
        df = _df(engine, """
            SELECT nb_transactions, median_prix_m2
            FROM mart.stats_commune
            WHERE code_commune = '75115' AND type_bien = 'appartement'
              AND annee = 2024 AND semestre = 1
        """)
        if len(df) > 0:
            nb = int(df["nb_transactions"].iloc[0])
            med = float(df["median_prix_m2"].iloc[0])
            assert nb >= 100, f"Paris 75115 appart 2024-S1: seulement {nb} transactions"
            assert 7000 <= med <= 15000, f"Paris 75115 appart 2024-S1: median = {med:.0f}"


# ============================================================
# 4. MART.STATS_DEPARTEMENT — Coherence avec core
# ============================================================

class TestMartStatsDepartement:

    def test_all_departments_present(self, conn):
        """Les 9 departements sont presents."""
        expected = {"13", "75", "77", "78", "91", "92", "93", "94", "95"}
        rows = conn.execute(text(
            "SELECT DISTINCT code_departement FROM mart.stats_departement"
        )).fetchall()
        actual = {r[0] for r in rows}
        assert expected == actual, f"Departements manquants: {expected - actual}"

    def test_total_transactions_matches_core(self, engine):
        """Somme nb_transactions = count core hors outliers."""
        mart_total = _df(engine, "SELECT SUM(nb_transactions) AS s FROM mart.stats_departement")["s"].iloc[0]
        core_total = _df(engine, "SELECT COUNT(*) AS c FROM core.transactions WHERE NOT is_outlier")["c"].iloc[0]
        assert mart_total == core_total, (
            f"Mart dept total = {mart_total}, core hors outliers = {core_total}"
        )

    def test_median_between_q1_q3(self, conn):
        """Mediane entre Q1 et Q3."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM mart.stats_departement
            WHERE median_prix_m2 < q1_prix_m2 OR median_prix_m2 > q3_prix_m2
        """)
        assert n == 0, f"{n} lignes ou median pas entre Q1 et Q3"


# ============================================================
# 5. MART.ZONE_STATS — Stats 12 derniers mois
# ============================================================

class TestMartZoneStats:

    def test_not_empty(self, conn):
        """Au moins 1000 lignes dans zone_stats."""
        n = _scalar(conn, "SELECT COUNT(*) FROM mart.zone_stats")
        assert n >= 1000, f"Seulement {n} lignes dans zone_stats"

    def test_quality_flag_values(self, conn):
        """data_quality_flag in {good, moderate, sparse}."""
        rows = conn.execute(text(
            "SELECT DISTINCT data_quality_flag FROM mart.zone_stats"
        )).fetchall()
        actual = {r[0] for r in rows}
        assert actual.issubset({"good", "moderate", "sparse"}), f"Flags inattendus: {actual}"

    def test_quality_flag_consistency(self, conn):
        """good = 30+, moderate = 10-29, sparse < 10."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM mart.zone_stats
            WHERE (data_quality_flag = 'good' AND last_12m_transactions < 30)
               OR (data_quality_flag = 'moderate' AND (last_12m_transactions >= 30 OR last_12m_transactions < 10))
               OR (data_quality_flag = 'sparse' AND last_12m_transactions >= 10)
        """)
        assert n == 0, f"{n} lignes avec quality_flag incoherent"

    def test_last_12m_leq_total(self, conn):
        """last_12m_transactions <= total_transactions."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM mart.zone_stats
            WHERE last_12m_transactions > total_transactions
        """)
        assert n == 0, f"{n} lignes ou 12m > total"

    def test_median_positive(self, conn):
        """Toutes les medianes > 0."""
        n = _scalar(conn, "SELECT COUNT(*) FROM mart.zone_stats WHERE median_prix_m2_12m <= 0")
        assert n == 0, f"{n} lignes avec median <= 0"

    def test_trend_reasonable_for_good_data(self, conn):
        """Tendances raisonnables pour les communes avec assez de donnees."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM mart.zone_stats
            WHERE trend_12m IS NOT NULL
              AND data_quality_flag = 'good'
              AND (trend_12m < -50 OR trend_12m > 100)
        """)
        assert n == 0, f"{n} communes 'good' avec trend hors [-50%, +100%]"


# ============================================================
# 6. MART.INDICES_TEMPORELS — Couverture temporelle
# ============================================================

class TestMartIndicesTemporels:

    def test_not_empty(self, conn):
        """Au moins 50k lignes dans indices_temporels."""
        n = _scalar(conn, "SELECT COUNT(*) FROM mart.indices_temporels")
        assert n >= 50_000, f"Seulement {n} lignes dans indices_temporels"

    def test_all_years_present(self, conn):
        """Les 6 annees (2020-2025) sont presentes."""
        rows = conn.execute(text(
            "SELECT DISTINCT annee FROM mart.indices_temporels ORDER BY annee"
        )).fetchall()
        actual = {r[0] for r in rows}
        assert {2020, 2021, 2022, 2023, 2024, 2025}.issubset(actual), f"Annees: {actual}"

    def test_mois_1_to_12(self, conn):
        """Mois entre 1 et 12."""
        min_m = _scalar(conn, "SELECT MIN(mois) FROM mart.indices_temporels")
        max_m = _scalar(conn, "SELECT MAX(mois) FROM mart.indices_temporels")
        assert min_m == 1 and max_m == 12, f"Mois: [{min_m}, {max_m}]"

    def test_total_matches_core(self, engine):
        """Somme nb_transactions = count core hors outliers."""
        mart_total = _df(engine, "SELECT SUM(nb_transactions) AS s FROM mart.indices_temporels")["s"].iloc[0]
        core_total = _df(engine, "SELECT COUNT(*) AS c FROM core.transactions WHERE NOT is_outlier")["c"].iloc[0]
        assert mart_total == core_total, (
            f"Indices total = {mart_total}, core hors outliers = {core_total}"
        )

    def test_rolling_median_not_all_null(self, conn):
        """rolling_median_6m ne doit pas etre NULL partout."""
        n = _scalar(conn, "SELECT COUNT(*) FROM mart.indices_temporels WHERE rolling_median_6m IS NOT NULL")
        assert n > 0, "Aucun rolling_median_6m calcule"

    def test_rolling_median_positive(self, conn):
        """rolling_median_6m > 0 quand present."""
        n = _scalar(conn, """
            SELECT COUNT(*) FROM mart.indices_temporels
            WHERE rolling_median_6m IS NOT NULL AND rolling_median_6m <= 0
        """)
        assert n == 0, f"{n} lignes avec rolling_median <= 0"


# ============================================================
# 7. CROSS-TABLE — Coherence entre tables
# ============================================================

class TestCrossTable:

    def test_zone_stats_communes_exist_in_core(self, engine):
        """Toutes les communes de zone_stats existent dans core."""
        df = _df(engine, """
            SELECT z.code_commune
            FROM mart.zone_stats z
            LEFT JOIN (SELECT DISTINCT code_commune FROM core.transactions) c
              ON z.code_commune = c.code_commune
            WHERE c.code_commune IS NULL
        """)
        assert len(df) == 0, f"{len(df)} communes dans zone_stats absentes de core"

    def test_indices_communes_exist_in_core(self, engine):
        """Toutes les communes de indices_temporels existent dans core."""
        df = _df(engine, """
            SELECT DISTINCT i.code_commune
            FROM mart.indices_temporels i
            LEFT JOIN (SELECT DISTINCT code_commune FROM core.transactions) c
              ON i.code_commune = c.code_commune
            WHERE c.code_commune IS NULL
        """)
        assert len(df) == 0, f"{len(df)} communes dans indices absentes de core"

    def test_stats_commune_communes_in_core(self, engine):
        """Toutes les communes de stats_commune existent dans core."""
        df = _df(engine, """
            SELECT DISTINCT sc.code_commune
            FROM mart.stats_commune sc
            LEFT JOIN (SELECT DISTINCT code_commune FROM core.transactions) c
              ON sc.code_commune = c.code_commune
            WHERE c.code_commune IS NULL
        """)
        assert len(df) == 0, f"{len(df)} communes dans stats_commune absentes de core"

    def test_dept_in_stats_matches_core(self, engine):
        """Tous les departements de stats_departement sont dans core."""
        df = _df(engine, """
            SELECT DISTINCT sd.code_departement
            FROM mart.stats_departement sd
            LEFT JOIN (SELECT DISTINCT code_departement FROM core.transactions) c
              ON sd.code_departement = c.code_departement
            WHERE c.code_departement IS NULL
        """)
        assert len(df) == 0, f"Departements dans mart absents de core: {df}"

    def test_spot_check_commune_median_vs_indices(self, engine):
        """Mediane commune = median des medianes mensuelles (approx)."""
        # Prendre une commune avec beaucoup de donnees : 75115 (Paris 15e)
        sc = _df(engine, """
            SELECT median_prix_m2 FROM mart.stats_commune
            WHERE code_commune = '75115' AND type_bien = 'appartement'
              AND annee = 2023 AND semestre = 1
        """)
        it = _df(engine, """
            SELECT AVG(median_prix_m2) AS avg_med
            FROM mart.indices_temporels
            WHERE code_commune = '75115' AND type_bien = 'appartement'
              AND annee = 2023 AND mois BETWEEN 1 AND 6
        """)
        if len(sc) > 0 and len(it) > 0:
            sc_med = float(sc["median_prix_m2"].iloc[0])
            it_avg = float(it["avg_med"].iloc[0])
            # Tolerance 30% car methodes differentes (percentile vs avg of medians)
            ratio = abs(sc_med - it_avg) / max(sc_med, 1)
            assert ratio < 0.30, (
                f"Ecart trop grand: stats_commune={sc_med:.0f}, "
                f"avg indices={it_avg:.0f} (ratio={ratio:.2%})"
            )


# ============================================================
# 8. ESTIMATION END-TO-END
# ============================================================

class TestEstimationEndToEnd:

    def test_comparables_paris_centre(self):
        """Trouve des comparables pour un appart a Paris 1er (75101)."""
        from src.estimation.comparables import find_comparables
        result = find_comparables(
            latitude=48.8606,
            longitude=2.3376,
            code_commune="75101",
            type_bien="appartement",
            surface=50,
        )
        assert len(result.comparables) >= 5, (
            f"Seulement {len(result.comparables)} comparables pour Paris 1er"
        )
        assert result.level <= 2, f"Fallback trop bas: level={result.level}"

    def test_comparables_marseille(self):
        """Trouve des comparables pour un appart a Marseille 1er."""
        from src.estimation.comparables import find_comparables
        result = find_comparables(
            latitude=43.2965,
            longitude=5.3698,
            code_commune="13201",
            type_bien="appartement",
            surface=60,
        )
        assert len(result.comparables) >= 5, (
            f"Seulement {len(result.comparables)} comparables pour Marseille"
        )

    def test_comparables_prix_m2_reasonable(self):
        """Les comparables retournes ont des prix_m2 raisonnables."""
        from src.estimation.comparables import find_comparables
        result = find_comparables(
            latitude=48.8606,
            longitude=2.3376,
            code_commune="75101",
            type_bien="appartement",
            surface=50,
        )
        if len(result.comparables) > 0:
            med = result.comparables["prix_m2"].median()
            assert 5000 <= med <= 20000, f"Median comparables Paris = {med:.0f}"

    def test_zone_stats_accessible(self):
        """Les zone_stats sont accessibles via l'estimateur."""
        from src.estimation.estimator import get_zone_stats
        # Paris 15e (75115) — plus gros arrondissement
        stats = get_zone_stats("75115", "appartement")
        assert stats is not None, "zone_stats introuvable pour Paris 75115"
        assert stats["total_transactions"] > 100
        assert stats["median_prix_m2_12m"] > 5000

    def test_historical_stats_accessible(self):
        """Les historiques stats sont accessibles."""
        from src.estimation.estimator import get_historical_stats
        df = get_historical_stats("75115", "75", "appartement")
        assert len(df) >= 6, f"Seulement {len(df)} periodes historiques pour Paris 15e"

    def test_geocode_paris_address(self):
        """Geocodage d'une adresse parisienne connue."""
        from src.estimation.geocoder import geocode_best
        result = geocode_best("12 rue de Rivoli, Paris", postcode="75001")
        assert result is not None, "Geocodage echoue pour 12 rue de Rivoli"
        assert result.citycode.startswith("75"), f"citycode={result.citycode}"
        assert abs(result.latitude - 48.862) < 0.01
        assert abs(result.longitude - 2.336) < 0.02

    def test_full_estimation_paris(self):
        """Estimation complete pour un appart a Paris."""
        from src.estimation.estimator import estimate
        result = estimate(
            address="12 rue de Rivoli, Paris",
            type_bien="appartement",
            surface=50,
            nb_pieces=2,
            postcode="75001",
        )
        assert result is not None, "Estimation echouee"
        assert result.prix_m2_estime > 5000, f"prix_m2 = {result.prix_m2_estime}"
        assert result.prix_total_estime > 250_000, f"prix_total = {result.prix_total_estime}"
        assert result.nb_comparables >= 5, f"nb_comparables = {result.nb_comparables}"
        assert result.confidence.level in ("high", "medium", "low")

    def test_full_estimation_marseille(self):
        """Estimation complete pour un appart a Marseille."""
        from src.estimation.estimator import estimate
        result = estimate(
            address="1 La Canebiere, Marseille",
            type_bien="appartement",
            surface=60,
            nb_pieces=3,
            postcode="13001",
        )
        assert result is not None, "Estimation echouee"
        assert result.prix_m2_estime > 1000, f"prix_m2 = {result.prix_m2_estime}"
        assert result.prix_m2_estime < result.prix_total_estime

    def test_estimation_maison_yvelines(self):
        """Estimation maison dans les Yvelines."""
        from src.estimation.estimator import estimate
        result = estimate(
            address="10 rue de la Paix, Versailles",
            type_bien="maison",
            surface=120,
            nb_pieces=5,
            postcode="78000",
        )
        assert result is not None, "Estimation echouee"
        assert result.prix_m2_estime > 2000


# ============================================================
# 9. STAGING — Doit etre vide apres pipeline
# ============================================================

class TestStaging:

    def test_staging_empty(self, conn):
        """staging.dvf doit etre vide apres le pipeline."""
        n = _scalar(conn, "SELECT COUNT(*) FROM staging.dvf")
        assert n == 0, f"staging.dvf contient encore {n} lignes"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
