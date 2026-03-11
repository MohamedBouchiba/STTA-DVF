"""Tests unitaires du moteur d'ajustement."""

import pytest

from src.app.models.property_input import (
    PropertyInput,
    PropertyType,
    QualityLevel,
    ConstructionPeriod,
    PropertyCondition,
)
from src.app.models.adjustments import (
    compute_adjustments,
    _compute_floor_adjustment,
    TYPE_COEFFICIENTS,
    QUALITY_COEFFICIENTS,
    CONDITION_COEFFICIENTS,
    CONSTRUCTION_COEFFICIENTS,
    CoefficientOverrides,
    FloorParams,
    get_default_coefficients,
)
from src.estimation.zone_config import ZoneConfig


def _default_prop(**overrides) -> PropertyInput:
    """Cree un PropertyInput avec tous les defauts."""
    defaults = dict(
        property_type=PropertyType.APPARTEMENT,
        surface=50.0,
    )
    defaults.update(overrides)
    return PropertyInput(**defaults)


class TestDefaultAdjustments:
    """Aucun ajustement quand tous les champs sont aux defauts."""

    def test_multiplier_is_one(self):
        prop = _default_prop()
        result = compute_adjustments(prop, 500_000)
        assert result.total_multiplier == 1.0

    def test_adjusted_price_equals_base(self):
        prop = _default_prop()
        result = compute_adjustments(prop, 500_000)
        assert result.adjusted_price == 500_000

    def test_no_explanations(self):
        prop = _default_prop()
        result = compute_adjustments(prop, 500_000)
        assert result.explanations == []


class TestTypeAdjustment:
    """Coefficients par type de bien."""

    def test_appartement_no_adjustment(self):
        prop = _default_prop(property_type=PropertyType.APPARTEMENT)
        result = compute_adjustments(prop, 100_000)
        assert result.type_adjustment == 1.0

    def test_maison_no_adjustment(self):
        prop = _default_prop(property_type=PropertyType.MAISON)
        result = compute_adjustments(prop, 100_000)
        assert result.type_adjustment == 1.0

    def test_duplex_premium(self):
        prop = _default_prop(property_type=PropertyType.DUPLEX)
        result = compute_adjustments(prop, 100_000)
        assert result.type_adjustment == 1.05
        assert result.adjusted_price == 105_000

    def test_hotel_particulier_premium(self):
        prop = _default_prop(property_type=PropertyType.HOTEL_PARTICULIER)
        result = compute_adjustments(prop, 100_000)
        assert result.type_adjustment == 1.15
        assert result.adjusted_price == 115_000


class TestFloorAdjustment:
    """Logique etage avec/sans ascenseur."""

    def test_no_floor_info(self):
        adj, expl = _compute_floor_adjustment(None, None, False)
        assert adj == 1.0
        assert expl == ""

    def test_ground_floor_discount(self):
        adj, expl = _compute_floor_adjustment(0, 5, False)
        assert adj == 0.93
        assert "Rez-de-chaussee" in expl

    def test_floor_1_to_3_baseline(self):
        for floor in [1, 2, 3]:
            adj, _ = _compute_floor_adjustment(floor, 5, False)
            assert adj == 1.0

    def test_floor_5_no_elevator_penalty(self):
        adj, expl = _compute_floor_adjustment(5, 6, False)
        expected = 1.0 - (5 - 3) * 0.03  # -6%
        assert adj == round(expected, 4)
        assert "sans ascenseur" in expl

    def test_floor_5_with_elevator_bonus(self):
        adj, expl = _compute_floor_adjustment(5, 6, True)
        expected = 1.0 + (5 - 3) * 0.01  # +2%
        assert adj == round(expected, 4)
        assert "avec ascenseur" in expl

    def test_high_floor_no_elevator_capped(self):
        adj, _ = _compute_floor_adjustment(10, 10, False)
        assert adj >= 0.85  # penalty capped at 12%

    def test_high_floor_with_elevator_capped(self):
        adj, _ = _compute_floor_adjustment(15, 15, True)
        # bonus capped at 5% + dernier etage 3%
        assert adj <= 1.08 + 0.001

    def test_last_floor_bonus(self):
        adj, expl = _compute_floor_adjustment(5, 5, True)
        # +2% (elevator) + 3% (dernier etage)
        assert adj == round(1.0 + 0.02 + 0.03, 4)
        assert "dernier etage" in expl


class TestCharacteristics:
    """Ajustements des caracteristiques (checkboxes)."""

    def test_single_characteristic(self):
        prop = _default_prop(terrasse=True)
        result = compute_adjustments(prop, 100_000)
        assert result.characteristics_adjustment == 1.04
        assert result.adjusted_price == 104_000

    def test_multiple_characteristics(self):
        prop = _default_prop(terrasse=True, vue_exceptionnelle=True, parking=True)
        result = compute_adjustments(prop, 100_000)
        expected_char = 1.0 + 0.04 + 0.06 + 0.03  # 1.13
        assert abs(result.characteristics_adjustment - expected_char) < 0.001

    def test_all_characteristics(self):
        prop = _default_prop(
            ascenseur=True, balcon=True, terrasse=True, cave=True,
            parking=True, chambre_service=True, vue_exceptionnelle=True,
            parties_communes_renovees=True, ravalement_recent=True,
        )
        result = compute_adjustments(prop, 100_000)
        expected = 1.0 + 0.03 + 0.02 + 0.04 + 0.01 + 0.03 + 0.01 + 0.06 + 0.02 + 0.01
        assert abs(result.characteristics_adjustment - expected) < 0.001


class TestConditionAndQuality:
    """Coefficients d'etat et qualite."""

    def test_a_renover_discount(self):
        prop = _default_prop(condition=PropertyCondition.A_RENOVER)
        result = compute_adjustments(prop, 100_000)
        assert result.condition_adjustment == 0.85
        assert result.adjusted_price == 85_000

    def test_refait_a_neuf_premium(self):
        prop = _default_prop(condition=PropertyCondition.REFAIT_A_NEUF)
        result = compute_adjustments(prop, 100_000)
        assert result.condition_adjustment == 1.12

    def test_quality_inferieure(self):
        prop = _default_prop(quality=QualityLevel.INFERIEURE)
        result = compute_adjustments(prop, 100_000)
        assert result.quality_adjustment == 0.90

    def test_quality_superieure(self):
        prop = _default_prop(quality=QualityLevel.SUPERIEURE)
        result = compute_adjustments(prop, 100_000)
        assert result.quality_adjustment == 1.10


class TestConstructionPeriod:
    """Coefficients par periode de construction."""

    def test_unknown_no_adjustment(self):
        prop = _default_prop(construction_period=ConstructionPeriod.UNKNOWN)
        result = compute_adjustments(prop, 100_000)
        assert result.construction_adjustment == 1.0

    def test_haussmannien_premium(self):
        prop = _default_prop(construction_period=ConstructionPeriod.P1850_1913)
        result = compute_adjustments(prop, 100_000)
        assert result.construction_adjustment == 1.03

    def test_postwar_discount(self):
        prop = _default_prop(construction_period=ConstructionPeriod.P1948_1969)
        result = compute_adjustments(prop, 100_000)
        assert result.construction_adjustment == 0.95


class TestClamping:
    """Plafonnement du multiplicateur total."""

    def test_max_clamped_at_140(self):
        """Empiler tous les facteurs max ne depasse pas 1.40."""
        prop = _default_prop(
            property_type=PropertyType.HOTEL_PARTICULIER,
            etage=8, nb_etages_immeuble=8, ascenseur=True,
            terrasse=True, vue_exceptionnelle=True, parking=True,
            balcon=True, cave=True, chambre_service=True,
            parties_communes_renovees=True, ravalement_recent=True,
            condition=PropertyCondition.REFAIT_A_NEUF,
            quality=QualityLevel.SUPERIEURE,
            construction_period=ConstructionPeriod.APRES_2005,
        )
        result = compute_adjustments(prop, 100_000)
        assert result.total_multiplier <= 1.40

    def test_min_clamped_at_070(self):
        """Empiler tous les facteurs min ne descend pas sous 0.70."""
        prop = _default_prop(
            property_type=PropertyType.APPARTEMENT,
            etage=0,
            condition=PropertyCondition.A_RENOVER,
            quality=QualityLevel.INFERIEURE,
            construction_period=ConstructionPeriod.P1948_1969,
        )
        result = compute_adjustments(prop, 100_000)
        assert result.total_multiplier >= 0.70


class TestPropertyTypeMapping:
    """Verification du mapping PropertyType -> DVF."""

    def test_maison_types(self):
        assert PropertyType.MAISON.dvf_type == "maison"
        assert PropertyType.HOTEL_PARTICULIER.dvf_type == "maison"

    def test_appartement_types(self):
        for pt in [PropertyType.APPARTEMENT, PropertyType.DUPLEX,
                   PropertyType.TRIPLEX, PropertyType.LOFT]:
            assert pt.dvf_type == "appartement"


class TestGetDefaultCoefficients:
    """get_default_coefficients() retourne un dict serialisable."""

    def test_returns_dict(self):
        defaults = get_default_coefficients()
        assert isinstance(defaults, dict)

    def test_all_groups_present(self):
        defaults = get_default_coefficients()
        for key in ("type", "quality", "condition", "construction", "characteristics", "floor", "zone"):
            assert key in defaults

    def test_type_keys_are_strings(self):
        defaults = get_default_coefficients()
        for key in defaults["type"]:
            assert isinstance(key, str)

    def test_floor_has_all_params(self):
        defaults = get_default_coefficients()
        fp = FloorParams()
        for attr in fp.__dict__:
            assert attr in defaults["floor"]


class TestCoefficientOverrides:
    """compute_adjustments avec des overrides admin."""

    def test_no_overrides_same_as_default(self):
        prop = _default_prop(property_type=PropertyType.DUPLEX)
        r1 = compute_adjustments(prop, 100_000)
        r2 = compute_adjustments(prop, 100_000, overrides=None)
        assert r1.adjusted_price == r2.adjusted_price

    def test_type_override_changes_result(self):
        prop = _default_prop(property_type=PropertyType.DUPLEX)
        # Default duplex = 1.05, override to 1.20
        ov = CoefficientOverrides(type_coefficients={"duplex": 1.20})
        result = compute_adjustments(prop, 100_000, overrides=ov)
        assert result.adjusted_price == 120_000

    def test_condition_override(self):
        prop = _default_prop(condition=PropertyCondition.A_RENOVER)
        # Default a_renover = 0.85, override to 0.90
        ov = CoefficientOverrides(condition_coefficients={"a_renover": 0.90})
        result = compute_adjustments(prop, 100_000, overrides=ov)
        assert result.condition_adjustment == 0.90
        assert result.adjusted_price == 90_000

    def test_floor_params_override(self):
        fp = FloorParams(ground_floor_discount=0.15)
        ov = CoefficientOverrides(floor_params=fp)
        prop = _default_prop(etage=0)
        result = compute_adjustments(prop, 100_000, overrides=ov)
        assert result.floor_adjustment == 0.85

    def test_characteristic_override(self):
        prop = _default_prop(terrasse=True)
        # Default terrasse = 0.04, override to 0.10
        ov = CoefficientOverrides(characteristic_adjustments={"terrasse": 0.10})
        result = compute_adjustments(prop, 100_000, overrides=ov)
        assert result.characteristics_adjustment == 1.10
        assert result.adjusted_price == 110_000

    def test_multiple_overrides_combined(self):
        prop = _default_prop(
            property_type=PropertyType.DUPLEX,
            condition=PropertyCondition.REFAIT_A_NEUF,
        )
        ov = CoefficientOverrides(
            type_coefficients={"duplex": 1.10},
            condition_coefficients={"refait_a_neuf": 1.20},
        )
        result = compute_adjustments(prop, 100_000, overrides=ov)
        expected = round(100_000 * 1.10 * 1.20)
        assert result.adjusted_price == expected

    def test_zone_config_in_overrides(self):
        """CoefficientOverrides peut contenir un ZoneConfig."""
        zc = ZoneConfig(radius_1_km=1.5, radius_2_km=3.0, radius_3_km=5.0)
        ov = CoefficientOverrides(zone_config=zc)
        assert ov.zone_config is not None
        assert ov.zone_config.radius_1_km == 1.5
        assert ov.zone_config.radii_meters == (1500.0, 3000.0, 5000.0)

    def test_zone_defaults_in_get_default_coefficients(self):
        """get_default_coefficients inclut les valeurs de zone."""
        defaults = get_default_coefficients()
        assert "zone" in defaults
        assert defaults["zone"]["radius_1_km"] == 1.0
        assert defaults["zone"]["weight_1"] == 0.60
