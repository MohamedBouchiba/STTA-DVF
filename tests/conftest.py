"""Fixtures de test."""

import pandas as pd
import pytest
import numpy as np


@pytest.fixture
def sample_comparables():
    """DataFrame de transactions comparables synthetiques."""
    np.random.seed(42)
    n = 50
    return pd.DataFrame({
        "idmutation": range(1, n + 1),
        "datemut": pd.date_range("2023-01-01", periods=n, freq="W"),
        "valeurfonc": np.random.normal(250000, 50000, n).clip(100000),
        "type_bien": ["appartement"] * n,
        "surface_utilisee": np.random.normal(60, 15, n).clip(20),
        "nb_pieces": np.random.choice([1, 2, 3, 4], n),
        "prix_m2": np.random.normal(4500, 800, n).clip(1000),
        "codinsee": ["75101"] * n,
        "libcommune": ["PARIS 1ER ARRONDISSEMENT"] * n,
        "coddep": ["75"] * n,
        "latitude": np.random.normal(48.8606, 0.005, n),
        "longitude": np.random.normal(2.3376, 0.005, n),
    })


@pytest.fixture
def sample_comparables_sparse():
    """DataFrame avec tres peu de comparables (pour tester les fallbacks)."""
    return pd.DataFrame({
        "idmutation": [1, 2, 3],
        "datemut": pd.to_datetime(["2024-01-15", "2024-03-20", "2024-06-10"]),
        "valeurfonc": [180000, 200000, 220000],
        "type_bien": ["maison"] * 3,
        "surface_utilisee": [90.0, 100.0, 110.0],
        "nb_pieces": [4, 4, 5],
        "prix_m2": [2000, 2000, 2000],
        "codinsee": ["23001"] * 3,
        "libcommune": ["AHUN"] * 3,
        "coddep": ["23"] * 3,
        "latitude": [46.0833] * 3,
        "longitude": [2.0500] * 3,
    })
