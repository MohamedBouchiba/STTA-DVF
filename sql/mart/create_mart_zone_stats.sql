CREATE TABLE IF NOT EXISTS mart.zone_stats (
    codinsee            TEXT NOT NULL,
    type_bien           TEXT NOT NULL,
    total_transactions  INTEGER,
    last_12m_transactions INTEGER,
    median_prix_m2_12m  NUMERIC(10,2),
    stddev_prix_m2_12m  NUMERIC(10,2),
    trend_12m           NUMERIC(6,2),
    data_quality_flag   TEXT,
    PRIMARY KEY (codinsee, type_bien)
);
