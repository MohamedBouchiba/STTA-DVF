-- ============================================================
-- Transformation staging.dvf (Etalab CSV) -> core.transactions
-- Le CSV a 1 ligne par lot/local. On agregre par id_mutation
-- pour ne garder que les ventes mono-bien residentielles.
-- ============================================================

-- IMPORTANT : on n'utilise PAS TRUNCATE core.transactions ici
-- car le chargement se fait par lot (1 CSV a la fois).
-- Le TRUNCATE est fait une seule fois au debut du pipeline complet.

-- ============================================================
-- ETAPE 1 : Inserer les ventes mono-bien depuis le staging courant
-- ============================================================
INSERT INTO core.transactions (
    id_mutation, date_mutation, annee, mois,
    valeur_fonciere, type_bien,
    surface, nb_pieces,
    code_departement, code_commune, nom_commune, code_postal, adresse,
    latitude, longitude, geom,
    prix_m2
)
WITH lots_residentiels AS (
    -- Filtrer aux ventes de maisons/appartements avec surface valide
    SELECT
        id_mutation,
        date_mutation,
        valeur_fonciere,
        code_type_local,
        type_local,
        surface_reelle_bati,
        nombre_pieces_principales,
        code_departement,
        code_commune,
        nom_commune,
        code_postal,
        adresse_numero,
        adresse_nom_voie,
        latitude,
        longitude
    FROM staging.dvf
    WHERE nature_mutation = 'Vente'
      AND code_type_local IN (1, 2)
      AND valeur_fonciere >= 100
      AND surface_reelle_bati IS NOT NULL
      AND surface_reelle_bati >= 9
),
mutations_comptees AS (
    -- Compter le nombre de locaux residentiels par mutation
    SELECT
        id_mutation,
        COUNT(*) AS nb_locaux
    FROM lots_residentiels
    GROUP BY id_mutation
),
mono_bien AS (
    -- Ne garder que les mutations avec exactement 1 local residentiel
    SELECT l.*
    FROM lots_residentiels l
    JOIN mutations_comptees m ON m.id_mutation = l.id_mutation
    WHERE m.nb_locaux = 1
)
SELECT
    id_mutation,
    date_mutation,
    EXTRACT(YEAR FROM date_mutation)::INTEGER AS annee,
    EXTRACT(MONTH FROM date_mutation)::INTEGER AS mois,
    valeur_fonciere,
    CASE code_type_local
        WHEN 1 THEN 'maison'
        WHEN 2 THEN 'appartement'
    END AS type_bien,
    surface_reelle_bati AS surface,
    nombre_pieces_principales AS nb_pieces,
    code_departement,
    code_commune,
    nom_commune,
    code_postal,
    TRIM(COALESCE(adresse_numero, '') || ' ' || COALESCE(adresse_nom_voie, '')) AS adresse,
    latitude,
    longitude,
    CASE
        WHEN latitude IS NOT NULL AND longitude IS NOT NULL
        THEN ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    END AS geom,
    valeur_fonciere / surface_reelle_bati AS prix_m2
FROM mono_bien
WHERE valeur_fonciere / surface_reelle_bati > 0
