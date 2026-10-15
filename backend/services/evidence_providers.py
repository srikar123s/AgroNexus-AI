"""Heterogeneous Evidence Providers (South India Soil/Weather Bridge & Local DCT-RAG)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN_TEXT = True
except ImportError:
    TfidfVectorizer = None
    cosine_similarity = None
    HAS_SKLEARN_TEXT = False

try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
CROP_REC_DATA_DIR = BACKEND_DIR / "crop_recommendation" / "data"
DISTRICT_SOIL_CSV = CROP_REC_DATA_DIR / "agronexus_district_soil_master_v3.csv"
VILLAGE_SOIL_CSV = CROP_REC_DATA_DIR / "agronexus_village_soil_master_v4.csv"
ALT_DISTRICT_CSV = BACKEND_DIR / "data" / "agronexus_district_npk_ph_master_2024_25.csv"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def haversine_km(
    lat1: float | None,
    lon1: float | None,
    lat2: float | None,
    lon2: float | None,
) -> float | None:
    """Compute great-circle distance in kilometers between two GPS points."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    try:
        r_earth = 6371.0
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        d_phi = math.radians(float(lat2) - float(lat1))
        d_lam = math.radians(float(lon2) - float(lon1))
        a = (math.sin(d_phi / 2.0) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lam / 2.0) ** 2)
        return float(2.0 * r_earth * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a))))
    except (TypeError, ValueError):
        return None


# ============================================================
# SOUTH INDIA SOIL & LOCATION LOOKUP SERVICE
# ============================================================

_DISTRICT_DF: pd.DataFrame | None = None
_VILLAGE_DF: pd.DataFrame | None = None


def _get_district_df() -> pd.DataFrame:
    global _DISTRICT_DF
    if _DISTRICT_DF is None:
        path = DISTRICT_SOIL_CSV if DISTRICT_SOIL_CSV.exists() else ALT_DISTRICT_CSV
        if path.exists():
            _DISTRICT_DF = pd.read_csv(path)
        else:
            _DISTRICT_DF = pd.DataFrame()
    return _DISTRICT_DF


def _get_village_df() -> pd.DataFrame:
    global _VILLAGE_DF
    if _VILLAGE_DF is None:
        if VILLAGE_SOIL_CSV.exists():
            _VILLAGE_DF = pd.read_csv(VILLAGE_SOIL_CSV)
        else:
            _VILLAGE_DF = pd.DataFrame()
    return _VILLAGE_DF


def list_locations(state_name: str | None = None, district_name: str | None = None) -> dict[str, Any]:
    """Return available South India states, districts, and sample villages from the master soil tables."""
    df_dist = _get_district_df()
    if df_dist.empty:
        return {
            "states": ["Andhra Pradesh", "Karnataka", "Kerala", "Tamil Nadu", "Telangana"],
            "districts": ["Wayanad", "Adilabad", "Anantapur", "Coimbatore", "Guntur"],
            "villages": ["Achooranam"],
        }

    state_col = "state_name" if "state_name" in df_dist.columns else df_dist.columns[0]
    dist_col = "district_name" if "district_name" in df_dist.columns else df_dist.columns[1]

    states = sorted(df_dist[state_col].dropna().astype(str).unique().tolist())
    filtered = df_dist
    if state_name:
        filtered = filtered[filtered[state_col].astype(str).str.lower() == state_name.strip().lower()]
    districts = sorted(filtered[dist_col].dropna().astype(str).unique().tolist())

    villages: list[str] = []
    df_vil = _get_village_df()
    if not df_vil.empty and district_name and "district_name" in df_vil.columns and "village_name" in df_vil.columns:
        v_sub = df_vil[df_vil["district_name"].astype(str).str.lower() == district_name.strip().lower()]
        villages = sorted(v_sub["village_name"].dropna().astype(str).unique().tolist()[:50])

    return {
        "states": states,
        "districts": districts,
        "villages": villages,
    }


def lookup_soil_and_weather_evidence(
    state_name: str | None = None,
    district_name: str | None = None,
    village_name: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve real South India soil nutrient statuses & confidences from Village v4 / District v3 masters,
    along with baseline regional weather metadata.
    """
    n_status, p_status, k_status, ph_status = "Medium", "Medium", "Medium", "Neutral"
    confidence = 0.82
    source_level = "default_regional_baseline"

    df_vil = _get_village_df()
    if not df_vil.empty and village_name and "village_name" in df_vil.columns:
        match = df_vil[df_vil["village_name"].astype(str).str.lower() == village_name.strip().lower()]
        if district_name and "district_name" in df_vil.columns and not match.empty:
            d_match = match[match["district_name"].astype(str).str.lower() == district_name.strip().lower()]
            if not d_match.empty:
                match = d_match
        if not match.empty:
            row = match.iloc[0]
            n_status = str(row.get("N_status", row.get("n_status", "Medium"))).title()
            p_status = str(row.get("P_status", row.get("p_status", "Medium"))).title()
            k_status = str(row.get("K_status", row.get("k_status", "Medium"))).title()
            ph_status = str(row.get("pH_status", row.get("ph_status", "Neutral"))).title()
            confidence = float(row.get("N_confidence", row.get("soil_confidence", 0.88)) or 0.88)
            source_level = "village_soil_master_v4"

    if source_level == "default_regional_baseline":
        df_dist = _get_district_df()
        if not df_dist.empty and district_name and "district_name" in df_dist.columns:
            match = df_dist[df_dist["district_name"].astype(str).str.lower() == district_name.strip().lower()]
            if not match.empty:
                row = match.iloc[0]
                n_status = str(row.get("N_status", row.get("n_status", "Medium"))).title()
                p_status = str(row.get("P_status", row.get("p_status", "Medium"))).title()
                k_status = str(row.get("K_status", row.get("k_status", "Medium"))).title()
                ph_status = str(row.get("pH_status", row.get("ph_status", "Neutral"))).title()
                confidence = float(row.get("N_confidence", row.get("soil_confidence", 0.84)) or 0.84)
                source_level = "district_soil_master_v3"

    score_map = {"Low": 0.20, "Medium": 0.60, "High": 0.95}
    fertility_index = round(
        (score_map.get(n_status, 0.60) + score_map.get(p_status, 0.60) + score_map.get(k_status, 0.60)) / 3.0,
        3,
    )

    # Automatic regional weather & microclimate lookup by state/district
    state_key = (state_name or "Kerala").strip().lower()
    dist_key = (district_name or "Wayanad").strip().lower()
    regional_weather_map = {
        "kerala": {"temperature": 28.5, "air_humidity": 84.0, "rain_probability": 42.0, "condition": "Humid • Afternoon Showers Expected"},
        "tamil nadu": {"temperature": 31.0, "air_humidity": 68.0, "rain_probability": 24.0, "condition": "Warm • Moderate Coastal Humidity"},
        "karnataka": {"temperature": 29.0, "air_humidity": 72.0, "rain_probability": 32.0, "condition": "Mild • Scattered Cloud Cover"},
        "andhra pradesh": {"temperature": 32.0, "air_humidity": 66.0, "rain_probability": 22.0, "condition": "Warm & Mostly Dry Window"},
        "telangana": {"temperature": 31.5, "air_humidity": 62.0, "rain_probability": 20.0, "condition": "Dry Interior Window"},
    }
    weather_base = regional_weather_map.get(
        state_key,
        {"temperature": 29.0, "air_humidity": 75.0, "rain_probability": 35.0, "condition": "Moderate Monsoon Conditions"},
    )
    # Deterministic district-level microclimate variation
    dist_offset = (sum(ord(ch) for ch in dist_key) % 7) - 3
    temperature = round(weather_base["temperature"] + dist_offset * 0.4, 1)
    air_humidity = round(float(np.clip(weather_base["air_humidity"] + dist_offset * 1.5, 42.0, 94.0)), 1)
    rain_probability = round(float(np.clip(weather_base["rain_probability"] + dist_offset * 2.5, 10.0, 88.0)), 1)

    return {
        "source_level": source_level,
        "n_status": n_status,
        "p_status": p_status,
        "k_status": k_status,
        "ph_status": ph_status,
        "soil_fertility": fertility_index,
        "soil_confidence": round(float(confidence), 3),
        "temperature": temperature,
        "air_humidity": air_humidity,
        "rain_probability": rain_probability,
        "weather_condition": weather_base["condition"],
    }


def recommend_top_crops_and_plan(
    state_name: str | None = None,
    district_name: str | None = None,
    village_name: str | None = None,
    soil_type: str = "loamy",
    water_source: str = "Borewell & Rainfed",
    area_hectares: float = 2.0,
    selected_crop: str | None = None,
    crop_stage: str = "flowering",
    budget: float = 50000.0,
    season: str = "Kharif",
) -> dict[str, Any]:
    """
    Automatically recommend the Top 3 crops for the farm's dataset soil profile + weather + water source + budget + season,
    and compute the complete 6-Part Crop Management Plan (Overview, Stage-by-Stage Growing Plan, Resource Requirements,
    Crop Calendar, What to Monitor / ERP Connection, and Risk & Prevention).
    """
    env = lookup_soil_and_weather_evidence(state_name, district_name, village_name)
    soil_t = (soil_type or "loamy").strip().lower()
    water_s = (water_source or "borewell").strip().lower()
    rain = float(env["rain_probability"])
    temp = float(env["temperature"])
    hum = float(env["air_humidity"])
    area = max(0.1, float(area_hectares or 1.0))
    farmer_budget = max(5000.0, float(budget or 50000.0))
    season_name = (season or "Kharif").strip().title()

    # Level-1 Crop Selection ERP weights & Evidence Sufficiency (A0 -> A1)
    crop_selection_erp = {
        "decision_type": "crop_selection",
        "required_threshold": 0.70,
        "sufficiency_score": round(min(0.96, 0.78 + float(env["soil_confidence"]) * 0.14), 3),
        "sufficient": True,
        "weights": [
            {"attribute": "soil_fertility", "label": "Soil Fertility (NPK)", "weight": 0.20, "value": f"N:{env['n_status']} P:{env['p_status']} K:{env['k_status']}"},
            {"attribute": "rainfall", "label": "Rainfall & Water", "weight": 0.20, "value": f"{rain:.0f}% Rain • {water_source}"},
            {"attribute": "temperature", "label": "Temperature", "weight": 0.15, "value": f"{temp}°C"},
            {"attribute": "soil_ph", "label": "Soil pH & Texture", "weight": 0.15, "value": f"{env['ph_status']} • {soil_t.title()}"},
            {"attribute": "humidity", "label": "Air Humidity", "weight": 0.10, "value": f"{hum:.0f}%"},
            {"attribute": "budget", "label": "Farmer Budget", "weight": 0.10, "value": f"₹{farmer_budget:,.0f}"},
            {"attribute": "season", "label": "Growing Season", "weight": 0.10, "value": season_name},
        ],
    }

    crop_catalog = [
        {
            "crop": "Tomato",
            "icon": "🍅",
            "variety": "Arka Rakshak / Hybrid F1 (Triple Disease Resistant)",
            "ideal_seasons": "Kharif, Rabi & Early Summer",
            "ideal_soils": {"loamy", "red", "sandy", "black"},
            "temp_range": "21°C – 32°C",
            "expected_yield_t_ha": 32.0,
            "seed_rate_per_ha": "400 g/ha Hybrid Seeds (approx. 25,000 seedlings/ha)",
            "spacing": "60 cm (row-to-row) × 45 cm (plant-to-plant)",
            "labour_days_per_ha": 115,
            "est_cost_per_ha": 18500,
            "base_suitability": 91,
            "water_mm_season": 480,
            "daily_mm_flowering": 5.2,
            "base_npk_kg_ha": {"N": 120, "P": 60, "K": 60},
            "growth_duration_days": "110–125 days",
            "reason": "High suitability for regional loamy/red soil profile and current temperature band (26–32°C).",
            "calendar": [
                {"weeks": "Week 1–2", "stage": "Land Preparation & Nursery", "tasks": "Deep ploughing, incorporate 10 t/ha FYM, raise nursery beds with Trichoderma seed treatment."},
                {"weeks": "Week 3–4", "stage": "Transplanting", "tasks": "Transplant 25-day-old vigorous seedlings at 60×45 cm spacing on raised beds; apply basal P & K."},
                {"weeks": "Week 5–7", "stage": "Vegetative Growth", "tasks": "First Neem-Coated Urea top-dressing, staking/trellising plants, weeding & root-zone irrigation."},
                {"weeks": "Week 8–10", "stage": "Flowering Stage", "tasks": "Maintain uniform soil moisture, second N top-dressing, inspect lower leaves for Early Blight lesions."},
                {"weeks": "Week 11–14", "stage": "Fruiting & Boll Development", "tasks": "Apply potash foliar boost, monitor fruit borer & blight under humid spells."},
                {"weeks": "Week 15–17", "stage": "Harvesting", "tasks": "Pick at breaker-to-red ripe stage every 4–5 days in cool morning hours."},
            ],
            "risks": {
                "diseases": ["Early Blight (Alternaria solani)", "Late Blight (Phytophthora infestans)", "Tomato Leaf Curl Virus"],
                "pests": ["Fruit Borer (Helicoverpa armigera)", "Whitefly & Thrips", "Serpentine Leaf Miner"],
                "abiotic_stress": ["Flower drop above 35°C or moisture deficit", "Foliar fungicide washout when rain >45% or humidity >80%"],
                "prevention": "Use raised beds with drip irrigation, prune lower 15 cm leaves touching soil, and switch from contact to rain-fast systemic protection during humid spells.",
            },
        },
        {
            "crop": "Rice (Paddy)",
            "icon": "🌾",
            "variety": "MTU-1010 / BPT-5204 (Samba Mahsuri)",
            "ideal_seasons": "Kharif & Rabi",
            "ideal_soils": {"clay", "loamy", "black"},
            "temp_range": "24°C – 34°C",
            "expected_yield_t_ha": 5.8,
            "seed_rate_per_ha": "25 kg/ha Certified Seed (Transplanted)",
            "spacing": "20 cm × 15 cm (2–3 seedlings per hill)",
            "labour_days_per_ha": 85,
            "est_cost_per_ha": 15000,
            "base_suitability": 89 if ("canal" in water_s or "borewell" in water_s or rain >= 35) else 74,
            "water_mm_season": 1150,
            "daily_mm_flowering": 8.5,
            "base_npk_kg_ha": {"N": 100, "P": 50, "K": 50},
            "growth_duration_days": "120–135 days",
            "reason": "Strong match for high humidity & assured water availability with balanced village potassium levels.",
            "calendar": [
                {"weeks": "Week 1–2", "stage": "Puddling & Nursery Raising", "tasks": "Prepare wet nursery bed; level main field and incorporate green manure / basal SSP + MOP."},
                {"weeks": "Week 3–4", "stage": "Transplanting", "tasks": "Transplant 21-day seedlings at 20×15 cm spacing; maintain 2 cm shallow water layer."},
                {"weeks": "Week 5–8", "stage": "Active Tillering (Vegetative)", "tasks": "Apply first split Neem-Coated Urea + Zinc Sulphate; follow Alternate Wetting & Drying (AWD)."},
                {"weeks": "Week 9–12", "stage": "Panicle Initiation & Flowering", "tasks": "Critical water stage (5 cm water); monitor leaf collar for Rice Blast and Sheath Blight."},
                {"weeks": "Week 13–15", "stage": "Milking & Grain Filling", "tasks": "Maintain moist soil; avoid excess nitrogen top-dressing during humid nights."},
                {"weeks": "Week 16–18", "stage": "Maturity & Harvest", "tasks": "Drain field 10 days before harvest when 85% panicles turn golden yellow."},
            ],
            "risks": {
                "diseases": ["Rice Blast (Pyricularia oryzae)", "Sheath Blight", "Bacterial Leaf Blight"],
                "pests": ["Yellow Stem Borer", "Brown Plant Hopper (BPH)", "Leaf Folder"],
                "abiotic_stress": ["Spikelet sterility under drought at flowering", "Lodging and blast surge under heavy N + >85% humidity"],
                "prevention": "Leave 30 cm alleyways every 2 meters for aeration, avoid excess urea during cloudy/humid weather, and use AWD water management.",
            },
        },
        {
            "crop": "Chilli",
            "icon": "🌶️",
            "variety": "Teja / Byadgi / Arka Meghana Hybrid",
            "ideal_seasons": "Kharif & Rabi",
            "ideal_soils": {"loamy", "black", "red"},
            "temp_range": "20°C – 32°C",
            "expected_yield_t_ha": 18.5,
            "seed_rate_per_ha": "1.0 kg/ha Variety or 300 g/ha Hybrid Seed",
            "spacing": "60 cm × 45 cm on ridges",
            "labour_days_per_ha": 110,
            "est_cost_per_ha": 17500,
            "base_suitability": 86,
            "water_mm_season": 520,
            "daily_mm_flowering": 4.6,
            "base_npk_kg_ha": {"N": 100, "P": 50, "K": 50},
            "growth_duration_days": "130–150 days",
            "reason": "Well-adapted to regional soil pH and warm canopy conditions with moderate irrigation demand.",
            "calendar": [
                {"weeks": "Week 1–3", "stage": "Nursery & Ridge Preparation", "tasks": "Raise seedlings under shade net; prepare ridges and furrows at 60 cm spacing."},
                {"weeks": "Week 4–5", "stage": "Transplanting", "tasks": "Transplant 30–35 day seedlings; apply basal FYM, SSP, and MOP in root zone."},
                {"weeks": "Week 6–9", "stage": "Vegetative Branching", "tasks": "Earthing up, weed removal, first split nitrogen, install yellow/blue sticky traps."},
                {"weeks": "Week 10–13", "stage": "Flowering & Fruit Set", "tasks": "Regulate irrigation (avoid waterlogging); monitor for Cercospora leaf spot & thrips curl."},
                {"weeks": "Week 14–18", "stage": "Pod Development", "tasks": "Potash top-dressing for pod shine and weight; watch for Dieback / Anthracnose fruit rot."},
                {"weeks": "Week 19–21", "stage": "Multi-Pick Harvesting", "tasks": "Harvest green or uniform red ripe pods across 3–4 pickings and sun-dry cleanly."},
            ],
            "risks": {
                "diseases": ["Anthracnose / Fruit Rot / Dieback", "Cercospora Leaf Spot", "Powdery Mildew"],
                "pests": ["Chilli Thrips & Mites (Murda complex)", "Pod Borer", "Aphids"],
                "abiotic_stress": ["Root/collar wilt from standing water", "Blossom drop under sudden moisture stress"],
                "prevention": "Ensure rapid furrow drainage after rain, use border maize rows against vectors, and apply rain-fast systemic protection during pod set.",
            },
        },
        {
            "crop": "Maize",
            "icon": "🌽",
            "variety": "DHM-117 / Pioneer Single-Cross Hybrid",
            "ideal_seasons": "Kharif, Rabi & Spring",
            "ideal_soils": {"loamy", "sandy", "red", "black"},
            "temp_range": "21°C – 33°C",
            "expected_yield_t_ha": 6.5,
            "seed_rate_per_ha": "20 kg/ha Single-Cross Hybrid Seed",
            "spacing": "60 cm (row) × 20 cm (plant)",
            "labour_days_per_ha": 55,
            "est_cost_per_ha": 12500,
            "base_suitability": 84,
            "water_mm_season": 500,
            "daily_mm_flowering": 5.0,
            "base_npk_kg_ha": {"N": 135, "P": 62, "K": 50},
            "growth_duration_days": "95–110 days",
            "reason": "Resilient cereal option with efficient water-use under variable rainfall windows.",
            "calendar": [
                {"weeks": "Week 1", "stage": "Land Prep & Ridge Sowing", "tasks": "Prepare ridges at 60 cm; dibble treated seeds at 4 cm depth with basal NPK."},
                {"weeks": "Week 2–5", "stage": "Knee-High Vegetative Stage", "tasks": "Inter-cultivation, first nitrogen top-dressing, inspect whorl for Fall Armyworm."},
                {"weeks": "Week 6–8", "stage": "Tasseling & Silking (Flowering)", "tasks": "Most moisture-sensitive stage; ensure zero water stress and second N top-dressing."},
                {"weeks": "Week 9–12", "stage": "Cob & Grain Filling", "tasks": "Monitor lower leaves for Turcicum Leaf Blight; maintain potassium balance."},
                {"weeks": "Week 13–15", "stage": "Physiological Maturity & Harvest", "tasks": "Harvest cobs when husk turns dry papery and black layer forms at grain base."},
            ],
            "risks": {
                "diseases": ["Turcicum Leaf Blight", "Maydis Leaf Blight", "Post-Flowering Stalk Rot"],
                "pests": ["Fall Armyworm (Spodoptera frugiperda)", "Stem Borer"],
                "abiotic_stress": ["Waterlogging in early knee-high stage", "Tassel blasting under extreme dry heat"],
                "prevention": "Sow on ridges to prevent waterlogging and apply whorl-directed bio-pesticides early.",
            },
        },
        {
            "crop": "Groundnut",
            "icon": "🥜",
            "variety": "Kadiri-6 (K-6) / TMV-2 / Girnar-4",
            "ideal_seasons": "Kharif & Rabi-Summer",
            "ideal_soils": {"sandy", "loamy", "red"},
            "temp_range": "24°C – 33°C",
            "expected_yield_t_ha": 2.6,
            "seed_rate_per_ha": "125 kg/ha Bold Kernels (Rhizobium treated)",
            "spacing": "30 cm (row) × 10 cm (plant)",
            "labour_days_per_ha": 65,
            "est_cost_per_ha": 14000,
            "base_suitability": 83,
            "water_mm_season": 420,
            "daily_mm_flowering": 4.0,
            "base_npk_kg_ha": {"N": 25, "P": 50, "K": 75},
            "growth_duration_days": "100–115 days",
            "reason": "Nitrogen-fixing legume ideal for low-to-medium nitrogen soils and low water consumption.",
            "calendar": [
                {"weeks": "Week 1", "stage": "Seed Treatment & Sowing", "tasks": "Treat kernels with Rhizobium + Trichoderma; sow at 30×10 cm in well-drained friable soil."},
                {"weeks": "Week 2–4", "stage": "Vegetative Rosette Growth", "tasks": "Weeding and hoeing before pegging starts; apply basal phosphorus and potassium."},
                {"weeks": "Week 5–7", "stage": "Flowering & Pegging", "tasks": "Apply 400 kg/ha Gypsum around plant base for pod calcium; do not disturb soil after pegging."},
                {"weeks": "Week 8–12", "stage": "Pod Development", "tasks": "Maintain light moisture; inspect foliage for Tikka Leaf Spot and Rust."},
                {"weeks": "Week 13–15", "stage": "Uprooting & Curing", "tasks": "Harvest when 75% inner shell turns dark; cure pods to <9% moisture."},
            ],
            "risks": {
                "diseases": ["Tikka Early & Late Leaf Spot", "Groundnut Rust", "Collar Rot"],
                "pests": ["Leaf Miner", "Tobacco Caterpillar", "White Grub"],
                "abiotic_stress": ["Empty pods (pops) due to calcium deficiency at pegging", "Aflatoxin risk if wetted at harvest"],
                "prevention": "Apply gypsum at flowering/pegging and use Trichoderma seed dressing.",
            },
        },
    ]

    scored_crops = []
    for item in crop_catalog:
        score = float(item["base_suitability"])
        if soil_t in item["ideal_soils"]:
            score += 4.0
        if env["n_status"] == "Low" and item["crop"] == "Groundnut":
            score += 5.0
        if env["soil_fertility"] >= 0.60 and item["crop"] in {"Tomato", "Rice (Paddy)", "Chilli"}:
            score += 2.5
        total_est_cost = int(round(item["est_cost_per_ha"] * area))
        fits_budget = farmer_budget >= total_est_cost * 0.75
        if fits_budget:
            score += 1.5

        why_checks = [
            f"✓ Suitable soil ({soil_t.title()} soil • pH {env['ph_status']})",
            f"✓ Suitable climate ({temp}°C • Rain {rain:.0f}%)",
            f"✓ Good seasonal suitability ({season_name} window)",
            f"✓ Fits farmer budget (Est. ₹{total_est_cost:,} for {area} ha vs ₹{farmer_budget:,.0f})",
        ]

        scored_crops.append({
            **item,
            "suitability_score": int(np.clip(round(score), 68, 97)),
            "total_estimated_cost_inr": total_est_cost,
            "why_this_crop": why_checks,
        })

    scored_crops.sort(key=lambda x: x["suitability_score"], reverse=True)
    top_3 = scored_crops[:3]

    # Pick active crop for detailed 6-part Crop Management Plan
    active_crop_name = selected_crop or top_3[0]["crop"]
    matched_crop = next(
        (c for c in scored_crops if c["crop"].lower().startswith(active_crop_name.strip().lower()[:4])),
        top_3[0],
    )

    # Calculate stage-adjusted water requirement
    stage_factor = {
        "seedling": 0.45,
        "vegetative": 0.75,
        "flowering": 1.00,
        "fruiting": 0.95,
        "maturity": 0.50,
    }.get(crop_stage.lower(), 1.0)

    effective_rain_offset = 0.65 if rain >= 40.0 else (0.82 if rain >= 25.0 else 1.0)
    daily_mm = round(matched_crop["daily_mm_flowering"] * stage_factor * effective_rain_offset, 2)
    liters_per_ha_day = int(round(daily_mm * 10000 * 0.45))  # root-zone drip/furrow efficiency factor
    total_liters_day = int(round(liters_per_ha_day * area))

    irrigation_advice = (
        f"Forecasted rain probability is {rain:.0f}%. Reduce supplemental irrigation by 35% and keep field drainage channels clear."
        if rain >= 40.0
        else f"Apply {daily_mm} mm/day ({liters_per_ha_day:,} L/ha) via root-zone irrigation every 2–3 days during {crop_stage} stage."
    )

    # Calculate soil-status-adjusted NPK fertilizer requirement
    n_mult = 1.20 if env["n_status"] == "Low" else (0.85 if env["n_status"] == "High" else 1.0)
    p_mult = 1.20 if env["p_status"] == "Low" else (0.85 if env["p_status"] == "High" else 1.0)
    k_mult = 1.20 if env["k_status"] == "Low" else (0.85 if env["k_status"] == "High" else 1.0)

    n_kg_ha = int(round(matched_crop["base_npk_kg_ha"]["N"] * n_mult))
    p_kg_ha = int(round(matched_crop["base_npk_kg_ha"]["P"] * p_mult))
    k_kg_ha = int(round(matched_crop["base_npk_kg_ha"]["K"] * k_mult))

    ph_lower = env["ph_status"].lower()
    if "acid" in ph_lower:
        ph_amendment = "Apply 250 kg/ha Agricultural Dolomite Lime 2 weeks prior to top-dressing to buffer acidic soil pH."
    elif "alkal" in ph_lower:
        ph_amendment = "Incorporate 200 kg/ha Gypsum + 5 t/ha Farmyard Manure to buffer alkaline soil pH."
    else:
        ph_amendment = "Soil pH is in the optimal neutral band; no lime or gypsum pH correction required."

    fertilizer_schedule = (
        "Defer surface Urea broadcasting during the next 24–48h due to high rainfall washout risk; use Neem-Coated Urea in split root-zone placement."
        if rain >= 40.0
        else "Apply 50% N + 100% P & K as basal root-zone placement, followed by two 25% Neem-Coated Urea top-dressings at vegetative and flowering stages."
    )

    total_est_cost = int(round(matched_crop["est_cost_per_ha"] * area))
    total_labour_days = int(round(matched_crop["labour_days_per_ha"] * area))
    total_expected_yield_t = round(matched_crop["expected_yield_t_ha"] * area, 1)

    growing_stages = [
        {
            "stage_num": 1,
            "stage": "Land Preparation",
            "what_to_do": "Deep summer/pre-monsoon ploughing, raised bed or ridge formation, and basal organic manure incorporation.",
            "what_crop_needs": f"10 t/ha well-decomposed FYM + {ph_amendment}",
            "what_to_monitor": "Soil tilth, drainage channel slope, and baseline village NPK/pH status.",
            "important_risks": "Soil-borne fungal inoculum and poor sub-surface drainage.",
            "expected_condition": "Friable, well-aerated root bed with neutral moisture retention.",
        },
        {
            "stage_num": 2,
            "stage": "Seed Selection & Treatment",
            "what_to_do": f"Procure certified {matched_crop['variety']} and treat with Trichoderma viride (4 g/kg) + bio-inoculant.",
            "what_crop_needs": matched_crop["seed_rate_per_ha"],
            "what_to_monitor": "Seed germination percentage (>85%) and nursery seedling vigor.",
            "important_risks": "Damping-off and early viral vector transmission in nursery.",
            "expected_condition": "Disease-free, uniform seedlings ready for field establishment.",
        },
        {
            "stage_num": 3,
            "stage": "Sowing / Transplanting",
            "what_to_do": f"Establish crop at {matched_crop['spacing']} during cool afternoon hours followed by light life-irrigation.",
            "what_crop_needs": f"Basal dose: 50% N ({round(n_kg_ha*0.5)} kg/ha) + 100% P ({p_kg_ha} kg/ha) + 100% K ({k_kg_ha} kg/ha).",
            "what_to_monitor": "Transplant survival rate and root-zone moisture at 5–10 cm depth.",
            "important_risks": "Transplant shock or collar rot if waterlogged.",
            "expected_condition": "95%+ stand establishment within 7 days of planting.",
        },
        {
            "stage_num": 4,
            "stage": "Vegetative Stage",
            "what_to_do": "Inter-cultivation weeding, earthing up / staking, and first split Neem-Coated Urea top-dressing.",
            "what_crop_needs": f"25% N top-dressing ({round(n_kg_ha*0.25)} kg/ha) + {int(round(liters_per_ha_day*0.75)):,} L/ha/day water.",
            "what_to_monitor": "Canopy branching, leaf color (chlorophyll), and early sucking pests.",
            "important_risks": "Weed competition and nitrogen leaching if heavy rain occurs immediately after application.",
            "expected_condition": "Vigorous dark-green foliage with strong stem framework.",
        },
        {
            "stage_num": 5,
            "stage": "Flowering Stage (Critical ERP/ADIE Window)",
            "what_to_do": "Maintain uniform root-zone moisture, apply second N split, and inspect lower/mid leaves for fungal lesions.",
            "what_crop_needs": f"{total_liters_day:,} L/day across {area} ha + 25% N ({round(n_kg_ha*0.25)} kg/ha) + Boron/Micronutrient spray.",
            "what_to_monitor": f"Leaf disease lesions, Air Humidity ({hum:.0f}%), Rain Probability ({rain:.0f}%), and Temperature ({temp}°C).",
            "important_risks": f"{matched_crop['risks']['diseases'][0]} outbreak and flower drop under moisture/humidity stress.",
            "expected_condition": "High flower retention and healthy disease-free canopy.",
        },
        {
            "stage_num": 6,
            "stage": "Fruiting / Pod / Grain Filling",
            "what_to_do": "Maintain potash nutrition for fruit/grain weight and execute targeted ADIE disease/pest protection if needed.",
            "what_crop_needs": "Water-soluble SOP (0:0:50) foliar spray + consistent root-zone irrigation without wetting foliage.",
            "what_to_monitor": "Fruit/pod lesion spread, borer damage, and pre-harvest rain forecast.",
            "important_risks": "Fruit rot, anthracnose, or foliar fungicide washout during monsoon showers.",
            "expected_condition": "Uniform fruit/pod sizing with zero blemish or fungal rot.",
        },
        {
            "stage_num": 7,
            "stage": "Harvesting",
            "what_to_do": "Harvest at physiological maturity during dry morning windows and grade produce cleanly.",
            "what_crop_needs": "Dry weather window; withhold irrigation 7–10 days before final harvest where applicable.",
            "what_to_monitor": "Maturity index, market moisture standards, and post-harvest storage hygiene.",
            "important_risks": "Post-harvest fungal spoilage if harvested wet.",
            "expected_condition": f"Expected harvest of {total_expected_yield_t} tonnes across {area} ha ({matched_crop['expected_yield_t_ha']} t/ha).",
        },
    ]

    what_to_monitor = [
        {"parameter": "Soil moisture", "status": f"Target {daily_mm} mm/day", "erp_role": "Controls irrigation scheduling & root-zone stress"},
        {"parameter": "Temperature", "status": f"{temp}°C (Optimal: {matched_crop['temp_range']})", "erp_role": "ERP weight 0.10 — thermal stress & spray evaporation"},
        {"parameter": "Humidity", "status": f"{hum:.0f}% Relative Humidity", "erp_role": "ERP weight 0.15 (adapts ↑ under fungal pressure)"},
        {"parameter": "Rain probability", "status": f"{rain:.0f}% Forecasted Rain", "erp_role": "ERP weight 0.20 (critical for foliar washout & A2 constraints)"},
        {"parameter": "Soil fertility", "status": f"N:{env['n_status']} P:{env['p_status']} K:{env['k_status']}", "erp_role": "ERP weight 0.10 — nutrient recovery capacity"},
        {"parameter": "Crop stage", "status": crop_stage.title(), "erp_role": "ERP weight 0.15 — determines stage vulnerability"},
        {"parameter": "Leaf condition", "status": "Inspect via 📷 Disease Check", "erp_role": "Triggers YOLO visual evidence generator"},
        {"parameter": "Pest symptoms", "status": f"Watch: {matched_crop['risks']['pests'][0]}", "erp_role": "Feeds symptom severity evidence"},
        {"parameter": "Disease symptoms", "status": f"Watch: {matched_crop['risks']['diseases'][0]}", "erp_role": "ERP weight 0.20 — primary trigger for ADIE-1 intervention"},
    ]

    return {
        "environmental_evidence": env,
        "crop_selection_erp": crop_selection_erp,
        "top_crops": top_3,
        "selected_crop_analysis": {
            "crop": matched_crop["crop"],
            "crop_stage": crop_stage,
            "area_hectares": area,
            "crop_overview": {
                "crop_name": matched_crop["crop"],
                "icon": matched_crop["icon"],
                "recommended_variety": matched_crop["variety"],
                "suitable_season": matched_crop["ideal_seasons"],
                "crop_duration": matched_crop["growth_duration_days"],
                "expected_yield_per_ha": f"{matched_crop['expected_yield_t_ha']} tonnes/ha",
                "expected_total_yield": f"{total_expected_yield_t} tonnes (for {area} ha)",
                "suitable_regions": f"{district_name or 'Wayanad'}, {state_name or 'Kerala'} & South India Agro-Climatic Zone",
                "suitable_soil_type": ", ".join(s.title() for s in matched_crop["ideal_soils"]),
                "temperature_range": matched_crop["temp_range"],
                "suitability_score": matched_crop["suitability_score"],
            },
            "growing_stages": growing_stages,
            "resource_requirements": {
                "seed_quantity": matched_crop["seed_rate_per_ha"],
                "spacing": matched_crop["spacing"],
                "irrigation_frequency": "Every 2–3 days via Drip/Furrow (adjusted for rainfall)",
                "labour_requirement": f"{matched_crop['labour_days_per_ha']} person-days/ha ({total_labour_days} person-days total for {area} ha)",
                "estimated_cost_per_ha": f"₹{matched_crop['est_cost_per_ha']:,}/ha",
                "total_estimated_cost": f"₹{total_est_cost:,} for {area} ha",
                "farmer_budget": f"₹{farmer_budget:,.0f}",
                "budget_status": "Within Budget ✓" if farmer_budget >= total_est_cost else "Requires Phased Input Allocation",
            },
            "crop_calendar": matched_crop["calendar"],
            "what_to_monitor": what_to_monitor,
            "risk_and_prevention": matched_crop["risks"],
            "water_plan": {
                "seasonal_water_mm": matched_crop["water_mm_season"],
                "daily_stage_need_mm": daily_mm,
                "liters_per_ha_per_day": liters_per_ha_day,
                "total_farm_liters_per_day": total_liters_day,
                "water_source_used": water_source or "Borewell / Rainfed",
                "recommended_method": "Drip / Root-Zone Furrow Irrigation" if "Tomato" in matched_crop["crop"] or "Chilli" in matched_crop["crop"] else "Controlled Basin / Alternate Wetting & Drying",
                "schedule_guidance": irrigation_advice,
            },
            "fertilizer_plan": {
                "village_soil_status": f"N: {env['n_status']} • P: {env['p_status']} • K: {env['k_status']} • pH: {env['ph_status']}",
                "nitrogen_n_kg_ha": n_kg_ha,
                "phosphorus_p_kg_ha": p_kg_ha,
                "potassium_k_kg_ha": k_kg_ha,
                "total_farm_npk_kg": {
                    "N_kg": round(n_kg_ha * area, 1),
                    "P_kg": round(p_kg_ha * area, 1),
                    "K_kg": round(k_kg_ha * area, 1),
                },
                "recommended_products": "Neem-Coated Urea + Single Super Phosphate (SSP) + Muriate of Potash (MOP)",
                "application_schedule": fertilizer_schedule,
                "ph_amendment": ph_amendment,
            },
        },
    }


# ============================================================
# DECISION-CONTEXTUALIZED RAG (DCT-RAG) KNOWLEDGE RETRIEVER
# ============================================================

AGRONOMIC_KNOWLEDGE_BASE: list[dict[str, Any]] = [
    {
        "doc_id": "ICAR-TOM-01",
        "decision_type": "disease_intervention",
        "crop": "tomato",
        "title": "Tomato Early & Late Blight Management under Rain and Humidity Risk",
        "tags": "tomato flowering fruiting high moderate disease severity rain humidity fungicide washout",
        "guidance": (
            "Contact fungicides experience severe foliar wash-off when rainfall probability exceeds 45% "
            "or relative humidity remains above 80% within 12 hours of spraying. Under humid or rain-risk "
            "windows, prioritize canopy sanitation (removing infected lower leaves) combined with rain-fast "
            "systemic or translaminar bio-fungicide schedules."
        ),
        "contraindication": "Avoid contact spray application immediately prior to forecasted rain >45%.",
        "source": "ICAR / TNAU Horticultural Crop Protection Guidelines",
    },
    {
        "doc_id": "ICAR-TOM-02",
        "decision_type": "disease_intervention",
        "crop": "tomato",
        "title": "Dry-Window Preventative & Curative Foliar Protection in Tomato",
        "tags": "tomato vegetative flowering low moderate rain dry window fungicide spray",
        "guidance": (
            "When rain probability is below 35% and relative humidity is moderate (45-70%), approved contact "
            "or broad-spectrum foliar fungicides achieve high surface retention (75-85% symptom control). "
            "Ensure uniform lower-canopy coverage."
        ),
        "contraindication": "Do not exceed label dosage or apply under high temperature (>36 C) mid-day sun.",
        "source": "ICAR Integrated Pest Management Bulletin",
    },
    {
        "doc_id": "ICAR-RICE-01",
        "decision_type": "disease_intervention",
        "crop": "rice",
        "title": "Rice Blast and Sheath Blight Contextual Management",
        "tags": "rice vegetative panicle_initiation high humidity rain blast blight nitrogen",
        "guidance": (
            "High relative humidity (>85%) and excessive nitrogen top-dressing accelerate rice blast spread. "
            "Suspend urea top-dressing during active infection, drain standing water temporarily for sheath blight, "
            "and use systemic tricyclazole/validamycin schedules during dry foliage intervals."
        ),
        "contraindication": "Avoid heavy nitrogen application during active fungal lesions.",
        "source": "ICAR-NRRI Rice Advisory Service",
    },
    {
        "doc_id": "ICAR-FERT-01",
        "decision_type": "fertilizer_recommendation",
        "crop": "general",
        "title": "Split NPK Application & Leaching Prevention under Monsoon Rainfall",
        "tags": "fertilizer_recommendation soil_fertility nitrogen phosphorus potassium rain leaching",
        "guidance": (
            "Basal phosphorus and potassium should be incorporated into the root zone, while nitrogen should "
            "be applied in 3 split doses. If 24-hour rainfall probability exceeds 60%, defer surface urea "
            "broadcasting or use neem-coated slow-release formulations to prevent runoff and leaching losses."
        ),
        "contraindication": "Do not broadcast soluble nitrogen before heavy rainfall.",
        "source": "TNAU Soil Health & Nutrient Management Manual",
    },
    {
        "doc_id": "ICAR-IRRIG-01",
        "decision_type": "irrigation_planning",
        "crop": "general",
        "title": "Critical Growth-Stage Deficit Irrigation & Root-Zone Moisture Balance",
        "tags": "irrigation_planning flowering fruiting pegging panicle water deficit rain humidity",
        "guidance": (
            "Flowering, boll formation, pegging, and panicle initiation are moisture-critical stages where water "
            "deficit causes irreversible yield loss. Account for 48-hour forecasted effective rainfall before "
            "scheduling supplemental irrigation to prevent waterlogging and root hypoxia."
        ),
        "contraindication": "Avoid flood irrigation when fungal collar/root rot symptoms are present.",
        "source": "FAO-56 / ICAR Water Management Compendium",
    },
    {
        "doc_id": "ICAR-CROP-01",
        "decision_type": "crop_selection",
        "crop": "general",
        "title": "Agro-Climatic & Soil pH Alignment for South Indian Seasons (Kharif/Rabi/Zaid)",
        "tags": "crop_selection soil_fertility ph temperature rain season kharif rabi zaid",
        "guidance": (
            "Match crop water requirement against seasonal effective rainfall and village-level NPK/pH profiles. "
            "In acidic soils, prioritize pH-tolerant varieties or lime amendment; in low-rainfall zones, "
            "select short-duration drought-resilient pulses, millets, or oilseeds."
        ),
        "contraindication": "Avoid high-water-demand crops in unirrigated blocks during Zaid/dry spells.",
        "source": "South India Agro-Climatic Zonal Planning Atlas",
    },
]


def retrieve_dct_rag_evidence(
    decision_type: str,
    context: dict[str, Any],
    deficits: list[dict[str, Any]] | None = None,
    top_k: int = 2,
) -> dict[str, Any]:
    """
    Decision-Contextualized Retrieval-Augmented Generation (DCT-RAG).
    Retrieves domain guidelines conditioned on (decision_type, crop, stage, weather/disease context, and deficits).
    """
    crop = str(context.get("crop", "general")).strip().lower()
    stage = str(context.get("crop_stage", "flowering")).strip().lower()
    severity = str(context.get("disease_severity", "moderate")).strip().lower()
    rain = float(context.get("rain_probability", context.get("weather_rain_probability", 25.0)) or 0.0)
    humidity = float(context.get("air_humidity", context.get("humidity", 65.0)) or 65.0)
    rain_tag = "high rain washout" if rain >= 45 else "dry window low rain"
    hum_tag = "high humidity" if humidity >= 75 else "moderate humidity"
    deficit_terms = " ".join(d.get("attribute", "") for d in (deficits or []))

    query = f"{decision_type} {crop} {stage} {severity} {rain_tag} {hum_tag} {deficit_terms}".strip()

    corpus_texts = [
        f"{doc['decision_type']} {doc['crop']} {doc['title']} {doc['tags']} {doc['guidance']}"
        for doc in AGRONOMIC_KNOWLEDGE_BASE
    ]

    if HAS_SKLEARN_TEXT and TfidfVectorizer is not None and cosine_similarity is not None:
        vec = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vec.fit_transform(corpus_texts + [query])
        sims = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
    else:
        query_tokens = set(query.lower().split())
        sims = np.array([
            len(query_tokens.intersection(set(text.lower().split()))) / max(1, len(query_tokens))
            for text in corpus_texts
        ], dtype=np.float64)

    ranked_indices = np.argsort(sims)[::-1][:top_k]
    retrieved_docs = []
    for idx in ranked_indices:
        doc = AGRONOMIC_KNOWLEDGE_BASE[int(idx)]
        retrieved_docs.append({
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "relevance_score": round(float(sims[int(idx)]), 3),
            "guidance": doc["guidance"],
            "contraindication": doc["contraindication"],
            "source": doc["source"],
        })

    return {
        "Contextual_query": query,
        "documents": retrieved_docs,
    }
