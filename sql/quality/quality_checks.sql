-- ============================================================
-- Controles qualite des donnees core
-- ============================================================

-- 1. Comptages par couche
SELECT 'staging.mutation' AS table_name, COUNT(*) AS row_count FROM staging.mutation
UNION ALL
SELECT 'core.transactions', COUNT(*) FROM core.transactions
UNION ALL
SELECT 'core.transactions (hors outliers)', COUNT(*) FROM core.transactions WHERE quality_score & 1 = 0
UNION ALL
SELECT 'core.geo', COUNT(*) FROM core.geo;

-- 2. Taux de surfaces nulles par departement
SELECT coddep, type_bien,
    COUNT(*) AS total,
    SUM(CASE WHEN surface_utilisee IS NULL OR surface_utilisee = 0 THEN 1 ELSE 0 END) AS null_surface,
    ROUND(100.0 * SUM(CASE WHEN surface_utilisee IS NULL OR surface_utilisee = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_null
FROM core.transactions
GROUP BY coddep, type_bien
ORDER BY pct_null DESC;

-- 3. Distribution des prix/m2 par departement
SELECT coddep, type_bien,
    COUNT(*) AS nb,
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY prix_m2) AS p01,
    PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY prix_m2) AS p10,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2) AS p25,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY prix_m2) AS p50,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2) AS p75,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY prix_m2) AS p90,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY prix_m2) AS p99
FROM core.transactions
WHERE quality_score & 1 = 0
GROUP BY coddep, type_bien;

-- 4. Nombre de transactions par annee (detecter les trous)
SELECT anneemut, type_bien, COUNT(*) AS nb_transactions
FROM core.transactions
WHERE quality_score & 1 = 0
GROUP BY anneemut, type_bien
ORDER BY anneemut, type_bien;

-- 5. Couverture geographique
SELECT
    COUNT(DISTINCT t.codinsee) AS communes_avec_transactions,
    COUNT(DISTINCT t.coddep) AS departements_couverts,
    COUNT(DISTINCT g.idmutation) AS transactions_geolocalisees,
    COUNT(DISTINCT t.idmutation) AS transactions_total,
    ROUND(100.0 * COUNT(DISTINCT g.idmutation) / NULLIF(COUNT(DISTINCT t.idmutation), 0), 1)
        AS pct_geolocalisees
FROM core.transactions t
LEFT JOIN core.geo g ON g.idmutation = t.idmutation
WHERE t.quality_score & 1 = 0;

-- 6. Taux d'outliers par departement
SELECT coddep, type_bien,
    COUNT(*) AS total,
    SUM(CASE WHEN quality_score & 1 = 1 THEN 1 ELSE 0 END) AS nb_outliers,
    ROUND(100.0 * SUM(CASE WHEN quality_score & 1 = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_outliers
FROM core.transactions
GROUP BY coddep, type_bien
ORDER BY pct_outliers DESC;
