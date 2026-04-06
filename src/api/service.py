"""Orchestration de l'estimation : appelle les modules existants et assemble la reponse."""

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.db import get_engine
from src.estimation.geocoder import geocode_best
from src.estimation.comparables import find_comparables
from src.estimation.estimator import (
    compute_surface_adjustment,
    compute_weighted_median,
    get_zone_stats,
)
from src.estimation.appreciation import compute_appreciation
from src.estimation.confidence import compute_confidence
from src.estimation.zone_config import ZoneConfig
from src.app.models.property_input import (
    PropertyInput,
    PropertyType,
    PropertyCondition,
    QualityLevel,
    ConstructionPeriod,
)
from src.app.models.adjustments import (
    compute_adjustments,
    CoefficientOverrides,
    FloorParams,
)
from src.api.schemas import (
    EstimationRequest,
    EstimationResponse,
    GeocodingSection,
    ConfidenceSchema,
    ZoneBreakdownItem,
    ZoneConfigSchema,
    EstimationSection,
    AdjustmentDetail,
    AdjustmentsSection,
    ZoneStatsSection,
    SemesterItem,
    MonthlyItem,
    EvolutionSection,
    ComparableItem,
    ComparablesSection,
    VALID_SECTIONS,
    AppreciationRequest,
    AppreciationResponse,
    AppreciationGeocodingSchema,
    HistoriqueSchema,
    BenchmarkDeptSchema,
    SegmentSurfaceSchema,
    VolatiliteSchema,
    VolumeSchema,
    AppreciationSection,
    ScenarioSchema,
    ProjectionSchema,
    ProjectionAnneeSchema,
    RisqueSchema,
    ConfidenceAppreciationSchema,
)


def _build_zone_config(req: EstimationRequest) -> ZoneConfig | None:
    """Convertit le schema Pydantic en ZoneConfig dataclass."""
    if req.zone_config is None:
        return None
    zc = req.zone_config
    return ZoneConfig(
        radius_1_km=zc.radius_1_km,
        radius_2_km=zc.radius_2_km,
        radius_3_km=zc.radius_3_km,
        weight_1=zc.weight_1,
        weight_2=zc.weight_2,
        weight_3=zc.weight_3,
    )


def _build_property_input(req: EstimationRequest) -> PropertyInput:
    """Convertit la requete en PropertyInput dataclass."""
    return PropertyInput(
        property_type=PropertyType(req.property_type),
        surface=req.surface,
        nb_pieces=req.nb_pieces,
        nb_salles_de_bain=req.nb_salles_de_bain,
        etage=req.etage,
        nb_etages_immeuble=req.nb_etages_immeuble,
        ascenseur=req.ascenseur,
        balcon=req.balcon,
        terrasse=req.terrasse,
        cave=req.cave,
        parking=req.parking,
        chambre_service=req.chambre_service,
        vue_exceptionnelle=req.vue_exceptionnelle,
        parties_communes_renovees=req.parties_communes_renovees,
        ravalement_recent=req.ravalement_recent,
        construction_period=ConstructionPeriod(req.construction_period),
        condition=PropertyCondition(req.condition),
        quality=QualityLevel(req.quality),
    )


def _build_coefficient_overrides(req: EstimationRequest) -> CoefficientOverrides | None:
    """Convertit les overrides Pydantic en CoefficientOverrides dataclass."""
    if req.coefficient_overrides is None:
        return None
    ov = req.coefficient_overrides
    floor_params = None
    if ov.floor_params:
        fp = ov.floor_params
        floor_params = FloorParams(
            ground_floor_discount=fp.ground_floor_discount,
            elevator_bonus_per_floor=fp.elevator_bonus_per_floor,
            no_elevator_penalty_per_floor=fp.no_elevator_penalty_per_floor,
            last_floor_bonus=fp.last_floor_bonus,
            max_elevator_bonus=fp.max_elevator_bonus,
            max_no_elevator_penalty=fp.max_no_elevator_penalty,
        )

    zone_config = _build_zone_config(req)

    return CoefficientOverrides(
        type_coefficients=ov.type_coefficients,
        quality_coefficients=ov.quality_coefficients,
        condition_coefficients=ov.condition_coefficients,
        construction_coefficients=ov.construction_coefficients,
        characteristic_adjustments=ov.characteristic_adjustments,
        floor_params=floor_params,
        zone_config=zone_config,
    )


def _get_evolution_data(
    code_commune: str,
    code_departement: str,
    type_bien: str,
) -> EvolutionSection:
    """Recupere les donnees d'evolution (semestrielle + mensuelle)."""
    engine = get_engine()

    # Semestre : commune puis fallback departement
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2,
               q1_prix_m2, q3_prix_m2
        FROM mart.stats_commune
        WHERE code_commune = :code_commune AND type_bien = :type_bien
        ORDER BY annee, semestre
    """)
    df = pd.read_sql(query, engine, params={"code_commune": code_commune, "type_bien": type_bien})

    source = "commune"
    if len(df) < 2:
        query = text("""
            SELECT annee, semestre, nb_transactions, median_prix_m2,
                   q1_prix_m2, q3_prix_m2
            FROM mart.stats_departement
            WHERE code_departement = :code_departement AND type_bien = :type_bien
            ORDER BY annee, semestre
        """)
        df = pd.read_sql(query, engine, params={"code_departement": code_departement, "type_bien": type_bien})
        source = "departement"

    semester = [
        SemesterItem(
            annee=int(row["annee"]),
            semestre=int(row["semestre"]),
            nb_transactions=int(row["nb_transactions"]),
            median_prix_m2=float(row["median_prix_m2"]),
            q1_prix_m2=float(row["q1_prix_m2"]) if pd.notna(row.get("q1_prix_m2")) else None,
            q3_prix_m2=float(row["q3_prix_m2"]) if pd.notna(row.get("q3_prix_m2")) else None,
        )
        for _, row in df.iterrows()
    ]

    # Mensuel : indices_temporels (colonnes: annee, mois)
    query_monthly = text("""
        SELECT annee || '-' || LPAD(mois::TEXT, 2, '0') AS annee_mois,
               nb_transactions, median_prix_m2, rolling_median_6m
        FROM mart.indices_temporels
        WHERE code_commune = :code_commune AND type_bien = :type_bien
        ORDER BY annee, mois
    """)
    df_monthly = pd.read_sql(query_monthly, engine, params={"code_commune": code_commune, "type_bien": type_bien})

    monthly = [
        MonthlyItem(
            annee_mois=str(row["annee_mois"]),
            nb_transactions=int(row["nb_transactions"]),
            median_prix_m2=float(row["median_prix_m2"]),
            rolling_median_6m=float(row["rolling_median_6m"]) if pd.notna(row.get("rolling_median_6m")) else None,
        )
        for _, row in df_monthly.iterrows()
    ]

    return EvolutionSection(source=source, semester=semester, monthly=monthly)


def _comparables_to_items(df: pd.DataFrame) -> list[ComparableItem]:
    """Convertit un DataFrame de comparables en liste de ComparableItem."""
    items = []
    for _, row in df.iterrows():
        items.append(ComparableItem(
            id_mutation=str(row["id_mutation"]),
            date_mutation=str(row["date_mutation"]),
            valeur_fonciere=float(row["valeur_fonciere"]),
            type_bien=str(row["type_bien"]),
            surface=float(row["surface"]),
            nb_pieces=int(row["nb_pieces"]) if pd.notna(row.get("nb_pieces")) else None,
            prix_m2=float(row["prix_m2"]),
            code_commune=str(row["code_commune"]),
            nom_commune=str(row.get("nom_commune", "")),
            code_departement=str(row["code_departement"]),
            latitude=float(row["latitude"]) if pd.notna(row.get("latitude")) else None,
            longitude=float(row["longitude"]) if pd.notna(row.get("longitude")) else None,
            distance_m=float(row["distance_m"]) if pd.notna(row.get("distance_m")) else None,
            zone=int(row["zone"]) if pd.notna(row.get("zone")) else None,
        ))
    return items


def process_estimation(request: EstimationRequest) -> EstimationResponse:
    """Traite une requete d'estimation et retourne la reponse complete."""

    # Sections demandees
    sections = set(request.include) & VALID_SECTIONS if request.include else VALID_SECTIONS

    # 1. Geocodage
    geo = geocode_best(request.address, postcode=request.postcode)
    if geo is None:
        return EstimationResponse(status="geocoding_failed")

    geocoding_section = None
    if "geocoding" in sections:
        geocoding_section = GeocodingSection(
            label=geo.label,
            score=geo.score,
            latitude=geo.latitude,
            longitude=geo.longitude,
            citycode=geo.citycode,
            city=geo.city,
            postcode=geo.postcode,
            context=geo.context,
        )

    # 2. Comparables
    zone_config = _build_zone_config(request)
    dvf_type = PropertyType(request.property_type).dvf_type

    search = find_comparables(
        latitude=geo.latitude,
        longitude=geo.longitude,
        code_commune=geo.citycode,
        type_bien=dvf_type,
        surface=request.surface,
        nb_pieces=request.nb_pieces,
        zone_config=zone_config,
    )
    comparables_df = search.comparables

    if len(comparables_df) == 0:
        return EstimationResponse(
            status="no_data",
            geocoding=geocoding_section,
        )

    # 3. Mediane (ponderee par zone si multi-zones)
    zone_breakdown_raw = None
    if search.zone_config and "zone" in comparables_df.columns:
        base_median, zone_breakdown_raw = compute_weighted_median(comparables_df, search.zone_config)
    else:
        base_median = float(np.median(comparables_df["prix_m2"]))

    # 4. Ajustement surface
    adjustment_factor = compute_surface_adjustment(request.surface, comparables_df)
    prix_m2_base = base_median * adjustment_factor
    prix_total_base = prix_m2_base * request.surface

    # 5. Confiance
    confidence = compute_confidence(
        comparables=comparables_df,
        search_level=search.level,
        surface=request.surface,
        adjustment=adjustment_factor,
    )

    # 6. Ajustements heuristiques
    prop = _build_property_input(request)
    overrides = _build_coefficient_overrides(request)
    adj = compute_adjustments(prop, prix_total_base, overrides)

    total_multiplier = adj.total_multiplier
    prix_m2_ajuste = prix_m2_base * total_multiplier
    prix_total_ajuste = adj.adjusted_price

    # Fourchette ajustee par multiplier (cf results_panel.py:461-462)
    low_adjusted = round(confidence.low_estimate * total_multiplier)
    high_adjusted = round(confidence.high_estimate * total_multiplier)

    # 7. Assembler les sections

    estimation_section = None
    if "estimation" in sections:
        # Zone breakdown
        zb_schema = None
        if zone_breakdown_raw:
            zb_schema = {}
            for z_key, z_data in zone_breakdown_raw.items():
                zb_schema[str(z_key)] = ZoneBreakdownItem(
                    count=z_data.get("count", 0),
                    median_prix_m2=z_data.get("median_prix_m2"),
                    effective_weight=z_data.get("effective_weight", 0),
                )

        # Zone config retournee
        zc_schema = None
        if search.zone_config:
            zc = search.zone_config
            zc_schema = ZoneConfigSchema(
                radius_1_km=zc.radius_1_km,
                radius_2_km=zc.radius_2_km,
                radius_3_km=zc.radius_3_km,
                weight_1=zc.weight_1,
                weight_2=zc.weight_2,
                weight_3=zc.weight_3,
            )

        estimation_section = EstimationSection(
            prix_m2_base=round(prix_m2_base, 2),
            prix_total_base=round(prix_total_base, 0),
            adjustment_factor=round(adjustment_factor, 4),
            prix_m2_ajuste=round(prix_m2_ajuste, 2),
            prix_total_ajuste=round(prix_total_ajuste, 0),
            total_multiplier=total_multiplier,
            confidence=ConfidenceSchema(
                level=confidence.level,
                label=confidence.level_label,
                low_estimate=low_adjusted,
                high_estimate=high_adjusted,
            ),
            nb_comparables=len(comparables_df),
            niveau_geo=search.level_desc,
            zone_breakdown=zb_schema,
            zone_config=zc_schema,
        )

    adjustments_section = None
    if "adjustments" in sections:
        details = []
        # Map adjustment names from AdjustmentBreakdown
        adj_names = [
            ("type", adj.type_adjustment),
            ("floor", adj.floor_adjustment),
            ("characteristics", adj.characteristics_adjustment),
            ("condition", adj.condition_adjustment),
            ("quality", adj.quality_adjustment),
            ("construction", adj.construction_adjustment),
        ]
        expl_idx = 0
        for name, coeff in adj_names:
            if abs(coeff - 1.0) > 0.001:
                explanation = adj.explanations[expl_idx] if expl_idx < len(adj.explanations) else ""
                details.append(AdjustmentDetail(
                    name=name,
                    coefficient=coeff,
                    explanation=explanation,
                ))
                expl_idx += 1

        adjustments_section = AdjustmentsSection(
            base_price=round(prix_total_base, 0),
            adjusted_price=round(prix_total_ajuste, 0),
            total_multiplier=total_multiplier,
            details=details,
        )

    zone_stats_section = None
    if "zone_stats" in sections:
        stats = get_zone_stats(geo.citycode, dvf_type)
        if stats:
            zone_stats_section = ZoneStatsSection(
                total_transactions=stats["total_transactions"],
                last_12m_transactions=stats["last_12m_transactions"],
                median_prix_m2_12m=stats["median_prix_m2_12m"],
                stddev_prix_m2_12m=stats["stddev_prix_m2_12m"],
                trend_12m=stats["trend_12m"],
                data_quality_flag=stats["data_quality_flag"],
            )

    evolution_section = None
    if "evolution" in sections:
        code_departement = geo.citycode[:2] if len(geo.citycode) >= 2 else geo.citycode
        evolution_section = _get_evolution_data(geo.citycode, code_departement, dvf_type)

    comparables_section = None
    if "comparables" in sections:
        comparables_section = ComparablesSection(
            count=len(comparables_df),
            items=_comparables_to_items(comparables_df),
        )

    return EstimationResponse(
        status="ok",
        geocoding=geocoding_section,
        estimation=estimation_section,
        adjustments=adjustments_section,
        zone_stats=zone_stats_section,
        evolution=evolution_section,
        comparables=comparables_section,
    )


# ---------------------------------------------------------------------------
# Appreciation
# ---------------------------------------------------------------------------

def process_appreciation(request: AppreciationRequest) -> AppreciationResponse:
    """Traite une requete d'appreciation et retourne la reponse complete."""

    # 1. Geocodage
    geo = geocode_best(request.address, postcode=request.postcode)
    if geo is None:
        return AppreciationResponse(status="geocoding_failed",
                                    error_detail="Adresse introuvable")

    # 2. Mapper le type_bien vers le type DVF binaire
    dvf_type = PropertyType(request.type_bien).dvf_type

    # 3. Calcul d'appreciation
    result = compute_appreciation(
        code_commune=geo.citycode,
        type_bien=dvf_type,
        surface=request.surface,
        prix_achat=request.prix_achat,
        dpe_classe=request.dpe_classe,
        dpe_valeur=request.dpe_valeur,
        annee_construction=request.annee_construction,
        etat_copropriete=request.etat_copropriete,
        zone_tendue=request.zone_tendue,
        travaux_prevus=request.travaux_prevus,
        horizon_annees=request.horizon_annees,
        taux_inflation=request.taux_inflation,
    )

    # 4. Conversion dataclasses -> Pydantic
    geocoding = AppreciationGeocodingSchema(
        commune=geo.city,
        code_commune=geo.citycode,
        departement=geo.citycode[:2] if len(geo.citycode) >= 2 else geo.citycode,
    )

    h = result.historique
    historique = HistoriqueSchema(
        cagr_total_pct=h.cagr_total_pct,
        cagr_3ans_pct=h.cagr_3ans_pct,
        trend_12m_pct=h.trend_12m_pct,
        periode_analyse=h.periode_analyse,
        nb_semestres=h.nb_semestres,
        source=h.source,
        benchmark_departement=BenchmarkDeptSchema(
            cagr_dept_pct=h.benchmark_departement.cagr_dept_pct,
            surperformance_pct=h.benchmark_departement.surperformance_pct,
        ) if h.benchmark_departement else None,
        segment_surface=SegmentSurfaceSchema(
            tranche=h.segment_surface.tranche,
            label=h.segment_surface.label,
            cagr_segment_pct=h.segment_surface.cagr_segment_pct,
        ) if h.segment_surface else None,
        volatilite=VolatiliteSchema(
            coefficient_variation=h.volatilite.coefficient_variation,
            classification=h.volatilite.classification,
        ),
        volume=VolumeSchema(
            total_transactions=h.volume.total_transactions,
            last_12m_transactions=h.volume.last_12m_transactions,
            tendance_volume=h.volume.tendance_volume,
        ),
    )

    a = result.appreciation
    appreciation = AppreciationSection(
        taux_annuel_estime_pct=a.taux_annuel_estime_pct,
        ajustements=a.ajustements,
        taux_final_pct=a.taux_final_pct,
        methode=a.methode,
        scenarios={
            k: ScenarioSchema(taux_pct=v.taux_pct, label=v.label)
            for k, v in a.scenarios.items()
        },
    )

    p = result.projection
    projection = ProjectionSchema(
        prix_achat=p.prix_achat,
        horizon_annees=p.horizon_annees,
        taux_inflation_pct=p.taux_inflation_pct,
        annees=[
            ProjectionAnneeSchema(
                annee=pa.annee,
                pessimiste=pa.pessimiste,
                pragmatique=pa.pragmatique,
                optimiste=pa.optimiste,
            )
            for pa in p.annees
        ],
        plus_value_estimee=p.plus_value_estimee,
        rendement_annualise_nominal_pct=p.rendement_annualise_nominal_pct,
        rendement_annualise_reel_pct=p.rendement_annualise_reel_pct,
    )

    risques = [
        RisqueSchema(facteur=r.facteur, impact=r.impact, detail=r.detail)
        for r in result.risques
    ]

    c = result.confidence
    confidence = ConfidenceAppreciationSchema(
        level=c.level, score=c.score, detail=c.detail,
    )

    return AppreciationResponse(
        status="ok",
        geocoding=geocoding,
        historique=historique,
        appreciation=appreciation,
        projection=projection,
        risques=risques,
        confidence=confidence,
    )
