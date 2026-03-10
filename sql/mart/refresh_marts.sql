-- ============================================================
-- Rafraichissement des tables mart depuis core
-- ============================================================

-- 1. Mediane prix/m2 par commune x type x semestre
TRUNCATE mart.stats_commune;
INSERT INTO mart.stats_commune
SELECT
    code_commune,
    type_bien,
    annee,
    CASE WHEN mois <= 6 THEN 1 ELSE 2 END AS semestre,
    COUNT(*) AS nb_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2) AS q1_prix_m2,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2) AS q3_prix_m2,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY surface) AS median_surface
FROM core.transactions
WHERE NOT is_outlier
GROUP BY code_commune, type_bien, annee,
         CASE WHEN mois <= 6 THEN 1 ELSE 2 END;

-- 2. Mediane prix/m2 par departement (fallback)
TRUNCATE mart.stats_departement;
INSERT INTO mart.stats_departement
SELECT
    code_departement,
    type_bien,
    annee,
    CASE WHEN mois <= 6 THEN 1 ELSE 2 END AS semestre,
    COUNT(*) AS nb_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2) AS q1_prix_m2,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2) AS q3_prix_m2,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY surface) AS median_surface
FROM core.transactions
WHERE NOT is_outlier
GROUP BY code_departement, type_bien, annee,
         CASE WHEN mois <= 6 THEN 1 ELSE 2 END;

-- 3. Statistiques par zone (12 derniers mois)
TRUNCATE mart.zone_stats;
INSERT INTO mart.zone_stats
WITH max_date AS (
    SELECT MAX(date_mutation) AS d FROM core.transactions WHERE NOT is_outlier
),
last_12m AS (
    SELECT t.*
    FROM core.transactions t, max_date md
    WHERE NOT t.is_outlier
      AND t.date_mutation >= md.d - INTERVAL '12 months'
),
prev_12m AS (
    SELECT t.*
    FROM core.transactions t, max_date md
    WHERE NOT t.is_outlier
      AND t.date_mutation >= md.d - INTERVAL '24 months'
      AND t.date_mutation < md.d - INTERVAL '12 months'
)
SELECT
    l.code_commune,
    l.type_bien,
    (SELECT COUNT(*) FROM core.transactions t2
     WHERE t2.code_commune = l.code_commune AND t2.type_bien = l.type_bien
       AND NOT t2.is_outlier) AS total_transactions,
    COUNT(*) AS last_12m_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.prix_m2) AS median_prix_m2_12m,
    STDDEV(l.prix_m2) AS stddev_prix_m2_12m,
    CASE
        WHEN (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.prix_m2)
              FROM prev_12m p
              WHERE p.code_commune = l.code_commune AND p.type_bien = l.type_bien) > 0
        THEN ROUND(
            100.0 * (
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.prix_m2)
                - (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.prix_m2)
                   FROM prev_12m p
                   WHERE p.code_commune = l.code_commune AND p.type_bien = l.type_bien)
            ) / (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.prix_m2)
                 FROM prev_12m p
                 WHERE p.code_commune = l.code_commune AND p.type_bien = l.type_bien),
            2
        )
    END AS trend_12m,
    CASE
        WHEN COUNT(*) >= 30 THEN 'good'
        WHEN COUNT(*) >= 10 THEN 'moderate'
        ELSE 'sparse'
    END AS data_quality_flag
FROM last_12m l
GROUP BY l.code_commune, l.type_bien;

-- 4. Indices temporels mensuels par commune
TRUNCATE mart.indices_temporels;
INSERT INTO mart.indices_temporels (code_commune, type_bien, annee, mois, nb_transactions, median_prix_m2)
SELECT
    code_commune,
    type_bien,
    annee,
    mois,
    COUNT(*) AS nb_transactions,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS median_prix_m2
FROM core.transactions
WHERE NOT is_outlier
GROUP BY code_commune, type_bien, annee, mois;

-- Mediane glissante 6 mois (approximation via moyenne des 6 dernieres medianes)
UPDATE mart.indices_temporels i
SET rolling_median_6m = sub.rolling_avg
FROM (
    SELECT
        code_commune, type_bien, annee, mois,
        AVG(median_prix_m2) OVER (
            PARTITION BY code_commune, type_bien
            ORDER BY annee, mois
            ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
        ) AS rolling_avg
    FROM mart.indices_temporels
) sub
WHERE i.code_commune = sub.code_commune
  AND i.type_bien = sub.type_bien
  AND i.annee = sub.annee
  AND i.mois = sub.mois;
