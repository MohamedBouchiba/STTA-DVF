CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS mart.stats_commune;
CREATE TABLE mart.stats_commune (
    code_commune    TEXT NOT NULL,
    type_bien       TEXT NOT NULL,
    annee           INTEGER NOT NULL,
    semestre        INTEGER NOT NULL,
    nb_transactions INTEGER NOT NULL,
    median_prix_m2  NUMERIC(10,2),
    q1_prix_m2      NUMERIC(10,2),
    q3_prix_m2      NUMERIC(10,2),
    median_surface  NUMERIC(10,2),
    PRIMARY KEY (code_commune, type_bien, annee, semestre)
);

DROP TABLE IF EXISTS mart.stats_departement;
CREATE TABLE mart.stats_departement (
    code_departement TEXT NOT NULL,
    type_bien        TEXT NOT NULL,
    annee            INTEGER NOT NULL,
    semestre         INTEGER NOT NULL,
    nb_transactions  INTEGER NOT NULL,
    median_prix_m2   NUMERIC(10,2),
    q1_prix_m2       NUMERIC(10,2),
    q3_prix_m2       NUMERIC(10,2),
    median_surface   NUMERIC(10,2),
    PRIMARY KEY (code_departement, type_bien, annee, semestre)
);
