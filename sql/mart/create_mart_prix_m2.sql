CREATE TABLE IF NOT EXISTS mart.prix_m2_commune (
    codinsee        TEXT NOT NULL,
    type_bien       TEXT NOT NULL,
    annee           INTEGER NOT NULL,
    semestre        INTEGER NOT NULL,
    nb_transactions INTEGER NOT NULL,
    median_prix_m2  NUMERIC(10,2),
    q1_prix_m2      NUMERIC(10,2),
    q3_prix_m2      NUMERIC(10,2),
    mean_prix_m2    NUMERIC(10,2),
    median_surface  NUMERIC(10,2),
    PRIMARY KEY (codinsee, type_bien, annee, semestre)
);

CREATE TABLE IF NOT EXISTS mart.prix_m2_departement (
    coddep          TEXT NOT NULL,
    type_bien       TEXT NOT NULL,
    annee           INTEGER NOT NULL,
    semestre        INTEGER NOT NULL,
    nb_transactions INTEGER NOT NULL,
    median_prix_m2  NUMERIC(10,2),
    q1_prix_m2      NUMERIC(10,2),
    q3_prix_m2      NUMERIC(10,2),
    mean_prix_m2    NUMERIC(10,2),
    median_surface  NUMERIC(10,2),
    PRIMARY KEY (coddep, type_bien, annee, semestre)
);
