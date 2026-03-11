"""Moteur de coefficients d'ajustement post-estimation DVF."""

from dataclasses import dataclass, field

from src.app.models.property_input import (
    PropertyInput,
    PropertyType,
    QualityLevel,
    ConstructionPeriod,
    PropertyCondition,
)
from src.estimation.zone_config import ZoneConfig


@dataclass
class AdjustmentBreakdown:
    """Detail de tous les ajustements appliques."""

    base_price: float
    type_adjustment: float
    floor_adjustment: float
    characteristics_adjustment: float
    condition_adjustment: float
    quality_adjustment: float
    construction_adjustment: float
    total_multiplier: float
    adjusted_price: float
    explanations: list[str] = field(default_factory=list)


@dataclass
class FloorParams:
    """Parametres d'ajustement etage (editables via admin)."""

    ground_floor_discount: float = 0.07
    elevator_bonus_per_floor: float = 0.01
    no_elevator_penalty_per_floor: float = 0.03
    last_floor_bonus: float = 0.03
    max_elevator_bonus: float = 0.05
    max_no_elevator_penalty: float = 0.12


@dataclass
class CoefficientOverrides:
    """Surcharges des coefficients (None = utiliser les defauts)."""

    type_coefficients: dict[str, float] | None = None
    quality_coefficients: dict[str, float] | None = None
    condition_coefficients: dict[str, float] | None = None
    construction_coefficients: dict[str, float] | None = None
    characteristic_adjustments: dict[str, float] | None = None
    floor_params: FloorParams | None = None
    zone_config: ZoneConfig | None = None


# -- Coefficients heuristiques par defaut --

TYPE_COEFFICIENTS: dict[PropertyType, float] = {
    PropertyType.APPARTEMENT: 1.00,
    PropertyType.MAISON: 1.00,
    PropertyType.DUPLEX: 1.05,
    PropertyType.TRIPLEX: 1.08,
    PropertyType.LOFT: 1.10,
    PropertyType.HOTEL_PARTICULIER: 1.15,
}

QUALITY_COEFFICIENTS: dict[QualityLevel, float] = {
    QualityLevel.INFERIEURE: 0.90,
    QualityLevel.COMPARABLE: 1.00,
    QualityLevel.SUPERIEURE: 1.10,
}

CONDITION_COEFFICIENTS: dict[PropertyCondition, float] = {
    PropertyCondition.A_RENOVER: 0.85,
    PropertyCondition.STANDARD: 1.00,
    PropertyCondition.BON_ETAT: 1.05,
    PropertyCondition.REFAIT_A_NEUF: 1.12,
}

CONSTRUCTION_COEFFICIENTS: dict[ConstructionPeriod, float] = {
    ConstructionPeriod.AVANT_1850: 1.02,
    ConstructionPeriod.P1850_1913: 1.03,
    ConstructionPeriod.P1914_1947: 0.98,
    ConstructionPeriod.P1948_1969: 0.95,
    ConstructionPeriod.P1970_1989: 0.97,
    ConstructionPeriod.P1990_2005: 1.00,
    ConstructionPeriod.APRES_2005: 1.04,
    ConstructionPeriod.UNKNOWN: 1.00,
}

CHARACTERISTIC_ADJUSTMENTS: dict[str, float] = {
    "ascenseur": 0.03,
    "balcon": 0.02,
    "terrasse": 0.04,
    "cave": 0.01,
    "parking": 0.03,
    "chambre_service": 0.01,
    "vue_exceptionnelle": 0.06,
    "parties_communes_renovees": 0.02,
    "ravalement_recent": 0.01,
}


def get_default_coefficients() -> dict:
    """Retourne tous les coefficients par defaut (cles str, serialisable)."""
    return {
        "type": {k.value: v for k, v in TYPE_COEFFICIENTS.items()},
        "quality": {k.value: v for k, v in QUALITY_COEFFICIENTS.items()},
        "condition": {k.value: v for k, v in CONDITION_COEFFICIENTS.items()},
        "construction": {k.value: v for k, v in CONSTRUCTION_COEFFICIENTS.items()},
        "characteristics": dict(CHARACTERISTIC_ADJUSTMENTS),
        "floor": FloorParams().__dict__,
        "zone": ZoneConfig().__dict__,
    }


def _resolve_coeff(
    defaults: dict,
    overrides_dict: dict[str, float] | None,
) -> dict:
    """Fusionne les overrides (cles str) sur les defauts (cles enum)."""
    result = dict(defaults)
    if overrides_dict:
        for k in result:
            str_key = k.value if hasattr(k, "value") else str(k)
            if str_key in overrides_dict:
                result[k] = overrides_dict[str_key]
    return result


def _compute_floor_adjustment(
    etage: int | None,
    nb_etages: int | None,
    has_elevator: bool,
    fp: FloorParams | None = None,
) -> tuple[float, str]:
    """Ajustement selon l'etage avec parametres configurables."""
    if etage is None:
        return 1.0, ""

    if fp is None:
        fp = FloorParams()

    adjustment = 1.0
    explanation = ""

    if etage == 0:
        adjustment = 1.0 - fp.ground_floor_discount
        explanation = f"Rez-de-chaussee : -{fp.ground_floor_discount:.0%}"
    elif etage <= 3:
        adjustment = 1.0
    else:
        if has_elevator:
            bonus = min(
                (etage - 3) * fp.elevator_bonus_per_floor, fp.max_elevator_bonus
            )
            adjustment = 1.0 + bonus
            explanation = f"Etage {etage} avec ascenseur : +{bonus:.0%}"
        else:
            penalty = min(
                (etage - 3) * fp.no_elevator_penalty_per_floor,
                fp.max_no_elevator_penalty,
            )
            adjustment = 1.0 - penalty
            explanation = f"Etage {etage} sans ascenseur : -{penalty:.0%}"

    if nb_etages and etage == nb_etages and etage > 0:
        adjustment += fp.last_floor_bonus
        if explanation:
            explanation += f" + dernier etage : +{fp.last_floor_bonus:.0%}"
        else:
            explanation = f"Dernier etage : +{fp.last_floor_bonus:.0%}"

    return round(adjustment, 4), explanation


def compute_adjustments(
    prop: PropertyInput,
    base_price: float,
    overrides: CoefficientOverrides | None = None,
) -> AdjustmentBreakdown:
    """
    Calcule tous les ajustements et retourne le prix ajuste avec detail.

    Args:
        prop: Description complete du bien.
        base_price: prix_total_estime de estimate().
        overrides: Surcharges optionnelles des coefficients (mode admin).

    Returns:
        AdjustmentBreakdown avec prix ajuste et explications.
    """
    ov = overrides or CoefficientOverrides()
    explanations: list[str] = []

    # Resoudre les coefficients (defauts + overrides)
    r_type = _resolve_coeff(TYPE_COEFFICIENTS, ov.type_coefficients)
    r_quality = _resolve_coeff(QUALITY_COEFFICIENTS, ov.quality_coefficients)
    r_condition = _resolve_coeff(CONDITION_COEFFICIENTS, ov.condition_coefficients)
    r_construction = _resolve_coeff(
        CONSTRUCTION_COEFFICIENTS, ov.construction_coefficients
    )
    r_chars = _resolve_coeff(CHARACTERISTIC_ADJUSTMENTS, ov.characteristic_adjustments)

    # 1. Type
    type_adj = r_type.get(prop.property_type, 1.0)
    if type_adj != 1.0:
        explanations.append(
            f"Type {prop.property_type.label} : {type_adj - 1:+.0%}"
        )

    # 2. Etage
    floor_adj, floor_expl = _compute_floor_adjustment(
        prop.etage, prop.nb_etages_immeuble, prop.ascenseur, ov.floor_params
    )
    if floor_expl:
        explanations.append(floor_expl)

    # 3. Caracteristiques (somme additive -> multiplicateur)
    char_sum = 0.0
    for attr_name, coeff in r_chars.items():
        if getattr(prop, attr_name, False):
            char_sum += coeff
            label = attr_name.replace("_", " ").capitalize()
            explanations.append(f"{label} : +{coeff:.0%}")
    char_adj = 1.0 + char_sum

    # 4. Etat du bien
    cond_adj = r_condition.get(prop.condition, 1.0)
    if cond_adj != 1.0:
        label = prop.condition.value.replace("_", " ").capitalize()
        explanations.append(f"Etat {label} : {cond_adj - 1:+.0%}")

    # 5. Qualite
    qual_adj = r_quality.get(prop.quality, 1.0)
    if qual_adj != 1.0:
        explanations.append(f"Qualite {prop.quality.value} : {qual_adj - 1:+.0%}")

    # 6. Periode de construction
    cons_adj = r_construction.get(prop.construction_period, 1.0)
    if cons_adj != 1.0:
        label = prop.construction_period.value.replace("_", " ")
        explanations.append(f"Construction {label} : {cons_adj - 1:+.0%}")

    # Multiplicateur total (produit), plafonne a [0.70, 1.40]
    total = type_adj * floor_adj * char_adj * cond_adj * qual_adj * cons_adj
    total = max(0.70, min(1.40, round(total, 4)))

    adjusted_price = round(base_price * total, 0)

    return AdjustmentBreakdown(
        base_price=base_price,
        type_adjustment=type_adj,
        floor_adjustment=floor_adj,
        characteristics_adjustment=char_adj,
        condition_adjustment=cond_adj,
        quality_adjustment=qual_adj,
        construction_adjustment=cons_adj,
        total_multiplier=total,
        adjusted_price=adjusted_price,
        explanations=explanations,
    )
