BEGIN;

CREATE TABLE IF NOT EXISTS state_snapshots (
    id BIGSERIAL PRIMARY KEY,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    schema_version TEXT NOT NULL,
    source_revision TEXT,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    module TEXT NOT NULL,
    source_revision TEXT,
    decision_key TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS power_intents (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_revision TEXT,
    ev_target_w INTEGER,
    ww_target_w INTEGER,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS gate_results (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    gate_name TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('PASS','BLOCK','ERROR')),
    reason TEXT,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS shadow_comparisons (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    module TEXT NOT NULL,
    input_revision TEXT,
    homey_output JSONB,
    pi_output JSONB NOT NULL,
    equivalent BOOLEAN,
    difference JSONB
);

CREATE TABLE IF NOT EXISTS device_observations (
    id BIGSERIAL PRIMARY KEY,
    observed_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL,
    quality TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS system_health (
    id BIGSERIAL PRIMARY KEY,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_state_snapshots_captured_at ON state_snapshots(captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_shadow_comparisons_module_time ON shadow_comparisons(module, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_observations_source_time ON device_observations(source, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_health_component_time ON system_health(component, captured_at DESC);

COMMIT;
