CREATE TABLE IF NOT EXISTS core.transactions (
    id                  BIGSERIAL PRIMARY KEY,
    idmutation          BIGINT NOT NULL,
    idmutinvar          TEXT,

    -- Transaction
    datemut             DATE NOT NULL,
    anneemut            INTEGER NOT NULL,
    moismut             INTEGER NOT NULL,
    valeurfonc          NUMERIC(15,2) NOT NULL,

    -- Type de bien
    codtypbien          TEXT NOT NULL,
    libtypbien          TEXT,
    type_bien           TEXT NOT NULL,

    -- Surfaces
    sbati               NUMERIC(10,2),
    sbatmai             NUMERIC(10,2),
    sbatapt             NUMERIC(10,2),
    surface_utilisee    NUMERIC(10,2) NOT NULL,
    sterr               NUMERIC(12,2),

    -- Pieces
    nbppmut             INTEGER,
    nb_pieces           INTEGER,

    -- Comptages
    nblocmut            INTEGER,
    nblocmai            INTEGER,
    nblocapt            INTEGER,

    -- Geographie
    coddep              TEXT NOT NULL,
    codinsee            TEXT NOT NULL,
    libcommune          TEXT,

    -- Calcule
    prix_m2             NUMERIC(10,2) NOT NULL,

    -- Qualite
    filtre              TEXT,
    quality_score       INTEGER DEFAULT 0,

    -- Metadata
    dvf_version         TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT chk_prix_m2_positive CHECK (prix_m2 > 0),
    CONSTRAINT chk_surface_positive CHECK (surface_utilisee > 0),
    CONSTRAINT chk_valeur_positive CHECK (valeurfonc > 0)
);

CREATE INDEX IF NOT EXISTS idx_core_tx_codinsee_type
    ON core.transactions (codinsee, type_bien);
CREATE INDEX IF NOT EXISTS idx_core_tx_coddep_type
    ON core.transactions (coddep, type_bien);
CREATE INDEX IF NOT EXISTS idx_core_tx_annee_mois
    ON core.transactions (anneemut, moismut);
CREATE INDEX IF NOT EXISTS idx_core_tx_prix_m2
    ON core.transactions (prix_m2);
CREATE INDEX IF NOT EXISTS idx_core_tx_datemut
    ON core.transactions (datemut);
CREATE INDEX IF NOT EXISTS idx_core_tx_quality
    ON core.transactions (quality_score);
