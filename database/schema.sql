
-- ==========================================
-- URBAN RISK ANALYTICS DATABASE
-- PostgreSQL + PostGIS
-- ==========================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. DATASET SOURCE AND VERSION TRACKING
CREATE TABLE dataset_versions (
    dataset_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_name VARCHAR(150) NOT NULL,
    source_name VARCHAR(200) NOT NULL,
    file_path TEXT,
    version_label VARCHAR(100),
    date_range_start DATE,
    date_range_end DATE,
    retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    record_count BIGINT,
    UNIQUE (dataset_name, version_label)
);

-- 2. GEOGRAPHIC LOCATIONS
-- Stores reference grid points and user-selected plot locations.
CREATE TABLE spatial_locations (
    location_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    location_type VARCHAR(30) NOT NULL
        CHECK (location_type IN ('grid_point', 'plot')),
    external_key VARCHAR(150),
    latitude DOUBLE PRECISION NOT NULL
        CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL
        CHECK (longitude BETWEEN -180 AND 180),
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (location_type, external_key)
);

CREATE INDEX idx_spatial_locations_geom
ON spatial_locations USING GIST (geom);

-- 3. HAZARD OBSERVATIONS
-- Stores measured flood/heat-related observations.
CREATE TABLE hazard_observations (
    observation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id BIGINT NOT NULL
        REFERENCES dataset_versions(dataset_id),
    location_id BIGINT
        REFERENCES spatial_locations(location_id),
    hazard_type VARCHAR(30) NOT NULL
        CHECK (hazard_type IN ('flood', 'heat')),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DOUBLE PRECISION,
    unit VARCHAR(50),
    observed_at DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hazard_location
ON hazard_observations(location_id);

CREATE INDEX idx_hazard_type_date
ON hazard_observations(hazard_type, observed_at);

-- 4. HISTORICAL FLOOD EVENTS
-- District-level events are stored separately because
-- the available inventory does not provide event coordinates.
CREATE TABLE flood_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id BIGINT NOT NULL
        REFERENCES dataset_versions(dataset_id),
    source_event_id VARCHAR(100),
    district VARCHAR(150),
    start_date DATE,
    end_date DATE,
    main_cause TEXT,
    duration_days INTEGER,
    human_fatality INTEGER,
    human_injured INTEGER,
    UNIQUE (dataset_id, source_event_id)
);

-- 5. INFRASTRUCTURE ASSETS
CREATE TABLE infrastructure_assets (
    asset_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id BIGINT NOT NULL
        REFERENCES dataset_versions(dataset_id),
    osm_id VARCHAR(100),
    category VARCHAR(80) NOT NULL,
    asset_name VARCHAR(200),
    subtype VARCHAR(100),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    UNIQUE (dataset_id, osm_id)
);

CREATE INDEX idx_infrastructure_geom
ON infrastructure_assets USING GIST (geom);

-- 6. ROAD DATA
-- Current processed data contains representative coordinates,
-- not complete road geometries.
CREATE TABLE road_segments (
    road_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_id BIGINT NOT NULL
        REFERENCES dataset_versions(dataset_id),
    osm_id VARCHAR(100),
    road_name VARCHAR(200),
    road_type VARCHAR(100),
    maxspeed VARCHAR(50),
    oneway VARCHAR(30),
    length_km DOUBLE PRECISION,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    representative_point GEOMETRY(Point, 4326) NOT NULL,
    UNIQUE (dataset_id, osm_id)
);

CREATE INDEX idx_roads_geom
ON road_segments USING GIST (representative_point);

-- 7. MODEL EXECUTION HISTORY
CREATE TABLE model_runs (
    model_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    module_name VARCHAR(100) NOT NULL,
    algorithm_name VARCHAR(150),
    model_version VARCHAR(100),
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(30) DEFAULT 'pending',
    parameters JSONB
);

-- 8. INTEGRATED RISK ASSESSMENTS
CREATE TABLE risk_assessments (
    assessment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    location_id BIGINT NOT NULL
        REFERENCES spatial_locations(location_id),
    model_run_id BIGINT NOT NULL
        REFERENCES model_runs(model_run_id),
    flood_score DOUBLE PRECISION,
    heat_score DOUBLE PRECISION,
    infrastructure_score DOUBLE PRECISION,
    overall_score DOUBLE PRECISION,
    risk_level VARCHAR(30),
    assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (location_id, model_run_id)
);

-- 9. RESOURCE PRIORITIZATION
CREATE TABLE resource_priorities (
    priority_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assessment_id BIGINT NOT NULL
        REFERENCES risk_assessments(assessment_id),
    priority_rank INTEGER NOT NULL CHECK (priority_rank > 0),
    resource_type VARCHAR(100),
    justification TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (assessment_id, priority_rank)
);
