"""Tests du moteur d'estimation."""

import math

import numpy as np
import pandas as pd
import pytest

from src.estimation.estimator import compute_surface_adjustment, compute_weighted_median
from src.estimation.confidence import compute_confidence
from src.estimation.zone_config import ZoneConfig
from src.app.utils.formatting import format_distance


class TestSurfaceAdjustment:
    """Tests de l'ajustement surface."""

    def test_same_surface_no_adjustment(self, sample_comparables):
        """Si la surface = mediane des comparables, ajustement = 1."""
        median_surface = sample_comparables["surface"].median()
        adj = compute_surface_adjustment(median_surface, sample_comparables)
        assert adj == pytest.approx(1.0, abs=0.01)

    def test_double_surface_reduces_price(self, sample_comparables):
        """Doubler la surface reduit le prix/m2."""
        median_surface = sample_comparables["surface"].median()
        adj = compute_surface_adjustment(median_surface * 2, sample_comparables)
        assert adj < 1.0
        assert adj == pytest.approx(0.9, abs=0.05)

    def test_half_surface_increases_price(self, sample_comparables):
        """Diviser la surface par 2 augmente le prix/m2."""
        median_surface = sample_comparables["surface"].median()
        adj = compute_surface_adjustment(median_surface / 2, sample_comparables)
        assert adj > 1.0
        assert adj == pytest.approx(1.1, abs=0.05)

    def test_adjustment_clamped(self, sample_comparables):
        """L'ajustement est plafonne a [0.8, 1.2]."""
        adj_small = compute_surface_adjustment(1.0, sample_comparables)
        adj_large = compute_surface_adjustment(10000.0, sample_comparables)
        assert adj_small <= 1.2
        assert adj_large >= 0.8

    def test_empty_comparables(self):
        """Pas de comparables -> ajustement = 1."""
        empty_df = pd.DataFrame(columns=["surface"])
        adj = compute_surface_adjustment(50.0, empty_df)
        assert adj == 1.0


class TestConfidence:
    """Tests du calcul de confiance."""

    def test_high_confidence(self, sample_comparables):
        """Beaucoup de comparables + niveau geo precis = haute confiance."""
        result = compute_confidence(sample_comparables, search_level=1, surface=50.0)
        assert result.level == "high"

    def test_medium_confidence(self, sample_comparables):
        """10+ comparables + niveau 3 = confiance moyenne."""
        small_df = sample_comparables.head(15)
        result = compute_confidence(small_df, search_level=3, surface=50.0)
        assert result.level == "medium"

    def test_low_confidence(self, sample_comparables_sparse):
        """Peu de comparables = faible confiance."""
        result = compute_confidence(sample_comparables_sparse, search_level=4, surface=100.0)
        assert result.level == "low"

    def test_confidence_interval_ordered(self, sample_comparables):
        """La borne basse < borne haute."""
        result = compute_confidence(sample_comparables, search_level=1, surface=50.0)
        assert result.low_estimate < result.high_estimate

    def test_confidence_interval_positive(self, sample_comparables):
        """Les bornes sont positives."""
        result = compute_confidence(sample_comparables, search_level=1, surface=50.0)
        assert result.low_estimate > 0
        assert result.high_estimate > 0


class TestZoneConfig:
    """Tests de la configuration multi-zones."""

    def test_default_values(self):
        zc = ZoneConfig()
        assert zc.radius_1_km == 1.0
        assert zc.radius_2_km == 2.0
        assert zc.radius_3_km == 3.0
        assert zc.weight_1 == 0.60
        assert zc.weight_2 == 0.30
        assert zc.weight_3 == 0.10

    def test_radii_meters(self):
        zc = ZoneConfig(radius_1_km=1.5, radius_2_km=3.0, radius_3_km=5.0)
        assert zc.radii_meters == (1500.0, 3000.0, 5000.0)

    def test_weights_normalized(self):
        zc = ZoneConfig(weight_1=6, weight_2=3, weight_3=1)
        w1, w2, w3 = zc.weights
        assert w1 == pytest.approx(0.6, abs=0.01)
        assert w2 == pytest.approx(0.3, abs=0.01)
        assert w3 == pytest.approx(0.1, abs=0.01)

    def test_weights_zero_total(self):
        """Poids tous nuls -> equirepartition."""
        zc = ZoneConfig(weight_1=0, weight_2=0, weight_3=0)
        w1, w2, w3 = zc.weights
        assert w1 == pytest.approx(1/3, abs=0.01)

    def test_weight_for_zone(self):
        zc = ZoneConfig(weight_1=0.5, weight_2=0.3, weight_3=0.2)
        assert zc.weight_for_zone(1) == 0.5
        assert zc.weight_for_zone(2) == 0.3
        assert zc.weight_for_zone(3) == 0.2
        assert zc.weight_for_zone(4) == 0


class TestWeightedMedian:
    """Tests de la mediane ponderee par zone."""

    def test_with_zones(self, sample_comparables):
        """Mediane ponderee utilise les poids."""
        zc = ZoneConfig()
        prix_m2, breakdown = compute_weighted_median(sample_comparables, zc)
        assert prix_m2 > 0
        assert 1 in breakdown
        assert 2 in breakdown
        assert 3 in breakdown
        assert breakdown[1]["count"] == 20
        assert breakdown[2]["count"] == 20
        assert breakdown[3]["count"] == 10

    def test_breakdown_has_effective_weights(self, sample_comparables):
        zc = ZoneConfig()
        _, breakdown = compute_weighted_median(sample_comparables, zc)
        total_eff = sum(breakdown[z]["effective_weight"] for z in [1, 2, 3])
        assert total_eff == pytest.approx(1.0, abs=0.01)

    def test_without_zone_column(self, sample_comparables):
        """Sans colonne zone -> mediane classique."""
        df = sample_comparables.drop(columns=["zone"])
        zc = ZoneConfig()
        prix_m2, breakdown = compute_weighted_median(df, zc)
        assert prix_m2 > 0
        assert breakdown == {}

    def test_empty_zone_redistribution(self):
        """Si une zone est vide, son poids est redistribue."""
        df = pd.DataFrame({
            "prix_m2": [5000, 5000, 3000, 3000],
            "zone": [1, 1, 2, 2],
        })
        zc = ZoneConfig(weight_1=0.6, weight_2=0.3, weight_3=0.1)
        prix_m2, breakdown = compute_weighted_median(df, zc)
        # Zone 3 vide -> poids redistribues: w1=0.6/0.9, w2=0.3/0.9
        assert breakdown[3]["count"] == 0
        expected = 5000 * (0.6 / 0.9) + 3000 * (0.3 / 0.9)
        assert prix_m2 == pytest.approx(expected, abs=1)

    def test_equal_weights(self):
        """Poids egaux -> moyenne simple des medianes."""
        df = pd.DataFrame({
            "prix_m2": [4000, 4000, 6000, 6000, 8000, 8000],
            "zone": [1, 1, 2, 2, 3, 3],
        })
        zc = ZoneConfig(weight_1=1, weight_2=1, weight_3=1)
        prix_m2, _ = compute_weighted_median(df, zc)
        assert prix_m2 == pytest.approx(6000, abs=1)


class TestFormatDistance:
    """Tests de format_distance."""

    def test_meters(self):
        assert format_distance(850) == "850 m"

    def test_kilometers(self):
        assert format_distance(1200) == "1.2 km"

    def test_none(self):
        assert format_distance(None) == "N/A"

    def test_exactly_1000(self):
        assert format_distance(1000) == "1.0 km"

    def test_small_distance(self):
        assert format_distance(50) == "50 m"
