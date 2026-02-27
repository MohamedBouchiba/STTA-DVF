# STTA-DVF — Estimateur immobilier basé sur DVF+

Estimateur de prix immobilier "fait maison" pour la France, basé sur les données ouvertes DVF+ du Cerema. Méthode : médiane locale des transactions comparables, sans machine learning.

---

## Ce qui a été fait

### Code complet scaffoldé (50 fichiers)

| Couche | Fichiers | Description |
|--------|----------|-------------|
| **Infrastructure** | `docker-compose.yml`, `Dockerfile`, init SQL, `.env`, `config.py`, `db.py` | PostgreSQL 16 + PostGIS 3.4 via Docker, config centralisée, connexion SQLAlchemy |
| **Ingestion** | `src/ingestion/download.py`, `restore.py`, `checksum.py`, `metadata.py` | Téléchargement DVF+ avec manifest JSON, pg_restore wrapper, suivi des exécutions |
| **Transform SQL** | `sql/core/transform_staging_to_core.sql`, DDL core | Filtrage ventes résidentielles, calcul prix/m², nettoyage outliers IQR |
| **Mart SQL** | `sql/mart/refresh_marts.sql`, DDL mart | Agrégations par commune/département/semestre, stats zone, indices temporels |
| **Qualité** | `sql/quality/quality_checks.sql`, `src/transform/quality.py` | 6 contrôles qualité (comptages, distributions, couverture géo, taux outliers) |
| **Estimation** | `src/estimation/geocoder.py`, `comparables.py`, `estimator.py`, `confidence.py` | Géocodage API Geoplateforme, recherche spatiale PostGIS avec fallback 4 niveaux, médiane + ajustement surface |
| **Streamlit** | `src/app/streamlit_app.py`, 5 composants | Saisie adresse, formulaire bien, affichage prix, carte folium, stats locales |
| **CLI** | `scripts/run_pipeline.py` | Pipeline Click (check, restore, transform, mart, quality, all) |
| **Tests** | `tests/test_geocoder.py`, `test_estimator.py`, `test_quality.py` | Tests unitaires avec mocks et fixtures |

### Dépendances Python installées

`pip install -r requirements.txt` exécuté avec succès (sqlalchemy, streamlit, folium, pandas, etc.)

### Repo Git initialisé et poussé

- Remote : `https://github.com/MohamedBouchiba/STTA-DVF.git`
- Branche : `main`
- `.env` exclu du versionning (`.env.example` fourni)

---

## Ce qui reste à faire

### 1. Lancer Docker PostgreSQL/PostGIS

```bash
# Démarrer Docker Desktop d'abord, puis :
cd STTA-DVF
docker compose up -d
```

Vérifier la connexion :
```bash
python -c "from src.db import check_connection; check_connection()"
```

### 2. Télécharger les données DVF+

Télécharger manuellement les dumps depuis [Cerema Box](https://cerema.box.com/v/dvfplus-opendata) dans `data/landing/`.

Les fichiers sont au format `.backup` (un par département). Pour un pilote, commencer par `dvfplus_75.backup` (Paris).

### 3. Exécuter le pipeline (pilote Paris d'abord)

```bash
# Pilote sur un département
python scripts/run_pipeline.py all --dep 75

# Ou étape par étape :
python scripts/run_pipeline.py restore --dep 75
python scripts/run_pipeline.py transform
python scripts/run_pipeline.py mart
python scripts/run_pipeline.py quality
```

### 4. Valider les données

- Vérifier les comptages (staging vs core vs mart)
- Contrôler la distribution prix/m² sur Paris (attendu : ~8 000-15 000 EUR/m² pour les appartements)
- S'assurer que le taux d'outliers est raisonnable (~5-15%)

### 5. Charger la France entière

```bash
# Après validation du pilote, charger les 101 départements
python scripts/run_pipeline.py all
```

**Attention** : le chargement complet peut prendre plusieurs heures (30M+ lignes).

### 6. Lancer l'app Streamlit

```bash
streamlit run src/app/streamlit_app.py
```

Tester avec :
- "10 rue de Rivoli, Paris" + Appartement + 50m² → estimation ~10 000-15 000 EUR/m²
- Une adresse rurale → confiance "moderate" ou "low"

### 7. Ajustements potentiels après premiers tests

- **SQL transform** : les colonnes DVF+ exactes (`codtypbien`, `l_codinsee`, `nbapt1pp`...) peuvent varier selon la version du dump. Adapter le SQL si nécessaire après exploration du staging.
- **Filtre `codtypbien`** : confirmer que `111%` = maison seule et `121%` = appartement seul en vérifiant `staging.ann_type_local`.
- **Surface** : valider que `sbatmai`/`sbatapt` excluent bien les dépendances.
- **Géocodage** : l'URL `data.geopf.fr/geocodage/search` remplace l'ancienne API BAN. Vérifier que ça fonctionne.

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Base de données | PostgreSQL 16 + PostGIS 3.4 (Docker) |
| Backend | Python 3.12 + SQLAlchemy + pandas |
| Géocodage | API Geoplateforme (ex-BAN) |
| Frontend | Streamlit + Folium |
| Pipeline CLI | Click |
| Tests | pytest |
| Données | DVF+ Cerema (2014-2024, ~30M lignes) |

## Algorithme d'estimation

1. **Géocodage** de l'adresse → coordonnées + code INSEE
2. **Recherche de comparables** (fallback : 1km → commune → commune 48 mois → département)
3. **Médiane prix/m²** des comparables
4. **Ajustement surface** (log-linéaire, ±20% max)
5. **Intervalle de confiance** (Q25-Q75)
6. **Niveau de confiance** : haute (≥30 comparables), moyenne (≥10), faible

## Arborescence

```
STTA-DVF/
├── docker-compose.yml          # PostgreSQL + PostGIS
├── .env.example                # Configuration (copier vers .env)
├── requirements.txt            # Dépendances Python
├── docker/postgres/            # Dockerfile + init SQL
├── data/landing/               # Dumps DVF+ (gitignored)
├── sql/
│   ├── core/                   # DDL + transform staging→core
│   ├── mart/                   # DDL + agrégations
│   └── quality/                # Contrôles qualité
├── src/
│   ├── config.py + db.py       # Configuration + connexion DB
│   ├── ingestion/              # Download, restore, checksum
│   ├── transform/              # Staging→core, core→mart, qualité
│   ├── estimation/             # Géocodeur, comparables, estimateur
│   └── app/                    # Streamlit app + composants
├── scripts/run_pipeline.py     # CLI pipeline
└── tests/                      # Tests unitaires
```
