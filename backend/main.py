"""AgroNexus AI FastAPI Backend — Complete V2 Frozen Adaptive Decision API."""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
import hashlib
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.database import connect, initialize_database
from services.adaptive_engine import (
    create_decision,
    evaluate_actions,
    get_active_erp_profile,
    get_scoring_config,
    record_outcome,
    update_scoring_config,
)
from services.benchmark import run_benchmark_suite, run_guided_closed_loop_demo
from services.evidence_providers import (
    list_locations,
    lookup_soil_and_weather_evidence,
    recommend_top_crops_and_plan,
)
from services.seed import seed_database
from ml.disease_evidence import analyze_disease_evidence
from auth import current_user, create_token, hash_password, verify_password
from config import ALLOWED_ORIGINS, AUTH_MODE, JWT_TTL_MINUTES, RESET_TOKEN_TTL_MINUTES, RATE_LIMIT_PER_MINUTE
from services.weather import get_weather

_rate_buckets: dict[str, list[float]] = {}


def rate_limit(request: Request):
    now = time.time()
    key = request.client.host if request.client else "unknown"
    calls = [stamp for stamp in _rate_buckets.get(key, []) if now - stamp < 60]
    if len(calls) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Too many requests; try again shortly")
    calls.append(now)
    _rate_buckets[key] = calls


class AuthRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=254)
    username: str | None = Field(default=None, min_length=3, max_length=40)
    phone: str | None = Field(default=None, min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class ResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class ResetConfirmRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class SoilTestRequest(BaseModel):
    farm_id: str
    ph: float | None = Field(default=None, ge=0, le=14)
    nitrogen: float | None = Field(default=None, ge=0)
    phosphorus: float | None = Field(default=None, ge=0)
    potassium: float | None = Field(default=None, ge=0)
    source: str = Field(default="farmer_input", max_length=100)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    with connect() as connection:
        seed_database(connection)
    yield


app = FastAPI(
    title="AgroNexus AI API",
    version="2.0.0",
    description="Software-only agricultural decision support for crop planning, monitoring, recommendations, and outcome learning.",
    lifespan=lifespan,
)


async def _rate_dispatch(request: Request, call_next):
    if request.url.path not in {"/api/health", "/docs", "/openapi.json"}:
        rate_limit(request)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    BaseHTTPMiddleware,
    dispatch=_rate_dispatch,
)


class FarmRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    state_name: str | None = None
    district_name: str | None = None
    village_name: str | None = None
    field_name: str = Field(default="Main field", min_length=2, max_length=100)
    soil_type: str | None = "loamy"
    water_source: str | None = "Borewell & Rainfed"
    additional_constraints: str | None = ""
    area_hectares: float | None = Field(default=None, gt=0)
    budget: float | None = Field(default=50000.0, ge=0)
    season: str | None = "Kharif"
    latitude: float | None = Field(default=11.60, ge=-90, le=90)
    longitude: float | None = Field(default=76.08, ge=-180, le=180)


class CropRecommendRequest(BaseModel):
    state_name: str | None = "Kerala"
    district_name: str | None = "Wayanad"
    village_name: str | None = "Achooranam"
    soil_type: str = "loamy"
    water_source: str = "Borewell & Rainfed"
    area_hectares: float = 2.0
    selected_crop: str | None = None
    crop_stage: str = "flowering"
    budget: float = 50000.0
    season: str = "Kharif"


class DiseaseImageEvidenceRequest(BaseModel):
    crop: str = "Tomato"
    crop_stage: str = "flowering"
    sample_id: str | None = None
    image_name: str | None = None


class DecisionRequest(BaseModel):
    farm_id: str
    field_id: str | None = None
    decision_type: Literal[
        "disease_intervention",
        "fertilizer_recommendation",
        "irrigation_planning",
        "crop_selection",
    ] = "disease_intervention"
    crop: str = Field(default="Tomato", min_length=2, max_length=60)
    crop_stage: str = Field(default="flowering", min_length=2, max_length=60)
    disease_severity: Literal["none", "low", "moderate", "high"] = "moderate"
    rain_probability: float = Field(default=25.0, ge=0, le=100)
    air_humidity: float = Field(default=68.0, ge=0, le=100)
    temperature: float = Field(default=28.0, ge=-5, le=55)
    soil_fertility: float = Field(default=0.65, ge=0, le=1)
    budget: float = Field(default=500.0, ge=0)
    resources: str = "Labour and hand sprayer available"
    notes: str = ""
    region: str | None = None
    season: str | None = None
    scope: dict[str, Any] | None = None
    has_crop_image: bool = False
    weather_age_hours: float = Field(default=1.0, ge=0)
    weather_distance_km: float = Field(default=1.5, ge=0)
    enforce_inclusion_floor: bool = True


class OutcomeRequest(BaseModel):
    observed_outcome: float = Field(ge=0, le=100)
    outcome_status: Literal["improved", "unchanged", "worse", "unknown"]
    notes: str = ""
    outcome_measure_quality: float = Field(default=0.88, ge=0, le=1)
    feedback_completeness: float = Field(default=0.88, ge=0, le=1)


class ScoringConfigRequest(BaseModel):
    alpha_global: float | None = Field(default=None, ge=0, le=1)
    alpha_context: float | None = Field(default=None, ge=0, le=1)
    alpha_sufficiency: float | None = Field(default=None, ge=0, le=1)
    delta_risk: float | None = Field(default=None, ge=0, le=1)
    delta_cost: float | None = Field(default=None, ge=0, le=1)
    delta_uncertainty: float | None = Field(default=None, ge=0, le=1)
    shrinkage_lambda_0: float | None = Field(default=None, gt=0, le=50)
    kernel_sigma: float | None = Field(default=None, gt=0.05, le=2.0)


class BenchmarkRequest(BaseModel):
    cycles: int = Field(default=30, ge=10, le=100)
    seed: int = Field(default=42)


def _bad_request(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


@app.post("/api/auth/register", status_code=201)
def register(payload: AuthRequest) -> dict[str, Any]:
    email = payload.email.strip().lower() if payload.email else None
    username = payload.username.strip().lower() if payload.username else None
    phone = payload.phone.strip() if payload.phone else None
    if not email:
        raise HTTPException(status_code=422, detail="Email is required when creating an account")
    if not username:
        username = email.split("@", 1)[0] if email else None
    user_id = str(uuid.uuid4())
    try:
        with connect() as db:
            db.execute(
                "INSERT INTO users(user_id, email, username, phone, password_hash) VALUES (?, ?, ?, ?, ?)",
                (user_id, email, username, phone, hash_password(payload.password)),
            )
        return {
            "user_id": user_id,
            "email": email,
            "username": username,
            "phone": phone,
            "role": "farmer",
            "access_token": create_token(user_id, "farmer", JWT_TTL_MINUTES * 60),
        }
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email, username, or phone is already registered")


@app.post("/api/auth/login")
def login(payload: AuthRequest) -> dict[str, Any]:
    identifier = (payload.email or payload.username or payload.phone or "").strip().lower()
    if not identifier:
        raise HTTPException(status_code=422, detail="Enter your email, username, or phone")
    with connect() as db:
        user = db.execute(
            "SELECT * FROM users WHERE lower(email) = ? OR lower(username) = ? OR phone = ?",
            (identifier, identifier, identifier),
        ).fetchone()
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "username": user["username"],
        "phone": user["phone"],
        "role": user["role"],
        "access_token": create_token(user["user_id"], user["role"], JWT_TTL_MINUTES * 60),
    }


@app.post("/api/auth/password-reset/request")
def request_password_reset(payload: ResetRequest) -> dict[str, Any]:
    with connect() as db:
        user = db.execute("SELECT user_id FROM users WHERE email = ?", (payload.email.strip().lower(),)).fetchone()
        if not user:
            return {"status": "accepted"}
        raw = secrets.token_urlsafe(32)
        db.execute("INSERT INTO password_reset_tokens(token_hash, user_id, expires_at) VALUES (?, ?, ?)", (hashlib.sha256(raw.encode()).hexdigest(), user["user_id"], time.time() + RESET_TOKEN_TTL_MINUTES * 60))
    # Never send by email. Returning it is intentionally limited to local/demo mode.
    return {"status": "accepted", **({"reset_token": raw} if AUTH_MODE != "required" else {})}


@app.post("/api/auth/password-reset/confirm")
def confirm_password_reset(payload: ResetConfirmRequest) -> dict[str, str]:
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    with connect() as db:
        row = db.execute("SELECT * FROM password_reset_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?", (token_hash, time.time())).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        db.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (hash_password(payload.password), row["user_id"]))
        db.execute("UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP WHERE token_hash = ?", (token_hash,))
    return {"status": "password_updated"}


@app.get("/api/weather")
def weather(latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180)) -> dict[str, Any]:
    return get_weather(latitude, longitude)


@app.get("/api/health")
def health() -> dict[str, Any]:
    with connect() as connection:
        seed_database(connection)
        erp_rows = connection.execute(
            "SELECT decision_type, version, sufficiency_threshold, inclusion_floor FROM erp_profiles WHERE is_active = 1"
        ).fetchall()
        acer_count = connection.execute("SELECT COUNT(*) AS cnt FROM acer_records").fetchone()["cnt"]
    return {
        "status": "ok",
        "service": "AgroNexus AI V2 Adaptive Decision API",
        "version": "2.0.0",
        "software_only": True,
        "active_erp_profiles": [dict(r) for r in erp_rows],
        "total_acer_records": acer_count,
        "scoring_config": get_scoring_config(),
    }


@app.get("/api/config/scoring")
def read_scoring_config() -> dict[str, float]:
    return get_scoring_config()


@app.put("/api/config/scoring")
def modify_scoring_config(payload: ScoringConfigRequest) -> dict[str, float]:
    return update_scoring_config(payload.model_dump(exclude_none=True))


@app.get("/api/locations")
def get_locations(
    state_name: str | None = Query(default=None),
    district_name: str | None = Query(default=None),
    village_name: str | None = Query(default=None),
) -> dict[str, Any]:
    loc_lists = list_locations(state_name=state_name, district_name=district_name)
    soil_evidence = lookup_soil_and_weather_evidence(
        state_name=state_name,
        district_name=district_name,
        village_name=village_name,
    )
    return {
        **loc_lists,
        "soil_evidence": soil_evidence,
        "soil_preview": soil_evidence,
    }


@app.get("/api/crop-intelligence")
def get_crop_intelligence(
    state_name: str | None = Query(default="Kerala"),
    district_name: str | None = Query(default="Wayanad"),
    village_name: str | None = Query(default="Achooranam"),
    soil_type: str = Query(default="loamy"),
    water_source: str = Query(default="Borewell & Rainfed"),
    area_hectares: float = Query(default=2.0),
    selected_crop: str | None = Query(default=None),
    crop_stage: str = Query(default="flowering"),
    budget: float = Query(default=50000.0),
    season: str = Query(default="Kharif"),
) -> dict[str, Any]:
    return recommend_top_crops_and_plan(
        state_name=state_name,
        district_name=district_name,
        village_name=village_name,
        soil_type=soil_type,
        water_source=water_source,
        area_hectares=area_hectares,
        selected_crop=selected_crop,
        crop_stage=crop_stage,
        budget=budget,
        season=season,
    )


@app.post("/api/evidence/recommend-crops")
def post_recommend_crops(payload: CropRecommendRequest) -> dict[str, Any]:
    return recommend_top_crops_and_plan(
        state_name=payload.state_name,
        district_name=payload.district_name,
        village_name=payload.village_name,
        soil_type=payload.soil_type,
        water_source=payload.water_source,
        area_hectares=payload.area_hectares,
        selected_crop=payload.selected_crop,
        crop_stage=payload.crop_stage,
        budget=payload.budget,
        season=payload.season,
    )


@app.post("/api/evidence/image")
def process_disease_image_evidence(payload: DiseaseImageEvidenceRequest) -> dict[str, Any]:
    return analyze_disease_evidence(
        crop=payload.crop,
        crop_stage=payload.crop_stage,
        sample_id=payload.sample_id,
        image_name=payload.image_name,
    )


@app.get("/api/farms")
def list_farms(user: dict[str, Any] | None = Depends(current_user)) -> list[dict[str, Any]]:
    with connect() as connection:
        if user:
            farms = connection.execute("SELECT * FROM farms WHERE owner_id = ? OR ? IN ('admin', 'advisor') ORDER BY created_at DESC", (user["user_id"], user["role"])).fetchall()
        else:
            farms = connection.execute("SELECT * FROM farms ORDER BY created_at DESC").fetchall()
        out = []
        for f in farms:
            fields = connection.execute("SELECT * FROM fields WHERE farm_id = ?", (f["farm_id"],)).fetchall()
            out.append({**dict(f), "fields": [dict(fl) for fl in fields]})
        return out


@app.post("/api/farms", status_code=201)
def create_farm(payload: FarmRequest, user: dict[str, Any] | None = Depends(current_user)) -> dict[str, Any]:
    farm_id, field_id = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        soil_info = lookup_soil_and_weather_evidence(
            state_name=payload.state_name,
            district_name=payload.district_name,
            village_name=payload.village_name,
        )
        with connect() as connection:
            seed_database(connection)
            connection.execute(
                """INSERT INTO farms
                   (farm_id, name, owner_id, state_name, district_name, village_name, latitude, longitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    farm_id,
                    payload.name,
                    user["user_id"] if user else None,
                    payload.state_name,
                    payload.district_name,
                    payload.village_name,
                    payload.latitude,
                    payload.longitude,
                ),
            )
            connection.execute(
                """INSERT INTO fields
                   (field_id, farm_id, name, soil_type, area_hectares, latitude, longitude)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    field_id,
                    farm_id,
                    payload.field_name,
                    payload.soil_type,
                    payload.area_hectares,
                    payload.latitude,
                    payload.longitude,
                ),
            )
        return {
            "farm_id": farm_id,
            "field_id": field_id,
            "budget": payload.budget,
            "season": payload.season,
            "soil_evidence": soil_info,
        }
    except sqlite3.Error as error:
        raise _bad_request(error) from error


@app.post("/api/soil-tests", status_code=201)
def create_soil_test(payload: SoilTestRequest, user: dict[str, Any] | None = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        farm = db.execute("SELECT farm_id, owner_id FROM farms WHERE farm_id = ?", (payload.farm_id,)).fetchone()
        if not farm or (user and user["role"] == "farmer" and farm["owner_id"] != user["user_id"]):
            raise HTTPException(status_code=404, detail="Farm not found")
        soil_id = str(uuid.uuid4())
        db.execute("INSERT INTO soil_tests(soil_test_id, farm_id, owner_id, ph, nitrogen, phosphorus, potassium, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (soil_id, payload.farm_id, user["user_id"] if user else None, payload.ph, payload.nitrogen, payload.phosphorus, payload.potassium, payload.source))
    return {"soil_test_id": soil_id, **payload.model_dump()}


@app.get("/api/erp/{decision_type}")
def get_erp_details(decision_type: str) -> dict[str, Any]:
    try:
        with connect() as connection:
            seed_database(connection)
            active = get_active_erp_profile(connection, decision_type=decision_type)
            history = connection.execute(
                """SELECT erp_profile_id, version, sufficiency_threshold, inclusion_floor,
                          is_active, created_at, created_by
                   FROM erp_profiles
                   WHERE decision_type = ?
                   ORDER BY version DESC""",
                (decision_type,),
            ).fetchall()
            logs = connection.execute(
                """SELECT l.*, r.attribute_name
                   FROM erp_update_logs l
                   JOIN erp_requirements r ON l.erp_requirement_id = r.erp_requirement_id
                   JOIN erp_profiles p ON r.erp_profile_id = p.erp_profile_id
                   WHERE p.decision_type = ?
                   ORDER BY l.created_at DESC LIMIT 50""",
                (decision_type,),
            ).fetchall()
            return {
                "active_profile": active["profile"],
                "requirements": active["requirements"],
                "version_history": [dict(h) for h in history],
                "update_logs": [dict(lg) for lg in logs],
            }
    except (sqlite3.Error, ValueError) as error:
        raise _bad_request(error) from error


@app.post("/api/decisions", status_code=201)
def make_decision(payload: DecisionRequest, user: dict[str, Any] | None = Depends(current_user)) -> dict[str, Any]:
    if user and user["role"] == "farmer":
        with connect() as db:
            owned = db.execute("SELECT 1 FROM farms WHERE farm_id = ? AND owner_id = ?", (payload.farm_id, user["user_id"])).fetchone()
        if not owned:
            raise HTTPException(status_code=404, detail="Farm not found")
    context = {
        "crop": payload.crop,
        "crop_stage": payload.crop_stage,
        "disease_severity": payload.disease_severity,
        "rain_probability": payload.rain_probability,
        "weather_rain_probability": payload.rain_probability,
        "air_humidity": payload.air_humidity,
        "temperature": payload.temperature,
        "soil_fertility": payload.soil_fertility,
        "budget": payload.budget,
        "farmer_budget": payload.budget,
        "resources": payload.resources,
        "notes": payload.notes,
        "region": payload.region,
        "season": payload.season,
        "scope": {
            **(payload.scope or {}),
            "farm_id": payload.farm_id,
            "field_id": payload.field_id,
            "region": payload.region or (payload.scope or {}).get("region"),
            "season": payload.season or (payload.scope or {}).get("season"),
            "crop_stage": payload.crop_stage,
        },
    }
    evidence = [
        {"attribute": "crop", "value": payload.crop, "quality": 0.95, "reliability": 0.90},
        {"attribute": "crop_stage", "value": payload.crop_stage, "quality": 0.92, "reliability": 0.88},
        {"attribute": "disease_severity", "value": payload.disease_severity, "quality": 0.90, "reliability": 0.90},
        {
            "attribute": "weather_rain_probability",
            "value": payload.rain_probability,
            "unit": "percent",
            "quality": 0.95,
            "reliability": 0.92,
            "age_hours": payload.weather_age_hours,
            "distance_km": payload.weather_distance_km,
            "source_id": "agera5-weather-service-v1",
        },
        {
            "attribute": "air_humidity",
            "value": payload.air_humidity,
            "unit": "percent",
            "quality": 0.92,
            "reliability": 0.90,
            "age_hours": payload.weather_age_hours,
            "distance_km": payload.weather_distance_km,
            "source_id": "agera5-weather-service-v1",
        },
        {
            "attribute": "temperature",
            "value": payload.temperature,
            "unit": "celsius",
            "quality": 0.90,
            "reliability": 0.90,
            "age_hours": payload.weather_age_hours,
            "distance_km": payload.weather_distance_km,
            "source_id": "agera5-weather-service-v1",
        },
        {
            "attribute": "soil_fertility",
            "value": payload.soil_fertility,
            "quality": 0.88,
            "reliability": 0.90,
            "source_id": "south-india-soil-master-v4",
        },
        {
            "attribute": "farm_resources",
            "value": payload.resources or "not recorded",
            "quality": 0.85,
            "reliability": 0.85,
        },
        {
            "attribute": "farmer_budget",
            "value": payload.budget,
            "unit": "INR",
            "quality": 0.92,
            "reliability": 0.90,
        },
        {
            "attribute": "auxiliary_wind_gust",
            "value": 14.0,
            "unit": "km/h",
            "quality": 0.80,
            "reliability": 0.80,
            "age_hours": payload.weather_age_hours,
            "distance_km": payload.weather_distance_km,
        },
        {
            "attribute": "cosmetic_leaf_gloss",
            "value": 0.5,
            "quality": 0.75,
            "reliability": 0.75,
        },
    ]
    if payload.has_crop_image:
        evidence.append({"attribute": "crop_image", "value": "uploaded", "quality": 0.80, "reliability": 0.80})

    try:
        with connect() as connection:
            seed_database(connection)
            return create_decision(
                connection=connection,
                farm_id=payload.farm_id,
                field_id=payload.field_id,
                context=context,
                evidence=evidence,
                decision_type=payload.decision_type,
                enforce_inclusion_floor=payload.enforce_inclusion_floor,
            )
    except (sqlite3.Error, ValueError) as error:
        raise _bad_request(error) from error


@app.get("/api/decisions")
def list_decisions(farm_id: str | None = Query(default=None), limit: int = Query(default=25, le=100)) -> list[dict[str, Any]]:
    with connect() as connection:
        if farm_id:
            rows = connection.execute(
                """SELECT d.*, a.name AS action_name
                   FROM decisions d
                   LEFT JOIN actions a ON d.selected_action_id = a.action_id
                   WHERE d.farm_id = ?
                   ORDER BY d.created_at DESC LIMIT ?""",
                (farm_id, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT d.*, a.name AS action_name
                   FROM decisions d
                   LEFT JOIN actions a ON d.selected_action_id = a.action_id
                   ORDER BY d.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/decisions/{decision_id}")
def get_decision_detail(decision_id: str) -> dict[str, Any]:
    with connect() as connection:
        decision = connection.execute("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        if not decision:
            raise HTTPException(status_code=404, detail="Decision not found.")
        candidates = connection.execute(
            """SELECT c.*, a.name, a.description
               FROM decision_candidates c
               JOIN actions a ON c.action_id = a.action_id
               WHERE c.decision_id = ?
               ORDER BY c.is_feasible DESC, c.final_score DESC""",
            (decision_id,),
        ).fetchall()
        acer = connection.execute("SELECT * FROM acer_records WHERE decision_id = ?", (decision_id,)).fetchone()
        cnda = []
        if acer:
            cnda_rows = connection.execute(
                "SELECT * FROM cnda_attributions WHERE acer_id = ? ORDER BY ABS(association_value) DESC",
                (acer["acer_id"],),
            ).fetchall()
            cnda = [dict(r) for r in cnda_rows]
        evidence_rows = connection.execute(
            """SELECT evidence_id, source_id, attribute_name, value_json, unit,
                      quality_score, reliability_score, normalized_score, captured_at,
                      provenance_json
               FROM evidence_items WHERE decision_id = ?
               ORDER BY attribute_name""",
            (decision_id,),
        ).fetchall()
        sufficiency = connection.execute(
            """SELECT s.*, d.attribute_name, d.evidence_score, d.minimum_score,
                      d.weighted_deficit, d.acquisition_priority
               FROM evidence_sufficiency_results s
               LEFT JOIN evidence_deficits d ON d.sufficiency_result_id = s.sufficiency_result_id
               WHERE s.decision_id = ?""",
            (decision_id,),
        ).fetchall()
        trace = json.loads(decision["decision_trace_json"] or "{}")
        return {
            "decision": dict(decision),
            "context": json.loads(decision["context_json"]),
            "trace": trace,
            "candidates": [dict(c) for c in candidates],
            "acer": dict(acer) if acer else None,
            "cnda_attributions": cnda,
            "explanation": trace.get("explanation", {}),
            "evidence_used": [dict(item) for item in evidence_rows],
            "evidence_sufficiency": [dict(item) for item in sufficiency],
        }


@app.post("/api/decisions/{decision_id}/outcome")
def submit_outcome(decision_id: str, payload: OutcomeRequest) -> dict[str, Any]:
    try:
        with connect() as connection:
            seed_database(connection)
            dec_pre = connection.execute(
                "SELECT * FROM decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
            dt_pre = str(dec_pre["decision_type"] or "disease_intervention") if dec_pre else "disease_intervention"
            erp_before_bundle = get_active_erp_profile(connection, decision_type=dt_pre)
            erp_weights_before = {r["attribute_name"]: round(float(r["weight"]), 4) for r in erp_before_bundle["requirements"]}

            outcome_res = record_outcome(connection, decision_id, **payload.model_dump())

            dec_row = connection.execute(
                "SELECT * FROM decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()
            if dec_row:
                ctx = json.loads(dec_row["context_json"] or "{}")
                dt = str(dec_row["decision_type"] or "disease_intervention")
                suff = float(dec_row["evidence_sufficiency_score"] or 0.85)
                erp_bundle = get_active_erp_profile(connection, decision_type=dt)
                erp_weights = {r["attribute_name"]: round(float(r["weight"]), 4) for r in erp_bundle["requirements"]}
                inc_floor = float(erp_bundle["profile"]["inclusion_floor"])

                re_eval = evaluate_actions(
                    connection=connection,
                    decision_id=decision_id,
                    context=ctx,
                    sufficiency=suff,
                    decision_type=dt,
                    erp_weights=erp_weights,
                    inclusion_floor=inc_floor,
                )
                prev_action_id = str(dec_row["selected_action_id"])
                feasible_cands = [c for c in re_eval["candidates"] if c["feasible"]]
                top_cand = re_eval["selected"]
                # If the previous treatment performed worse than expected, highlight the best alternative intervention
                if (
                    top_cand
                    and top_cand["action_id"] == prev_action_id
                    and outcome_res["deviation"] <= -10.0
                    and len(feasible_cands) > 1
                ):
                    alt_cands = [c for c in feasible_cands if c["action_id"] != prev_action_id]
                    suggested_new = alt_cands[0] if alt_cands else top_cand
                else:
                    suggested_new = top_cand

                outcome_res["suggested_new_treatment"] = suggested_new
                outcome_res["updated_alternatives"] = re_eval["candidates"]
                outcome_res["context_summary"] = ctx
                outcome_res["erp_weights_before"] = erp_weights_before
                outcome_res["erp_weights_after"] = erp_weights
                outcome_res["erp_version_after"] = erp_bundle["profile"]["version"]

            return outcome_res
    except (sqlite3.Error, ValueError) as error:
        raise _bad_request(error) from error


@app.get("/api/acer")
def get_acer_ledger(decision_type: str = Query(default="disease_intervention")) -> dict[str, Any]:
    with connect() as connection:
        seed_database(connection)
        acers = connection.execute(
            """SELECT r.*, a.name AS action_name
               FROM acer_records r
               JOIN actions a ON r.action_id = a.action_id
               WHERE r.decision_type = ?
               ORDER BY r.created_at DESC LIMIT 50""",
            (decision_type,),
        ).fetchall()
        relationships = connection.execute(
            """SELECT rel.*, a.name AS action_name
               FROM action_context_relationships rel
               JOIN actions a ON rel.action_id = a.action_id
               WHERE rel.decision_type = ?
               ORDER BY rel.updated_at DESC""",
            (decision_type,),
        ).fetchall()
        r_logs = connection.execute(
            """SELECT l.*, rel.context_signature, a.name AS action_name
               FROM relationship_update_logs l
               JOIN action_context_relationships rel ON l.relationship_id = rel.relationship_id
               JOIN actions a ON rel.action_id = a.action_id
               WHERE rel.decision_type = ?
               ORDER BY l.created_at DESC LIMIT 40""",
            (decision_type,),
        ).fetchall()
        erp_logs = connection.execute(
            """SELECT l.*, req.attribute_name, p.version AS erp_version
               FROM erp_update_logs l
               JOIN erp_requirements req ON l.erp_requirement_id = req.erp_requirement_id
               JOIN erp_profiles p ON req.erp_profile_id = p.erp_profile_id
               WHERE p.decision_type = ?
               ORDER BY l.created_at DESC LIMIT 40""",
            (decision_type,),
        ).fetchall()
        return {
            "acer_records": [dict(x) for x in acers],
            "relationships": [dict(x) for x in relationships],
            "relationship_update_logs": [dict(x) for x in r_logs],
            "erp_update_logs": [dict(x) for x in erp_logs],
        }


@app.post("/api/demo/closed-loop")
def execute_closed_loop_demo() -> dict[str, Any]:
    try:
        with connect() as connection:
            seed_database(connection)
            return run_guided_closed_loop_demo(connection)
    except (sqlite3.Error, ValueError) as error:
        raise _bad_request(error) from error


@app.post("/api/benchmarks/run")
def execute_benchmarks(payload: BenchmarkRequest) -> dict[str, Any]:
    try:
        return run_benchmark_suite(cycles=payload.cycles, seed=payload.seed)
    except Exception as error:
        raise _bad_request(error) from error
