# STTA-DVF — Estimateur immobilier France

Estimateur de prix immobilier pour la France, basé sur les données ouvertes DVF (Demandes de Valeurs Foncières). Méthode : médiane pondérée multi-zones des transactions comparables + 6 ajustements heuristiques, sans machine learning.

**[App live](https://stta-dvf-production-c7bc.up.railway.app/)** | **[API Swagger](https://stta-dvf-production-c7bc.up.railway.app/docs)**

---

## Fonctionnalités

- **796 620 transactions** géolocalisées (Île-de-France + Bouches-du-Rhône, 2020-2025)
- **Recherche multi-zones concentriques** (3 rayons configurables) avec médiane pondérée
- **6 dimensions d'ajustement** : type de bien, étage, caractéristiques (9 booléens), état, qualité, période de construction
- **Coefficients admin surchargeables** pour personnalisation fine
- **Évolution historique** : semestrielle + mensuelle avec médiane glissante 6 mois
- **Carte interactive** avec comparables géolocalisés par zone
- **Intervalle de confiance** avec 3 niveaux (haute/moyenne/faible)
- **API REST générique** : un seul endpoint, 6 sections sélectionnables

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Base de données | PostgreSQL + PostGIS (Supabase) |
| Backend API | FastAPI + Pydantic v2 |
| Frontend | Streamlit + Folium + Plotly |
| Géocodage | API Géoplateforme (IGN) |
| Pipeline | Python + Click CLI |
| Déploiement | Docker + Railway |
| Données | Etalab DVF géolocalisées (CSV) |
| Tests | pytest (164 tests) |

---

## Démarrage rapide

### Prérequis

- Python 3.12+
- Une base PostgreSQL + PostGIS (ou Supabase)
- Variable `DATABASE_URL` dans `.env`

### Installation

```bash
git clone https://github.com/MohamedBouchiba/STTA-DVF.git
cd STTA-DVF
pip install -r requirements.txt
cp .env.example .env  # Configurer DATABASE_URL
```

### Pipeline de données

```bash
# Tout d'un coup
python scripts/run_pipeline.py run-all

# Ou étape par étape
python scripts/run_pipeline.py init-db      # Créer schemas + tables
python scripts/run_pipeline.py download     # Télécharger les CSV Etalab
python scripts/run_pipeline.py load         # Charger + transformer en core
python scripts/run_pipeline.py outliers     # Détecter les outliers
python scripts/run_pipeline.py mart         # Rafraîchir les marts
```

### Lancer en local

```bash
# Streamlit (frontend)
streamlit run src/app/streamlit_app.py

# API seule
uvicorn src.api.main:app --port 8000
```

---

## API REST

### Endpoints

| Méthode | URL | Description |
|---------|-----|-------------|
| `POST` | `/api/v1/estimate` | Estimation complète |
| `GET` | `/api/v1/health` | Health check (DB + PostGIS) |
| `GET` | `/api/v1/defaults` | Coefficients par défaut |

### Exemple minimal

```bash
curl -X POST https://stta-dvf-production-c7bc.up.railway.app/api/v1/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "address": "25 avenue des Champs-Elysées, Paris",
    "property_type": "appartement",
    "surface": 50
  }'
```

### Sections de réponse

La réponse contient 6 sections sélectionnables via le paramètre `include` :

| Section | Description |
|---------|-------------|
| `geocoding` | Coordonnées, code INSEE, score de géocodage |
| `estimation` | Prix base + ajusté, confiance, fourchette, zone breakdown |
| `adjustments` | Détail des 6 ajustements (coefficient + explication) |
| `zone_stats` | Statistiques de marché (transactions, tendance, qualité) |
| `evolution` | Historique semestriel + mensuel avec rolling median 6m |
| `comparables` | Liste des transactions (lat/lon, distance, zone, prix/m²) |

Documentation complète : **[docs/API.md](docs/API.md)** | **[Swagger](https://stta-dvf-production-c7bc.up.railway.app/docs)**

---

## Déploiement (Railway)

Le projet se déploie en **2 services Railway** depuis le même repo :

| Service | Dockerfile | Contenu |
|---------|-----------|---------|
| **API** | `Dockerfile` | FastAPI + Swagger (`/docs`, `/api/v1/*`) |
| **Frontend** | `Dockerfile.streamlit` | App Streamlit |

### Variables d'environnement

| Variable | Requis | Description |
|----------|--------|-------------|
| `DATABASE_URL` | Oui | PostgreSQL connection string |
| `ALLOWED_ORIGINS` | Non | Origines CORS (défaut: `*`) |
| `PORT` | Non | Injecté par Railway |

### Build & Run

```bash
docker build -t stta-dvf .
docker run --env-file .env -p 8000:8000 stta-dvf
```

---

## Algorithme d'estimation

1. **Géocodage** de l'adresse via API Géoplateforme → coordonnées + code INSEE
2. **Recherche de comparables** dans 3 zones concentriques (PostGIS `ST_DWithin`)
3. **Médiane pondérée** par zone (60% zone 1, 30% zone 2, 10% zone 3)
4. **Ajustement surface** (log2, plafonné ±20%)
5. **6 ajustements heuristiques** : type × étage × caractéristiques × état × qualité × construction (plafonné 0.70-1.40)
6. **Intervalle de confiance** (Q25-Q75) × total_multiplier
7. **Niveau de confiance** : haute (≥30 comp. & niveau ≤2), moyenne (≥10 & ≤3), faible

---

## Couverture géographique

| Département | Nom | Transactions |
|-------------|-----|--------------|
| 75 | Paris | ~160 000 |
| 77 | Seine-et-Marne | ~80 000 |
| 78 | Yvelines | ~60 000 |
| 91 | Essonne | ~55 000 |
| 92 | Hauts-de-Seine | ~70 000 |
| 93 | Seine-Saint-Denis | ~55 000 |
| 94 | Val-de-Marne | ~55 000 |
| 95 | Val-d'Oise | ~50 000 |
| 13 | Bouches-du-Rhône | ~170 000 |

**Période** : Juillet 2020 — Juin 2025 (5 ans) | **Source** : [Etalab DVF géolocalisées](https://files.data.gouv.fr/geo-dvf/latest/csv/)

---

## Arborescence

```
STTA-DVF/
├── Dockerfile                 # Image Docker API (FastAPI + uvicorn)
├── Dockerfile.streamlit       # Image Docker Frontend (Streamlit)
├── railway.json               # Config Railway (health check)
├── requirements.txt           # Dépendances Python (Streamlit + pipeline)
├── requirements-api.txt       # Dépendances prod (API seule)
├── docs/
│   └── API.md                 # Documentation API complète
├── sql/
│   ├── core/                  # DDL + transform staging → core
│   └── mart/                  # DDL + agrégations
├── src/
│   ├── config.py + db.py      # Configuration + connexion DB
│   ├── api/                   # FastAPI (main, schemas, service)
│   ├── ingestion/             # Download CSV Etalab + chargement
│   ├── transform/             # Staging → core, core → mart
│   ├── estimation/            # Géocodeur, comparables, estimateur, confiance
│   └── app/                   # Streamlit (wizard, admin, résultats, carte)
├── scripts/run_pipeline.py    # CLI pipeline (Click)
└── tests/                     # 164 tests (unit + integration + API)
```

---

## Tests

```bash
# Tous les tests
pytest tests/ -v

# Tests unitaires seulement
pytest tests/ -v -m "not integration"

# Tests API seulement
pytest tests/test_api.py -v
```

---

## Licence

Données DVF : [Licence Ouverte Etalab 2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence/)
