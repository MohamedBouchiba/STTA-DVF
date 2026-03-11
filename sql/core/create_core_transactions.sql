CREATE SCHEMA IF NOT EXISTS core;

DROP TABLE IF EXISTS core.transactions CASCADE;

CREATE TABLE core.transactions (
    id                  BIGSERIAL PRIMARY KEY,
    id_mutation         TEXT NOT NULL,
    date_mutation       DATE NOT NULL,
    annee               INTEGER NOT NULL,
    mois                INTEGER NOT NULL,
    valeur_fonciere     NUMERIC(15,2) NOT NULL,

    -- Type simplifie
    type_bien           TEXT NOT NULL,

    -- Surface et pieces
    surface             NUMERIC(10,2) NOT NULL,
    nb_pieces           INTEGER,

    -- Geographie
    code_departement    TEXT NOT NULL,
    code_commune        TEXT NOT NULL,
    nom_commune         TEXT,
    code_postal         TEXT,
    adresse             TEXT,

    -- Coordonnees
    latitude            NUMERIC(10,7),
    longitude           NUMERIC(10,7),
    geom                GEOMETRY(Point, 4326),

    -- Calcule
    prix_m2             NUMERIC(10,2) NOT NULL,

    -- Qualite
    is_outlier          BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_prix_m2_pos CHECK (prix_m2 > 0),
    CONSTRAINT chk_surface_pos CHECK (surface > 0),
    CONSTRAINT chk_valeur_pos CHECK (valeur_fonciere > 0)
);

CREATE INDEX IF NOT EXISTS idx_tx_commune_type ON core.transactions (code_commune, type_bien);
CREATE INDEX IF NOT EXISTS idx_tx_dept_type ON core.transactions (code_departement, type_bien);
CREATE INDEX IF NOT EXISTS idx_tx_date ON core.transactions (date_mutation);
CREATE INDEX IF NOT EXISTS idx_tx_prix_m2 ON core.transactions (prix_m2);
CREATE INDEX IF NOT EXISTS idx_tx_geom ON core.transactions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_tx_not_outlier ON core.transactions (is_outlier) WHERE NOT is_outlier;
