"""Moteur d'estimation d'appreciation immobiliere.

Calcule le taux d'appreciation annuel d'un bien en se basant sur :
1. CAGR historique de la commune (donnees DVF)
2. Momentum recent (trend_12m)
3. Ajustements : DPE, construction, copropriete
4. Scenarios pessimiste / base / optimiste
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import text

from src.db import get_engine


# ---------------------------------------------------------------------------
# Dataclasses de sortie
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkDept:
    cagr_dept_pct: float
    surperformance_pct: float


@dataclass
class SegmentSurface:
    tranche: str
    label: str
    cagr_segment_pct: float | None


@dataclass
class Volatilite:
    coefficient_variation: float | None
    classification: str  # "stable", "modere", "volatile"


@dataclass
class Volume:
    total_transactions: int
    last_12m_transactions: int
    tendance_volume: str  # "en_hausse", "stable", "en_baisse"


@dataclass
class Historique:
    cagr_total_pct: float | None
    cagr_3ans_pct: float | None
    trend_12m_pct: float | None
    periode_analyse: str
    nb_semestres: int
    source: str  # "commune" ou "departement"
    benchmark_departement: BenchmarkDept | None
    segment_surface: SegmentSurface | None
    volatilite: Volatilite
    volume: Volume


@dataclass
class Scenario:
    taux_pct: float
    label: str


@dataclass
class Appreciation:
    taux_annuel_estime_pct: float
    ajustements: dict[str, float]  # nom -> pct
    taux_final_pct: float
    methode: str
    scenarios: dict[str, Scenario]  # pessimiste, base, optimiste


@dataclass
class ProjectionAnnee:
    annee: int
    pessimiste: float
    base: float
    optimiste: float


@dataclass
class Projection:
    prix_achat: float
    horizon_annees: int
    taux_inflation_pct: float
    annees: list[ProjectionAnnee]
    plus_value_estimee: dict[str, float]
    rendement_annualise_nominal_pct: dict[str, float]
    rendement_annualise_reel_pct: dict[str, float]


@dataclass
class Risque:
    facteur: str
    impact: str  # "positif", "neutre", "faible", "modere", "eleve"
    detail: str


@dataclass
class Confidence:
    level: str  # "high", "medium", "low"
    score: int
    detail: str


@dataclass
class AppreciationResult:
    historique: Historique
    appreciation: Appreciation
    projection: Projection
    risques: list[Risque]
    confidence: Confidence


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Ajustement DPE annuel (Loi Climat & Resilience)
DPE_ADJUSTMENT: dict[str, float] = {
    "A": 0.5,
    "B": 0.3,
    "C": 0.1,
    "D": 0.0,
    "E": -0.3,
    "F": -0.8,
    "G": -1.5,
}

# Ajustement annee de construction
CONSTRUCTION_ADJUSTMENT: dict[str, float] = {
    "avant_1850": 0.15,   # Haussmannien / pierre — prime patrimoniale
    "1850_1913": 0.1,
    "1914_1947": -0.05,
    "1948_1969": -0.15,   # Grands ensembles, beton vieillissant
    "1970_1989": -0.1,
    "1990_2005": 0.0,
    "apres_2005": 0.1,    # RT2005+, bien isole
}

# Etat copropriete
COPRO_ADJUSTMENT: dict[str, float] = {
    "saine": 0.0,
    "correcte": -0.1,
    "en_difficulte": -0.5,
}

# Seuils de surface pour segmentation
SURFACE_PETIT = 40.0
SURFACE_GRAND = 80.0


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def _compute_cagr(first_value: float, last_value: float, nb_years: float) -> float | None:
    """Calcule le CAGR (taux de croissance annuel compose) en %."""
    if first_value <= 0 or last_value <= 0 or nb_years <= 0:
        return None
    ratio = last_value / first_value
    cagr = (ratio ** (1.0 / nb_years)) - 1.0
    return round(cagr * 100, 2)


def _surface_segment(surface: float) -> tuple[str, str]:
    """Retourne (tranche_key, label) pour une surface donnee."""
    if surface < SURFACE_PETIT:
        return "petit", f"petit (< {SURFACE_PETIT:.0f} m\u00b2)"
    if surface > SURFACE_GRAND:
        return "grand", f"grand (> {SURFACE_GRAND:.0f} m\u00b2)"
    return "moyen", f"moyen ({SURFACE_PETIT:.0f}-{SURFACE_GRAND:.0f} m\u00b2)"


def _construction_period_key(annee: int | None) -> str | None:
    """Convertit une annee de construction en cle de periode."""
    if annee is None:
        return None
    if annee < 1850:
        return "avant_1850"
    if annee <= 1913:
        return "1850_1913"
    if annee <= 1947:
        return "1914_1947"
    if annee <= 1969:
        return "1948_1969"
    if annee <= 1989:
        return "1970_1989"
    if annee <= 2005:
        return "1990_2005"
    return "apres_2005"


# ---------------------------------------------------------------------------
# Requetes DB
# ---------------------------------------------------------------------------

def _get_semester_data(
    code_commune: str,
    type_bien: str,
) -> tuple[pd.DataFrame, str]:
    """Recupere les medianes semestrielles. Fallback sur departement."""
    engine = get_engine()
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2,
               q1_prix_m2, q3_prix_m2
        FROM mart.stats_commune
        WHERE code_commune = :code AND type_bien = :type
        ORDER BY annee, semestre
    """)
    df = pd.read_sql(query, engine, params={"code": code_commune, "type": type_bien})

    if len(df) >= 2:
        return df, "commune"

    # Fallback departement
    dept = code_commune[:2] if len(code_commune) >= 2 else code_commune
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2,
               q1_prix_m2, q3_prix_m2
        FROM mart.stats_departement
        WHERE code_departement = :dept AND type_bien = :type
        ORDER BY annee, semestre
    """)
    df = pd.read_sql(query, engine, params={"dept": dept, "type": type_bien})
    return df, "departement"


def _get_dept_semester_data(
    code_departement: str,
    type_bien: str,
) -> pd.DataFrame:
    """Recupere les medianes semestrielles du departement."""
    engine = get_engine()
    query = text("""
        SELECT annee, semestre, nb_transactions, median_prix_m2
        FROM mart.stats_departement
        WHERE code_departement = :dept AND type_bien = :type
        ORDER BY annee, semestre
    """)
    return pd.read_sql(query, engine, params={"dept": code_departement, "type": type_bien})


def _get_zone_stats(code_commune: str, type_bien: str) -> dict | None:
    """Recupere zone_stats pour une commune."""
    engine = get_engine()
    query = text("""
        SELECT total_transactions, last_12m_transactions,
               median_prix_m2_12m, stddev_prix_m2_12m,
               trend_12m, data_quality_flag
        FROM mart.zone_stats
        WHERE code_commune = :code AND type_bien = :type
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"code": code_commune, "type": type_bien}).fetchone()
        if row:
            return {
                "total_transactions": row[0],
                "last_12m_transactions": row[1],
                "median_prix_m2_12m": float(row[2]) if row[2] else None,
                "stddev_prix_m2_12m": float(row[3]) if row[3] else None,
                "trend_12m": float(row[4]) if row[4] else None,
                "data_quality_flag": row[5],
            }
    return None


def _get_segment_cagr(
    code_commune: str,
    type_bien: str,
    surface: float,
) -> float | None:
    """Calcule le CAGR pour un segment de surface dans la commune.

    Interroge core.transactions directement avec un filtre surface.
    """
    segment_key, _ = _surface_segment(surface)
    if segment_key == "petit":
        surf_min, surf_max = 9, SURFACE_PETIT
    elif segment_key == "grand":
        surf_min, surf_max = SURFACE_GRAND, 500
    else:
        surf_min, surf_max = SURFACE_PETIT, SURFACE_GRAND

    engine = get_engine()
    query = text("""
        WITH semestres AS (
            SELECT
                annee,
                CASE WHEN mois <= 6 THEN 1 ELSE 2 END AS semestre,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2,
                COUNT(*) AS nb
            FROM core.transactions
            WHERE code_commune = :code
              AND type_bien = :type
              AND surface >= :surf_min AND surface < :surf_max
              AND NOT is_outlier
            GROUP BY annee, CASE WHEN mois <= 6 THEN 1 ELSE 2 END
            HAVING COUNT(*) >= 5
            ORDER BY annee, semestre
        )
        SELECT annee, semestre, median_prix_m2, nb
        FROM semestres
    """)
    df = pd.read_sql(
        query, engine,
        params={"code": code_commune, "type": type_bien,
                "surf_min": surf_min, "surf_max": surf_max},
    )

    if len(df) < 2:
        return None

    first_val = float(df.iloc[0]["median_prix_m2"])
    last_val = float(df.iloc[-1]["median_prix_m2"])
    first_sem = df.iloc[0]["annee"] + (df.iloc[0]["semestre"] - 1) * 0.5
    last_sem = df.iloc[-1]["annee"] + (df.iloc[-1]["semestre"] - 1) * 0.5
    nb_years = last_sem - first_sem

    return _compute_cagr(first_val, last_val, nb_years)


# ---------------------------------------------------------------------------
# Moteur principal
# ---------------------------------------------------------------------------

def compute_appreciation(
    code_commune: str,
    type_bien: str,
    surface: float,
    prix_achat: float,
    *,
    dpe_classe: str | None = None,
    dpe_valeur: float | None = None,
    annee_construction: int | None = None,
    etat_copropriete: str | None = None,
    zone_tendue: bool | None = None,
    travaux_prevus: float | None = None,
    horizon_annees: int = 5,
    taux_inflation: float = 2.0,
) -> AppreciationResult:
    """Calcule l'appreciation estimee d'un bien immobilier.

    Args:
        code_commune: Code INSEE de la commune (arrondissement pour Paris/Marseille).
        type_bien: 'appartement' ou 'maison'.
        surface: Surface en m2.
        prix_achat: Prix d'achat du bien en euros.
        dpe_classe: Classe DPE (A-G).
        dpe_valeur: Valeur DPE en kWh/m2/an.
        annee_construction: Annee de construction du batiment.
        etat_copropriete: 'saine', 'correcte', 'en_difficulte'.
        zone_tendue: True si le bien est en zone tendue.
        travaux_prevus: Budget travaux prevu (ameliore le DPE post-travaux).
        horizon_annees: Horizon de projection (defaut 5).
        taux_inflation: Taux d'inflation annuel en % (defaut 2.0).

    Returns:
        AppreciationResult avec historique, taux, scenarios, projections.
    """
    # -----------------------------------------------------------------------
    # Etape 1 : Donnees historiques semestrielles
    # -----------------------------------------------------------------------
    df_sem, source = _get_semester_data(code_commune, type_bien)
    zone_stats = _get_zone_stats(code_commune, type_bien)

    # Calcul CAGR total
    cagr_total = None
    cagr_3ans = None
    nb_semestres = len(df_sem)

    if nb_semestres >= 2:
        first_val = float(df_sem.iloc[0]["median_prix_m2"])
        last_val = float(df_sem.iloc[-1]["median_prix_m2"])
        first_t = df_sem.iloc[0]["annee"] + (df_sem.iloc[0]["semestre"] - 1) * 0.5
        last_t = df_sem.iloc[-1]["annee"] + (df_sem.iloc[-1]["semestre"] - 1) * 0.5
        nb_years = last_t - first_t
        cagr_total = _compute_cagr(first_val, last_val, nb_years)

        # CAGR 3 ans
        target_t = last_t - 3.0
        df_recent = df_sem[
            (df_sem["annee"] + (df_sem["semestre"] - 1) * 0.5) >= target_t
        ]
        if len(df_recent) >= 2:
            first_3 = float(df_recent.iloc[0]["median_prix_m2"])
            last_3 = float(df_recent.iloc[-1]["median_prix_m2"])
            t0 = df_recent.iloc[0]["annee"] + (df_recent.iloc[0]["semestre"] - 1) * 0.5
            t1 = df_recent.iloc[-1]["annee"] + (df_recent.iloc[-1]["semestre"] - 1) * 0.5
            cagr_3ans = _compute_cagr(first_3, last_3, t1 - t0)

    trend_12m = zone_stats["trend_12m"] if zone_stats else None

    # Periode d'analyse
    if nb_semestres >= 2:
        p0 = f"{int(df_sem.iloc[0]['annee'])}-S{int(df_sem.iloc[0]['semestre'])}"
        p1 = f"{int(df_sem.iloc[-1]['annee'])}-S{int(df_sem.iloc[-1]['semestre'])}"
        periode = f"{p0} a {p1}"
    else:
        periode = "donnees insuffisantes"

    # -----------------------------------------------------------------------
    # Etape 2 : Benchmark departement
    # -----------------------------------------------------------------------
    benchmark = None
    code_dept = code_commune[:2] if len(code_commune) >= 2 else code_commune

    if source == "commune":
        df_dept = _get_dept_semester_data(code_dept, type_bien)
        if len(df_dept) >= 2:
            dept_first = float(df_dept.iloc[0]["median_prix_m2"])
            dept_last = float(df_dept.iloc[-1]["median_prix_m2"])
            dt0 = df_dept.iloc[0]["annee"] + (df_dept.iloc[0]["semestre"] - 1) * 0.5
            dt1 = df_dept.iloc[-1]["annee"] + (df_dept.iloc[-1]["semestre"] - 1) * 0.5
            cagr_dept = _compute_cagr(dept_first, dept_last, dt1 - dt0)
            if cagr_dept is not None and cagr_total is not None:
                benchmark = BenchmarkDept(
                    cagr_dept_pct=cagr_dept,
                    surperformance_pct=round(cagr_total - cagr_dept, 2),
                )

    # -----------------------------------------------------------------------
    # Etape 3 : Segment de surface
    # -----------------------------------------------------------------------
    seg_key, seg_label = _surface_segment(surface)
    seg_cagr = _get_segment_cagr(code_commune, type_bien, surface)
    segment = SegmentSurface(tranche=seg_key, label=seg_label, cagr_segment_pct=seg_cagr)

    # -----------------------------------------------------------------------
    # Etape 4 : Volatilite
    # -----------------------------------------------------------------------
    cv = None
    cv_class = "inconnu"
    if zone_stats and zone_stats["median_prix_m2_12m"] and zone_stats["stddev_prix_m2_12m"]:
        median_12m = zone_stats["median_prix_m2_12m"]
        stddev_12m = zone_stats["stddev_prix_m2_12m"]
        if median_12m > 0:
            cv = round(stddev_12m / median_12m, 3)
            if cv < 0.15:
                cv_class = "stable"
            elif cv < 0.30:
                cv_class = "modere"
            else:
                cv_class = "volatile"

    volatilite = Volatilite(coefficient_variation=cv, classification=cv_class)

    # -----------------------------------------------------------------------
    # Etape 5 : Volume et tendance
    # -----------------------------------------------------------------------
    total_txn = zone_stats["total_transactions"] if zone_stats else 0
    last_12m_txn = zone_stats["last_12m_transactions"] if zone_stats else 0

    if total_txn > 0 and nb_semestres > 0:
        avg_annual = total_txn / max(nb_semestres / 2, 1)
        if last_12m_txn > avg_annual * 1.15:
            vol_tendance = "en_hausse"
        elif last_12m_txn < avg_annual * 0.85:
            vol_tendance = "en_baisse"
        else:
            vol_tendance = "stable"
    else:
        vol_tendance = "inconnu"

    volume = Volume(
        total_transactions=total_txn,
        last_12m_transactions=last_12m_txn,
        tendance_volume=vol_tendance,
    )

    historique = Historique(
        cagr_total_pct=cagr_total,
        cagr_3ans_pct=cagr_3ans,
        trend_12m_pct=trend_12m,
        periode_analyse=periode,
        nb_semestres=nb_semestres,
        source=source,
        benchmark_departement=benchmark,
        segment_surface=segment,
        volatilite=volatilite,
        volume=volume,
    )

    # -----------------------------------------------------------------------
    # Etape 6 : Taux d'appreciation de base (ponderation)
    # -----------------------------------------------------------------------
    components = []
    weights = []

    if cagr_total is not None:
        components.append(cagr_total)
        weights.append(0.50)

    if cagr_3ans is not None:
        components.append(cagr_3ans)
        weights.append(0.30)
    elif cagr_total is not None:
        # Pas de CAGR 3 ans -> reporter le poids sur CAGR total
        components.append(cagr_total)
        weights.append(0.30)

    if trend_12m is not None:
        # Mean-reversion : plafonner trend_12m si trop eloigne du CAGR
        trend_capped = trend_12m
        if cagr_total is not None and abs(trend_12m - cagr_total) > 5.0:
            trend_capped = cagr_total + 5.0 * (1 if trend_12m > cagr_total else -1)
        components.append(trend_capped)
        weights.append(0.20)
    elif cagr_total is not None:
        components.append(cagr_total)
        weights.append(0.20)

    if components:
        total_w = sum(weights)
        taux_base = sum(c * w for c, w in zip(components, weights)) / total_w
    else:
        taux_base = 0.0

    # -----------------------------------------------------------------------
    # Etape 7 : Ajustements (DPE, construction, copropriete, zone tendue)
    # -----------------------------------------------------------------------
    ajustements: dict[str, float] = {}

    # DPE
    if dpe_classe and dpe_classe.upper() in DPE_ADJUSTMENT:
        adj_dpe = DPE_ADJUSTMENT[dpe_classe.upper()]
        if adj_dpe != 0:
            ajustements["dpe"] = adj_dpe

    # Construction
    period_key = _construction_period_key(annee_construction)
    if period_key and period_key in CONSTRUCTION_ADJUSTMENT:
        adj_constr = CONSTRUCTION_ADJUSTMENT[period_key]
        if adj_constr != 0:
            ajustements["construction"] = adj_constr

    # Copropriete
    if etat_copropriete and etat_copropriete in COPRO_ADJUSTMENT:
        adj_copro = COPRO_ADJUSTMENT[etat_copropriete]
        if adj_copro != 0:
            ajustements["copropriete"] = adj_copro

    # Zone tendue
    if zone_tendue:
        ajustements["zone_tendue"] = 0.2

    # Travaux prevus (bonus si ameliore le DPE)
    if travaux_prevus and travaux_prevus > 0 and prix_achat > 0:
        travaux_ratio = travaux_prevus / prix_achat
        # Bonus proportionnel : 10% du prix en travaux -> +0.3%/an
        adj_travaux = round(min(travaux_ratio * 3.0, 0.5), 2)
        if adj_travaux > 0:
            ajustements["travaux"] = adj_travaux

    total_ajustement = sum(ajustements.values())
    taux_final = round(taux_base + total_ajustement, 2)

    appreciation = Appreciation(
        taux_annuel_estime_pct=round(taux_base, 2),
        ajustements=ajustements,
        taux_final_pct=taux_final,
        methode="weighted_cagr_momentum",
        scenarios={},  # Rempli ci-dessous
    )

    # -----------------------------------------------------------------------
    # Etape 8 : Scenarios
    # -----------------------------------------------------------------------
    # Ecart base sur la volatilite (ou 2pp par defaut)
    if cv and cv > 0:
        spread = max(round(1.5 * cv * abs(taux_final), 1), 1.5)
    else:
        spread = 2.0

    taux_pessimiste = round(taux_final - spread, 1)
    taux_optimiste = round(taux_final + spread, 1)

    appreciation.scenarios = {
        "pessimiste": Scenario(
            taux_pct=taux_pessimiste,
            label="Marche en ralentissement",
        ),
        "base": Scenario(
            taux_pct=taux_final,
            label="Tendance historique maintenue",
        ),
        "optimiste": Scenario(
            taux_pct=taux_optimiste,
            label="Acceleration du marche",
        ),
    }

    # -----------------------------------------------------------------------
    # Etape 9 : Projection
    # -----------------------------------------------------------------------
    annees = []
    for n in range(1, horizon_annees + 1):
        annees.append(ProjectionAnnee(
            annee=n,
            pessimiste=round(prix_achat * (1 + taux_pessimiste / 100) ** n),
            base=round(prix_achat * (1 + taux_final / 100) ** n),
            optimiste=round(prix_achat * (1 + taux_optimiste / 100) ** n),
        ))

    # Plus-value a l'horizon
    h = horizon_annees
    pv = {
        "pessimiste": round(prix_achat * (1 + taux_pessimiste / 100) ** h - prix_achat),
        "base": round(prix_achat * (1 + taux_final / 100) ** h - prix_achat),
        "optimiste": round(prix_achat * (1 + taux_optimiste / 100) ** h - prix_achat),
    }

    rdt_nominal = {
        "pessimiste": taux_pessimiste,
        "base": taux_final,
        "optimiste": taux_optimiste,
    }

    rdt_reel = {
        "pessimiste": round(taux_pessimiste - taux_inflation, 1),
        "base": round(taux_final - taux_inflation, 1),
        "optimiste": round(taux_optimiste - taux_inflation, 1),
    }

    projection = Projection(
        prix_achat=prix_achat,
        horizon_annees=horizon_annees,
        taux_inflation_pct=taux_inflation,
        annees=annees,
        plus_value_estimee=pv,
        rendement_annualise_nominal_pct=rdt_nominal,
        rendement_annualise_reel_pct=rdt_reel,
    )

    # -----------------------------------------------------------------------
    # Etape 10 : Risques
    # -----------------------------------------------------------------------
    risques: list[Risque] = []

    # DPE
    if dpe_classe:
        dc = dpe_classe.upper()
        if dc in ("A", "B"):
            risques.append(Risque("dpe", "positif",
                f"DPE {dc} — batiment performant, prime croissante"))
        elif dc in ("C", "D"):
            risques.append(Risque("dpe", "neutre",
                f"DPE {dc} — pas de contrainte reglementaire a court terme"))
        elif dc == "E":
            risques.append(Risque("dpe", "modere",
                "DPE E — interdiction location en 2034, decote progressive"))
        elif dc == "F":
            risques.append(Risque("dpe", "eleve",
                "DPE F — interdiction location en 2028, decote acceleree"))
        elif dc == "G":
            risques.append(Risque("dpe", "eleve",
                "DPE G — deja interdit en location depuis 2025, forte decote"))

    # Volatilite
    if cv is not None:
        if cv < 0.15:
            risques.append(Risque("volatilite", "faible",
                f"CV {cv:.2f} — marche stable"))
        elif cv < 0.30:
            risques.append(Risque("volatilite", "modere",
                f"CV {cv:.2f} — volatilite moderee"))
        else:
            risques.append(Risque("volatilite", "eleve",
                f"CV {cv:.2f} — marche volatile"))

    # Liquidite
    if last_12m_txn >= 30:
        risques.append(Risque("liquidite", "faible",
            f"{last_12m_txn} transactions/an — marche liquide"))
    elif last_12m_txn >= 10:
        risques.append(Risque("liquidite", "modere",
            f"{last_12m_txn} transactions/an — liquidite moderee"))
    elif last_12m_txn > 0:
        risques.append(Risque("liquidite", "eleve",
            f"{last_12m_txn} transactions/an — marche peu liquide"))

    # -----------------------------------------------------------------------
    # Etape 11 : Confiance
    # -----------------------------------------------------------------------
    score = 0
    details = []

    if nb_semestres >= 8:
        score += 30
        details.append(f"{nb_semestres} semestres d'historique")
    elif nb_semestres >= 4:
        score += 20
        details.append(f"{nb_semestres} semestres d'historique")
    elif nb_semestres >= 2:
        score += 10
        details.append(f"{nb_semestres} semestres seulement")

    if total_txn >= 100:
        score += 25
        details.append(f"{total_txn} transactions historiques")
    elif total_txn >= 30:
        score += 15
    elif total_txn >= 10:
        score += 5

    if last_12m_txn >= 30:
        score += 20
    elif last_12m_txn >= 10:
        score += 10

    if cv is not None and cv < 0.15:
        score += 15
    elif cv is not None and cv < 0.30:
        score += 5

    if source == "commune":
        score += 10
        details.append("donnees communales")
    else:
        details.append("fallback departement")

    score = min(score, 100)

    if score >= 70:
        conf_level = "high"
    elif score >= 40:
        conf_level = "medium"
    else:
        conf_level = "low"

    confidence = Confidence(
        level=conf_level,
        score=score,
        detail=", ".join(details),
    )

    return AppreciationResult(
        historique=historique,
        appreciation=appreciation,
        projection=projection,
        risques=risques,
        confidence=confidence,
    )
