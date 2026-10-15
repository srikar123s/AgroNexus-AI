"""Seed safe, non-ML decision types, ERP profiles, evidence sources, and action catalogs."""

from __future__ import annotations

import json
import sqlite3
import uuid


def seed_database(connection: sqlite3.Connection) -> None:
    decision_types = [
        ("disease_intervention", "Disease intervention", "Context-aware crop disease management and sanitation support", 0.70),
        ("fertilizer_recommendation", "Fertilizer management", "Context-conditioned nutrient split and amendment selection", 0.68),
        ("irrigation_planning", "Irrigation scheduling", "Moisture-critical stage and rain-adjusted irrigation support", 0.68),
        ("crop_selection", "Crop suitability selection", "Seasonal, soil, and water-aligned crop selection support", 0.65),
    ]
    for dt_id, name, desc, threshold in decision_types:
        connection.execute(
            """INSERT OR IGNORE INTO decision_types
            (decision_type, display_name, description, sufficiency_threshold)
            VALUES (?, ?, ?, ?)""",
            (dt_id, name, desc, threshold),
        )

    sources = [
        ("farmer-input-v1", "Farmer field observation", "farmer_input", 0.85, "1.0"),
        ("south-india-soil-master-v4", "South India Soil Master (Village v4 / District v3)", "dataset", 0.90, "4.0"),
        ("agera5-weather-service-v1", "Copernicus AgERA5 Weather Time-Series Service", "api", 0.92, "1.11"),
        ("dct-rag-kb-v1", "ICAR/TNAU Decision-Contextualized RAG Knowledge Base", "derived", 0.88, "1.0"),
    ]
    for src_id, name, src_type, rel, ver in sources:
        connection.execute(
            """INSERT OR IGNORE INTO evidence_sources
            (source_id, name, source_type, default_reliability, version)
            VALUES (?, ?, ?, ?, ?)""",
            (src_id, name, src_type, rel, ver),
        )

    # ERP specifications per decision type:
    # (attribute_name, weight, required, minimum_score, temporal_validity_hours, spatial_validity_km, cost_factor, priority)
    erp_specs: dict[str, list[tuple[str, float, int, float, float | None, float | None, float, int]]] = {
        "disease_intervention": [
            ("crop", 0.14, 1, 0.70, 24 * 365, None, 1.0, 10),
            ("crop_stage", 0.12, 1, 0.65, 30 * 24, None, 1.0, 9),
            ("disease_severity", 0.24, 1, 0.65, 7 * 24, None, 1.0, 10),
            ("weather_rain_probability", 0.20, 1, 0.65, 24.0, 25.0, 1.0, 9),
            ("air_humidity", 0.08, 0, 0.50, 24.0, 25.0, 1.0, 7),
            ("temperature", 0.06, 0, 0.50, 24.0, 30.0, 1.0, 5),
            ("soil_fertility", 0.06, 0, 0.50, 90 * 24, 20.0, 1.2, 4),
            ("farmer_budget", 0.08, 0, 0.50, 30 * 24, None, 1.0, 6),
            ("farm_resources", 0.06, 0, 0.50, 30 * 24, None, 1.0, 5),
            # Optional auxiliary attributes near/below inclusion_floor (0.05) to demonstrate workload pruning:
            ("auxiliary_wind_gust", 0.055, 0, 0.40, 12.0, 15.0, 1.5, 2),
            ("cosmetic_leaf_gloss", 0.035, 0, 0.40, 48.0, None, 2.0, 1),
        ],
        "fertilizer_recommendation": [
            ("crop", 0.15, 1, 0.70, 24 * 365, None, 1.0, 10),
            ("crop_stage", 0.15, 1, 0.65, 30 * 24, None, 1.0, 9),
            ("soil_fertility", 0.26, 1, 0.65, 180 * 24, 20.0, 1.0, 10),
            ("weather_rain_probability", 0.18, 1, 0.60, 24.0, 25.0, 1.0, 8),
            ("air_humidity", 0.08, 0, 0.50, 24.0, 25.0, 1.0, 5),
            ("temperature", 0.06, 0, 0.50, 24.0, 30.0, 1.0, 4),
            ("farmer_budget", 0.08, 0, 0.50, 30 * 24, None, 1.0, 6),
            ("cosmetic_leaf_gloss", 0.04, 0, 0.40, 48.0, None, 2.0, 1),
        ],
        "irrigation_planning": [
            ("crop", 0.15, 1, 0.70, 24 * 365, None, 1.0, 10),
            ("crop_stage", 0.18, 1, 0.65, 30 * 24, None, 1.0, 9),
            ("weather_rain_probability", 0.25, 1, 0.65, 24.0, 25.0, 1.0, 10),
            ("temperature", 0.14, 1, 0.60, 24.0, 30.0, 1.0, 8),
            ("air_humidity", 0.12, 0, 0.50, 24.0, 25.0, 1.0, 7),
            ("soil_fertility", 0.08, 0, 0.50, 90 * 24, 20.0, 1.2, 4),
            ("farmer_budget", 0.08, 0, 0.50, 30 * 24, None, 1.0, 5),
        ],
        "crop_selection": [
            ("crop", 0.12, 1, 0.65, 24 * 365, None, 1.0, 8),
            ("soil_fertility", 0.28, 1, 0.65, 180 * 24, 25.0, 1.0, 10),
            ("weather_rain_probability", 0.22, 1, 0.60, 72.0, 35.0, 1.0, 9),
            ("temperature", 0.16, 1, 0.60, 72.0, 35.0, 1.0, 8),
            ("air_humidity", 0.10, 0, 0.50, 72.0, 35.0, 1.0, 6),
            ("farmer_budget", 0.12, 0, 0.50, 30 * 24, None, 1.0, 7),
        ],
    }

    for dt_id, req_list in erp_specs.items():
        profile = connection.execute(
            "SELECT erp_profile_id FROM erp_profiles WHERE decision_type = ? AND is_active = 1",
            (dt_id,),
        ).fetchone()
        if not profile:
            profile_id = str(uuid.uuid4())
            threshold = 0.70 if dt_id == "disease_intervention" else 0.68
            connection.execute(
                """INSERT INTO erp_profiles
                (erp_profile_id, decision_type, version, sufficiency_threshold, inclusion_floor)
                VALUES (?, ?, 1, ?, 0.05)""",
                (profile_id, dt_id, threshold),
            )
            for attr, weight, req, min_s, temp_h, spat_km, cost_f, prio in req_list:
                connection.execute(
                    """INSERT INTO erp_requirements
                    (erp_requirement_id, erp_profile_id, attribute_name, weight, required,
                     minimum_score, temporal_validity_hours, spatial_validity_km,
                     acquisition_cost_factor, acquisition_priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), profile_id, attr, weight, req, min_s, temp_h, spat_km, cost_f, prio),
                )
        else:
            # Ensure new V2 attributes exist on existing disease_intervention profile
            profile_id = profile["erp_profile_id"]
            for attr, weight, req, min_s, temp_h, spat_km, cost_f, prio in req_list:
                connection.execute(
                    """INSERT OR IGNORE INTO erp_requirements
                    (erp_requirement_id, erp_profile_id, attribute_name, weight, required,
                     minimum_score, temporal_validity_hours, spatial_validity_km,
                     acquisition_cost_factor, acquisition_priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), profile_id, attr, weight, req, min_s, temp_h, spat_km, cost_f, prio),
                )

    actions_catalog = [
        # Disease intervention actions
        (
            "disease_intervention",
            "Inspect and monitor",
            "Record symptoms, isolate affected plants where practical, and monitor canopy microclimate.",
            55.0,
            0.10,
            0.0,
            {},
        ),
        (
            "disease_intervention",
            "Remove visibly affected leaves",
            "Sanitize canopy by removing and disposing of visibly infected leaves to reduce spore load.",
            65.0,
            0.18,
            80.0,
            {"requires_labor": True},
        ),
        (
            "disease_intervention",
            "Apply systemic bio-fungicide and canopy sanitation",
            "Use rain-fast systemic/translaminar bio-protection with lower-leaf pruning; resilient under humid or moderate rain windows.",
            75.0,
            0.20,
            260.0,
            {"requires_labor": True, "max_rain_probability": 85},
        ),
        (
            "disease_intervention",
            "Apply locally approved fungicide in a dry window",
            "Use a contact/broad-spectrum product approved for the crop and region during a dry application window.",
            80.0,
            0.30,
            350.0,
            {"max_rain_probability": 50},
        ),
        (
            "disease_intervention",
            "Request agronomist review",
            "Escalate for a local agronomist or extension officer review when evidence or risk is uncertain.",
            60.0,
            0.05,
            0.0,
            {},
        ),
        # Fertilizer actions
        (
            "fertilizer_recommendation",
            "Split neem-coated urea + basal P/K incorporation",
            "Apply slow-release nitrogen in split doses with root-zone phosphorus and potassium incorporation.",
            78.0,
            0.16,
            420.0,
            {"max_rain_probability": 75},
        ),
        (
            "fertilizer_recommendation",
            "Foliar water-soluble NPK micronutrient spray",
            "Rapid nutrient correction during flowering/fruiting under low-leaching dry foliage conditions.",
            74.0,
            0.22,
            300.0,
            {"max_rain_probability": 45},
        ),
        (
            "fertilizer_recommendation",
            "Defer top-dressing and apply organic compost mulch",
            "Hold soluble fertilizer during heavy rain risk and stabilize root-zone nutrients with organic amendment.",
            64.0,
            0.08,
            120.0,
            {},
        ),
        # Irrigation actions
        (
            "irrigation_planning",
            "Precision drip / root-zone deficit irrigation",
            "Supply targeted root-zone moisture during critical flowering/fruiting stage without wetting foliage.",
            82.0,
            0.12,
            180.0,
            {"max_rain_probability": 65},
        ),
        (
            "irrigation_planning",
            "Withhold irrigation and open field drainage channels",
            "Prevent waterlogging and collar rot when forecasted rainfall satisfies crop water requirement.",
            70.0,
            0.08,
            50.0,
            {},
        ),
        # Crop selection actions
        (
            "crop_selection",
            "Cultivate primary seasonal high-suitability crop variety",
            "Select top soil-and-rainfall aligned variety with standard agronomic spacing.",
            80.0,
            0.18,
            600.0,
            {},
        ),
        (
            "crop_selection",
            "Cultivate short-duration climate-resilient intercrop",
            "Mitigate rainfall uncertainty and soil nutrient deficit using pulse/oilseed intercropping.",
            72.0,
            0.10,
            350.0,
            {},
        ),
    ]

    for dt_id, name, description, outcome, risk, cost, rules in actions_catalog:
        connection.execute(
            """INSERT OR IGNORE INTO actions
            (action_id, decision_type, name, description, expected_global_outcome,
             default_risk, estimated_cost, applicability_rules_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), dt_id, name, description, outcome, risk, cost, json.dumps(rules)),
        )

    connection.commit()
