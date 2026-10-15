"""V2 Frozen Implementation of ERP, Inclusion-Floor Gating, ADIE-1, ACER, Sample-Gated CNDA, and Joint Adaptive Update."""

from __future__ import annotations

import json
import math
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from services.evidence_providers import haversine_km, retrieve_dct_rag_evidence
from services.spatial_cnda import (
    CONTEXT_DIMENSIONS,
    compute_dimension_weights,
    context_signature_from_7d,
    encode_7d_context,
    gaussian_kernel,
    normalize_crop,
    run_sample_gated_cnda,
    vector_from_encoded,
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


def _parse_iso_age_hours(captured_at: str | None, reference_time: datetime | None = None) -> float:
    """Compute elapsed hours between `captured_at` and `reference_time` (defaults to UTC now)."""
    if not captured_at:
        return 0.0
    ref = reference_time or datetime.now(UTC)
    try:
        cleaned = str(captured_at).replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        diff_seconds = (ref - dt).total_seconds()
        return max(0.0, diff_seconds / 3600.0)
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# CONFIGURABLE ADIE-1 SCORING PARAMETERS (V2 REVIEW FIX #2)
# ============================================================

@dataclass
class ADIEScoringConfig:
    alpha_global: float = 0.30
    alpha_context: float = 0.36
    alpha_sufficiency: float = 0.18
    delta_risk: float = 0.09
    delta_cost: float = 0.04
    delta_uncertainty: float = 0.03
    shrinkage_lambda_0: float = 3.0
    kernel_sigma: float = 0.30

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


_ACTIVE_SCORING_CONFIG = ADIEScoringConfig()


def get_scoring_config() -> dict[str, float]:
    return _ACTIVE_SCORING_CONFIG.to_dict()


def update_scoring_config(updates: dict[str, Any]) -> dict[str, float]:
    global _ACTIVE_SCORING_CONFIG
    current = _ACTIVE_SCORING_CONFIG.to_dict()
    for key, val in updates.items():
        if key in current and val is not None:
            current[key] = float(val)
    _ACTIVE_SCORING_CONFIG = ADIEScoringConfig(**current)
    return _ACTIVE_SCORING_CONFIG.to_dict()


# ============================================================
# A0: EVIDENCE NORMALIZATION WITH TEMPORAL & SPATIAL DECAY
# ============================================================

def compute_evidence_components(
    item: dict[str, Any] | None,
    temporal_validity_hours: float | None = None,
    spatial_validity_km: float | None = None,
    farm_lat: float | None = None,
    farm_lon: float | None = None,
) -> dict[str, float]:
    """
    Calculate normalized evidence components:
      q_i in [0, 1], r_i in [0, 1], c_i in [0, 1],
      t_i = max(0, 1 - age_i / tau_i),
      p_i = max(0, 1 - dist_i / rho_i),
      e_i = a_i * (q_i * c_i) * r_i * t_i * p_i
    """
    if not item or item.get("value") in (None, ""):
        return {
            "availability": 0.0,
            "quality": 0.0,
            "reliability": 0.0,
            "confidence": 0.0,
            "temporal": 0.0,
            "spatial": 0.0,
            "score": 0.0,
            "age_hours": 0.0,
            "distance_km": 0.0,
        }

    availability = 1.0
    quality = float(np.clip(float(item.get("quality", 0.85)), 0.0, 1.0))
    reliability = float(np.clip(float(item.get("reliability", 0.85)), 0.0, 1.0))
    confidence = float(np.clip(float(item.get("confidence", 1.0)), 0.0, 1.0))
    conflict_penalty = float(np.clip(float(item.get("conflict_factor", 1.0)), 0.25, 1.0))

    # Temporal decay t_i = max(0, 1 - age_i / tau_i)
    if "age_hours" in item and item["age_hours"] is not None:
        age_hours = max(0.0, float(item["age_hours"]))
    else:
        age_hours = _parse_iso_age_hours(item.get("captured_at"))

    if temporal_validity_hours and temporal_validity_hours > 0:
        temporal_score = max(0.0, 1.0 - (age_hours / float(temporal_validity_hours)))
    else:
        temporal_score = 1.0

    # Spatial decay p_i = max(0, 1 - dist_i / rho_i)
    if "distance_km" in item and item["distance_km"] is not None:
        dist_km: float | None = max(0.0, float(item["distance_km"]))
    else:
        dist_km = haversine_km(farm_lat, farm_lon, item.get("latitude"), item.get("longitude"))

    if spatial_validity_km and spatial_validity_km > 0 and dist_km is not None:
        spatial_score = max(0.0, 1.0 - (dist_km / float(spatial_validity_km)))
    else:
        spatial_score = 1.0

    effective_quality = quality * confidence * conflict_penalty
    composite_score = float(
        np.clip(availability * effective_quality * reliability * temporal_score * spatial_score, 0.0, 1.0)
    )

    return {
        "availability": availability,
        "quality": round(quality, 4),
        "reliability": round(reliability, 4),
        "confidence": round(confidence, 4),
        "temporal": round(float(temporal_score), 4),
        "spatial": round(float(spatial_score), 4),
        "score": round(composite_score, 4),
        "age_hours": round(age_hours, 2),
        "distance_km": round(dist_km or 0.0, 2),
    }


def _evidence_score(item: dict[str, Any]) -> float:
    return compute_evidence_components(item)["score"]


# ============================================================
# A1: ERP SUFFICIENCY & INCLUSION-FLOOR GATING
# ============================================================

def get_active_erp_profile(connection: sqlite3.Connection, decision_type: str = "disease_intervention") -> dict[str, Any]:
    profile = connection.execute(
        """SELECT * FROM erp_profiles
           WHERE decision_type = ? AND is_active = 1
           ORDER BY version DESC LIMIT 1""",
        (decision_type,),
    ).fetchone()
    if not profile:
        raise ValueError(f"No active ERP profile exists for decision_type='{decision_type}'.")

    requirements = connection.execute(
        """SELECT * FROM erp_requirements
           WHERE erp_profile_id = ?
           ORDER BY required DESC, weight DESC, acquisition_priority DESC""",
        (profile["erp_profile_id"],),
    ).fetchall()

    return {
        "profile": dict(profile),
        "requirements": [dict(r) for r in requirements],
    }


def _active_provider_evidence(
    connection: sqlite3.Connection,
    evidence: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Drop evidence from explicitly inactive providers without dropping ERP requirements.

    Unknown providers remain accepted for backwards compatibility with integrations
    that do not register their source yet. Required attributes therefore still show
    as deficits when their registered provider is inactive.
    """
    required_by_attribute = {r["attribute_name"]: bool(r["required"]) for r in requirements}
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for item in evidence:
        source_id = str(item.get("source_id", "farmer-input-v1"))
        row = connection.execute(
            "SELECT active FROM evidence_sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if row is not None and not bool(row["active"]):
            excluded.append({
                "attribute": str(item.get("attribute", "")),
                "source_id": source_id,
                "required": required_by_attribute.get(str(item.get("attribute", "")), False),
                "reason": "Provider is inactive in the evidence registry",
            })
            continue
        accepted.append(item)
    return accepted, excluded


def _scope_value(context: dict[str, Any], name: str) -> Any:
    scope = context.get("scope")
    if isinstance(scope, dict) and scope.get(name) not in (None, ""):
        return scope.get(name)
    return context.get(name)


def _relationship_scope_matches(query: dict[str, Any], projection: dict[str, Any]) -> bool:
    """Match stable adaptive scopes while leaving legacy rows globally usable."""
    for name in ("farm_id", "field_id", "region", "season"):
        query_value = _scope_value(query, name)
        row_value = _scope_value(projection, name)
        if query_value not in (None, "") and row_value not in (None, ""):
            if str(query_value).strip().lower() != str(row_value).strip().lower():
                return False
    return True


def _decision_explanation(
    selected: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
    sufficiency: dict[str, Any],
    adaptive_updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alternatives = [c for c in candidates if not selected or c["action_id"] != selected["action_id"]]
    return {
        "selected_action_rationale": (
            f"Selected {selected['name']} because it was feasible and had the highest "
            f"context-adjusted score ({selected['score']:.3f}), with expected effectiveness "
            f"{selected['expected_outcome']:.1f}%."
            if selected else "No action was selected because the evidence was insufficient."
        ),
        "evidence_used": sufficiency.get("evaluated_attributes", []),
        "evidence_deficits": sufficiency.get("deficits", []),
        "alternatives": alternatives,
        "historical_support": {
            "selected_action": selected.get("support", 0.0) if selected else 0.0,
            "unit": "effective historical relationship samples",
        },
        "adaptive_updates": adaptive_updates or {},
    }


def evaluate_sufficiency(
    connection: sqlite3.Connection,
    decision_id: str,
    profile_id: str,
    evidence: list[dict[str, Any]],
    farm_lat: float | None = None,
    farm_lon: float | None = None,
    enforce_inclusion_floor: bool = True,
) -> dict[str, Any]:
    """
    Evaluate numerical evidence sufficiency S(E,D) = sum(w_i * q_i * r_i * t_i * p_i) / sum(w_i).
    Excludes optional attributes whose ERP weight is below `inclusion_floor` before scoring/fetching.
    """
    profile = connection.execute(
        "SELECT * FROM erp_profiles WHERE erp_profile_id = ?",
        (profile_id,),
    ).fetchone()
    if not profile:
        raise ValueError(f"ERP profile '{profile_id}' not found.")

    inclusion_floor = float(profile["inclusion_floor"]) if enforce_inclusion_floor else 0.0
    requirements = connection.execute(
        """SELECT * FROM erp_requirements
           WHERE erp_profile_id = ?
           ORDER BY acquisition_priority DESC, weight DESC""",
        (profile_id,),
    ).fetchall()

    # Resolve conflicting evidence items for the same attribute by selecting highest score & flagging conflict
    grouped_evidence: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        attr_key = str(item.get("attribute", "")).strip()
        if attr_key:
            grouped_evidence.setdefault(attr_key, []).append(item)

    indexed: dict[str, dict[str, Any]] = {}
    for attr_key, items in grouped_evidence.items():
        if len(items) == 1:
            indexed[attr_key] = items[0]
        else:
            distinct_vals = {str(it.get("value")).strip().lower() for it in items if it.get("value") not in (None, "")}
            ranked = sorted(items, key=lambda x: _evidence_score(x), reverse=True)
            best = dict(ranked[0])
            if len(distinct_vals) > 1:
                best["conflict_factor"] = 0.75
            indexed[attr_key] = best

    weighted_total = 0.0
    total_weight = 0.0
    required_ok = True
    deficits: list[dict[str, Any]] = []
    evaluated_attributes: list[dict[str, Any]] = []
    excluded_attributes: list[dict[str, Any]] = []

    BYTES_PER_ATTRIBUTE_ESTIMATE = 256

    for requirement in requirements:
        attr_name = requirement["attribute_name"]
        weight = float(requirement["weight"])
        is_required = bool(requirement["required"])

        # Inclusion-floor exclusion (Patent Claims 1(f), 7, 9)
        if enforce_inclusion_floor and (not is_required) and (weight < inclusion_floor):
            excluded_attributes.append({
                "attribute": attr_name,
                "weight": round(weight, 4),
                "inclusion_floor": inclusion_floor,
                "reason": "Excluded below ERP inclusion floor without fetching or transforming",
            })
            continue

        item = indexed.get(attr_name)
        comp = compute_evidence_components(
            item,
            temporal_validity_hours=requirement["temporal_validity_hours"],
            spatial_validity_km=requirement["spatial_validity_km"],
            farm_lat=farm_lat,
            farm_lon=farm_lon,
        )
        score = comp["score"]
        weighted_total += weight * score
        total_weight += weight

        min_score = float(requirement["minimum_score"])
        if is_required and score < min_score:
            required_ok = False

        # Deficit ranking P_i = w_i * (1 - e_i) / cost_factor_i (Patent §7.4)
        raw_deficit = max(0.0, min_score - score) if score < min_score else (0.0 if score >= 0.75 else (1.0 - score) * 0.5)
        if score < min_score:
            patent_deficit = weight * (1.0 - score)
            cost_factor = max(0.1, float(requirement["acquisition_cost_factor"] or 1.0))
            priority = patent_deficit / cost_factor
            deficits.append({
                "attribute": attr_name,
                "required": is_required,
                "weight": round(weight, 4),
                "score": round(score, 3),
                "minimum": round(min_score, 3),
                "weighted_deficit": round(weight * max(0.0, min_score - score), 4),
                "priority": round(priority, 4),
                "temporal_score": comp["temporal"],
                "spatial_score": comp["spatial"],
            })

        evaluated_attributes.append({
            "attribute": attr_name,
            "required": is_required,
            "weight": round(weight, 4),
            "minimum_score": round(min_score, 3),
            "quality": comp["quality"],
            "reliability": comp["reliability"],
            "temporal": comp["temporal"],
            "spatial": comp["spatial"],
            "score": round(score, 4),
            "satisfied": score >= min_score,
        })

    overall = weighted_total / total_weight if total_weight > 1e-9 else 0.0
    threshold = float(profile["sufficiency_threshold"])
    sufficient = (overall >= threshold) and required_ok

    result_id = str(uuid.uuid4())
    connection.execute(
        "INSERT OR REPLACE INTO evidence_sufficiency_results VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            result_id,
            decision_id,
            round(overall, 4),
            threshold,
            int(required_ok),
            "sufficient" if sufficient else "insufficient",
            now(),
        ),
    )

    sorted_deficits = sorted(deficits, key=lambda d: (d["required"], d["priority"]), reverse=True)
    for deficit in sorted_deficits:
        connection.execute(
            "INSERT INTO evidence_deficits VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                str(uuid.uuid4()),
                result_id,
                deficit["attribute"],
                deficit["score"],
                deficit["minimum"],
                deficit["weighted_deficit"],
                deficit["priority"],
                "farmer_input",
            ),
        )

    return {
        "sufficient": sufficient,
        "score": round(overall, 4),
        "threshold": threshold,
        "required_ok": required_ok,
        "inclusion_floor": inclusion_floor,
        "evaluated_attributes": evaluated_attributes,
        "excluded_attributes": excluded_attributes,
        "attributes_fetched_count": len(evaluated_attributes),
        "attributes_excluded_count": len(excluded_attributes),
        "estimated_bytes_processed": len(evaluated_attributes) * BYTES_PER_ATTRIBUTE_ESTIMATE,
        "estimated_bytes_saved": len(excluded_attributes) * BYTES_PER_ATTRIBUTE_ESTIMATE,
        "deficits": sorted_deficits,
    }


# ============================================================
# A2 & A3: ADIE-1 KERNEL-SHRUNK ACTION EVALUATION
# ============================================================

def _relationship_kernel_estimate(
    connection: sqlite3.Connection,
    action_id: str,
    decision_type: str,
    crop: str,
    query_context: dict[str, Any],
    query_vec_7d: np.ndarray,
    lambda_weights: np.ndarray,
    fallback_global: float,
    scoring_cfg: ADIEScoringConfig,
    context_aware: bool = True,
) -> tuple[float, float, float, float]:
    """
    Compute context-conditioned expected outcome R(a, c) using Gaussian kernel weighting
    over stored action_context_relationships in partition (decision_type, action_id, crop),
    with empirical Bayes shrinkage toward fallback_global.
    Returns: (shrunk_effectiveness, uncertainty, effective_sample_size, local_mean)
    """
    rows = connection.execute(
        """SELECT context_signature, context_projection_json, effectiveness_mean,
                  uncertainty, effective_sample_size
           FROM action_context_relationships
           WHERE action_id = ? AND decision_type = ?""",
        (action_id, decision_type),
    ).fetchall()

    if not rows:
        return fallback_global, 1.0, 0.0, fallback_global

    target_crop = normalize_crop(crop)
    weighted_sum = 0.0
    n_eff = 0.0

    for row in rows:
        try:
            proj = json.loads(row["context_projection_json"])
        except (TypeError, ValueError):
            proj = {}

        row_crop = normalize_crop(proj.get("crop", str(row["context_signature"]).split("|")[0]))
        if row_crop != target_crop:
            continue
        if not _relationship_scope_matches(query_context, proj):
            continue

        if context_aware:
            row_encoded = encode_7d_context(proj)
            row_vec = vector_from_encoded(row_encoded)
            sim = gaussian_kernel(query_vec_7d, row_vec, lambda_weights, sigma=scoring_cfg.kernel_sigma)
        else:
            # Global action scoring baseline (ignores context differences within crop)
            sim = 1.0

        if sim < 0.05:
            continue

        support_r = float(row["effective_sample_size"] or 0.0)
        weight_r = sim * support_r
        weighted_sum += weight_r * float(row["effectiveness_mean"])
        n_eff += weight_r

    if n_eff <= 1e-6:
        return fallback_global, 1.0, 0.0, fallback_global

    local_mean = weighted_sum / n_eff
    lam0 = max(0.1, scoring_cfg.shrinkage_lambda_0)
    shrunk = (n_eff * local_mean + lam0 * fallback_global) / (n_eff + lam0)
    uncertainty = max(0.05, 1.0 / (1.0 + n_eff))

    return float(np.clip(shrunk, 0.0, 100.0)), float(uncertainty), float(n_eff), float(local_mean)


def evaluate_actions(
    connection: sqlite3.Connection,
    decision_id: str,
    context: dict[str, Any],
    sufficiency: float,
    decision_type: str = "disease_intervention",
    erp_weights: dict[str, float] | None = None,
    inclusion_floor: float = 0.05,
    scoring_cfg: ADIEScoringConfig | None = None,
    context_aware: bool = True,
) -> dict[str, Any]:
    """
    Evaluate candidate interventions for `decision_type` under hard contextual constraints
    and configurable multi-factor scoring with ERP-weighted Gaussian kernel shrinkage.
    """
    cfg = scoring_cfg or _ACTIVE_SCORING_CONFIG
    actions = connection.execute(
        "SELECT * FROM actions WHERE decision_type = ? AND active = 1 ORDER BY name",
        (decision_type,),
    ).fetchall()

    crop = normalize_crop(context.get("crop", "Tomato"))
    encoded_7d = encode_7d_context(context)
    vec_7d = vector_from_encoded(encoded_7d)
    signature = context_signature_from_7d(crop, encoded_7d)
    lambda_weights = compute_dimension_weights(erp_weights, inclusion_floor=inclusion_floor)

    budget = float(context.get("budget", context.get("farmer_budget", 0)) or 0)
    rain = float(context.get("rain_probability", context.get("weather_rain_probability", 0)) or 0)
    resources = str(context.get("resources", context.get("farm_resources", "available"))).strip()

    candidates: list[dict[str, Any]] = []
    for action in actions:
        rules = json.loads(action["applicability_rules_json"] or "{}")
        rejection: list[str] = []

        if action["estimated_cost"] and budget > 0 and float(action["estimated_cost"]) > budget:
            rejection.append("Estimated cost exceeds the recorded budget.")
        if rules.get("max_rain_probability") is not None and rain > float(rules["max_rain_probability"]):
            rejection.append(
                f"Rain probability ({rain:.0f}%) exceeds dry-window limit ({rules['max_rain_probability']}%)."
            )
        if rules.get("requires_labor") and (not resources or resources.lower() in {"none", "not recorded", "no"}):
            rejection.append("Available labour or equipment resources were not recorded.")

        feasible = not rejection
        global_prior = float(action["expected_global_outcome"])
        effectiveness, uncertainty, support, local_mean = _relationship_kernel_estimate(
            connection=connection,
            action_id=action["action_id"],
            decision_type=decision_type,
            crop=crop,
            query_context=context,
            query_vec_7d=vec_7d,
            lambda_weights=lambda_weights,
            fallback_global=global_prior,
            scoring_cfg=cfg,
            context_aware=context_aware,
        )

        intrinsic_benefit = global_prior / 100.0
        contextual_norm = effectiveness / 100.0
        risk = float(action["default_risk"])
        cost_penalty = min(1.0, float(action["estimated_cost"] or 0.0) / max(budget, 100.0))

        final_score = (
            cfg.alpha_global * intrinsic_benefit
            + cfg.alpha_context * contextual_norm
            + cfg.alpha_sufficiency * sufficiency
            - cfg.delta_risk * risk
            - cfg.delta_cost * cost_penalty
            - cfg.delta_uncertainty * uncertainty
        )

        candidate = {
            "action_id": action["action_id"],
            "name": action["name"],
            "description": action["description"],
            "feasible": feasible,
            "reasons": rejection,
            "global_prior_outcome": round(global_prior, 1),
            "local_kernel_outcome": round(local_mean, 1),
            "expected_outcome": round(effectiveness, 1),
            "uncertainty": round(uncertainty, 3),
            "estimated_cost": float(action["estimated_cost"] or 0.0),
            "risk": round(risk, 3),
            "score": round(final_score, 4),
            "support": round(support, 2),
        }
        candidates.append(candidate)

        connection.execute(
            """INSERT OR REPLACE INTO decision_candidates
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                decision_id,
                action["action_id"],
                int(feasible),
                _json(rejection),
                round(intrinsic_benefit, 4),
                round(effectiveness, 2),
                round(sufficiency, 4),
                round(risk, 4),
                round(cost_penalty, 4),
                round(uncertainty, 4),
                round(final_score, 4),
                _json({
                    "historical_support": round(support, 2),
                    "context_signature": signature,
                    "local_kernel_mean": round(local_mean, 2),
                }),
                now(),
            ),
        )

    feasible_list = [c for c in candidates if c["feasible"]]
    selected = max(feasible_list, key=lambda c: c["score"]) if feasible_list else None
    sorted_candidates = sorted(candidates, key=lambda c: (c["feasible"], c["score"]), reverse=True)

    return {
        "selected": selected,
        "candidates": sorted_candidates,
        "context_signature": signature,
        "encoded_7d_context": encoded_7d,
        "dimension_weights_lambda": {
            dim: round(float(w), 4) for dim, w in zip(CONTEXT_DIMENSIONS, lambda_weights)
        },
    }


def create_decision(
    connection: sqlite3.Connection,
    farm_id: str,
    field_id: str | None,
    context: dict[str, Any],
    evidence: list[dict[str, Any]],
    decision_type: str = "disease_intervention",
    enforce_inclusion_floor: bool = True,
    context_aware: bool = True,
    scoring_cfg: ADIEScoringConfig | None = None,
) -> dict[str, Any]:
    """
    Execute Phase I of the AgroNexus AI decision pipeline (A0 -> A1 -> A2 -> A3 + DCT-RAG).
    """
    t0 = time.perf_counter()
    # Keep scope metadata additive so existing context/API fields remain valid.
    context = dict(context)
    scope = dict(context.get("scope") or {})
    scope.setdefault("farm_id", farm_id)
    scope.setdefault("field_id", field_id)
    scope.setdefault("region", context.get("region"))
    scope.setdefault("season", context.get("season"))
    scope.setdefault("crop_stage", context.get("crop_stage"))
    context["scope"] = scope
    erp_bundle = get_active_erp_profile(connection, decision_type=decision_type)
    profile = erp_bundle["profile"]
    requirements = erp_bundle["requirements"]
    erp_weights = {r["attribute_name"]: float(r["weight"]) for r in requirements}
    inclusion_floor = float(profile["inclusion_floor"]) if enforce_inclusion_floor else 0.0

    farm_row = connection.execute(
        "SELECT latitude, longitude FROM farms WHERE farm_id = ?",
        (farm_id,),
    ).fetchone()
    farm_lat = float(farm_row["latitude"]) if farm_row and farm_row["latitude"] is not None else None
    farm_lon = float(farm_row["longitude"]) if farm_row and farm_row["longitude"] is not None else None

    decision_id = str(uuid.uuid4())
    connection.execute(
        """INSERT INTO decisions
           (decision_id, farm_id, field_id, decision_type, erp_profile_id, status, context_json)
           VALUES (?, ?, ?, ?, ?, 'draft', ?)""",
        (decision_id, farm_id, field_id, decision_type, profile["erp_profile_id"], _json(context)),
    )

    req_by_attr = {r["attribute_name"]: r for r in requirements}
    active_evidence, excluded_provider_evidence = _active_provider_evidence(
        connection, evidence, requirements
    )
    for item in active_evidence:
        attr_name = str(item.get("attribute", "")).strip()
        req = req_by_attr.get(attr_name)
        if enforce_inclusion_floor and req and (not req["required"]) and float(req["weight"]) < inclusion_floor:
            # Attribute is below inclusion floor: do not transform or insert into active evidence_items
            continue

        comp = compute_evidence_components(
            item,
            temporal_validity_hours=req["temporal_validity_hours"] if req else None,
            spatial_validity_km=req["spatial_validity_km"] if req else None,
            farm_lat=farm_lat,
            farm_lon=farm_lon,
        )
        source_id = str(item.get("source_id", "farmer-input-v1"))
        connection.execute(
            """INSERT INTO evidence_items
               (evidence_id, decision_id, source_id, attribute_name, value_json, unit,
                quality_score, reliability_score, confidence_score, temporal_score,
                spatial_score, normalized_score, captured_at, latitude, longitude, provenance_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                decision_id,
                source_id,
                attr_name,
                _json(item.get("value")),
                item.get("unit"),
                comp["quality"],
                comp["reliability"],
                comp["confidence"],
                comp["temporal"],
                comp["spatial"],
                comp["score"],
                item.get("captured_at") or now(),
                item.get("latitude"),
                item.get("longitude"),
                _json({"age_hours": comp["age_hours"], "distance_km": comp["distance_km"]}),
            ),
        )

    sufficiency_result = evaluate_sufficiency(
        connection=connection,
        decision_id=decision_id,
        profile_id=profile["erp_profile_id"],
        evidence=active_evidence,
        farm_lat=farm_lat,
        farm_lon=farm_lon,
        enforce_inclusion_floor=enforce_inclusion_floor,
    )

    dct_rag = retrieve_dct_rag_evidence(
        decision_type=decision_type,
        context=context,
        deficits=sufficiency_result["deficits"],
    )

    if not sufficiency_result["sufficient"]:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        connection.execute(
            """UPDATE decisions
               SET status = 'insufficient_evidence',
                   evidence_sufficiency_score = ?,
                   required_evidence_satisfied = 0,
                   decision_trace_json = ?,
                   updated_at = ?
               WHERE decision_id = ?""",
            (
                sufficiency_result["score"],
                _json({
                    "dct_rag": dct_rag,
                    "provider_filtered_evidence": excluded_provider_evidence,
                    "explanation": _decision_explanation(None, [], sufficiency_result),
                    "processing_time_ms": round(elapsed_ms, 2),
                }),
                now(),
                decision_id,
            ),
        )
        connection.commit()
        return {
            "decision_id": decision_id,
            "decision_type": decision_type,
            "erp_version": profile["version"],
            "status": "insufficient_evidence",
            "sufficiency": sufficiency_result,
            "recommendation": None,
            "alternatives": [],
            "dct_rag": dct_rag,
            "explanation": _decision_explanation(None, [], sufficiency_result),
            "provider_filtered_evidence": excluded_provider_evidence,
            "processing_time_ms": round(elapsed_ms, 2),
        }

    evaluation = evaluate_actions(
        connection=connection,
        decision_id=decision_id,
        context=context,
        sufficiency=sufficiency_result["score"],
        decision_type=decision_type,
        erp_weights=erp_weights,
        inclusion_floor=inclusion_floor,
        scoring_cfg=scoring_cfg,
        context_aware=context_aware,
    )
    selected = evaluation["selected"]
    if not selected:
        raise ValueError("No feasible action is available for this context.")

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    trace = {
        "erp_profile_id": profile["erp_profile_id"],
        "erp_version": profile["version"],
        "context_signature": evaluation["context_signature"],
        "encoded_7d_context": evaluation["encoded_7d_context"],
        "dimension_weights_lambda": evaluation["dimension_weights_lambda"],
        "excluded_attributes": sufficiency_result["excluded_attributes"],
        "provider_filtered_evidence": excluded_provider_evidence,
        "candidates": evaluation["candidates"],
        "dct_rag": dct_rag,
        "processing_time_ms": round(elapsed_ms, 2),
    }
    trace["explanation"] = _decision_explanation(
        selected, evaluation["candidates"], sufficiency_result
    )

    connection.execute(
        """UPDATE decisions
           SET status = 'recommended',
               evidence_sufficiency_score = ?,
               required_evidence_satisfied = 1,
               decision_ready = 1,
               selected_action_id = ?,
               expected_outcome = ?,
               decision_trace_json = ?,
               decided_at = ?,
               updated_at = ?
           WHERE decision_id = ?""",
        (
            sufficiency_result["score"],
            selected["action_id"],
            selected["expected_outcome"],
            _json(trace),
            now(),
            now(),
            decision_id,
        ),
    )
    connection.commit()

    return {
        "decision_id": decision_id,
        "decision_type": decision_type,
        "erp_version": profile["version"],
        "status": "recommended",
        "sufficiency": sufficiency_result,
        "recommendation": selected,
        "alternatives": evaluation["candidates"],
        "context_signature": evaluation["context_signature"],
        "encoded_7d_context": evaluation["encoded_7d_context"],
        "dimension_weights_lambda": evaluation["dimension_weights_lambda"],
        "dct_rag": dct_rag,
        "explanation": trace["explanation"],
        "provider_filtered_evidence": excluded_provider_evidence,
        "processing_time_ms": round(elapsed_ms, 2),
    }


# ============================================================
# A4, A5 & A6: ACER, SAMPLE-GATED CNDA & JOINT ADAPTIVE UPDATE
# ============================================================

def _update_action_context_relationships_kernel(
    connection: sqlite3.Connection,
    acer_id: str,
    decision_type: str,
    action_id: str,
    context: dict[str, Any],
    expected_outcome: float,
    deviation: float,
    outcome_confidence: float,
    erp_weights: dict[str, float],
    inclusion_floor: float,
    context_aware: bool = True,
) -> dict[str, Any]:
    """
    Update 1 of the Joint Adaptive Update:
    Upserts the exact context region and updates all neighboring context regions r in the
    same (decision_type, action_id, crop) partition where K_w(c_r, c_ACER) >= 0.25.
    """
    crop = normalize_crop(context.get("crop", "Tomato"))
    encoded_7d = encode_7d_context(context)
    vec_7d = vector_from_encoded(encoded_7d)
    signature = context_signature_from_7d(crop, encoded_7d) if context_aware else f"{crop}|global"
    lambda_weights = compute_dimension_weights(erp_weights, inclusion_floor=inclusion_floor)

    exact_row = connection.execute(
        """SELECT * FROM action_context_relationships
           WHERE action_id = ? AND decision_type = ? AND context_signature = ?""",
        (action_id, decision_type, signature),
    ).fetchall()

    if not exact_row:
        rel_id = str(uuid.uuid4())
        connection.execute(
            """INSERT INTO action_context_relationships
               (relationship_id, action_id, decision_type, context_signature,
                context_projection_json, effectiveness_mean, uncertainty,
                effective_sample_size, global_effectiveness_mean, last_acer_id)
               VALUES (?, ?, ?, ?, ?, ?, 1.0, 0.0, ?, ?)""",
            (
                rel_id,
                action_id,
                decision_type,
                signature,
                _json(context),
                expected_outcome,
                expected_outcome,
                acer_id,
            ),
        )

    all_rows = connection.execute(
        """SELECT * FROM action_context_relationships
           WHERE action_id = ? AND decision_type = ?""",
        (action_id, decision_type),
    ).fetchall()

    updated_regions: list[dict[str, Any]] = []
    primary_effectiveness = expected_outcome

    for row in all_rows:
        try:
            proj = json.loads(row["context_projection_json"])
        except (TypeError, ValueError):
            proj = {}
        row_crop = normalize_crop(proj.get("crop", str(row["context_signature"]).split("|")[0]))
        if row_crop != crop:
            continue

        if context_aware:
            row_vec = vector_from_encoded(encode_7d_context(proj))
            sim = gaussian_kernel(vec_7d, row_vec, lambda_weights, sigma=_ACTIVE_SCORING_CONFIG.kernel_sigma)
        else:
            sim = 1.0

        if sim < 0.25:
            continue

        old_mean = float(row["effectiveness_mean"])
        old_unc = float(row["uncertainty"])
        old_sample = float(row["effective_sample_size"])
        observed_val = expected_outcome + deviation
        region_error = observed_val - old_mean

        # Diminishing learning rate safeguard: alpha_r = 0.45 / (1 + 0.12 * n_r)
        alpha_r = 0.45 / (1.0 + 0.12 * old_sample)
        new_mean = float(np.clip(old_mean + alpha_r * outcome_confidence * sim * region_error, 0.0, 100.0))
        new_sample = old_sample + outcome_confidence * sim
        new_unc = max(0.05, 1.0 / (1.0 + new_sample))

        connection.execute(
            """UPDATE action_context_relationships
               SET effectiveness_mean = ?,
                   uncertainty = ?,
                   effective_sample_size = ?,
                   last_acer_id = ?,
                   version = version + 1,
                   updated_at = ?
               WHERE relationship_id = ?""",
            (
                round(new_mean, 3),
                round(new_unc, 4),
                round(new_sample, 3),
                acer_id,
                now(),
                row["relationship_id"],
            ),
        )

        connection.execute(
            """INSERT INTO relationship_update_logs
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                row["relationship_id"],
                acer_id,
                round(sim, 4),
                round(alpha_r, 4),
                round(old_mean, 3),
                round(new_mean, 3),
                round(old_unc, 4),
                round(new_unc, 4),
                now(),
            ),
        )

        if row["context_signature"] == signature:
            primary_effectiveness = new_mean

        updated_regions.append({
            "relationship_id": row["relationship_id"],
            "context_signature": row["context_signature"],
            "similarity": round(sim, 4),
            "previous_effectiveness": round(old_mean, 2),
            "updated_effectiveness": round(new_mean, 2),
            "previous_uncertainty": round(old_unc, 3),
            "updated_uncertainty": round(new_unc, 3),
            "effective_sample_size": round(new_sample, 2),
        })

    return {
        "updated": bool(updated_regions),
        "primary_signature": signature,
        "relationship_effectiveness": round(primary_effectiveness, 2),
        "regions_updated_count": len(updated_regions),
        "regions": updated_regions,
    }


def _update_erp_weights_from_cnda(
    connection: sqlite3.Connection,
    acer_id: str,
    decision_type: str,
    deviation: float,
    outcome_confidence: float,
    cnda_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Update 2 of the Joint Adaptive Update (Patent Claims 1(n), 1(o), 10, 11):
    Executes only when CNDA has sufficient sample support (N_pi >= 5).
    - Increases weights of CNDA-selected contextual factors associated with outcome deviation.
    - Applies mild decay toward w_min (0.02) for repeatedly unassociated optional factors (|rho_j| < 0.20),
      allowing non-informative optional attributes to cross below `inclusion_floor` (0.05).
    - Creates a new immutable ERP profile version and logs every weight change in `erp_update_logs`.
    """
    if cnda_result.get("status") != "attributed":
        return {
            "erp_updated": False,
            "reason": cnda_result.get("status", "insufficient_sample_support"),
            "sample_count": cnda_result.get("sample_count", 0),
            "changes": [],
        }

    erp_bundle = get_active_erp_profile(connection, decision_type=decision_type)
    old_profile = erp_bundle["profile"]
    old_reqs = erp_bundle["requirements"]

    attr_by_name = {item["feature_name"]: item for item in cnda_result.get("attributions", [])}
    psi = float(cnda_result.get("damping_factor_psi", 1.0))
    beta_lr = 0.15
    deviation_scale = min(1.0, abs(deviation) / 25.0)

    proposed_reqs: list[dict[str, Any]] = []
    weight_changes: list[dict[str, Any]] = []

    for req in old_reqs:
        attr_name = req["attribute_name"]
        old_w = float(req["weight"])
        is_req = int(req["required"]) == 1
        min_bound = 0.10 if is_req else 0.02
        max_bound = 1.00

        cnda_item = attr_by_name.get(attr_name)
        new_w = old_w
        update_reason: str | None = None
        attribution_id: str | None = None

        if cnda_item and cnda_item["selected"]:
            # Associated with deviation -> increase ERP weight (bounded by max step 0.08)
            kappa_j = float(cnda_item["association_confidence"])
            step = min(0.08, beta_lr * kappa_j * max(0.35, deviation_scale))
            new_w = float(np.clip(old_w + step, min_bound, max_bound))
            update_reason = "associated_deviation"
            attribution_id = cnda_item["attribution_id"]
        elif (not is_req) and (
            (cnda_item and abs(float(cnda_item["association_value"])) < 0.20)
            or (attr_name not in CONTEXT_DIMENSIONS)
        ):
            # Optional attribute repeatedly not associated with deviation -> decay toward 0.02
            decay_step = min(0.02, 0.018 * psi * outcome_confidence)
            new_w = float(np.clip(old_w - decay_step, min_bound, max_bound))
            update_reason = "non_association_decay"
            attribution_id = cnda_item["attribution_id"] if cnda_item else None

        proposed_reqs.append({
            **req,
            "new_weight": round(new_w, 4),
            "old_weight": round(old_w, 4),
            "update_reason": update_reason,
            "attribution_id": attribution_id,
        })

        if update_reason and abs(new_w - old_w) >= 1e-4:
            weight_changes.append({
                "attribute": attr_name,
                "required": is_req,
                "previous_weight": round(old_w, 4),
                "updated_weight": round(new_w, 4),
                "delta_weight": round(new_w - old_w, 4),
                "crossed_below_inclusion_floor": (old_w >= float(old_profile["inclusion_floor"]))
                and (new_w < float(old_profile["inclusion_floor"])),
                "reason": update_reason,
                "attribution_id": attribution_id,
            })

    if not weight_changes:
        return {
            "erp_updated": False,
            "reason": "no_significant_weight_delta",
            "erp_version": old_profile["version"],
            "changes": [],
        }

    # Create new immutable ERP profile version (version = old_version + 1)
    new_profile_id = str(uuid.uuid4())
    new_version = int(old_profile["version"]) + 1
    connection.execute(
        "UPDATE erp_profiles SET is_active = 0 WHERE decision_type = ?",
        (decision_type,),
    )
    connection.execute(
        """INSERT INTO erp_profiles
           (erp_profile_id, decision_type, version, sufficiency_threshold,
            inclusion_floor, is_active, created_at, created_by)
           VALUES (?, ?, ?, ?, ?, 1, ?, 'cnda_joint_updater')""",
        (
            new_profile_id,
            decision_type,
            new_version,
            old_profile["sufficiency_threshold"],
            old_profile["inclusion_floor"],
            now(),
        ),
    )

    for req_item in proposed_reqs:
        new_req_id = str(uuid.uuid4())
        connection.execute(
            """INSERT INTO erp_requirements
               (erp_requirement_id, erp_profile_id, attribute_name, weight, required,
                minimum_score, temporal_validity_hours, spatial_validity_km,
                acquisition_cost_factor, acquisition_priority, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_req_id,
                new_profile_id,
                req_item["attribute_name"],
                req_item["new_weight"],
                req_item["required"],
                req_item["minimum_score"],
                req_item["temporal_validity_hours"],
                req_item["spatial_validity_km"],
                req_item["acquisition_cost_factor"],
                req_item["acquisition_priority"],
                now(),
            ),
        )
        if req_item["update_reason"] and abs(req_item["new_weight"] - req_item["old_weight"]) >= 1e-4:
            connection.execute(
                """INSERT INTO erp_update_logs
                   (erp_update_id, erp_requirement_id, acer_id, attribution_id,
                    previous_weight, updated_weight, learning_rate, update_reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    new_req_id,
                    acer_id,
                    req_item["attribution_id"],
                    req_item["old_weight"],
                    req_item["new_weight"],
                    beta_lr,
                    req_item["update_reason"],
                    now(),
                ),
            )

    return {
        "erp_updated": True,
        "previous_erp_version": old_profile["version"],
        "new_erp_version": new_version,
        "new_erp_profile_id": new_profile_id,
        "inclusion_floor": old_profile["inclusion_floor"],
        "changes": weight_changes,
    }


def record_outcome(
    connection: sqlite3.Connection,
    decision_id: str,
    observed_outcome: float,
    outcome_status: str,
    notes: str = "",
    outcome_measure_quality: float = 0.85,
    feedback_completeness: float = 0.85,
    measure_quality: float | None = None,
    completeness: float | None = None,
    enable_r_update: bool = True,
    enable_erp_update: bool = True,
    context_aware: bool = True,
) -> dict[str, Any]:
    """
    Execute Phase II of the AgroNexus AI closed loop (A4 ACER -> A5 Sample-Gated BallTree CNDA -> A6 Joint Update).
    """
    if measure_quality is not None:
        outcome_measure_quality = measure_quality
    if completeness is not None:
        feedback_completeness = completeness

    decision = connection.execute(
        "SELECT * FROM decisions WHERE decision_id = ?",
        (decision_id,),
    ).fetchone()
    if not decision or decision["status"] != "recommended":
        raise ValueError("A recommended decision is required before recording an outcome.")

    decision_type = str(decision["decision_type"])
    action_id = str(decision["selected_action_id"])
    expected_outcome = float(decision["expected_outcome"])
    sufficiency_score = float(decision["evidence_sufficiency_score"] or 0.75)

    feedback_id = str(uuid.uuid4())
    connection.execute(
        """INSERT OR REPLACE INTO outcome_feedback
           VALUES (?, ?, ?, ?, ?, 'effectiveness_percent', ?, ?, ?, ?, ?, 'farmer')""",
        (
            feedback_id,
            decision_id,
            action_id,
            outcome_status,
            float(observed_outcome),
            float(outcome_measure_quality),
            float(feedback_completeness),
            notes,
            now(),
            now(),
        ),
    )

    confidence = float(outcome_measure_quality) * float(feedback_completeness) * sufficiency_score
    deviation = float(observed_outcome) - expected_outcome
    acer_id = str(uuid.uuid4())
    eligible = int(confidence >= 0.50 and outcome_status != "unknown")

    connection.execute(
        """INSERT OR REPLACE INTO acer_records
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'effectiveness_percent', ?, ?, ?, ?)""",
        (
            acer_id,
            decision_id,
            action_id,
            decision_type,
            decision["context_json"],
            expected_outcome,
            float(observed_outcome),
            round(deviation, 3),
            sufficiency_score,
            round(confidence, 4),
            eligible,
            now(),
        ),
    )

    context = json.loads(decision["context_json"])
    encoded_7d = encode_7d_context(context)
    erp_bundle = get_active_erp_profile(connection, decision_type=decision_type)
    erp_weights = {r["attribute_name"]: float(r["weight"]) for r in erp_bundle["requirements"]}
    inclusion_floor = float(erp_bundle["profile"]["inclusion_floor"])

    # Store both categorical partition key (`crop`) and the 7 normalized continuous/ordinal features
    connection.execute(
        "INSERT OR REPLACE INTO acer_context_features VALUES (?, ?, 'crop', 'categorical', NULL, ?, NULL, 1.0)",
        (str(uuid.uuid4()), acer_id, normalize_crop(context.get("crop", "Tomato"))),
    )
    for dim_name, norm_val in encoded_7d.items():
        raw_val = context.get(dim_name)
        num_val = float(raw_val) if isinstance(raw_val, (int, float)) else float(norm_val)
        feat_w = float(erp_weights.get(dim_name, 0.10))
        connection.execute(
            "INSERT OR REPLACE INTO acer_context_features VALUES (?, ?, ?, 'numeric', ?, NULL, ?, ?)",
            (str(uuid.uuid4()), acer_id, dim_name, num_val, round(norm_val, 4), round(feat_w, 4)),
        )

    r_update_result: dict[str, Any] = {"updated": False}
    cnda_result: dict[str, Any] = {"status": "ineligible_low_confidence", "attributions": [], "selected_factors": []}
    erp_update_result: dict[str, Any] = {"erp_updated": False, "changes": []}

    if eligible:
        if enable_r_update:
            r_update_result = _update_action_context_relationships_kernel(
                connection=connection,
                acer_id=acer_id,
                decision_type=decision_type,
                action_id=action_id,
                context=context,
                expected_outcome=expected_outcome,
                deviation=deviation,
                outcome_confidence=confidence,
                erp_weights=erp_weights,
                inclusion_floor=inclusion_floor,
                context_aware=context_aware,
            )

        cnda_result = run_sample_gated_cnda(
            connection=connection,
            acer_id=acer_id,
            decision_type=decision_type,
            action_id=action_id,
            current_context=context,
            current_outcome_confidence=confidence,
            erp_weights=erp_weights,
            inclusion_floor=inclusion_floor,
        )

        if enable_erp_update:
            erp_update_result = _update_erp_weights_from_cnda(
                connection=connection,
                acer_id=acer_id,
                decision_type=decision_type,
                deviation=deviation,
                outcome_confidence=confidence,
                cnda_result=cnda_result,
            )

    connection.execute(
        "UPDATE decisions SET status = 'outcome_recorded', updated_at = ? WHERE decision_id = ?",
        (now(), decision_id),
    )
    connection.commit()

    return {
        "acer_id": acer_id,
        "decision_id": decision_id,
        "expected_outcome": round(expected_outcome, 1),
        "observed_outcome": round(float(observed_outcome), 1),
        "deviation": round(deviation, 2),
        "outcome_confidence": round(confidence, 3),
        "eligible_for_adaptation": bool(eligible),
        "cnda": cnda_result,
        "adaptive_update": {
            "updated": bool(r_update_result.get("updated") or erp_update_result.get("erp_updated")),
            "r_updated": bool(r_update_result.get("updated")),
            "erp_updated": bool(erp_update_result.get("erp_updated")),
            "relationship_effectiveness": r_update_result.get("relationship_effectiveness"),
            "deviation": round(deviation, 2),
            "confidence": round(confidence, 3),
            "r_update_details": r_update_result,
            "erp_update_details": erp_update_result,
        },
    }
