CREATE SCHEMA IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.dvf;

CREATE TABLE staging.dvf (
    id_mutation             TEXT,
    date_mutation           DATE,
    numero_disposition      INTEGER,
    nature_mutation         TEXT,
    valeur_fonciere         NUMERIC(15,2),
    adresse_numero          TEXT,
    adresse_nom_voie        TEXT,
    code_postal             TEXT,
    code_commune            TEXT,
    nom_commune             TEXT,
    code_departement        TEXT,
    id_parcelle             TEXT,
    type_local              TEXT,
    code_type_local         INTEGER,
    surface_reelle_bati     NUMERIC(10,2),
    nombre_pieces_principales INTEGER,
    surface_terrain         NUMERIC(12,2),
    longitude               NUMERIC(10,7),
    latitude                NUMERIC(10,7),
    lot1_surface_carrez     NUMERIC(10,2),
    lot2_surface_carrez     NUMERIC(10,2),
    annee_fichier           INTEGER,
    loaded_at               TIMESTAMPTZ DEFAULT NOW()
)
