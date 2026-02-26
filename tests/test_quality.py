"""Tests des fonctions utilitaires de qualite et formatage."""

import pytest

from src.app.utils.formatting import (
    format_price,
    format_price_m2,
    format_surface,
    format_percentage,
    confidence_color,
)


class TestFormatPrice:
    def test_basic(self):
        assert format_price(250000) == "250 000 EUR"

    def test_zero(self):
        assert format_price(0) == "N/A"

    def test_large(self):
        assert format_price(1500000) == "1 500 000 EUR"


class TestFormatPriceM2:
    def test_basic(self):
        assert "4 500" in format_price_m2(4500)
        assert "m\u00b2" in format_price_m2(4500)

    def test_zero(self):
        assert format_price_m2(0) == "N/A"


class TestFormatSurface:
    def test_basic(self):
        result = format_surface(65.5)
        assert "65" in result
        assert "m\u00b2" in result


class TestFormatPercentage:
    def test_positive(self):
        assert format_percentage(5.23) == "+5,2%"

    def test_negative(self):
        assert format_percentage(-3.5) == "-3,5%"

    def test_none(self):
        assert format_percentage(None) == "N/A"


class TestConfidenceColor:
    def test_high(self):
        assert confidence_color("high") == "#28a745"

    def test_medium(self):
        assert confidence_color("medium") == "#ffc107"

    def test_low(self):
        assert confidence_color("low") == "#dc3545"

    def test_unknown(self):
        assert confidence_color("unknown") == "#6c757d"
