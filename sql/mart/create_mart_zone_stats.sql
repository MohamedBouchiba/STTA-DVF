DROP TABLE IF EXISTS mart.zone_stats;
CREATE TABLE mart.zone_stats (
    code_commune        TEXT NOT NULL,
    type_bien           TEXT NOT NULL,
    total_transactions  INTEGER,
    last_12m_transactions INTEGER,
    median_prix_m2_12m  NUMERIC(10,2),
    stddev_prix_m2_12m  NUMERIC(10,2),
    trend_12m           NUMERIC(6,2),
    data_quality_flag   TEXT,
    PRIMARY KEY (code_commune, type_bien)
);
