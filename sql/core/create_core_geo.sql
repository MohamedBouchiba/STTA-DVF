CREATE TABLE IF NOT EXISTS core.geo (
    id                  BIGSERIAL PRIMARY KEY,
    idmutation          BIGINT NOT NULL,

    -- Geometrie
    geom                GEOMETRY(Point, 4326),
    latitude            NUMERIC(10,7),
    longitude           NUMERIC(10,7),

    -- Administratif
    coddep              TEXT NOT NULL,
    codinsee            TEXT NOT NULL,

    -- Adresse
    codepostal          TEXT,
    commune             TEXT,

    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_core_geo_geom
    ON core.geo USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_core_geo_codinsee
    ON core.geo (codinsee);
CREATE INDEX IF NOT EXISTS idx_core_geo_idmutation
    ON core.geo (idmutation);
