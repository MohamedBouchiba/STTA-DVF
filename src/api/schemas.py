"""Modeles Pydantic v2 pour l'API d'estimation."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request sub-schemas
# ---------------------------------------------------------------------------

class ZoneConfigSchema(BaseModel):
    """Configuration des 3 zones concentriques."""

    radius_1_km: float = 1.0
    radius_2_km: float = 2.0
    radius_3_km: float = 3.0
    weight_1: float = 0.60
    weight_2: float = 0.30
    weight_3: float = 0.10


class FloorParamsSchema(BaseModel):
    """Parametres d'ajustement etage."""

    ground_floor_discount: float = 0.07
    elevator_bonus_per_floor: float = 0.01
    no_elevator_penalty_per_floor: float = 0.03
    last_floor_bonus: float = 0.03
    max_elevator_bonus: float = 0.05
    max_no_elevator_penalty: float = 0.12


class CoefficientOverridesSchema(BaseModel):
    """Surcharges optionnelles des coefficients d'ajustement."""

    type_coefficients: dict[str, float] | None = None
    quality_coefficients: dict[str, float] | None = None
    condition_coefficients: dict[str, float] | None = None
    construction_coefficients: dict[str, float] | None = None
    characteristic_adjustments: dict[str, float] | None = None
    floor_params: FloorParamsSchema | None = None


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

VALID_SECTIONS = {"geocoding", "estimation", "adjustments", "zone_stats", "evolution", "comparables"}


class EstimationRequest(BaseModel):
    """Requete d'estimation immobiliere."""

    # Adresse (obligatoire)
    address: str = Field(..., min_length=3)
    postcode: str | None = None

    # Bien (obligatoire)
    property_type: str = Field(..., description="appartement, maison, duplex, triplex, loft, hotel_particulier")
    surface: float = Field(..., gt=0)

    # Bien (optionnel)
    nb_pieces: int | None = None
    nb_salles_de_bain: int | None = None
    etage: int | None = None
    nb_etages_immeuble: int | None = None

    # Caracteristiques booleennes
    ascenseur: bool = False
    balcon: bool = False
    terrasse: bool = False
    cave: bool = False
    parking: bool = False
    chambre_service: bool = False
    vue_exceptionnelle: bool = False
    parties_communes_renovees: bool = False
    ravalement_recent: bool = False

    # Qualite / Etat / Construction
    condition: str = "standard"
    quality: str = "comparable"
    construction_period: str = "unknown"

    # Zones concentriques (optionnel)
    zone_config: ZoneConfigSchema | None = None

    # Overrides coefficients admin (optionnel)
    coefficient_overrides: CoefficientOverridesSchema | None = None

    # Sections a inclure (None = toutes)
    include: list[str] | None = None


# ---------------------------------------------------------------------------
# Response sub-schemas
# ---------------------------------------------------------------------------

class GeocodingSection(BaseModel):
    """Resultat du geocodage."""

    label: str
    score: float
    latitude: float
    longitude: float
    citycode: str
    city: str
    postcode: str
    context: str


class ConfidenceSchema(BaseModel):
    """Niveau de confiance et fourchette de prix."""

    level: str
    label: str
    low_estimate: float
    high_estimate: float


class ZoneBreakdownItem(BaseModel):
    """Detail d'une zone dans le zone_breakdown."""

    count: int
    median_prix_m2: float | None
    effective_weight: float


class EstimationSection(BaseModel):
    """Section estimation avec prix base + ajuste."""

    prix_m2_base: float
    prix_total_base: float
    adjustment_factor: float

    prix_m2_ajuste: float
    prix_total_ajuste: float
    total_multiplier: float

    confidence: ConfidenceSchema

    nb_comparables: int
    niveau_geo: str

    zone_breakdown: dict[str, ZoneBreakdownItem] | None = None
    zone_config: ZoneConfigSchema | None = None


class AdjustmentDetail(BaseModel):
    """Detail d'un ajustement individuel."""

    name: str
    coefficient: float
    explanation: str


class AdjustmentsSection(BaseModel):
    """Section ajustements heuristiques."""

    base_price: float
    adjusted_price: float
    total_multiplier: float
    details: list[AdjustmentDetail]


class ZoneStatsSection(BaseModel):
    """Statistiques de zone depuis mart.zone_stats."""

    total_transactions: int
    last_12m_transactions: int
    median_prix_m2_12m: float | None = None
    stddev_prix_m2_12m: float | None = None
    trend_12m: float | None = None
    data_quality_flag: str


class SemesterItem(BaseModel):
    """Donnee d'un semestre."""

    annee: int
    semestre: int
    nb_transactions: int
    median_prix_m2: float
    q1_prix_m2: float | None = None
    q3_prix_m2: float | None = None


class MonthlyItem(BaseModel):
    """Donnee mensuelle depuis indices_temporels."""

    annee_mois: str
    nb_transactions: int
    median_prix_m2: float
    rolling_median_6m: float | None = None


class EvolutionSection(BaseModel):
    """Section evolution historique."""

    source: str
    semester: list[SemesterItem]
    monthly: list[MonthlyItem]


class ComparableItem(BaseModel):
    """Transaction comparable individuelle."""

    id_mutation: str
    date_mutation: str
    valeur_fonciere: float
    type_bien: str
    surface: float
    nb_pieces: int | None = None
    prix_m2: float
    code_commune: str
    nom_commune: str
    code_departement: str
    latitude: float | None = None
    longitude: float | None = None
    distance_m: float | None = None
    zone: int | None = None


class ComparablesSection(BaseModel):
    """Section comparables."""

    count: int
    items: list[ComparableItem]


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class EstimationResponse(BaseModel):
    """Reponse complete de l'API d'estimation."""

    status: str  # "ok" | "geocoding_failed" | "no_data"

    geocoding: GeocodingSection | None = None
    estimation: EstimationSection | None = None
    adjustments: AdjustmentsSection | None = None
    zone_stats: ZoneStatsSection | None = None
    evolution: EvolutionSection | None = None
    comparables: ComparablesSection | None = None


class HealthResponse(BaseModel):
    """Reponse du health check."""

    status: str
    database: str
    postgis_version: str | None = None
    transactions_count: int | None = None
