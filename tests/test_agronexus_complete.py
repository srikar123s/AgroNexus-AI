from pathlib import Path
import uuid

from fastapi.testclient import TestClient

from backend.database import database as db_mod
from backend.main import app
from backend.services.adaptive_engine import (
    ADIEScoringConfig,
    _active_provider_evidence,
    compute_evidence_components,
    create_decision,
    get_active_erp_profile,
    record_outcome,
    update_scoring_config,
)
from backend.ml.adapters import MODEL_ADAPTERS
from backend.services.benchmark import run_benchmark_suite, run_guided_closed_loop_demo
from backend.services.evidence_providers import (
    haversine_km,
    list_locations,
    lookup_soil_and_weather_evidence,
    retrieve_dct_rag_evidence,
)
from backend.services.seed import seed_database
from backend.services.spatial_cnda import (
    CONTEXT_DIMENSIONS,
    PartitionedACERIndex,
    compute_dimension_weights,
    encode_7d_context,
    vector_from_encoded,
)


def _setup_temp_db(tmp_path: Path, monkeypatch) -> tuple[Path, str, str]:
    test_db = tmp_path / "test_agronexus_v2.db"
    monkeypatch.setattr(db_mod, "DEFAULT_DATABASE_PATH", test_db)
    db_mod.initialize_database(test_db)
    update_scoring_config(ADIEScoringConfig().to_dict())
    farm_id, field_id = str(uuid.uuid4()), str(uuid.uuid4())
    with db_mod.connect(test_db) as conn:
        seed_database(conn)
        conn.execute(
            """INSERT INTO farms (farm_id, name, state_name, district_name, village_name, latitude, longitude)
               VALUES (?, 'Test Farm', 'Kerala', 'Wayanad', 'Achooranam', 11.60, 76.08)""",
            (farm_id,),
        )
        conn.execute(
            """INSERT INTO fields (field_id, farm_id, name, soil_type, area_hectares, latitude, longitude)
               VALUES (?, ?, 'Plot 1', 'loamy', 2.0, 11.60, 76.08)""",
            (field_id, farm_id),
        )
        conn.commit()
    return test_db, farm_id, field_id


def test_a0_temporal_and_spatial_decay():
    fresh_comp = compute_evidence_components(
        {"value": 42.0, "quality": 0.90, "reliability": 0.90, "age_hours": 0.0, "distance_km": 0.0},
        temporal_validity_hours=24.0,
        spatial_validity_km=25.0,
    )
    assert fresh_comp["temporal"] == 1.0
    assert fresh_comp["spatial"] == 1.0
    assert fresh_comp["score"] == 0.81

    aged_comp = compute_evidence_components(
        {"value": 42.0, "quality": 0.90, "reliability": 0.90, "age_hours": 12.0, "distance_km": 12.5},
        temporal_validity_hours=24.0,
        spatial_validity_km=25.0,
    )
    assert aged_comp["temporal"] == 0.5
    assert aged_comp["spatial"] == 0.5
    assert aged_comp["score"] == round(0.81 * 0.25, 4)

    dist = haversine_km(11.0168, 76.9558, 11.0168, 76.9558)
    assert dist == 0.0


def test_7d_context_encoding_and_partitioned_balltree():
    encoded = encode_7d_context(
        {
            "crop": "Tomato",
            "crop_stage": "flowering",
            "disease_severity": "high",
            "weather_rain_probability": 80.0,
            "air_humidity": 85.0,
            "temperature": 30.0,
            "soil_fertility": 0.65,
            "farmer_budget": 1000.0,
        }
    )
    assert set(encoded.keys()) == set(CONTEXT_DIMENSIONS)
    vec = vector_from_encoded(encoded)
    assert len(vec) == 7
    assert all(0.0 <= float(x) <= 1.0 for x in vec)

    records = []
    for i in range(12):
        rec_enc = encode_7d_context(
            {
                "crop": "Tomato",
                "crop_stage": "flowering",
                "disease_severity": "high",
                "weather_rain_probability": 82.0 if i % 2 == 0 else 15.0,
                "air_humidity": 88.0 if i % 2 == 0 else 55.0,
                "temperature": 28.0,
                "soil_fertility": 0.65,
                "farmer_budget": 1000.0,
            }
        )
        records.append(
            {
                "acer_id": f"ACER-{i}",
                "encoded_7d": rec_enc,
                "vector_7d": vector_from_encoded(rec_enc),
                "expected_outcome": 81.0,
                "observed_outcome": 40.0 if i % 2 == 0 else 80.0,
                "deviation": -41.0 if i % 2 == 0 else -1.0,
                "outcome_confidence": 0.85,
            }
        )

    erp_weights = {dim: 1.0 / len(CONTEXT_DIMENSIONS) for dim in CONTEXT_DIMENSIONS}
    erp_weights["weather_rain_probability"] = 0.30
    erp_weights["air_humidity"] = 0.25
    lam = compute_dimension_weights(erp_weights, inclusion_floor=0.05)

    idx = PartitionedACERIndex(records=records, lambda_weights=lam)
    q = idx.query_knn(vec, k=6)
    assert len(q["neighbors"]) == 6
    assert q["balltree_time_us"] >= 0.0
    assert q["linear_time_us"] >= 0.0
    assert q["neighbors"][0]["distance"] <= q["neighbors"][-1]["distance"]


def test_evidence_providers_and_dct_rag():
    locs = list_locations(state_name="Kerala", district_name="Wayanad")
    assert "states" in locs
    assert len(locs["states"]) >= 3

    lookup = lookup_soil_and_weather_evidence(
        state_name="Kerala",
        district_name="Wayanad",
        village_name="Achooranam",
    )
    assert "soil_fertility" in lookup
    assert 0.0 <= lookup["soil_fertility"] <= 1.0

    rag = retrieve_dct_rag_evidence(
        decision_type="disease_intervention",
        context={
            "crop": "Tomato",
            "crop_stage": "flowering",
            "disease_severity": "high",
            "weather_rain_probability": 80.0,
            "air_humidity": 88.0,
        },
        deficits=[{"attribute": "weather_rain_probability"}],
    )
    assert len(rag["documents"]) >= 1
    assert "wash-off" in rag["documents"][0]["guidance"].lower() or "rain-fast" in rag["documents"][0]["guidance"].lower()


def test_active_provider_filter_preserves_required_attributes_and_dummy_model_catalog(tmp_path: Path, monkeypatch):
    test_db, _, _ = _setup_temp_db(tmp_path, monkeypatch)
    with db_mod.connect(test_db) as conn:
        requirements = get_active_erp_profile(conn, "disease_intervention")["requirements"]
        conn.execute("UPDATE evidence_sources SET active = 0 WHERE source_id = 'agera5-weather-service-v1'")
        accepted, excluded = _active_provider_evidence(
            conn,
            [
                {"attribute": "weather_rain_probability", "source_id": "agera5-weather-service-v1", "value": 40},
                {"attribute": "crop", "source_id": "farmer-input-v1", "value": "Tomato"},
            ],
            requirements,
        )
        assert [item["attribute"] for item in accepted] == ["crop"]
        assert excluded[0]["required"] is True
        assert set(MODEL_ADAPTERS) == {
            "disease_classification", "disease_severity", "crop_suitability",
            "fertilizer_suitability", "irrigation_requirement", "yield_prediction",
            "agricultural_risk_prediction",
        }
        assert all(adapter().predict()["dummy"] for adapter in MODEL_ADAPTERS.values())


def test_sample_gated_cnda_regimes_and_joint_update(tmp_path: Path, monkeypatch):
    test_db, farm_id, field_id = _setup_temp_db(tmp_path, monkeypatch)

    with db_mod.connect(test_db) as conn:
        erp_v1 = get_active_erp_profile(conn, "disease_intervention")
        assert erp_v1["profile"]["version"] == 1

        fungicide_row = conn.execute(
            "SELECT action_id, expected_global_outcome FROM actions WHERE name LIKE '%fungicide in a dry window%' LIMIT 1"
        ).fetchone()
        assert fungicide_row is not None

        episodes = [
            {"rain": 15.0, "humidity": 52.0, "observed": 82.0, "status": "improved"},
            {"rain": 42.0, "humidity": 88.0, "observed": 40.0, "status": "worse"},
            {"rain": 18.0, "humidity": 56.0, "observed": 80.0, "status": "improved"},
            {"rain": 44.0, "humidity": 90.0, "observed": 38.0, "status": "worse"},
            {"rain": 40.0, "humidity": 86.0, "observed": 41.0, "status": "worse"},
            # The current ACER is excluded from its own CNDA partition, so
            # attribution starts on the sixth recorded episode.
            {"rain": 38.0, "humidity": 84.0, "observed": 42.0, "status": "worse"},
        ]

        for idx, ep in enumerate(episodes, start=1):
            ctx = {
                "crop": "Tomato",
                "crop_stage": "flowering",
                "disease_severity": "high",
                "rain_probability": ep["rain"],
                "weather_rain_probability": ep["rain"],
                "air_humidity": ep["humidity"],
                "temperature": 28.0,
                "soil_fertility": 0.65,
                "budget": 600.0,
                "farmer_budget": 600.0,
                "resources": "Labour and sprayer",
            }
            ev = [
                {"attribute": "crop", "value": "Tomato", "quality": 0.95, "reliability": 0.92},
                {"attribute": "crop_stage", "value": "flowering", "quality": 0.92, "reliability": 0.90},
                {"attribute": "disease_severity", "value": "high", "quality": 0.92, "reliability": 0.90},
                {"attribute": "weather_rain_probability", "value": ep["rain"], "quality": 0.94, "reliability": 0.92},
                {"attribute": "air_humidity", "value": ep["humidity"], "quality": 0.92, "reliability": 0.90},
                {"attribute": "temperature", "value": 28.0, "quality": 0.90, "reliability": 0.90},
                {"attribute": "soil_fertility", "value": 0.65, "quality": 0.88, "reliability": 0.88},
                {"attribute": "farmer_budget", "value": 600.0, "quality": 0.92, "reliability": 0.90},
                {"attribute": "farm_resources", "value": "Labour and sprayer", "quality": 0.90, "reliability": 0.88},
                {"attribute": "auxiliary_wind_gust", "value": 15.0, "quality": 0.80, "reliability": 0.80},
                {"attribute": "cosmetic_leaf_gloss", "value": 0.50, "quality": 0.75, "reliability": 0.75},
            ]
            dec = create_decision(conn, farm_id, field_id, ctx, ev, decision_type="disease_intervention")
            excluded_names = [x["attribute"] for x in dec["sufficiency"]["excluded_attributes"]]
            assert "cosmetic_leaf_gloss" in excluded_names

            conn.execute(
                "UPDATE decisions SET selected_action_id = ?, expected_outcome = ? WHERE decision_id = ?",
                (fungicide_row["action_id"], float(fungicide_row["expected_global_outcome"]), dec["decision_id"]),
            )
            conn.commit()

            out = record_outcome(
                connection=conn,
                decision_id=dec["decision_id"],
                observed_outcome=ep["observed"],
                outcome_status=ep["status"],
                outcome_measure_quality=0.92,
                feedback_completeness=0.92,
            )

            if idx < 6:
                assert out["cnda"]["status"] == "insufficient_sample_support"
                assert out["cnda"]["sample_count"] == idx - 1
                assert out["adaptive_update"]["r_updated"] is True
                assert out["adaptive_update"]["erp_updated"] is False
            else:
                assert out["cnda"]["status"] == "attributed"
                assert out["cnda"]["regime"] == "5_to_9_damped_attribution"
                assert out["cnda"]["sample_count"] == 5
                assert abs(out["cnda"]["damping_factor_psi"] - (1.0 / 6.0)) < 1e-3
                assert out["adaptive_update"]["r_updated"] is True
                assert out["adaptive_update"]["erp_updated"] is True

        erp_v2 = get_active_erp_profile(conn, "disease_intervention")
        assert erp_v2["profile"]["version"] == 2
        w1 = {r["attribute_name"]: float(r["weight"]) for r in erp_v1["requirements"]}
        w2 = {r["attribute_name"]: float(r["weight"]) for r in erp_v2["requirements"]}
        assert w2["weather_rain_probability"] > w1["weather_rain_probability"]
        assert w2["air_humidity"] > w1["air_humidity"]


def test_closed_loop_demo_and_four_baseline_benchmark(tmp_path: Path, monkeypatch):
    test_db, _, _ = _setup_temp_db(tmp_path, monkeypatch)

    with db_mod.connect(test_db) as conn:
        demo = run_guided_closed_loop_demo(conn)
        assert demo["initial_erp_version"] == 1
        assert demo["final_erp_version"] == 2
        assert demo["final_erp_weights"]["weather_rain_probability"] > demo["initial_erp_weights"]["weather_rain_probability"]
        assert demo["summary"]["recommendation_shifted"] is True
        assert demo["summary"]["subsequent_excluded_count"] >= demo["summary"]["initial_excluded_count"]

    bench = run_benchmark_suite(cycles=24, seed=42)
    b = bench["baselines"]
    assert set(b.keys()) == {
        "fixed_full_evidence",
        "global_action_scoring",
        "context_only_adaptation",
        "agronexus_joint_adaptive",
    }
    joint = b["agronexus_joint_adaptive"]
    ctx_only = b["context_only_adaptation"]
    fixed = b["fixed_full_evidence"]

    # Prove Claim 5: Joint Adaptation beats Context-Only Adaptation AND Fixed Full Evidence
    assert joint["post_warmup_mad"] < ctx_only["post_warmup_mad"]
    assert joint["mean_attributes_fetched"] < ctx_only["mean_attributes_fetched"]
    assert joint["mean_attributes_fetched"] < fixed["mean_attributes_fetched"]
    assert bench["benchmark_targets_verification"]["joint_outperforms_context_only_on_mad"] is True
    assert bench["benchmark_targets_verification"]["joint_outperforms_context_only_on_workload"] is True


def test_fastapi_endpoints(tmp_path: Path, monkeypatch):
    test_db, _, _ = _setup_temp_db(tmp_path, monkeypatch)
    monkeypatch.setattr("backend.main.connect", lambda: db_mod.connect(test_db))
    client = TestClient(app)

    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["version"] == "2.0.0"

    r_cfg = client.get("/api/config/scoring")
    assert r_cfg.status_code == 200
    assert r_cfg.json()["alpha_context"] == 0.36

    r_put_cfg = client.put(
        "/api/config/scoring",
        json={
            "alpha_global": 0.32,
            "alpha_context": 0.34,
            "alpha_sufficiency": 0.18,
            "delta_risk": 0.09,
            "delta_cost": 0.04,
            "delta_uncertainty": 0.03,
            "shrinkage_lambda_0": 3.0,
            "kernel_sigma": 0.30,
        },
    )
    assert r_put_cfg.status_code == 200
    assert r_put_cfg.json()["alpha_global"] == 0.32

    r_erp = client.get("/api/erp/disease_intervention")
    assert r_erp.status_code == 200
    assert len(r_erp.json()["requirements"]) >= 8

    r_demo = client.post("/api/demo/closed-loop")
    assert r_demo.status_code == 200
    assert r_demo.json()["summary"]["recommendation_shifted"] is True

    r_ledger = client.get("/api/acer")
    assert r_ledger.status_code == 200
    assert len(r_ledger.json()["acer_records"]) >= 5
