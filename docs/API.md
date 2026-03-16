# STTA-DVF API - Documentation Complète

> API REST d'estimation immobilière basée sur les données DVF (Demandes de Valeurs Foncières).
> Version 1.0.0

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Démarrage rapide](#2-démarrage-rapide)
3. [Endpoints](#3-endpoints)
   - [GET /api/v1/health](#31-get-apiv1health)
   - [GET /api/v1/defaults](#32-get-apiv1defaults)
   - [POST /api/v1/estimate](#33-post-apiv1estimate)
4. [Requête d'estimation — Paramètres](#4-requête-destimation--paramètres)
5. [Réponse d'estimation — Sections](#5-réponse-destimation--sections)
   - [geocoding](#51-geocoding)
   - [estimation](#52-estimation)
   - [adjustments](#53-adjustments)
   - [zone_stats](#54-zone_stats)
   - [evolution](#55-evolution)
   - [comparables](#56-comparables)
6. [Filtre `include`](#6-filtre-include)
7. [Configuration avancée](#7-configuration-avancée)
   - [Zones concentriques](#71-zones-concentriques-zone_config)
   - [Surcharges de coefficients](#72-surcharges-de-coefficients-coefficient_overrides)
8. [Codes d'erreur](#8-codes-derreur)
9. [Déploiement (Railway)](#9-déploiement-railway)
10. [Architecture et flux de données](#10-architecture-et-flux-de-données)
11. [Coefficients par défaut](#11-coefficients-par-défaut)
12. [Exemples complets](#12-exemples-complets)

---

## 1. Vue d'ensemble

L'API STTA-DVF fournit une estimation immobilière basée sur :

- **796 620 transactions** DVF géolocalisées (2020-2025)
- **Couverture** : Île-de-France (75, 77, 78, 91, 92, 93, 94, 95) + Bouches-du-Rhône (13)
- **Recherche multi-zones concentriques** avec médiane pondérée
- **6 dimensions d'ajustement** heuristique (type, étage, caractéristiques, état, qualité, construction)
- **Coefficients admin surchargeables** pour personnalisation fine
- **Données historiques** semestrielles + mensuelles avec médiane glissante 6 mois

**Un seul endpoint POST** retourne toutes les données nécessaires pour n'importe quel frontend.

### Stack technique

| Composant | Technologie |
|-----------|-------------|
| API | FastAPI + Pydantic v2 |
| Base de données | PostgreSQL + PostGIS (Supabase) |
| Géocodage | API Géoplateforme (IGN) |
| Conteneur | Docker (python:3.12-slim) |

---

## 2. Démarrage rapide

### Installation locale

```bash
pip install -r requirements-api.txt
```

### Variables d'environnement

```bash
# .env
DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require
ALLOWED_ORIGINS=*    # Origines CORS (séparées par virgules)
```

### Lancement

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

### Documentation interactive

Une fois lancée, la documentation Swagger/OpenAPI est disponible à :

- **Swagger UI** : `https://stta-dvf-production-c7bc.up.railway.app/docs`
- **ReDoc** : `https://stta-dvf-production-c7bc.up.railway.app/redoc`
- **OpenAPI JSON** : `https://stta-dvf-production-c7bc.up.railway.app/openapi.json`

### Premier appel

```bash
curl -X POST https://stta-dvf-production-c7bc.up.railway.app/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{"address": "25 avenue des Champs-Elysées, Paris", "property_type": "appartement", "surface": 50}'
```

---

## 3. Endpoints

| Méthode | URL | Description |
|---------|-----|-------------|
| `GET` | `/` | Redirige vers `/docs` (Swagger UI) |
| `GET` | `/api/v1/health` | Health check (DB + PostGIS) |
| `GET` | `/api/v1/defaults` | Coefficients par défaut |
| `POST` | `/api/v1/estimate` | Estimation complète |

### 3.1 GET /api/v1/health

Vérifie la connexion à la base de données et PostGIS.

**Réponse** :

```json
{
  "status": "ok",
  "database": "connected",
  "postgis_version": "3.3 USE_GEOS=1 USE_PROJ=1 USE_STATS=1",
  "transactions_count": 796620
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` ou `"error"` |
| `database` | string | `"connected"` ou message d'erreur |
| `postgis_version` | string\|null | Version PostGIS installée |
| `transactions_count` | int\|null | Nombre total de transactions en base |

---

### 3.2 GET /api/v1/defaults

Retourne tous les coefficients par défaut utilisés pour les ajustements. Utile pour pré-remplir les sliders d'un panneau d'administration frontend.

**Réponse** : voir [Section 11 — Coefficients par défaut](#11-coefficients-par-défaut).

---

### 3.3 POST /api/v1/estimate

**Endpoint principal.** Prend les paramètres du bien et retourne l'estimation complète.

- **Content-Type** : `application/json`
- **Réponse** : toujours HTTP 200 avec un champ `status` indiquant le résultat
- **Validation** : HTTP 422 si les paramètres sont invalides

---

## 4. Requête d'estimation — Paramètres

### Paramètres obligatoires

| Paramètre | Type | Description |
|-----------|------|-------------|
| `address` | string | Adresse complète (min. 3 caractères) |
| `property_type` | string | Type de bien (voir valeurs ci-dessous) |
| `surface` | float | Surface en m² (> 0) |

**Valeurs de `property_type`** :

| Valeur | Description | Coef. par défaut |
|--------|-------------|-----------------|
| `appartement` | Appartement standard | 1.00 |
| `maison` | Maison individuelle | 1.00 |
| `duplex` | Duplex | 1.05 (+5%) |
| `triplex` | Triplex | 1.08 (+8%) |
| `loft` | Loft | 1.10 (+10%) |
| `hotel_particulier` | Hôtel particulier | 1.15 (+15%) |

### Paramètres optionnels — Bien

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `postcode` | string\|null | null | Code postal (aide le géocodage) |
| `nb_pieces` | int\|null | null | Nombre de pièces |
| `nb_salles_de_bain` | int\|null | null | Nombre de salles de bain |
| `etage` | int\|null | null | Étage du bien (0 = RDC) |
| `nb_etages_immeuble` | int\|null | null | Nombre d'étages de l'immeuble |

### Paramètres optionnels — Caractéristiques (booléens)

Chacun ajoute un bonus au prix si `true`. Défaut : `false`.

| Paramètre | Bonus par défaut | Description |
|-----------|-----------------|-------------|
| `ascenseur` | +3% | Ascenseur dans l'immeuble |
| `balcon` | +2% | Balcon |
| `terrasse` | +4% | Terrasse |
| `cave` | +1% | Cave |
| `parking` | +3% | Place de parking |
| `chambre_service` | +1% | Chambre de service |
| `vue_exceptionnelle` | +6% | Vue exceptionnelle |
| `parties_communes_renovees` | +2% | Parties communes rénovées |
| `ravalement_recent` | +1% | Ravalement récent |

### Paramètres optionnels — Qualité / État / Construction

| Paramètre | Type | Défaut | Valeurs possibles |
|-----------|------|--------|-------------------|
| `condition` | string | `"standard"` | `"a_renover"` (-15%), `"standard"` (0%), `"bon_etat"` (+5%), `"refait_a_neuf"` (+12%) |
| `quality` | string | `"comparable"` | `"inferieure"` (-10%), `"comparable"` (0%), `"superieure"` (+10%) |
| `construction_period` | string | `"unknown"` | `"avant_1850"` (+2%), `"1850_1913"` (+3%), `"1914_1947"` (-2%), `"1948_1969"` (-5%), `"1970_1989"` (-3%), `"1990_2005"` (0%), `"apres_2005"` (+4%), `"unknown"` (0%) |

### Paramètres optionnels — Configuration avancée

| Paramètre | Type | Description |
|-----------|------|-------------|
| `zone_config` | object\|null | Configuration des zones concentriques (voir [7.1](#71-zones-concentriques-zone_config)) |
| `coefficient_overrides` | object\|null | Surcharges des coefficients (voir [7.2](#72-surcharges-de-coefficients-coefficient_overrides)) |
| `include` | list\|null | Sections à inclure dans la réponse (voir [6](#6-filtre-include)) |

---

## 5. Réponse d'estimation — Sections

La réponse contient un `status` et 6 sections optionnelles.

```json
{
  "status": "ok",
  "geocoding": { ... },
  "estimation": { ... },
  "adjustments": { ... },
  "zone_stats": { ... },
  "evolution": { ... },
  "comparables": { ... }
}
```

**Valeurs de `status`** :

| Valeur | Description |
|--------|-------------|
| `"ok"` | Estimation réussie, toutes les sections demandées sont remplies |
| `"geocoding_failed"` | L'adresse n'a pas pu être géocodée, aucune section disponible |
| `"no_data"` | Adresse géocodée mais aucun comparable trouvé dans la zone |

---

### 5.1 geocoding

Résultat du géocodage de l'adresse via l'API Géoplateforme (IGN).

```json
{
  "label": "25 Avenue des Champs-Élysées 75008 Paris",
  "score": 0.93,
  "latitude": 48.870762,
  "longitude": 2.306773,
  "citycode": "75108",
  "city": "Paris 8e Arrondissement",
  "postcode": "75008",
  "context": "75, Paris, Île-de-France"
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `label` | string | Adresse complète normalisée |
| `score` | float | Score de confiance du géocodage (0-1) |
| `latitude` | float | Latitude WGS84 |
| `longitude` | float | Longitude WGS84 |
| `citycode` | string | Code INSEE de la commune (arrondissement pour Paris/Marseille) |
| `city` | string | Nom de la commune |
| `postcode` | string | Code postal |
| `context` | string | Contexte géographique (département, région) |

> **Note Paris/Marseille** : le `citycode` utilise les codes d'arrondissement (75101-75120 pour Paris, 13201-13216 pour Marseille), pas le code commune générique (75056 ou 13055).

**Utilisation frontend** : Marqueur de l'adresse sur la carte + affichage info.

---

### 5.2 estimation

Section principale avec le prix estimé, la confiance et le détail multi-zones.

```json
{
  "prix_m2_base": 12302.0,
  "prix_total_base": 615100.0,
  "adjustment_factor": 1.0,
  "prix_m2_ajuste": 12302.0,
  "prix_total_ajuste": 615100.0,
  "total_multiplier": 1.0,
  "confidence": {
    "level": "high",
    "label": "Confiance haute",
    "low_estimate": 492500.0,
    "high_estimate": 716200.0
  },
  "nb_comparables": 500,
  "niveau_geo": "zone 1 (0-1.0 km): 500",
  "zone_breakdown": {
    "1": { "count": 205, "median_prix_m2": 12850.56, "effective_weight": 0.6667 },
    "2": { "count": 295, "median_prix_m2": 11340.02, "effective_weight": 0.3333 },
    "3": { "count": 0, "median_prix_m2": null, "effective_weight": 0.0 }
  },
  "zone_config": {
    "radius_1_km": 1.0,
    "radius_2_km": 2.0,
    "radius_3_km": 3.0,
    "weight_1": 0.6,
    "weight_2": 0.3,
    "weight_3": 0.1
  }
}
```

#### Champs prix

| Champ | Type | Description |
|-------|------|-------------|
| `prix_m2_base` | float | Médiane pondérée par zone × ajustement surface (EUR/m²) |
| `prix_total_base` | float | `prix_m2_base × surface` (EUR) |
| `adjustment_factor` | float | Facteur d'ajustement surface (log2, plafonné 0.8-1.2) |
| `prix_m2_ajuste` | float | `prix_m2_base × total_multiplier` (EUR/m²) |
| `prix_total_ajuste` | float | Prix final après les 6 ajustements heuristiques (EUR) |
| `total_multiplier` | float | Produit des 6 coefficients d'ajustement (plafonné 0.70-1.40) |

#### Confiance et fourchette

| Champ | Type | Description |
|-------|------|-------------|
| `confidence.level` | string | `"high"`, `"medium"` ou `"low"` |
| `confidence.label` | string | Libellé français |
| `confidence.low_estimate` | float | Fourchette basse (Q25 × surface × adjustments × multiplier) |
| `confidence.high_estimate` | float | Fourchette haute (Q75 × surface × adjustments × multiplier) |

**Règles de confiance** :

| Niveau | Conditions |
|--------|-----------|
| `high` | ≥ 30 comparables ET niveau géo ≤ 2 |
| `medium` | ≥ 10 comparables ET niveau géo ≤ 3 |
| `low` | Sinon |

#### Méta

| Champ | Type | Description |
|-------|------|-------------|
| `nb_comparables` | int | Nombre de transactions comparables utilisées |
| `niveau_geo` | string | Description du niveau de recherche géographique |

#### Multi-zones (optionnel)

| Champ | Type | Description |
|-------|------|-------------|
| `zone_breakdown` | dict\|null | Détail par zone : count, médiane, poids effectif |
| `zone_config` | object\|null | Configuration des zones utilisée (rayons + poids) |

`zone_breakdown` est `null` si la recherche n'a pas utilisé de zones (fallback commune ou département).

**Utilisation frontend** :
- **Jauge** : `low_estimate` → `prix_total_ajuste` → `high_estimate`
- **Carte** : Dessiner 3 cercles concentriques avec `zone_config.radius_*_km`
- **Indicateur** : Nombre de comparables et niveau de confiance

---

### 5.3 adjustments

Détail des 6 ajustements heuristiques appliqués au prix de base.

```json
{
  "base_price": 968736.0,
  "adjusted_price": 1295587.0,
  "total_multiplier": 1.3374,
  "details": [
    { "name": "type", "coefficient": 1.05, "explanation": "Type Duplex : +5%" },
    { "name": "floor", "coefficient": 1.02, "explanation": "Etage 5 avec ascenseur : +2%" },
    { "name": "characteristics", "coefficient": 1.06, "explanation": "Ascenseur : +3%" },
    { "name": "condition", "coefficient": 1.05, "explanation": "Balcon : +2%" },
    { "name": "quality", "coefficient": 1.1, "explanation": "Cave : +1%" },
    { "name": "construction", "coefficient": 1.02, "explanation": "Etat Bon etat : +5%" }
  ]
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `base_price` | float | Prix avant ajustements (`prix_total_base`) |
| `adjusted_price` | float | Prix après ajustements (`prix_total_ajuste`) |
| `total_multiplier` | float | Produit de tous les coefficients (plafonné 0.70-1.40) |
| `details` | list | Uniquement les ajustements actifs (coefficient ≠ 1.0) |
| `details[].name` | string | `"type"`, `"floor"`, `"characteristics"`, `"condition"`, `"quality"`, `"construction"` |
| `details[].coefficient` | float | Multiplicateur appliqué (ex: 1.05 = +5%) |
| `details[].explanation` | string | Explication en français |

**Les 6 dimensions d'ajustement** :

| Dimension | Source | Description |
|-----------|--------|-------------|
| `type` | `property_type` | Bonus pour duplex, triplex, loft, hôtel particulier |
| `floor` | `etage`, `ascenseur`, `nb_etages_immeuble` | RDC -7%, étage élevé +/- selon ascenseur, dernier étage +3% |
| `characteristics` | 9 booléens | Somme des bonus (ascenseur +3%, terrasse +4%, etc.) |
| `condition` | `condition` | État du bien (à rénover -15% → refait à neuf +12%) |
| `quality` | `quality` | Qualité relative (inférieure -10% → supérieure +10%) |
| `construction` | `construction_period` | Période de construction (1948-1969 -5% → après 2005 +4%) |

**Utilisation frontend** : Barres horizontales montrant chaque ajustement et son impact sur le prix.

---

### 5.4 zone_stats

Statistiques agrégées de la zone (commune) depuis `mart.zone_stats`.

```json
{
  "total_transactions": 4687,
  "last_12m_transactions": 691,
  "median_prix_m2_12m": 3719.51,
  "stddev_prix_m2_12m": 1524.8,
  "trend_12m": -0.25,
  "data_quality_flag": "good"
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `total_transactions` | int | Total des transactions dans la commune (toutes années) |
| `last_12m_transactions` | int | Transactions des 12 derniers mois |
| `median_prix_m2_12m` | float\|null | Médiane prix/m² sur 12 mois |
| `stddev_prix_m2_12m` | float\|null | Écart-type prix/m² sur 12 mois |
| `trend_12m` | float\|null | Tendance 12 mois en % (positif = hausse) |
| `data_quality_flag` | string | `"good"` (≥ 30 tx/12m), `"moderate"` (10-29), `"sparse"` (< 10) |

**Utilisation frontend** : Indicateurs de marché, badge qualité des données, flèche tendance.

---

### 5.5 evolution

Données d'évolution historique : semestrielle + mensuelle.

```json
{
  "source": "commune",
  "semester": [
    {
      "annee": 2020, "semestre": 2,
      "nb_transactions": 257, "median_prix_m2": 12586.21,
      "q1_prix_m2": 10200.0, "q3_prix_m2": 14800.0
    },
    ...
  ],
  "monthly": [
    {
      "annee_mois": "2020-07",
      "nb_transactions": 50, "median_prix_m2": 12400.0,
      "rolling_median_6m": null
    },
    {
      "annee_mois": "2025-06",
      "nb_transactions": 30, "median_prix_m2": 11800.0,
      "rolling_median_6m": 11840.62
    },
    ...
  ]
}
```

#### Champ `source`

| Valeur | Signification |
|--------|---------------|
| `"commune"` | Données au niveau de la commune (suffisamment de transactions) |
| `"departement"` | Fallback au département (< 2 semestres de données communales) |

#### Données semestrielles (`semester`)

| Champ | Type | Description |
|-------|------|-------------|
| `annee` | int | Année |
| `semestre` | int | 1 ou 2 |
| `nb_transactions` | int | Nombre de transactions du semestre |
| `median_prix_m2` | float | Médiane du prix au m² |
| `q1_prix_m2` | float\|null | 1er quartile (Q25) |
| `q3_prix_m2` | float\|null | 3ème quartile (Q75) |

#### Données mensuelles (`monthly`)

| Champ | Type | Description |
|-------|------|-------------|
| `annee_mois` | string | Format `"YYYY-MM"` |
| `nb_transactions` | int | Nombre de transactions du mois |
| `median_prix_m2` | float | Médiane du prix au m² |
| `rolling_median_6m` | float\|null | Médiane glissante sur 6 mois |

**Utilisation frontend** :
- **Graphique semestriel** : Barres avec Q1/médiane/Q3 (box plot simplifié)
- **Graphique mensuel** : Courbe médiane + courbe lissée (rolling 6m)

---

### 5.6 comparables

Liste complète des transactions comparables utilisées pour l'estimation.

```json
{
  "count": 500,
  "items": [
    {
      "id_mutation": "2024-74523",
      "date_mutation": "2024-06-15",
      "valeur_fonciere": 485000.0,
      "type_bien": "Appartement",
      "surface": 42.0,
      "nb_pieces": 2,
      "prix_m2": 11547.62,
      "code_commune": "75108",
      "nom_commune": "Paris 8e Arrondissement",
      "code_departement": "75",
      "latitude": 48.8712,
      "longitude": 2.3089,
      "distance_m": 245.7,
      "zone": 1
    },
    ...
  ]
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `count` | int | Nombre total de comparables |
| `items[].id_mutation` | string | Identifiant unique de la mutation DVF |
| `items[].date_mutation` | string | Date de la vente |
| `items[].valeur_fonciere` | float | Prix de vente (EUR) |
| `items[].type_bien` | string | Type de bien DVF |
| `items[].surface` | float | Surface en m² |
| `items[].nb_pieces` | int\|null | Nombre de pièces |
| `items[].prix_m2` | float | Prix au m² |
| `items[].code_commune` | string | Code INSEE de la commune |
| `items[].nom_commune` | string | Nom de la commune |
| `items[].code_departement` | string | Code département |
| `items[].latitude` | float\|null | Latitude WGS84 |
| `items[].longitude` | float\|null | Longitude WGS84 |
| `items[].distance_m` | float\|null | Distance au point géocodé (mètres) |
| `items[].zone` | int\|null | Zone concentrique (1, 2 ou 3) — null si pas de multi-zones |

**Utilisation frontend** :
- **Carte** : Marqueurs colorés par zone (1=vert, 2=orange, 3=rouge)
- **Scatter plot** : `prix_m2` vs `surface`, couleur par zone
- **Tableau** : Liste triable/filtrable des transactions

---

## 6. Filtre `include`

Le paramètre `include` permet de ne recevoir que les sections souhaitées, réduisant la taille de la réponse.

```json
{ "include": ["estimation", "comparables"] }
```

**Sections disponibles** :

| Section | Description | Taille typique |
|---------|-------------|----------------|
| `geocoding` | Résultat géocodage | ~200 octets |
| `estimation` | Prix + confiance + zones | ~500 octets |
| `adjustments` | Détail des ajustements | ~400 octets |
| `zone_stats` | Statistiques de marché | ~150 octets |
| `evolution` | Historique semestriel + mensuel | ~5 Ko |
| `comparables` | Liste des transactions | ~100-300 Ko |

**Si `include` est `null` ou absent** : toutes les 6 sections sont retournées.

**Exemples d'usage** :

| Cas d'usage | Sections recommandées |
|-------------|----------------------|
| Résultat principal | `["estimation", "adjustments", "geocoding"]` |
| Carte uniquement | `["geocoding", "comparables"]` |
| Graphique évolution | `["evolution"]` |
| Tout (page complète) | `null` (ou ne pas envoyer `include`) |

---

## 7. Configuration avancée

### 7.1 Zones concentriques (`zone_config`)

L'estimation utilise 3 zones concentriques autour de l'adresse. Chaque zone a un rayon et un poids pour le calcul de la médiane pondérée.

```json
{
  "zone_config": {
    "radius_1_km": 0.5,
    "radius_2_km": 1.5,
    "radius_3_km": 3.0,
    "weight_1": 0.60,
    "weight_2": 0.30,
    "weight_3": 0.10
  }
}
```

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `radius_1_km` | 1.0 | Rayon zone 1 (km) — comparables les plus proches |
| `radius_2_km` | 2.0 | Rayon zone 2 (km) |
| `radius_3_km` | 3.0 | Rayon zone 3 (km) — comparables les plus éloignés |
| `weight_1` | 0.60 | Poids zone 1 dans la médiane pondérée |
| `weight_2` | 0.30 | Poids zone 2 |
| `weight_3` | 0.10 | Poids zone 3 |

**Comment ça marche** : Si les 3 zones ont des comparables, la médiane finale est :

```
médiane = median_zone1 × w1_eff + median_zone2 × w2_eff + median_zone3 × w3_eff
```

Les poids effectifs (`effective_weight`) sont redistribués proportionnellement si une zone est vide. Par exemple, si zone 3 est vide, ses 10% sont redistribués entre zone 1 et zone 2.

**Si `zone_config` est `null`** : les valeurs par défaut (1/2/3 km, 60/30/10%) sont utilisées.

---

### 7.2 Surcharges de coefficients (`coefficient_overrides`)

Permet à un admin de surcharger les coefficients d'ajustement par défaut.

```json
{
  "coefficient_overrides": {
    "type_coefficients": { "duplex": 1.10 },
    "quality_coefficients": { "superieure": 1.15 },
    "condition_coefficients": { "refait_a_neuf": 1.20 },
    "construction_coefficients": { "avant_1850": 1.05 },
    "characteristic_adjustments": { "balcon": 0.05, "terrasse": 0.06 },
    "floor_params": {
      "ground_floor_discount": 0.10,
      "elevator_bonus_per_floor": 0.015,
      "no_elevator_penalty_per_floor": 0.04,
      "last_floor_bonus": 0.05,
      "max_elevator_bonus": 0.08,
      "max_no_elevator_penalty": 0.15
    }
  }
}
```

| Paramètre | Type | Description |
|-----------|------|-------------|
| `type_coefficients` | dict | Multiplicateurs par type de bien (ex: `{"duplex": 1.10}`) |
| `quality_coefficients` | dict | Multiplicateurs par qualité |
| `condition_coefficients` | dict | Multiplicateurs par état |
| `construction_coefficients` | dict | Multiplicateurs par période de construction |
| `characteristic_adjustments` | dict | Bonus par caractéristique (additifs, ex: 0.05 = +5%) |
| `floor_params` | object | Paramètres d'ajustement étage |

#### Paramètres étage (`floor_params`)

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `ground_floor_discount` | 0.07 | Décote RDC (7%) |
| `elevator_bonus_per_floor` | 0.01 | Bonus par étage avec ascenseur (+1%/étage) |
| `no_elevator_penalty_per_floor` | 0.03 | Pénalité par étage sans ascenseur (-3%/étage) |
| `last_floor_bonus` | 0.03 | Bonus dernier étage (+3%) |
| `max_elevator_bonus` | 0.05 | Plafond bonus ascenseur (5%) |
| `max_no_elevator_penalty` | 0.12 | Plafond pénalité sans ascenseur (12%) |

---

## 8. Codes d'erreur

| HTTP | Status | Description |
|------|--------|-------------|
| 200 | `"ok"` | Estimation réussie |
| 200 | `"geocoding_failed"` | Adresse non trouvée — toutes les sections sont `null` |
| 200 | `"no_data"` | Adresse géocodée mais aucun comparable — seul `geocoding` peut être rempli |
| 422 | — | Validation Pydantic échouée (champs manquants, types invalides, `surface ≤ 0`, etc.) |
| 500 | — | Erreur interne (détail dans `{"detail": "..."}`) |

---

## 9. Déploiement (Railway)

Le projet est déployé en **2 services Railway** depuis le même repo GitHub :

| Service | Dockerfile | URL de production |
|---------|-----------|-------------------|
| **API** | `Dockerfile` | [stta-dvf-production-c7bc.up.railway.app](https://stta-dvf-production-c7bc.up.railway.app) |
| **Frontend** | `Dockerfile.streamlit` | Domaine Railway séparé |

### Variables d'environnement

| Variable | Requis | Description |
|----------|--------|-------------|
| `DATABASE_URL` | Oui | URL de connexion PostgreSQL (avec `?sslmode=require` pour Supabase) |
| `ALLOWED_ORIGINS` | Non | Origines CORS autorisées, séparées par virgules (défaut: `*`) |
| `PORT` | Non | Injecté automatiquement par Railway |

### Configuration Railway

- **Health Check Path** : `/api/v1/health`
- **Port** : auto-détecté (ne pas configurer manuellement)

### Build & Run local

```bash
# API
docker build -t stta-dvf-api .
docker run --env-file .env -p 8000:8000 stta-dvf-api

# Frontend
docker build -f Dockerfile.streamlit -t stta-dvf-front .
docker run --env-file .env -p 8501:8501 stta-dvf-front
```

### Performance

Chaque requête d'estimation prend environ :

| Étape | Durée typique |
|-------|---------------|
| Géocodage (API IGN) | ~200-500 ms |
| Requête comparables (PostGIS) | ~300-800 ms |
| Calculs (médiane, ajustements, confiance) | ~10-50 ms |
| Requêtes évolution (2 queries SQL) | ~100-300 ms |
| **Total** | **~0.6 - 1.5 s** |

---

## 10. Architecture et flux de données

```
                     ┌─────────────────────────────────────────────────┐
                     │              POST /api/v1/estimate              │
                     └───────────────────┬─────────────────────────────┘
                                         │
                                         ▼
                              ┌──────────────────────┐
                              │   1. Géocodage        │
                              │   (API Géoplateforme) │
                              └──────────┬───────────┘
                                         │ lat, lon, citycode
                                         ▼
                              ┌──────────────────────┐
                              │   2. Comparables      │
                              │   (PostGIS ST_Distance│
                              │    multi-zones)       │
                              └──────────┬───────────┘
                                         │ DataFrame (500 max)
                                         ▼
                    ┌────────────────────────────────────────┐
                    │   3. Calcul estimation                  │
                    │                                        │
                    │  ┌─ Médiane pondérée par zone          │
                    │  ├─ Ajustement surface (log2)          │
                    │  ├─ 6 ajustements heuristiques         │
                    │  ├─ Confiance (high/medium/low)        │
                    │  └─ Fourchette (Q25-Q75 × multiplier)  │
                    └────────────────┬───────────────────────┘
                                     │
                    ┌────────────────┼───────────────────────┐
                    │                │                       │
                    ▼                ▼                       ▼
          ┌─────────────┐  ┌─────────────────┐   ┌──────────────────┐
          │ Zone Stats   │  │ Evolution       │   │ Assemblage       │
          │ (mart.       │  │ (mart.stats_*   │   │ réponse JSON     │
          │  zone_stats) │  │  + indices_     │   │ (6 sections)     │
          │              │  │  temporels)     │   │                  │
          └──────────────┘  └─────────────────┘   └──────────────────┘
```

### Base de données

```
┌─────────────────────────────────────────────────┐
│  PostgreSQL + PostGIS (Supabase)                │
│                                                 │
│  core.transactions     (796 620 rows, ~230 MB)  │
│    ├─ id_mutation, date_mutation                │
│    ├─ valeur_fonciere, surface, prix_m2         │
│    ├─ code_commune, code_departement            │
│    ├─ geom (GEOMETRY Point 4326)                │
│    └─ is_outlier                                │
│                                                 │
│  mart.stats_commune    (20 764 rows)            │
│  mart.stats_departement (180 rows)              │
│  mart.zone_stats       (2 172 rows)             │
│  mart.indices_temporels (85 102 rows)           │
└─────────────────────────────────────────────────┘
```

---

## 11. Coefficients par défaut

Retournés par `GET /api/v1/defaults`. Ces valeurs sont utilisées quand aucun `coefficient_overrides` n'est fourni.

### Type de bien

| Clé | Coefficient | Description |
|-----|-------------|-------------|
| `appartement` | 1.00 | Référence |
| `maison` | 1.00 | Référence |
| `duplex` | 1.05 | +5% |
| `triplex` | 1.08 | +8% |
| `loft` | 1.10 | +10% |
| `hotel_particulier` | 1.15 | +15% |

### Qualité

| Clé | Coefficient |
|-----|-------------|
| `inferieure` | 0.90 (-10%) |
| `comparable` | 1.00 |
| `superieure` | 1.10 (+10%) |

### État

| Clé | Coefficient |
|-----|-------------|
| `a_renover` | 0.85 (-15%) |
| `standard` | 1.00 |
| `bon_etat` | 1.05 (+5%) |
| `refait_a_neuf` | 1.12 (+12%) |

### Période de construction

| Clé | Coefficient |
|-----|-------------|
| `avant_1850` | 1.02 (+2%) |
| `1850_1913` | 1.03 (+3%) |
| `1914_1947` | 0.98 (-2%) |
| `1948_1969` | 0.95 (-5%) |
| `1970_1989` | 0.97 (-3%) |
| `1990_2005` | 1.00 |
| `apres_2005` | 1.04 (+4%) |
| `unknown` | 1.00 |

### Caractéristiques (bonus additifs)

| Clé | Bonus |
|-----|-------|
| `ascenseur` | +3% |
| `balcon` | +2% |
| `terrasse` | +4% |
| `cave` | +1% |
| `parking` | +3% |
| `chambre_service` | +1% |
| `vue_exceptionnelle` | +6% |
| `parties_communes_renovees` | +2% |
| `ravalement_recent` | +1% |

### Paramètres étage

| Clé | Valeur |
|-----|--------|
| `ground_floor_discount` | 0.07 (7%) |
| `elevator_bonus_per_floor` | 0.01 (1%/étage) |
| `no_elevator_penalty_per_floor` | 0.03 (3%/étage) |
| `last_floor_bonus` | 0.03 (3%) |
| `max_elevator_bonus` | 0.05 (5%) |
| `max_no_elevator_penalty` | 0.12 (12%) |

### Zones par défaut

| Clé | Valeur |
|-----|--------|
| `radius_1_km` | 1.0 km |
| `radius_2_km` | 2.0 km |
| `radius_3_km` | 3.0 km |
| `weight_1` | 0.60 (60%) |
| `weight_2` | 0.30 (30%) |
| `weight_3` | 0.10 (10%) |

---

## 12. Exemples complets

### Estimation minimale

```bash
curl -X POST https://stta-dvf-production-c7bc.up.railway.app/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "address": "25 avenue des Champs-Elysées, Paris",
    "property_type": "appartement",
    "surface": 50
  }'
```

### Estimation avec toutes les options

```bash
curl -X POST https://stta-dvf-production-c7bc.up.railway.app/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "address": "15 rue de la Paix, Paris",
    "postcode": "75002",
    "property_type": "duplex",
    "surface": 80,
    "nb_pieces": 3,
    "nb_salles_de_bain": 2,
    "etage": 5,
    "nb_etages_immeuble": 7,
    "ascenseur": true,
    "balcon": true,
    "terrasse": false,
    "cave": true,
    "parking": true,
    "chambre_service": false,
    "vue_exceptionnelle": false,
    "parties_communes_renovees": true,
    "ravalement_recent": false,
    "condition": "bon_etat",
    "quality": "superieure",
    "construction_period": "avant_1850",
    "zone_config": {
      "radius_1_km": 0.5,
      "radius_2_km": 1.5,
      "radius_3_km": 3.0,
      "weight_1": 0.70,
      "weight_2": 0.20,
      "weight_3": 0.10
    }
  }'
```

### Estimation avec surcharges admin

```bash
curl -X POST https://stta-dvf-production-c7bc.up.railway.app/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1 avenue du Prado, Marseille",
    "postcode": "13006",
    "property_type": "appartement",
    "surface": 70,
    "condition": "refait_a_neuf",
    "quality": "superieure",
    "include": ["estimation", "adjustments"],
    "coefficient_overrides": {
      "condition_coefficients": { "refait_a_neuf": 1.20 },
      "quality_coefficients": { "superieure": 1.15 }
    }
  }'
```

### Estimation pour carte uniquement

```bash
curl -X POST https://stta-dvf-production-c7bc.up.railway.app/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1 place de la Bastille, Paris",
    "property_type": "appartement",
    "surface": 45,
    "include": ["geocoding", "comparables"]
  }'
```

### Graphique d'évolution uniquement

```bash
curl -X POST https://stta-dvf-production-c7bc.up.railway.app/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "address": "12 rue de Rivoli, Paris",
    "property_type": "appartement",
    "surface": 60,
    "include": ["evolution"]
  }'
```

---

## Annexe : Couverture géographique

| Département | Nom | Transactions |
|-------------|-----|-------------|
| 75 | Paris (20 arrondissements) | ~160 000 |
| 77 | Seine-et-Marne | ~80 000 |
| 78 | Yvelines | ~60 000 |
| 91 | Essonne | ~55 000 |
| 92 | Hauts-de-Seine | ~70 000 |
| 93 | Seine-Saint-Denis | ~55 000 |
| 94 | Val-de-Marne | ~55 000 |
| 95 | Val-d'Oise | ~50 000 |
| 13 | Bouches-du-Rhône | ~170 000 |
| **Total** | | **~796 620** |

**Période** : Juillet 2020 — Juin 2025 (5 ans)

**Source** : [Etalab DVF géolocalisées](https://files.data.gouv.fr/geo-dvf/latest/csv/)
