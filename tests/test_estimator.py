"""Tests du moteur d'estimation."""

import math

import numpy as np
import pandas as pd
import pytest

from src.estimation.estimator import _compute_surface_adjustment
from src.estimation.confidence import compute_confidence


class TestSurfaceAdjustment:
    """Tests de l'ajustement surface."""

    def test_same_surface_no_adjustment(self, sample_comparables):
        """Si la surface = mediane des comparables, ajustement = 1."""
        median_surface = sample_comparables["surface_utilisee"].median()
        adj = _compute_surface_adjustment(median_surface, sample_comparables)
        assert adj == pytest.approx(1.0, abs=0.01)

    def test_double_surface_reduces_price(self, sample_comparables):
        """Doubler la surface reduit le prix/m2."""
        median_surface = sample_comparables["surface_utilisee"].median()
        adj = _compute_surface_adjustment(median_surface * 2, sample_comparables)
        assert adj < 1.0
        assert adj == pytest.approx(0.9, abs=0.05)

    def test_half_surface_increases_price(self, sample_comparables):
        """Diviser la surface par 2 augmente le prix/m2."""
        median_surface = sample_comparables["surface_utilisee"].median()
        adj = _compute_surface_adjustment(median_surface / 2, sample_comparables)
        assert adj > 1.0
        assert adj == pytest.approx(1.1, abs=0.05)

    def test_adjustment_clamped(self, sample_comparables):
        """L'ajustement est plafonne a [0.8, 1.2]."""
        adj_small = _compute_surface_adjustment(1.0, sample_comparables)
        adj_large = _compute_surface_adjustment(10000.0, sample_comparables)
        assert adj_small <= 1.2
        assert adj_large >= 0.8

    def test_empty_comparables(self):
        """Pas de comparables -> ajustement = 1."""
        empty_df = pd.DataFrame(columns=["surface_utilisee"])
        adj = _compute_surface_adjustment(50.0, empty_df)
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
