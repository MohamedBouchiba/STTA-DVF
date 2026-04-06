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


class AutocompleteItem(BaseModel):
    """Suggestion d'adresse."""

    label: str
    street: str | None = None
    city: str
    postcode: str
    latitude: float
    longitude: float


class AutocompleteResponse(BaseModel):
    """Reponse de l'autocompletion d'adresse."""

    results: list[AutocompleteItem]


class HealthResponse(BaseModel):
    """Reponse du health check."""

    status: str
    database: str
    postgis_version: str | None = None
    transactions_count: int | None = None


# ---------------------------------------------------------------------------
# Appreciation : Request
# ---------------------------------------------------------------------------

class AppreciationRequest(BaseModel):
    """Requete d'estimation d'appreciation immobiliere."""

    # --- Obligatoires ---
    address: str = Field(..., min_length=3)
    type_bien: str = Field(..., description="appartement, maison, duplex, triplex, loft, hotel_particulier")
    surface: float = Field(..., gt=0)
    prix_achat: float = Field(..., gt=0)

    # --- Fortement recommandes ---
    postcode: str | None = None
    dpe_classe: str | None = Field(None, pattern=r"^[A-Ga-g]$")
    nb_pieces: int | None = Field(None, ge=1)
    annee_construction: int | None = Field(None, ge=1500, le=2030)
    condition: str | None = None
    usage_prevu: str | None = None

    # --- Affinent le taux ---
    dpe_valeur: float | None = Field(None, ge=0)
    ges_classe: str | None = Field(None, pattern=r"^[A-Ga-g]$")
    type_chauffage: str | None = None
    nb_chambres: int | None = Field(None, ge=0)
    etat_copropriete: str | None = Field(None, description="saine, correcte, en_difficulte")
    charges_copro_mensuelles: float | None = Field(None, ge=0)
    zone_tendue: bool | None = None
    travaux_prevus: float | None = Field(None, ge=0)
    surface_terrain: float | None = Field(None, gt=0)

    # --- Affinent le prix de depart ---
    etage: int | None = None
    nb_etages_immeuble: int | None = Field(None, ge=1)
    ascenseur: bool | None = None
    balcon: bool | None = None
    terrasse: bool | None = None
    surface_exterieur: float | None = Field(None, ge=0)
    cave: bool | None = None
    parking: bool | None = None
    nb_parkings: int | None = Field(None, ge=0)
    orientation: str | None = None
    vue: str | None = None
    luminosite: str | None = None
    qualite_prestations: str | None = None
    type_immeuble: str | None = None
    ravalement_recent: bool | None = None
    loyer_mensuel_estime: float | None = Field(None, ge=0)

    # --- Financier ---
    horizon_annees: int = Field(5, ge=1, le=30)
    taux_inflation: float = Field(2.0, ge=0, le=20)


# ---------------------------------------------------------------------------
# Appreciation : Response sub-schemas
# ---------------------------------------------------------------------------

class BenchmarkDeptSchema(BaseModel):
    cagr_dept_pct: float
    surperformance_pct: float


class SegmentSurfaceSchema(BaseModel):
    tranche: str
    label: str
    cagr_segment_pct: float | None = None


class VolatiliteSchema(BaseModel):
    coefficient_variation: float | None = None
    classification: str


class VolumeSchema(BaseModel):
    total_transactions: int
    last_12m_transactions: int
    tendance_volume: str


class HistoriqueSchema(BaseModel):
    cagr_total_pct: float | None = None
    cagr_3ans_pct: float | None = None
    trend_12m_pct: float | None = None
    periode_analyse: str
    nb_semestres: int
    source: str
    benchmark_departement: BenchmarkDeptSchema | None = None
    segment_surface: SegmentSurfaceSchema | None = None
    volatilite: VolatiliteSchema
    volume: VolumeSchema


class ScenarioSchema(BaseModel):
    taux_pct: float
    label: str


class AppreciationSection(BaseModel):
    taux_annuel_estime_pct: float
    ajustements: dict[str, float]
    taux_final_pct: float
    methode: str
    scenarios: dict[str, ScenarioSchema]


class ProjectionAnneeSchema(BaseModel):
    annee: int
    pessimiste: float
    pragmatique: float
    optimiste: float


class ProjectionSchema(BaseModel):
    prix_achat: float
    horizon_annees: int
    taux_inflation_pct: float
    annees: list[ProjectionAnneeSchema]
    plus_value_estimee: dict[str, float]
    rendement_annualise_nominal_pct: dict[str, float]
    rendement_annualise_reel_pct: dict[str, float]


class RisqueSchema(BaseModel):
    facteur: str
    impact: str
    detail: str


class ConfidenceAppreciationSchema(BaseModel):
    level: str
    score: int
    detail: str


class AppreciationGeocodingSchema(BaseModel):
    commune: str
    code_commune: str
    departement: str


# ---------------------------------------------------------------------------
# Appreciation : Response
# ---------------------------------------------------------------------------

class AppreciationResponse(BaseModel):
    """Reponse complete de l'endpoint d'appreciation."""

    status: str  # "ok" | "geocoding_failed" | "no_data" | "error"
    error_detail: str | None = None

    geocoding: AppreciationGeocodingSchema | None = None
    historique: HistoriqueSchema | None = None
    appreciation: AppreciationSection | None = None
    projection: ProjectionSchema | None = None
    risques: list[RisqueSchema] | None = None
    confidence: ConfidenceAppreciationSchema | None = None
