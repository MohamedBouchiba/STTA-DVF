-- ============================================================
-- Rafraichissement des tables mart depuis core
-- ============================================================

-- 1. Mediane prix/m2 par commune x type x semestre
TRUNCATE mart.prix_m2_commune;
INSERT INTO mart.prix_m2_commune
SELECT
    codinsee,
    type_bien,
    anneemut AS annee,
    CASE WHEN moismut <= 6 THEN 1 ELSE 2 END AS semestre,
    COUNT(*) AS nb_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2) AS q1_prix_m2,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2) AS q3_prix_m2,
    AVG(prix_m2) AS mean_prix_m2,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY surface_utilisee) AS median_surface
FROM core.transactions
WHERE quality_score & 1 = 0
GROUP BY codinsee, type_bien, anneemut,
         CASE WHEN moismut <= 6 THEN 1 ELSE 2 END;

-- 2. Mediane prix/m2 par departement (fallback)
TRUNCATE mart.prix_m2_departement;
INSERT INTO mart.prix_m2_departement
SELECT
    coddep,
    type_bien,
    anneemut AS annee,
    CASE WHEN moismut <= 6 THEN 1 ELSE 2 END AS semestre,
    COUNT(*) AS nb_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2) AS q1_prix_m2,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2) AS q3_prix_m2,
    AVG(prix_m2) AS mean_prix_m2,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY surface_utilisee) AS median_surface
FROM core.transactions
WHERE quality_score & 1 = 0
GROUP BY coddep, type_bien, anneemut,
         CASE WHEN moismut <= 6 THEN 1 ELSE 2 END;

-- 3. Statistiques par zone (12 derniers mois)
TRUNCATE mart.zone_stats;
INSERT INTO mart.zone_stats
WITH max_date AS (
    SELECT MAX(datemut) AS d FROM core.transactions WHERE quality_score & 1 = 0
),
last_12m AS (
    SELECT t.*
    FROM core.transactions t, max_date md
    WHERE t.quality_score & 1 = 0
      AND t.datemut >= md.d - INTERVAL '12 months'
),
prev_12m AS (
    SELECT t.*
    FROM core.transactions t, max_date md
    WHERE t.quality_score & 1 = 0
      AND t.datemut >= md.d - INTERVAL '24 months'
      AND t.datemut < md.d - INTERVAL '12 months'
)
SELECT
    l.codinsee,
    l.type_bien,
    (SELECT COUNT(*) FROM core.transactions t2
     WHERE t2.codinsee = l.codinsee AND t2.type_bien = l.type_bien
       AND t2.quality_score & 1 = 0) AS total_transactions,
    COUNT(*) AS last_12m_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.prix_m2) AS median_prix_m2_12m,
    STDDEV(l.prix_m2) AS stddev_prix_m2_12m,
    -- Tendance : variation mediane 12m vs 12m precedents
    CASE
        WHEN (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.prix_m2)
              FROM prev_12m p
              WHERE p.codinsee = l.codinsee AND p.type_bien = l.type_bien) > 0
        THEN ROUND(
            100.0 * (
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.prix_m2)
                - (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.prix_m2)
                   FROM prev_12m p
                   WHERE p.codinsee = l.codinsee AND p.type_bien = l.type_bien)
            ) / (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.prix_m2)
                 FROM prev_12m p
                 WHERE p.codinsee = l.codinsee AND p.type_bien = l.type_bien),
            2
        )
    END AS trend_12m,
    CASE
        WHEN COUNT(*) >= 30 THEN 'good'
        WHEN COUNT(*) >= 10 THEN 'moderate'
        ELSE 'sparse'
    END AS data_quality_flag
FROM last_12m l
GROUP BY l.codinsee, l.type_bien;

-- 4. Indices temporels mensuels par commune
TRUNCATE mart.indices_temporels;
INSERT INTO mart.indices_temporels (codinsee, type_bien, annee, mois, nb_transactions, median_prix_m2)
SELECT
    codinsee,
    type_bien,
    anneemut AS annee,
    moismut AS mois,
    COUNT(*) AS nb_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2
FROM core.transactions
WHERE quality_score & 1 = 0
GROUP BY codinsee, type_bien, anneemut, moismut;

-- Mediane glissante 6 mois (approximation via moyenne des 6 dernieres medianes)
UPDATE mart.indices_temporels i
SET rolling_median_6m = sub.rolling_avg
FROM (
    SELECT
        codinsee, type_bien, annee, mois,
        AVG(median_prix_m2) OVER (
            PARTITION BY codinsee, type_bien
            ORDER BY annee, mois
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
        ) AS rolling_avg
    FROM mart.indices_temporels
) sub
WHERE i.codinsee = sub.codinsee
  AND i.type_bien = sub.type_bien
  AND i.annee = sub.annee
  AND i.mois = sub.mois;
