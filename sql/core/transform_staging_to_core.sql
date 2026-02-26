-- ============================================================
-- Transformation staging -> core
-- Filtre, nettoie et calcule prix/m2 depuis DVF+
-- ============================================================

TRUNCATE core.transactions CASCADE;
TRUNCATE core.geo CASCADE;

-- ============================================================
-- ETAPE 1 : Transactions nettoyees
-- ============================================================
INSERT INTO core.transactions (
    idmutation, idmutinvar, datemut, anneemut, moismut,
    valeurfonc, codtypbien, libtypbien, type_bien,
    sbati, sbatmai, sbatapt, surface_utilisee, sterr,
    nbppmut, nb_pieces, nblocmut, nblocmai, nblocapt,
    coddep, codinsee, libcommune, prix_m2, filtre, dvf_version
)
SELECT
    m.idmutation,
    m.idmutinvar,
    m.datemut,
    m.anneemut,
    m.moismut,
    m.valeurfonc,
    m.codtypbien,
    m.libtypbien,

    -- Type simplifie
    CASE
        WHEN m.codtypbien LIKE '111%' THEN 'maison'
        WHEN m.codtypbien LIKE '121%' THEN 'appartement'
    END AS type_bien,

    m.sbati,
    m.sbatmai,
    m.sbatapt,

    -- Surface pour le calcul prix/m2
    CASE
        WHEN m.codtypbien LIKE '121%' AND m.sbatapt > 0 THEN m.sbatapt
        WHEN m.codtypbien LIKE '111%' AND m.sbatmai > 0 THEN m.sbatmai
        ELSE m.sbati
    END AS surface_utilisee,

    m.sterr,

    -- Nombre de pieces principal
    m.nbppmut,

    -- Nb pieces simplifie (pour mutations mono-bien)
    CASE
        WHEN m.codtypbien LIKE '121%' THEN
            CASE
                WHEN m.nbapt1pp = 1 THEN 1
                WHEN m.nbapt2pp = 1 THEN 2
                WHEN m.nbapt3pp = 1 THEN 3
                WHEN m.nbapt4pp = 1 THEN 4
                WHEN m.nbapt5pp = 1 THEN 5
            END
        WHEN m.codtypbien LIKE '111%' THEN
            CASE
                WHEN m.nbmai1pp = 1 THEN 1
                WHEN m.nbmai2pp = 1 THEN 2
                WHEN m.nbmai3pp = 1 THEN 3
                WHEN m.nbmai4pp = 1 THEN 4
                WHEN m.nbmai5pp = 1 THEN 5
            END
    END AS nb_pieces,

    m.nblocmut,
    m.nblocmai,
    m.nblocapt,
    m.coddep,

    -- Premier code INSEE de la liste
    (string_to_array(m.l_codinsee, '|'))[1] AS codinsee,

    -- Libelle commune
    (string_to_array(m.l_libcom, '|'))[1] AS libcommune,

    -- Prix au m2
    m.valeurfonc / NULLIF(
        CASE
            WHEN m.codtypbien LIKE '121%' AND m.sbatapt > 0 THEN m.sbatapt
            WHEN m.codtypbien LIKE '111%' AND m.sbatmai > 0 THEN m.sbatmai
            ELSE m.sbati
        END, 0
    ) AS prix_m2,

    m.filtre,
    'current' AS dvf_version

FROM staging.mutation m
WHERE
    -- Ventes uniquement
    m.libnatmut = 'Vente'

    -- Types residentiels mono-bien
    AND (m.codtypbien LIKE '111%' OR m.codtypbien LIKE '121%')

    -- Prix valide
    AND m.valeurfonc > 0

    -- Surface valide
    AND CASE
        WHEN m.codtypbien LIKE '121%' THEN COALESCE(m.sbatapt, m.sbati)
        WHEN m.codtypbien LIKE '111%' THEN COALESCE(m.sbatmai, m.sbati)
    END > 0

    -- Surface minimum 9m2
    AND CASE
        WHEN m.codtypbien LIKE '121%' THEN COALESCE(m.sbatapt, m.sbati)
        WHEN m.codtypbien LIKE '111%' THEN COALESCE(m.sbatmai, m.sbati)
    END >= 9

    -- Mutations mono-bien (prix/m2 fiable)
    AND (
        (m.codtypbien LIKE '111%' AND m.nblocmai = 1)
        OR (m.codtypbien LIKE '121%' AND m.nblocapt = 1)
    )

    -- Filtre DVF+ (exclut transactions a 0/1 EUR)
    AND (m.filtre IS NULL OR m.filtre NOT IN ('0', '1'))
;

-- ============================================================
-- ETAPE 2 : Donnees geographiques
-- ============================================================
INSERT INTO core.geo (
    idmutation, geom, latitude, longitude,
    coddep, codinsee, commune
)
SELECT
    t.idmutation,
    m.geomlocmut,
    ST_Y(m.geomlocmut::geometry),
    ST_X(m.geomlocmut::geometry),
    t.coddep,
    t.codinsee,
    t.libcommune
FROM core.transactions t
JOIN staging.mutation m ON m.idmutation = t.idmutation
WHERE m.geomlocmut IS NOT NULL;

-- ============================================================
-- ETAPE 3 : Detection des outliers (IQR par dep x type x annee)
-- ============================================================
WITH quartiles AS (
    SELECT
        coddep,
        type_bien,
        anneemut,
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY prix_m2) AS q1,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY prix_m2) AS q3
    FROM core.transactions
    GROUP BY coddep, type_bien, anneemut
),
bounds AS (
    SELECT
        coddep, type_bien, anneemut,
        q1 - 1.5 * (q3 - q1) AS lower_bound,
        q3 + 1.5 * (q3 - q1) AS upper_bound
    FROM quartiles
)
UPDATE core.transactions t
SET quality_score = quality_score | 1
FROM bounds b
WHERE t.coddep = b.coddep
  AND t.type_bien = b.type_bien
  AND t.anneemut = b.anneemut
  AND (t.prix_m2 < b.lower_bound OR t.prix_m2 > b.upper_bound);
