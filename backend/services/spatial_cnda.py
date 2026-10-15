"""Partitioned 7D Context Encoding, Spatial ACER Index (BallTree), and Sample-Gated CNDA."""

from __future__ import annotations

import json
import math
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np

try:
    from sklearn.neighbors import BallTree
    HAS_BALLTREE = True
except ImportError:
    BallTree = None
    HAS_BALLTREE = False

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc


def now() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================
# V2 FROZEN 7D CONTINUOUS / ORDINAL CONTEXT SPECIFICATION
# ============================================================
# Categorical `crop` is an exact partition key:
#     partition_key = (decision_type, action_id, normalize_crop(crop))
# Inside each partition, the context vector is strictly 7D continuous/ordinal in [0, 1]^7.

CONTEXT_DIMENSIONS: list[str] = [
    "crop_stage",
    "disease_severity",
    "weather_rain_probability",
    "air_humidity",
    "temperature",
    "soil_fertility",
    "farmer_budget",
]

STAGE_ORDINAL: dict[str, float] = {
    "seedling": 0.10,
    "vegetative": 0.35,
    "flowering": 0.60,
    "fruiting": 0.80,
    "boll_formation": 0.80,
    "panicle_initiation": 0.55,
    "bulb_formation": 0.70,
    "pegging": 0.65,
    "maturity": 1.00,
    "harvest": 1.00,
}

SEVERITY_ORDINAL: dict[str, float] = {
    "none": 0.05,
    "low": 0.20,
    "moderate": 0.55,
    "medium": 0.55,
    "high": 0.90,
    "severe": 0.98,
}

SOIL_STATUS_ORDINAL: dict[str, float] = {
    "low": 0.20,
    "acidic": 0.35,
    "alkaline": 0.40,
    "medium": 0.60,
    "moderate": 0.60,
    "neutral": 0.85,
    "high": 0.95,
}


def normalize_crop(crop: Any) -> str:
    return str(crop or "unknown").strip().lower()


def encode_7d_context(context: dict[str, Any]) -> dict[str, float]:
    """Encode raw decision context into the 7 canonical continuous/ordinal dimensions in [0, 1]."""
    stage_raw = str(context.get("crop_stage", "flowering")).strip().lower()
    stage_val = STAGE_ORDINAL.get(stage_raw, 0.50)

    sev_raw = context.get("disease_severity", "moderate")
    if isinstance(sev_raw, (int, float)):
        val = float(sev_raw)
        sev_val = val / 100.0 if val > 1.0 else val
    else:
        sev_val = SEVERITY_ORDINAL.get(str(sev_raw).strip().lower(), 0.55)

    rain_raw = float(context.get("rain_probability", context.get("weather_rain_probability", 25.0)) or 0.0)
    rain_val = rain_raw / 100.0 if rain_raw > 1.0 else rain_raw

    hum_raw = float(context.get("air_humidity", context.get("humidity", 65.0)) or 65.0)
    hum_val = hum_raw / 100.0 if hum_raw > 1.0 else hum_raw

    temp_raw = float(context.get("temperature", 28.0) or 28.0)
    temp_val = (temp_raw - 10.0) / 35.0

    if "soil_fertility" in context and isinstance(context["soil_fertility"], (int, float)):
        fert_raw = float(context["soil_fertility"])
        soil_val = fert_raw / 100.0 if fert_raw > 1.0 else fert_raw
    else:
        n_stat = SOIL_STATUS_ORDINAL.get(str(context.get("n_status", "medium")).strip().lower(), 0.60)
        p_stat = SOIL_STATUS_ORDINAL.get(str(context.get("p_status", "medium")).strip().lower(), 0.60)
        k_stat = SOIL_STATUS_ORDINAL.get(str(context.get("k_status", "medium")).strip().lower(), 0.60)
        soil_val = (n_stat + p_stat + k_stat) / 3.0

    budget_raw = float(context.get("budget", context.get("farmer_budget", 500.0)) or 0.0)
    budget_val = budget_raw / 2000.0

    encoded = {
        "crop_stage": float(np.clip(stage_val, 0.0, 1.0)),
        "disease_severity": float(np.clip(sev_val, 0.0, 1.0)),
        "weather_rain_probability": float(np.clip(rain_val, 0.0, 1.0)),
        "air_humidity": float(np.clip(hum_val, 0.0, 1.0)),
        "temperature": float(np.clip(temp_val, 0.0, 1.0)),
        "soil_fertility": float(np.clip(soil_val, 0.0, 1.0)),
        "farmer_budget": float(np.clip(budget_val, 0.0, 1.0)),
    }
    return encoded


def vector_from_encoded(encoded: dict[str, float]) -> np.ndarray:
    """Return a 1D numpy array in the canonical 7D order."""
    return np.array([encoded[dim] for dim in CONTEXT_DIMENSIONS], dtype=np.float64)


def compute_dimension_weights(erp_weights: dict[str, float] | None = None, inclusion_floor: float = 0.0) -> np.ndarray:
    """
    Compute normalized feature relevance weights lambda_j = w_j / sum(w_m) for the 7 context dimensions.
    Dimensions whose ERP weight is below inclusion_floor receive 0 weight in distance calculations.
    """
    if not erp_weights:
        weights = np.ones(len(CONTEXT_DIMENSIONS), dtype=np.float64)
        return weights / weights.sum()

    raw = []
    for dim in CONTEXT_DIMENSIONS:
        w = float(erp_weights.get(dim, 0.10))
        if w < inclusion_floor:
            w = 0.0
        raw.append(max(0.0, w))

    arr = np.array(raw, dtype=np.float64)
    total = float(arr.sum())
    if total <= 1e-9:
        return np.ones(len(CONTEXT_DIMENSIONS), dtype=np.float64) / len(CONTEXT_DIMENSIONS)
    return arr / total


def weighted_euclidean_distance(
    vec_a: np.ndarray,
    vec_b: np.ndarray,
    lambda_weights: np.ndarray | None = None,
) -> float:
    """Compute d_w(c, c') = sqrt(sum_j lambda_j * (c_j - c'_j)^2)."""
    if lambda_weights is None:
        lambda_weights = np.ones(len(CONTEXT_DIMENSIONS), dtype=np.float64) / len(CONTEXT_DIMENSIONS)
    diff = vec_a - vec_b
    return float(math.sqrt(float(np.sum(lambda_weights * (diff ** 2)))))


def gaussian_kernel(
    vec_a: np.ndarray,
    vec_b: np.ndarray,
    lambda_weights: np.ndarray | None = None,
    sigma: float = 0.30,
) -> float:
    """Compute K_w(c, c') = exp(-d_w(c, c')^2 / (2 * sigma^2))."""
    dist = weighted_euclidean_distance(vec_a, vec_b, lambda_weights)
    return float(math.exp(-(dist ** 2) / (2.0 * (sigma ** 2))))


def context_signature_from_7d(crop: str, encoded: dict[str, float]) -> str:
    """Generate a reproducible context cluster signature from the 7D vector."""
    rain_band = "high_rain" if encoded["weather_rain_probability"] >= 0.55 else (
        "mod_rain" if encoded["weather_rain_probability"] >= 0.30 else "low_rain"
    )
    hum_band = "humid" if encoded["air_humidity"] >= 0.75 else (
        "norm_hum" if encoded["air_humidity"] >= 0.45 else "dry_hum"
    )
    sev_band = "high_sev" if encoded["disease_severity"] >= 0.70 else (
        "mod_sev" if encoded["disease_severity"] >= 0.40 else "low_sev"
    )
    stage_band = "early" if encoded["crop_stage"] <= 0.40 else (
        "reproductive" if encoded["crop_stage"] <= 0.85 else "late"
    )
    return f"{normalize_crop(crop)}|{stage_band}|{sev_band}|{rain_band}|{hum_band}"


# ============================================================
# PARTITIONED BALLTREE SPATIAL INDEX FOR ACER RECORDS
# ============================================================

class PartitionedACERIndex:
    """
    Spatial index over historical ACER records for a specific (decision_type, action_id, crop) partition.
    Transforms each 7D vector by sqrt(lambda_j) so standard Euclidean BallTree queries
    compute exact ERP-weighted Euclidean distances d_w(c, c').
    """

    def __init__(
        self,
        records: list[dict[str, Any]],
        lambda_weights: np.ndarray,
        leaf_size: int = 16,
    ) -> None:
        self.records = records
        self.lambda_weights = lambda_weights
        self.sqrt_lambda = np.sqrt(lambda_weights)
        self.matrix: np.ndarray | None = None
        self.tree: Any = None

        if records:
            raw_vectors = np.vstack([rec["vector_7d"] for rec in records])
            self.matrix = raw_vectors * self.sqrt_lambda
            if HAS_BALLTREE and BallTree is not None:
                self.tree = BallTree(self.matrix, leaf_size=leaf_size, metric="euclidean")

    def query_knn(self, query_vec_7d: np.ndarray, k: int = 15) -> dict[str, Any]:
        """
        Query k nearest ACER records using BallTree and also measure linear scan time for benchmarking.
        """
        if not self.records or self.matrix is None:
            return {"neighbors": [], "balltree_time_us": 0.0, "linear_time_us": 0.0}

        k_eff = min(k, len(self.records))
        scaled_query = (query_vec_7d * self.sqrt_lambda).reshape(1, -1)

        # 1. Measure BallTree query latency
        t0 = time.perf_counter()
        if self.tree is not None:
            distances, indices = self.tree.query(scaled_query, k=k_eff)
            dists = distances[0].tolist()
            idxs = indices[0].tolist()
        else:
            diffs = self.matrix - scaled_query
            all_dists = np.sqrt(np.sum(diffs ** 2, axis=1))
            idxs = np.argsort(all_dists)[:k_eff].tolist()
            dists = all_dists[idxs].tolist()
        balltree_us = (time.perf_counter() - t0) * 1_000_000.0

        # 2. Measure Linear Scan latency on the same partition for benchmark comparison
        t1 = time.perf_counter()
        linear_dists = [
            weighted_euclidean_distance(query_vec_7d, rec["vector_7d"], self.lambda_weights)
            for rec in self.records
        ]
        _ = sorted(range(len(linear_dists)), key=lambda idx: linear_dists[idx])[:k_eff]
        linear_us = (time.perf_counter() - t1) * 1_000_000.0

        neighbors = []
        for dist_val, rec_idx in zip(dists, idxs):
            rec = self.records[int(rec_idx)]
            sim = float(math.exp(-(float(dist_val) ** 2) / (2.0 * (0.30 ** 2))))
            neighbors.append({
                "acer_id": rec["acer_id"],
                "distance": round(float(dist_val), 4),
                "similarity": round(sim, 4),
                "deviation": float(rec["deviation"]),
                "observed_outcome": float(rec["observed_outcome"]),
                "expected_outcome": float(rec["expected_outcome"]),
                "outcome_confidence": float(rec["outcome_confidence"]),
                "encoded_7d": rec["encoded_7d"],
                "vector_7d": rec["vector_7d"],
            })

        return {
            "neighbors": neighbors,
            "balltree_time_us": round(balltree_us, 2),
            "linear_time_us": round(linear_us, 2),
            "index_type": "sklearn_BallTree" if self.tree is not None else "numpy_vectorized",
        }


def load_partition_acers(
    connection: sqlite3.Connection,
    decision_type: str,
    action_id: str,
    crop: str,
    exclude_acer_id: str | None = None,
) -> list[dict[str, Any]]:
    """Load all eligible ACER records belonging to partition (decision_type, action_id, crop)."""
    rows = connection.execute(
        """SELECT acer_id, context_json, expected_outcome, observed_outcome,
                  deviation, outcome_confidence, created_at
           FROM acer_records
           WHERE decision_type = ? AND action_id = ? AND eligible_for_adaptation = 1
           ORDER BY created_at ASC""",
        (decision_type, action_id),
    ).fetchall()

    target_crop = normalize_crop(crop)
    partition_records: list[dict[str, Any]] = []

    for row in rows:
        # The current ACER is written before CNDA runs.  It must not become
        # its own historical neighbour or inflate the sample gate.
        if exclude_acer_id and row["acer_id"] == exclude_acer_id:
            continue
        try:
            ctx = json.loads(row["context_json"])
        except (TypeError, ValueError):
            ctx = {}
        if normalize_crop(ctx.get("crop")) != target_crop:
            continue
        encoded = encode_7d_context(ctx)
        vec = vector_from_encoded(encoded)
        partition_records.append({
            "acer_id": row["acer_id"],
            "context": ctx,
            "encoded_7d": encoded,
            "vector_7d": vec,
            "expected_outcome": float(row["expected_outcome"]),
            "observed_outcome": float(row["observed_outcome"]),
            "deviation": float(row["deviation"]),
            "outcome_confidence": float(row["outcome_confidence"]),
            "created_at": row["created_at"],
        })

    return partition_records


# ============================================================
# SAMPLE-GATED CNDA (V2 FROZEN SPECIFICATION)
# ============================================================
# Regime 1: N_pi < 5       -> No attribution ("insufficient_sample_support")
# Regime 2: 5 <= N_pi < 10 -> Damped attribution confidence psi(N) = (N - 4) / 6
# Regime 3: N_pi >= 10     -> Full statistical CNDA psi(N) = 1.0

def run_sample_gated_cnda(
    connection: sqlite3.Connection,
    acer_id: str,
    decision_type: str,
    action_id: str,
    current_context: dict[str, Any],
    current_outcome_confidence: float,
    erp_weights: dict[str, float] | None = None,
    inclusion_floor: float = 0.0,
    correlation_threshold: float = 0.35,
    confidence_threshold: float = 0.08,
    k_max: int = 15,
) -> dict[str, Any]:
    """
    Execute V2 Sample-Gated Contextual Nearest-Neighbor Deviation Attribution (CNDA).
    Persists rows in `cnda_attributions` when N_pi >= 5 and returns full diagnostic summary.
    """
    crop = normalize_crop(current_context.get("crop"))
    partition_records = load_partition_acers(
        connection, decision_type, action_id, crop, exclude_acer_id=acer_id
    )
    n_pi = len(partition_records)

    if n_pi < 5:
        return {
            "status": "insufficient_sample_support",
            "regime": "N_lt_5_no_attribution",
            "sample_count": n_pi,
            "damping_factor_psi": 0.0,
            "attributions": [],
            "selected_factors": [],
            "balltree_time_us": 0.0,
            "linear_time_us": 0.0,
        }

    psi = (float(n_pi) - 4.0) / 6.0 if n_pi < 10 else 1.0
    regime = "5_to_9_damped_attribution" if n_pi < 10 else "N_ge_10_full_cnda"

    lambda_weights = compute_dimension_weights(erp_weights, inclusion_floor=inclusion_floor)
    index = PartitionedACERIndex(partition_records, lambda_weights=lambda_weights)

    current_encoded = encode_7d_context(current_context)
    current_vec = vector_from_encoded(current_encoded)
    query_result = index.query_knn(current_vec, k=min(k_max, n_pi))
    neighbors = query_result["neighbors"]

    # Neighbor relevance weights: omega_n = similarity_n * outcome_confidence_n
    omega = np.array(
        [max(1e-6, nb["similarity"] * nb["outcome_confidence"]) for nb in neighbors],
        dtype=np.float64,
    )
    weight_sum = float(np.sum(omega))
    deviations = np.array([nb["deviation"] for nb in neighbors], dtype=np.float64)

    mean_dev = float(np.sum(omega * deviations) / (weight_sum + 1e-9))
    var_dev = float(np.sum(omega * ((deviations - mean_dev) ** 2)) / (weight_sum + 1e-9))
    std_dev = math.sqrt(max(0.0, var_dev))

    attributions: list[dict[str, Any]] = []
    selected_factors: list[dict[str, Any]] = []

    for dim_idx, dim_name in enumerate(CONTEXT_DIMENSIONS):
        vals = np.array([nb["vector_7d"][dim_idx] for nb in neighbors], dtype=np.float64)
        mean_val = float(np.sum(omega * vals) / (weight_sum + 1e-9))
        var_val = float(np.sum(omega * ((vals - mean_val) ** 2)) / (weight_sum + 1e-9))
        std_val = math.sqrt(max(0.0, var_val))

        if std_val > 1e-4 and std_dev > 1e-4:
            cov = float(np.sum(omega * (vals - mean_val) * (deviations - mean_dev)) / (weight_sum + 1e-9))
            rho = float(np.clip(cov / (std_val * std_dev + 1e-9), -1.0, 1.0))
        else:
            rho = 0.0

        support_factor = min(1.0, weight_sum / 1.8)
        assoc_conf = float(np.clip(psi * support_factor * abs(rho) * current_outcome_confidence, 0.0, 1.0))
        is_selected = bool(abs(rho) >= correlation_threshold and assoc_conf >= confidence_threshold)

        attribution_id = str(uuid.uuid4())
        details = {
            "regime": regime,
            "partition_sample_count": n_pi,
            "k_neighbors_used": len(neighbors),
            "damping_psi": round(psi, 4),
            "feature_std": round(std_val, 4),
            "deviation_std": round(std_dev, 4),
            "interpretation": (
                "Statistically associated with outcome deviation (non-causal)"
                if is_selected
                else "Below attribution threshold"
            ),
        }

        connection.execute(
            """INSERT OR REPLACE INTO cnda_attributions
               (attribution_id, acer_id, feature_name, association_method,
                association_value, association_confidence, effective_sample_size,
                selected, details_json, created_at)
               VALUES (?, ?, ?, 'weighted_correlation', ?, ?, ?, ?, ?, ?)""",
            (
                attribution_id,
                acer_id,
                dim_name,
                round(rho, 4),
                round(assoc_conf, 4),
                round(weight_sum, 3),
                int(is_selected),
                json.dumps(details, separators=(",", ":")),
                now(),
            ),
        )

        item = {
            "attribution_id": attribution_id,
            "feature_name": dim_name,
            "association_value": round(rho, 4),
            "association_confidence": round(assoc_conf, 4),
            "effective_sample_size": round(weight_sum, 2),
            "selected": is_selected,
            "details": details,
        }
        attributions.append(item)
        if is_selected:
            selected_factors.append(item)

    attributions.sort(key=lambda x: abs(x["association_value"]), reverse=True)
    selected_factors.sort(key=lambda x: x["association_confidence"], reverse=True)

    return {
        "status": "attributed",
        "regime": regime,
        "sample_count": n_pi,
        "damping_factor_psi": round(psi, 4),
        "effective_neighbor_support": round(weight_sum, 2),
        "attributions": attributions,
        "selected_factors": selected_factors,
        "balltree_time_us": query_result["balltree_time_us"],
        "linear_time_us": query_result["linear_time_us"],
        "index_type": query_result["index_type"],
    }
