DROP TABLE IF EXISTS mart.indices_temporels;
CREATE TABLE mart.indices_temporels (
    code_commune    TEXT NOT NULL,
    type_bien       TEXT NOT NULL,
    annee           INTEGER NOT NULL,
    mois            INTEGER NOT NULL,
    nb_transactions INTEGER,
    median_prix_m2  NUMERIC(10,2),
    rolling_median_6m NUMERIC(10,2),
    PRIMARY KEY (code_commune, type_bien, annee, mois)
);
