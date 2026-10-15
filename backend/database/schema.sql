-- AgroNexus AI adaptive decision database schema.
-- SQLite 3.x. Store all timestamps as ISO-8601 UTC strings.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    username TEXT UNIQUE,
    phone TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'farmer' CHECK (role IN ('farmer', 'advisor', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    expires_at REAL NOT NULL,
    used_at TEXT
);

CREATE TABLE IF NOT EXISTS weather_cache (
    cache_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    fetched_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS soil_tests (
    soil_test_id TEXT PRIMARY KEY,
    farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
    owner_id TEXT REFERENCES users(user_id),
    ph REAL,
    nitrogen REAL,
    phosphorus REAL,
    potassium REAL,
    source TEXT NOT NULL DEFAULT 'farmer_input',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS farms (
    farm_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_name TEXT,
    state_name TEXT,
    district_name TEXT,
    village_name TEXT,
    latitude REAL CHECK (latitude BETWEEN -90 AND 90),
    longitude REAL CHECK (longitude BETWEEN -180 AND 180),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fields (
    field_id TEXT PRIMARY KEY,
    farm_id TEXT NOT NULL REFERENCES farms(farm_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    area_hectares REAL CHECK (area_hectares IS NULL OR area_hectares > 0),
    soil_type TEXT,
    latitude REAL CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude REAL CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_types (
    decision_type TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    sufficiency_threshold REAL NOT NULL CHECK (sufficiency_threshold BETWEEN 0 AND 1),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- A profile is immutable once used by a decision. Create a new version for changes.
CREATE TABLE IF NOT EXISTS erp_profiles (
    erp_profile_id TEXT PRIMARY KEY,
    decision_type TEXT NOT NULL REFERENCES decision_types(decision_type),
    version INTEGER NOT NULL,
    sufficiency_threshold REAL NOT NULL CHECK (sufficiency_threshold BETWEEN 0 AND 1),
    inclusion_floor REAL NOT NULL CHECK (inclusion_floor BETWEEN 0 AND 1),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL DEFAULT 'system',
    UNIQUE (decision_type, version)
);

CREATE TABLE IF NOT EXISTS erp_requirements (
    erp_requirement_id TEXT PRIMARY KEY,
    erp_profile_id TEXT NOT NULL REFERENCES erp_profiles(erp_profile_id) ON DELETE CASCADE,
    attribute_name TEXT NOT NULL,
    weight REAL NOT NULL CHECK (weight >= 0),
    required INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
    minimum_score REAL NOT NULL CHECK (minimum_score BETWEEN 0 AND 1),
    temporal_validity_hours REAL CHECK (temporal_validity_hours IS NULL OR temporal_validity_hours > 0),
    spatial_validity_km REAL CHECK (spatial_validity_km IS NULL OR spatial_validity_km > 0),
    acquisition_cost_factor REAL NOT NULL DEFAULT 1 CHECK (acquisition_cost_factor >= 0),
    acquisition_priority INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (erp_profile_id, attribute_name)
);

CREATE TABLE IF NOT EXISTS evidence_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL CHECK (source_type IN ('farmer_input', 'dataset', 'api', 'ml_model', 'manual_review', 'derived')),
    default_reliability REAL NOT NULL CHECK (default_reliability BETWEEN 0 AND 1),
    version TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Stores model metadata without requiring models to be database-managed.
CREATE TABLE IF NOT EXISTS model_registry (
    model_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    version TEXT NOT NULL,
    source_id TEXT REFERENCES evidence_sources(source_id),
    artifact_path TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    decision_type TEXT NOT NULL REFERENCES decision_types(decision_type),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    expected_global_outcome REAL CHECK (expected_global_outcome BETWEEN 0 AND 100),
    default_risk REAL NOT NULL DEFAULT 0.5 CHECK (default_risk BETWEEN 0 AND 1),
    estimated_cost REAL CHECK (estimated_cost IS NULL OR estimated_cost >= 0),
    resource_requirements_json TEXT NOT NULL DEFAULT '{}',
    safety_constraints_json TEXT NOT NULL DEFAULT '{}',
    applicability_rules_json TEXT NOT NULL DEFAULT '{}',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (decision_type, name)
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    farm_id TEXT NOT NULL REFERENCES farms(farm_id),
    field_id TEXT REFERENCES fields(field_id),
    decision_type TEXT NOT NULL REFERENCES decision_types(decision_type),
    erp_profile_id TEXT NOT NULL REFERENCES erp_profiles(erp_profile_id),
    status TEXT NOT NULL CHECK (status IN ('draft', 'insufficient_evidence', 'recommended', 'accepted', 'modified', 'rejected', 'outcome_recorded', 'cancelled')),
    context_json TEXT NOT NULL,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    evidence_sufficiency_score REAL CHECK (evidence_sufficiency_score BETWEEN 0 AND 1),
    required_evidence_satisfied INTEGER NOT NULL DEFAULT 0 CHECK (required_evidence_satisfied IN (0, 1)),
    decision_ready INTEGER NOT NULL DEFAULT 0 CHECK (decision_ready IN (0, 1)),
    selected_action_id TEXT REFERENCES actions(action_id),
    expected_outcome REAL CHECK (expected_outcome BETWEEN 0 AND 100),
    expected_outcome_unit TEXT NOT NULL DEFAULT 'effectiveness_percent',
    decision_trace_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES evidence_sources(source_id),
    model_id TEXT REFERENCES model_registry(model_id),
    attribute_name TEXT NOT NULL,
    value_json TEXT NOT NULL,
    unit TEXT,
    quality_score REAL NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    reliability_score REAL NOT NULL CHECK (reliability_score BETWEEN 0 AND 1),
    confidence_score REAL CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 1),
    temporal_score REAL CHECK (temporal_score IS NULL OR temporal_score BETWEEN 0 AND 1),
    spatial_score REAL CHECK (spatial_score IS NULL OR spatial_score BETWEEN 0 AND 1),
    normalized_score REAL CHECK (normalized_score IS NULL OR normalized_score BETWEEN 0 AND 1),
    captured_at TEXT NOT NULL,
    valid_until TEXT,
    latitude REAL CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
    longitude REAL CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
    provenance_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence_sufficiency_results (
    sufficiency_result_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(decision_id) ON DELETE CASCADE,
    overall_score REAL NOT NULL CHECK (overall_score BETWEEN 0 AND 1),
    threshold REAL NOT NULL CHECK (threshold BETWEEN 0 AND 1),
    required_attributes_satisfied INTEGER NOT NULL CHECK (required_attributes_satisfied IN (0, 1)),
    status TEXT NOT NULL CHECK (status IN ('sufficient', 'insufficient')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence_deficits (
    evidence_deficit_id TEXT PRIMARY KEY,
    sufficiency_result_id TEXT NOT NULL REFERENCES evidence_sufficiency_results(sufficiency_result_id) ON DELETE CASCADE,
    attribute_name TEXT NOT NULL,
    evidence_score REAL NOT NULL CHECK (evidence_score BETWEEN 0 AND 1),
    minimum_score REAL NOT NULL CHECK (minimum_score BETWEEN 0 AND 1),
    weighted_deficit REAL NOT NULL CHECK (weighted_deficit >= 0),
    acquisition_priority REAL NOT NULL CHECK (acquisition_priority >= 0),
    suggested_source_type TEXT,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS decision_candidates (
    candidate_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decisions(decision_id) ON DELETE CASCADE,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    is_feasible INTEGER NOT NULL CHECK (is_feasible IN (0, 1)),
    rejection_reasons_json TEXT NOT NULL DEFAULT '[]',
    benefit_score REAL CHECK (benefit_score BETWEEN 0 AND 1),
    contextual_effectiveness REAL CHECK (contextual_effectiveness BETWEEN 0 AND 100),
    evidence_confidence REAL CHECK (evidence_confidence BETWEEN 0 AND 1),
    risk_score REAL CHECK (risk_score BETWEEN 0 AND 1),
    cost_penalty REAL CHECK (cost_penalty BETWEEN 0 AND 1),
    uncertainty_score REAL CHECK (uncertainty_score BETWEEN 0 AND 1),
    final_score REAL,
    explanation_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (decision_id, action_id)
);

CREATE TABLE IF NOT EXISTS outcome_feedback (
    outcome_feedback_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(decision_id),
    actual_action_id TEXT REFERENCES actions(action_id),
    outcome_status TEXT NOT NULL CHECK (outcome_status IN ('improved', 'unchanged', 'worse', 'unknown')),
    observed_outcome REAL CHECK (observed_outcome BETWEEN 0 AND 100),
    outcome_unit TEXT NOT NULL DEFAULT 'effectiveness_percent',
    outcome_measure_quality REAL NOT NULL CHECK (outcome_measure_quality BETWEEN 0 AND 1),
    feedback_completeness REAL NOT NULL CHECK (feedback_completeness BETWEEN 0 AND 1),
    notes TEXT,
    observed_at TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_by TEXT NOT NULL DEFAULT 'farmer'
);

-- ACER retains an immutable decision-and-outcome snapshot for audit and replay.
CREATE TABLE IF NOT EXISTS acer_records (
    acer_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE REFERENCES decisions(decision_id),
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    decision_type TEXT NOT NULL REFERENCES decision_types(decision_type),
    context_json TEXT NOT NULL,
    expected_outcome REAL NOT NULL CHECK (expected_outcome BETWEEN 0 AND 100),
    observed_outcome REAL NOT NULL CHECK (observed_outcome BETWEEN 0 AND 100),
    deviation REAL NOT NULL,
    outcome_unit TEXT NOT NULL,
    evidence_sufficiency_score REAL NOT NULL CHECK (evidence_sufficiency_score BETWEEN 0 AND 1),
    outcome_confidence REAL NOT NULL CHECK (outcome_confidence BETWEEN 0 AND 1),
    eligible_for_adaptation INTEGER NOT NULL CHECK (eligible_for_adaptation IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS acer_context_features (
    acer_context_feature_id TEXT PRIMARY KEY,
    acer_id TEXT NOT NULL REFERENCES acer_records(acer_id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL,
    feature_type TEXT NOT NULL CHECK (feature_type IN ('numeric', 'categorical', 'boolean')),
    numeric_value REAL,
    text_value TEXT,
    normalized_value REAL CHECK (normalized_value IS NULL OR normalized_value BETWEEN 0 AND 1),
    feature_weight REAL NOT NULL DEFAULT 1 CHECK (feature_weight >= 0),
    UNIQUE (acer_id, feature_name),
    CHECK ((feature_type = 'numeric' AND numeric_value IS NOT NULL) OR (feature_type IN ('categorical', 'boolean') AND text_value IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS cnda_attributions (
    attribution_id TEXT PRIMARY KEY,
    acer_id TEXT NOT NULL REFERENCES acer_records(acer_id) ON DELETE CASCADE,
    feature_name TEXT NOT NULL,
    association_method TEXT NOT NULL CHECK (association_method IN ('weighted_correlation', 'group_mean_difference', 'manual_review')),
    association_value REAL NOT NULL,
    association_confidence REAL NOT NULL CHECK (association_confidence BETWEEN 0 AND 1),
    effective_sample_size REAL NOT NULL CHECK (effective_sample_size >= 0),
    selected INTEGER NOT NULL CHECK (selected IN (0, 1)),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (acer_id, feature_name)
);

-- A context region is represented by a reproducible signature plus the source context projection.
CREATE TABLE IF NOT EXISTS action_context_relationships (
    relationship_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    decision_type TEXT NOT NULL REFERENCES decision_types(decision_type),
    context_signature TEXT NOT NULL,
    context_projection_json TEXT NOT NULL,
    effectiveness_mean REAL NOT NULL CHECK (effectiveness_mean BETWEEN 0 AND 100),
    uncertainty REAL NOT NULL DEFAULT 1 CHECK (uncertainty BETWEEN 0 AND 1),
    effective_sample_size REAL NOT NULL DEFAULT 0 CHECK (effective_sample_size >= 0),
    global_effectiveness_mean REAL CHECK (global_effectiveness_mean BETWEEN 0 AND 100),
    last_acer_id TEXT REFERENCES acer_records(acer_id),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (action_id, decision_type, context_signature)
);

CREATE TABLE IF NOT EXISTS relationship_update_logs (
    relationship_update_id TEXT PRIMARY KEY,
    relationship_id TEXT NOT NULL REFERENCES action_context_relationships(relationship_id),
    acer_id TEXT NOT NULL REFERENCES acer_records(acer_id),
    similarity REAL NOT NULL CHECK (similarity BETWEEN 0 AND 1),
    learning_rate REAL NOT NULL CHECK (learning_rate >= 0),
    previous_effectiveness REAL NOT NULL CHECK (previous_effectiveness BETWEEN 0 AND 100),
    updated_effectiveness REAL NOT NULL CHECK (updated_effectiveness BETWEEN 0 AND 100),
    previous_uncertainty REAL NOT NULL CHECK (previous_uncertainty BETWEEN 0 AND 1),
    updated_uncertainty REAL NOT NULL CHECK (updated_uncertainty BETWEEN 0 AND 1),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS erp_update_logs (
    erp_update_id TEXT PRIMARY KEY,
    erp_requirement_id TEXT NOT NULL REFERENCES erp_requirements(erp_requirement_id),
    acer_id TEXT NOT NULL REFERENCES acer_records(acer_id),
    attribution_id TEXT REFERENCES cnda_attributions(attribution_id),
    previous_weight REAL NOT NULL CHECK (previous_weight >= 0),
    updated_weight REAL NOT NULL CHECK (updated_weight >= 0),
    learning_rate REAL NOT NULL CHECK (learning_rate >= 0),
    update_reason TEXT NOT NULL CHECK (update_reason IN ('associated_deviation', 'non_association_decay', 'manual_calibration')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fields_farm ON fields(farm_id);
CREATE INDEX IF NOT EXISTS idx_evidence_decision_attribute ON evidence_items(decision_id, attribute_name);
CREATE INDEX IF NOT EXISTS idx_decisions_farm_type_time ON decisions(farm_id, decision_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_decision ON decision_candidates(decision_id);
CREATE INDEX IF NOT EXISTS idx_acer_action_type ON acer_records(action_id, decision_type, eligible_for_adaptation);
CREATE INDEX IF NOT EXISTS idx_acer_features_name_value ON acer_context_features(feature_name, normalized_value, text_value);
CREATE INDEX IF NOT EXISTS idx_relationship_action_type ON action_context_relationships(action_id, decision_type);
CREATE INDEX IF NOT EXISTS idx_attribution_acer_selected ON cnda_attributions(acer_id, selected);

INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
