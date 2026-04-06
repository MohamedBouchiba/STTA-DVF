# POST /api/v1/appreciation

Estimation d'appreciation immobiliere sur N annees.

Calcule le taux d'appreciation annuel estime d'un bien en se basant sur l'historique DVF (CAGR, momentum), le DPE, l'annee de construction, et retourne 3 scenarios (pessimiste / pragmatique / optimiste) avec projections annuelles.

---

## Methode de calcul

Le moteur combine 3 niveaux d'analyse :

1. **Marche local (~80%)** — CAGR historique de la commune (donnees DVF 2020-2025), momentum 3 ans et tendance 12 mois
2. **Segment de bien (~15%)** — Appartement vs maison, tranche de surface (petit <40m², moyen 40-80m², grand >80m²)
3. **Caracteristiques propres (~5%)** — DPE (Loi Climat), annee de construction, etat copropriete

### Calcul du CAGR (regression log-lineaire ponderee)

Chaque CAGR (total, 3 ans, segment) est calcule par **regression log-lineaire ponderee** sur les medianes semestrielles :

```
log(prix_m2) = slope x t + intercept
CAGR = (exp(slope) - 1) x 100
```

- **Filtrage** : seuls les semestres avec >= 5 transactions sont inclus
- **Ponderation temporelle** : decay exponentiel (0.85/an) — un semestre d'il y a 5 ans pese ~44% d'un semestre recent
- **Robustesse** : utilise tous les points, pas juste premier/dernier — moins sensible aux valeurs aberrantes

### Formule du taux de base

```
taux_base = 0.50 x CAGR_total + 0.30 x CAGR_3ans + 0.20 x trend_12m
```

Avec mean-reversion : si `trend_12m` s'ecarte de plus de 8 points du CAGR total, il est plafonne.

### Ajustements appliques au taux

| Facteur | Valeurs possibles | Impact annuel |
|---------|-------------------|---------------|
| **DPE** | A: +0.5%, B: +0.3%, C: +0.1%, D: 0%, E: -0.15%, F: -0.4%, G: -0.8% | Loi Climat & Resilience |
| **Construction** | avant 1850: +0.15%, 1850-1913: +0.1%, 1914-1947: 0%, 1948-1969: -0.05%, 1970-1989: -0.05%, 1990-2005: 0%, apres 2005: +0.1% | Prime patrimoniale / depreciation beton |
| **Copropriete** | saine: +0.1%, correcte: 0%, en_difficulte: -0.3% | Impact sur valeur future |
| **Zone tendue** | true: +0.3% | Pression haussiere demande locative |
| **Travaux** | proportionnel au ratio travaux/prix (max +0.5%) | Amelioration DPE post-travaux |

### Scenarios

L'ecart entre scenarios est base sur la volatilite historique (coefficient de variation = stddev/median) :

```
spread = max(1.5 x CV x |taux_final|, 1.5 pp)
pessimiste = taux_final - spread
optimiste  = taux_final + spread
```

---

## Parametres de la requete

### Obligatoires

| Parametre | Type | Contraintes | Description |
|-----------|------|-------------|-------------|
| `address` | string | min 3 caracteres | Adresse du bien (geocodee via API Geoplateforme) |
| `type_bien` | string | `appartement`, `maison`, `duplex`, `triplex`, `loft`, `hotel_particulier` | Type de bien immobilier |
| `surface` | float | > 0 | Surface habitable en m² |
| `prix_achat` | float | > 0 | Prix d'achat du bien en euros |

### Fortement recommandes

| Parametre | Type | Contraintes | Description |
|-----------|------|-------------|-------------|
| `postcode` | string? | — | Code postal (aide le geocodeur a desambiguer) |
| `dpe_classe` | string? | `A` a `G` (case insensitive) | Classe energetique DPE |
| `nb_pieces` | int? | >= 1 | Nombre de pieces |
| `annee_construction` | int? | 1500-2030 | Annee de construction du batiment |
| `condition` | string? | `a_renover`, `standard`, `bon_etat`, `refait_neuf` | Etat general du bien |
| `usage_prevu` | string? | `residence_principale`, `investissement_locatif`, `residence_secondaire` | Usage prevu de l'achat |

### Affinent le taux d'appreciation

| Parametre | Type | Contraintes | Description |
|-----------|------|-------------|-------------|
| `dpe_valeur` | float? | >= 0 | Valeur DPE en kWh/m²/an (plus precis que la lettre) |
| `ges_classe` | string? | `A` a `G` | Classe GES (emissions CO2) |
| `type_chauffage` | string? | `individuel_elec`, `individuel_gaz`, `collectif_gaz`, `pac`, `autre` | Type de chauffage |
| `nb_chambres` | int? | >= 0 | Nombre de chambres |
| `etat_copropriete` | string? | `saine`, `correcte`, `en_difficulte` | Sante financiere de la copropriete |
| `charges_copro_mensuelles` | float? | >= 0 | Charges de copropriete mensuelles en euros |
| `zone_tendue` | bool? | — | Bien situe en zone tendue (forte demande locative) |
| `travaux_prevus` | float? | >= 0 | Budget travaux prevu en euros |
| `surface_terrain` | float? | > 0 | Surface du terrain en m² (maisons uniquement) |

### Affinent le prix de depart (projections)

| Parametre | Type | Contraintes | Description |
|-----------|------|-------------|-------------|
| `etage` | int? | — | Etage du bien (0 = RDC) |
| `nb_etages_immeuble` | int? | >= 1 | Nombre total d'etages de l'immeuble |
| `ascenseur` | bool? | — | Presence d'un ascenseur |
| `balcon` | bool? | — | Presence d'un balcon |
| `terrasse` | bool? | — | Presence d'une terrasse |
| `surface_exterieur` | float? | >= 0 | Surface exterieure totale (balcon + terrasse) en m² |
| `cave` | bool? | — | Presence d'une cave |
| `parking` | bool? | — | Presence d'un parking |
| `nb_parkings` | int? | >= 0 | Nombre de places de parking |
| `orientation` | string? | `nord`, `sud`, `est`, `ouest`, `sud_est`, `sud_ouest`, `nord_est`, `nord_ouest` | Orientation principale |
| `vue` | string? | `vis_a_vis`, `degagee`, `exceptionnelle` | Type de vue |
| `luminosite` | string? | `sombre`, `standard`, `lumineux`, `double_exposition` | Niveau de luminosite |
| `qualite_prestations` | string? | `inferieure`, `standard`, `superieure` | Qualite des finitions |
| `type_immeuble` | string? | `haussmannien`, `pierre_taille`, `residence_recente`, `tour_70s`, `autre` | Type d'immeuble |
| `ravalement_recent` | bool? | — | Ravalement de facade recent |
| `loyer_mensuel_estime` | float? | >= 0 | Loyer mensuel estime en euros |

### Parametres financiers

| Parametre | Type | Defaut | Contraintes | Description |
|-----------|------|--------|-------------|-------------|
| `horizon_annees` | int | 5 | 1-30 | Horizon de projection en annees |
| `taux_inflation` | float | 2.0 | 0-20 | Taux d'inflation annuel estime en % |

---

## Exemple de requete

### Requete minimale

```json
{
  "address": "15 rue Oberkampf, Paris",
  "type_bien": "appartement",
  "surface": 55,
  "prix_achat": 450000
}
```

### Requete complete

```json
{
  "address": "15 rue Oberkampf, Paris",
  "type_bien": "appartement",
  "surface": 55,
  "prix_achat": 450000,

  "postcode": "75011",
  "dpe_classe": "D",
  "nb_pieces": 3,
  "annee_construction": 1920,
  "condition": "bon_etat",
  "usage_prevu": "investissement_locatif",

  "dpe_valeur": 230,
  "ges_classe": "C",
  "type_chauffage": "collectif_gaz",
  "nb_chambres": 2,
  "etat_copropriete": "saine",
  "charges_copro_mensuelles": 180,
  "zone_tendue": true,
  "travaux_prevus": 0,

  "etage": 3,
  "nb_etages_immeuble": 6,
  "ascenseur": true,
  "balcon": true,
  "terrasse": false,
  "surface_exterieur": 5.0,
  "cave": true,
  "parking": false,
  "nb_parkings": 0,
  "orientation": "sud_est",
  "vue": "degagee",
  "luminosite": "double_exposition",
  "qualite_prestations": "superieure",
  "type_immeuble": "haussmannien",
  "ravalement_recent": true,
  "loyer_mensuel_estime": 1200,

  "horizon_annees": 5,
  "taux_inflation": 2.0
}
```

---

## Reponse

### Structure

```json
{
  "status": "ok",
  "error_detail": null,
  "geocoding": { ... },
  "historique": { ... },
  "appreciation": { ... },
  "projection": { ... },
  "risques": [ ... ],
  "confidence": { ... }
}
```

### Statuts possibles

| Statut | Description |
|--------|-------------|
| `ok` | Calcul reussi |
| `geocoding_failed` | Adresse introuvable via le geocodeur |
| `error` | Erreur interne |

### Section `geocoding`

| Champ | Type | Description |
|-------|------|-------------|
| `commune` | string | Nom de la commune |
| `code_commune` | string | Code INSEE (ex: `75111` pour Paris 11e) |
| `departement` | string | Code departement (ex: `75`) |

### Section `historique`

| Champ | Type | Description |
|-------|------|-------------|
| `cagr_total_pct` | float? | CAGR total sur toute la periode (%) |
| `cagr_3ans_pct` | float? | CAGR sur les 3 dernieres annees (%) |
| `trend_12m_pct` | float? | Tendance sur les 12 derniers mois (%) |
| `periode_analyse` | string | Periode d'analyse (ex: `"2020-S2 a 2025-S1"`) |
| `nb_semestres` | int | Nombre de semestres de donnees |
| `source` | string | `"commune"` ou `"departement"` (fallback) |
| `benchmark_departement` | object? | Comparaison avec la moyenne du departement |
| `benchmark_departement.cagr_dept_pct` | float | CAGR du departement (%) |
| `benchmark_departement.surperformance_pct` | float | Ecart commune vs departement (pp) |
| `segment_surface` | object? | Performance du segment de surface |
| `segment_surface.tranche` | string | `"petit"`, `"moyen"`, `"grand"` |
| `segment_surface.label` | string | Label lisible (ex: `"moyen (40-80 m²)"`) |
| `segment_surface.cagr_segment_pct` | float? | CAGR du segment dans la commune (%) |
| `volatilite` | object | Volatilite du marche local |
| `volatilite.coefficient_variation` | float? | Coefficient de variation (stddev/median) |
| `volatilite.classification` | string | `"stable"` (<0.15), `"modere"` (0.15-0.30), `"volatile"` (>0.30) |
| `volume` | object | Volume transactionnel |
| `volume.total_transactions` | int | Total historique de transactions |
| `volume.last_12m_transactions` | int | Transactions sur les 12 derniers mois |
| `volume.tendance_volume` | string | `"en_hausse"`, `"stable"`, `"en_baisse"` |

### Section `appreciation`

| Champ | Type | Description |
|-------|------|-------------|
| `taux_annuel_estime_pct` | float | Taux de base avant ajustements (%) |
| `ajustements` | dict | Ajustements appliques (cle: facteur, valeur: impact en pp) |
| `taux_final_pct` | float | Taux apres tous les ajustements (%) |
| `methode` | string | Methode utilisee (`"weighted_loglinear_regression"`) |
| `scenarios` | dict | 3 scenarios : `pessimiste`, `pragmatique`, `optimiste` |
| `scenarios.*.taux_pct` | float | Taux du scenario (%) |
| `scenarios.*.label` | string | Description du scenario |

### Section `projection`

| Champ | Type | Description |
|-------|------|-------------|
| `prix_achat` | float | Prix d'achat initial (euros) |
| `horizon_annees` | int | Horizon de projection |
| `taux_inflation_pct` | float | Taux d'inflation utilise (%) |
| `annees` | array | Projection annee par annee |
| `annees[].annee` | int | Numero de l'annee (1 a N) |
| `annees[].pessimiste` | float | Valeur estimee scenario pessimiste (euros) |
| `annees[].pragmatique` | float | Valeur estimee scenario pragmatique (euros) |
| `annees[].optimiste` | float | Valeur estimee scenario optimiste (euros) |
| `plus_value_estimee` | dict | Plus-value a l'horizon par scenario (euros) |
| `rendement_annualise_nominal_pct` | dict | Rendement nominal par scenario (%) |
| `rendement_annualise_reel_pct` | dict | Rendement reel (hors inflation) par scenario (%) |

### Section `risques`

Tableau de facteurs de risque identifies :

| Champ | Type | Description |
|-------|------|-------------|
| `facteur` | string | `"dpe"`, `"volatilite"`, `"liquidite"` |
| `impact` | string | `"positif"`, `"neutre"`, `"faible"`, `"modere"`, `"eleve"` |
| `detail` | string | Explication detaillee du risque |

### Section `confidence`

| Champ | Type | Description |
|-------|------|-------------|
| `level` | string | `"high"` (>=70), `"medium"` (40-69), `"low"` (<40) |
| `score` | int | Score de confiance (0-100) |
| `detail` | string | Facteurs pris en compte |

Le score de confiance est calcule a partir de :
- Nombre de semestres d'historique (max 30 pts)
- Volume total de transactions (max 25 pts)
- Transactions sur 12 mois (max 20 pts)
- Faible volatilite (max 15 pts)
- Source communale vs departement (10 pts)

---

## Exemple de reponse complete

```json
{
  "status": "ok",
  "error_detail": null,
  "geocoding": {
    "commune": "Paris",
    "code_commune": "75111",
    "departement": "75"
  },
  "historique": {
    "cagr_total_pct": -2.72,
    "cagr_3ans_pct": -3.04,
    "trend_12m_pct": -1.43,
    "periode_analyse": "2020-S2 a 2025-S1",
    "nb_semestres": 10,
    "source": "commune",
    "benchmark_departement": {
      "cagr_dept_pct": -2.85,
      "surperformance_pct": 0.13
    },
    "segment_surface": {
      "tranche": "moyen",
      "label": "moyen (40-80 m\u00b2)",
      "cagr_segment_pct": -2.31
    },
    "volatilite": {
      "coefficient_variation": 0.202,
      "classification": "modere"
    },
    "volume": {
      "total_transactions": 11436,
      "last_12m_transactions": 1813,
      "tendance_volume": "en_baisse"
    }
  },
  "appreciation": {
    "taux_annuel_estime_pct": -2.56,
    "ajustements": {
      "construction": -0.05
    },
    "taux_final_pct": -2.61,
    "methode": "weighted_loglinear_regression",
    "scenarios": {
      "pessimiste": {
        "taux_pct": -4.1,
        "label": "Marche en ralentissement"
      },
      "pragmatique": {
        "taux_pct": -2.61,
        "label": "Tendance historique maintenue"
      },
      "optimiste": {
        "taux_pct": -1.1,
        "label": "Acceleration du marche"
      }
    }
  },
  "projection": {
    "prix_achat": 450000.0,
    "horizon_annees": 5,
    "taux_inflation_pct": 2.0,
    "annees": [
      { "annee": 1, "pessimiste": 431550, "pragmatique": 438255, "optimiste": 445050 },
      { "annee": 2, "pessimiste": 413856, "pragmatique": 426817, "optimiste": 440154 },
      { "annee": 3, "pessimiste": 396888, "pragmatique": 415677, "optimiste": 435313 },
      { "annee": 4, "pessimiste": 380616, "pragmatique": 404827, "optimiste": 430524 },
      { "annee": 5, "pessimiste": 365011, "pragmatique": 394261, "optimiste": 425789 }
    ],
    "plus_value_estimee": {
      "pessimiste": -84989,
      "pragmatique": -55739,
      "optimiste": -24211
    },
    "rendement_annualise_nominal_pct": {
      "pessimiste": -4.1,
      "pragmatique": -2.61,
      "optimiste": -1.1
    },
    "rendement_annualise_reel_pct": {
      "pessimiste": -6.1,
      "pragmatique": -4.6,
      "optimiste": -3.1
    }
  },
  "risques": [
    {
      "facteur": "dpe",
      "impact": "neutre",
      "detail": "DPE D \u2014 pas de contrainte reglementaire a court terme"
    },
    {
      "facteur": "volatilite",
      "impact": "modere",
      "detail": "CV 0.20 \u2014 volatilite moderee"
    },
    {
      "facteur": "liquidite",
      "impact": "faible",
      "detail": "1813 transactions/an \u2014 marche liquide"
    }
  ],
  "confidence": {
    "level": "high",
    "score": 90,
    "detail": "10 semestres d'historique, 11436 transactions historiques, donnees communales"
  }
}
```

---

## Codes d'erreur HTTP

| Code | Cas |
|------|-----|
| `200` | Succes (verifier `status` dans le body pour les erreurs metier) |
| `422` | Parametres invalides (champs obligatoires manquants, valeurs hors bornes) |
| `500` | Erreur interne serveur |

---

## Notes

- **Couverture geographique** : IDF (75, 77, 78, 91, 92, 93, 94, 95) + Bouches-du-Rhone (13)
- **Periode historique** : 2020-2025 (donnees DVF Etalab)
- **Fallback** : si les donnees communales sont insuffisantes (<2 semestres), le calcul utilise les donnees departementales
- **Paris / Marseille** : les arrondissements sont traites individuellement (codes INSEE 75101-75120, 13201-13216)
- **DPE et Loi Climat** : les ajustements refletent l'impact reglementaire de la Loi Climat & Resilience (G interdit location 2025, F en 2028, E en 2034)
- **Donnees source** : 796 620 transactions reelles issues du fichier DVF (Demandes de Valeurs Foncieres) publie par Etalab
