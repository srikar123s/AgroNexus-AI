import os
import pandas as pd
import numpy as np

try:
    from season_service import get_season_info
except ImportError:
    from .season_service import get_season_info


# ============================================================
# AGRONEXUS CROP RECOMMENDATION V1.11
# ============================================================
#
# V1.11:
#   - Village V4 soil preferred
#   - District V3 fallback
#   - Automatic season
#   - Season contributes 0% to suitability score
#   - In-season crops receive ranking priority separately
#   - Off-season crops remain visible and are flagged
#   - 7-day / 30-day / seasonal water information retained
#   - Critical-condition assessment retained
#
# WATER MODEL V1.11:
#
#   OLD:
#       Root-zone water storage
#           vs.
#       Whole-crop water requirement
#
#   NEW:
#       Seasonal effective rainfall
#           vs.
#       Crop water requirement
#
#   Root-zone water remains available as farm/current
#   water-status information, but is NOT used as the
#   crop-cycle water suitability score.
#
#
# SCORE MATRIX:
#
#   Water        20%
#   Temperature  15%
#   Soil         15%
#   Nitrogen     10%
#   Phosphorus   10%
#   Potassium    10%
#   pH           10%
#   Humidity     10%
#   Season        0%
#
# Total = 100%
# ============================================================


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

CROP_FILE = os.path.join(
    DATA_DIR,
    "Crop recommendation dataset.csv"
)

DISTRICT_SOIL_FILE = os.path.join(
    DATA_DIR,
    "agronexus_district_soil_master_v3.csv"
)

if not os.path.exists(DISTRICT_SOIL_FILE):

    alternate_district_file = os.path.join(
        DATA_DIR,
        "agronexus_district_npk_ph_master_2024_25.csv"
    )

    if os.path.exists(alternate_district_file):
        DISTRICT_SOIL_FILE = alternate_district_file


VILLAGE_SOIL_FILE = os.path.join(
    DATA_DIR,
    "agronexus_village_soil_master_v4.csv"
)


# ============================================================
# V1.11 SCORE WEIGHTS
# ============================================================

BASE_WEIGHTS = {
    "water": 20,
    "temperature": 15,
    "soil": 15,
    "nitrogen": 10,
    "phosphorus": 10,
    "potassium": 10,
    "ph": 10,
    "humidity": 10,

    # Season is deliberately NOT part of the 100-point score.
    "season": 0,
}

assert sum(BASE_WEIGHTS.values()) == 100


LEVELS = {
    "low": 0,
    "medium": 1,
    "high": 2,
}


# ============================================================
# DATA LOADING
# ============================================================

def load_crop_data():

    if not os.path.exists(CROP_FILE):
        raise FileNotFoundError(
            f"Crop dataset not found: {CROP_FILE}"
        )

    df = pd.read_csv(CROP_FILE)

    required_columns = [
        "CROPS",
        "SOIL",
        "SEASON",
        "SOIL_PH",
        "SOIL_PH_HIGH",
        "TEMP",
        "MAX_TEMP",
        "WATERREQUIRED",
        "WATERREQUIRED_MAX",
        "RELATIVE_HUMIDITY",
        "RELATIVE_HUMIDITY_MAX",
        "N",
        "N_MAX",
        "P",
        "P_MAX",
        "K",
        "K_MAX",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing crop dataset columns: {missing}"
        )

    numeric_columns = [
        "SOIL_PH",
        "SOIL_PH_HIGH",
        "TEMP",
        "MAX_TEMP",
        "WATERREQUIRED",
        "WATERREQUIRED_MAX",
        "RELATIVE_HUMIDITY",
        "RELATIVE_HUMIDITY_MAX",
        "N",
        "N_MAX",
        "P",
        "P_MAX",
        "K",
        "K_MAX",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    return df


def load_soil_data():

    if not os.path.exists(DISTRICT_SOIL_FILE):
        raise FileNotFoundError(
            f"District soil master not found: "
            f"{DISTRICT_SOIL_FILE}"
        )

    return pd.read_csv(DISTRICT_SOIL_FILE)


def load_village_soil_data():

    if not os.path.exists(VILLAGE_SOIL_FILE):
        return pd.DataFrame()

    return pd.read_csv(VILLAGE_SOIL_FILE)


CROP_DATA = load_crop_data()
SOIL_DATA = load_soil_data()
VILLAGE_SOIL_DATA = load_village_soil_data()


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(value):

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip().casefold()


def split_values(value):

    if value is None:
        return []

    try:
        if pd.isna(value):
            return []
    except (TypeError, ValueError):
        pass

    return [
        item.strip().casefold()
        for item in str(value).split("|")
        if item.strip()
    ]


# ============================================================
# CROP NUTRIENT LEVEL PREPARATION
# ============================================================

def prepare_crop_levels(df):

    df = df.copy()

    for nutrient in ["N", "P", "K"]:

        midpoint = (
            df[nutrient]
            + df[f"{nutrient}_MAX"]
        ) / 2

        q1 = midpoint.quantile(1 / 3)
        q2 = midpoint.quantile(2 / 3)

        df[f"{nutrient}_requirement_level"] = pd.cut(
            midpoint,
            bins=[
                -np.inf,
                q1,
                q2,
                np.inf,
            ],
            labels=[
                "Low",
                "Medium",
                "High",
            ],
        )

    return df


CROP_DATA = prepare_crop_levels(CROP_DATA)


# ============================================================
# CATEGORICAL MATCH
# ============================================================

def categorical_match(actual, requirement):

    actual_value = normalize_text(actual)

    if not actual_value:
        return 0.5

    requirements = split_values(requirement)

    if not requirements:
        return 0.5

    for required in requirements:

        if (
            actual_value == required
            or actual_value in required
            or required in actual_value
        ):
            return 1.0

    return 0.0


# ============================================================
# NPK MATCH
# ============================================================

def nutrient_level_score(actual, required):

    actual_value = normalize_text(actual)
    required_value = normalize_text(required)

    if not actual_value or not required_value:
        return 0.5

    if actual_value in {
        "tie",
        "ambiguous",
        "unknown",
        "unavailable",
    }:
        return 0.5

    actual_level = LEVELS.get(actual_value)
    required_level = LEVELS.get(required_value)

    if actual_level is None or required_level is None:
        return 0.5

    difference = abs(
        actual_level - required_level
    )

    if difference == 0:
        return 1.0

    if difference == 1:
        return 0.5

    return 0.0


# ============================================================
# NUMERIC RANGE MATCH
# ============================================================

def range_score(value, minimum, maximum):

    if value is None or minimum is None or maximum is None:
        return 0.5

    try:
        if (
            pd.isna(value)
            or pd.isna(minimum)
            or pd.isna(maximum)
        ):
            return 0.5
    except (TypeError, ValueError):
        return 0.5

    value = float(value)
    minimum = float(minimum)
    maximum = float(maximum)

    if minimum <= value <= maximum:
        return 1.0

    width = max(
        maximum - minimum,
        1e-9
    )

    if value < minimum:
        distance = minimum - value
    else:
        distance = value - maximum

    score = 1.0 - distance / width

    return max(
        0.0,
        min(1.0, score)
    )


# ============================================================
# pH COMPATIBILITY
# ============================================================

def ph_compatibility_score(
    ph_level,
    minimum,
    maximum
):

    level = normalize_text(ph_level)

    if not level:
        return 0.5

    if minimum is None or maximum is None:
        return 0.5

    try:
        minimum = float(minimum)
        maximum = float(maximum)
    except (TypeError, ValueError):
        return 0.5

    if level == "acidic":

        actual_min = 0.0
        actual_max = 6.5

    elif level == "neutral":

        actual_min = 6.0
        actual_max = 7.5

    elif level == "alkaline":

        actual_min = 7.5
        actual_max = 14.0

    elif level in {
        "tie",
        "ambiguous",
        "unknown",
        "unavailable",
    }:

        return 0.5

    else:
        return 0.5

    if (
        actual_max >= minimum
        and actual_min <= maximum
    ):
        return 1.0

    return 0.0


# ============================================================
# WATER SUITABILITY V1.11
# ============================================================

def water_score(
    seasonal_effective_rainfall_mm,
    crop_minimum,
    crop_maximum
):
    """
    V1.11 WATER MODEL

    Compares seasonal effective rainfall against the
    crop's reported seasonal/crop-cycle water requirement.

    IMPORTANT:

        estimated_root_zone_water_mm is NOT used here.

    This is a rainfall-based water adequacy score.

    It does NOT represent:

        - total crop water availability
        - irrigation requirement
        - soil water storage
        - crop evapotranspiration

    Those are separate concepts.
    """

    if (
        seasonal_effective_rainfall_mm is None
        or crop_minimum is None
    ):
        return 0.5

    try:

        if pd.isna(
            seasonal_effective_rainfall_mm
        ):
            return 0.5

        if pd.isna(crop_minimum):
            return 0.5

    except (TypeError, ValueError):

        return 0.5

    rainfall = max(
        float(seasonal_effective_rainfall_mm),
        0.0
    )

    minimum = max(
        float(crop_minimum),
        0.0
    )

    if (
        crop_maximum is not None
        and not pd.isna(crop_maximum)
    ):

        maximum = max(
            float(crop_maximum),
            minimum
        )

    else:

        maximum = minimum

    if minimum <= 0:
        return 1.0

    # Rainfall reaches or exceeds upper requirement.
    if rainfall >= maximum:
        return 1.0

    # Rainfall is inside the reported requirement range.
    if rainfall >= minimum:
        return 0.85

    # Rainfall is below minimum requirement.
    # Gradual penalty prevents an abrupt binary decision.
    return max(
        0.0,
        min(
            0.85,
            rainfall / minimum
        )
    )


# ============================================================
# DATA QUALITY
# ============================================================

def quality_factor(quality):

    quality = normalize_text(quality)

    if quality == "good":
        return 1.00

    if quality == "moderate":
        return 0.75

    if quality == "caution":
        return 0.50

    if quality in {
        "weak",
        "ambiguous",
    }:
        return 0.35

    if quality == "unavailable":
        return 0.00

    if quality == "poor":
        return 0.50

    return 0.50


# ============================================================
# DISTRICT SOIL LOOKUP
# ============================================================

def get_district_soil(state, district):

    state_value = normalize_text(state)
    district_value = normalize_text(district)

    if SOIL_DATA.empty:
        return None

    result = SOIL_DATA[
        (
            SOIL_DATA["state_name"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == state_value
        )
        &
        (
            SOIL_DATA["district_name"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == district_value
        )
    ]

    if result.empty:
        return None

    return result.iloc[0]


# ============================================================
# VILLAGE SOIL LOOKUP
# ============================================================

def get_village_soil(
    state,
    district,
    village
):

    if VILLAGE_SOIL_DATA.empty:
        return None

    village_value = normalize_text(village)

    if not village_value:
        return None

    state_value = normalize_text(state)
    district_value = normalize_text(district)

    required_columns = {
        "state_name",
        "district_name",
        "village_name",
    }

    if not required_columns.issubset(
        VILLAGE_SOIL_DATA.columns
    ):
        return None

    result = VILLAGE_SOIL_DATA[
        (
            VILLAGE_SOIL_DATA["state_name"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == state_value
        )
        &
        (
            VILLAGE_SOIL_DATA["district_name"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == district_value
        )
        &
        (
            VILLAGE_SOIL_DATA["village_name"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == village_value
        )
    ]

    if result.empty:
        return None

    if "complete_NPK_pH_profile" in result.columns:

        complete = result[
            result["complete_NPK_pH_profile"]
            .fillna(False)
            .astype(bool)
        ]

        if not complete.empty:
            result = complete

    return result.iloc[0]


# ============================================================
# VILLAGE SOIL PROFILE
# ============================================================

def build_village_soil_profile(
    row,
    soil_type
):

    def get_quality(column):

        if column not in row.index:
            return "Unknown"

        value = row.get(column)

        if value is None or pd.isna(value):
            return "Unknown"

        return str(value).strip()

    def get_level(column):

        if column not in row.index:
            return None

        value = row.get(column)

        if value is None or pd.isna(value):
            return None

        value = str(value).strip()

        if normalize_text(value) in {
            "tie",
            "ambiguous",
            "unknown",
            "unavailable",
        }:
            return None

        return value.title()

    complete_value = row.get(
        "complete_NPK_pH_profile",
        False
    )

    try:
        complete_value = bool(complete_value)
    except Exception:
        complete_value = False

    return {

        "source_level": "village",

        "state_name":
            row.get("state_name"),

        "district_name":
            row.get("district_name"),

        "block_name":
            row.get("block_name"),

        "village_name":
            row.get("village_name"),

        "village_code":
            row.get("village_code"),

        "soil_type":
            soil_type,

        "nitrogen":
            get_level("N_level"),

        "phosphorus":
            get_level("P_level"),

        "potassium":
            get_level("K_level"),

        "ph_level":
            get_level("pH_level"),

        "N_quality":
            (
                "Unavailable"
                if get_level("N_level") is None
                else get_quality("N_data_quality")
            ),

        "P_quality":
            (
                "Unavailable"
                if get_level("P_level") is None
                else get_quality("P_data_quality")
            ),

        "K_quality":
            (
                "Unavailable"
                if get_level("K_level") is None
                else get_quality("K_data_quality")
            ),

        "pH_quality":
            (
                "Unavailable"
                if get_level("pH_level") is None
                else get_quality("pH_data_quality")
            ),

        "data_quality":
            get_quality(
                "overall_soil_data_quality"
            ),

        "complete_NPK_pH_profile":
            complete_value,
    }


# ============================================================
# DISTRICT SOIL PROFILE
# ============================================================

def build_district_soil_profile(
    row,
    soil_type
):

    if row is None:
        return None

    return {

        "source_level": "district",

        "state_name":
            row.get("state_name"),

        "district_name":
            row.get("district_name"),

        "block_name":
            None,

        "village_name":
            None,

        "village_code":
            None,

        "soil_type":
            soil_type,

        "nitrogen":
            row.get("N_level"),

        "phosphorus":
            row.get("P_level"),

        "potassium":
            row.get("K_level"),

        "ph_level":
            row.get("pH_level"),

        "N_quality":
            row.get(
                "N_data_quality",
                "Unknown"
            ),

        "P_quality":
            row.get(
                "P_data_quality",
                "Unknown"
            ),

        "K_quality":
            row.get(
                "K_data_quality",
                "Unknown"
            ),

        "pH_quality":
            row.get(
                "pH_data_quality",
                "Unknown"
            ),

        "data_quality":
            row.get(
                "overall_soil_data_quality",
                "Unknown"
            ),

        "complete_NPK_pH_profile":
            False,
    }


# ============================================================
# CROP PROFILE SELECTION
# ============================================================

def select_crop_profile(
    crop_rows,
    soil_type,
    season
):

    rows = crop_rows.copy()

    soil_value = normalize_text(soil_type)
    season_value = normalize_text(season)

    def soil_matches(series):

        return series.astype(str).map(
            lambda value:
                (
                    soil_value in split_values(value)
                )
                or
                (
                    soil_value in normalize_text(value)
                )
        )

    def season_matches(series):

        return series.astype(str).map(
            lambda value:
                (
                    season_value in split_values(value)
                )
                or
                (
                    season_value in normalize_text(value)
                )
        )

    soil_rows = (
        rows[
            soil_matches(rows["SOIL"])
        ]
        if soil_value
        else pd.DataFrame()
    )

    season_rows = (
        rows[
            season_matches(rows["SEASON"])
        ]
        if season_value
        else pd.DataFrame()
    )

    if (
        not soil_rows.empty
        and not season_rows.empty
    ):

        both_rows = rows[
            soil_matches(rows["SOIL"])
            &
            season_matches(rows["SEASON"])
        ]

    else:

        both_rows = pd.DataFrame()

    if not both_rows.empty:

        selected = both_rows
        profile_source = "soil_and_season"

    elif not season_rows.empty:

        selected = season_rows
        profile_source = "season"

    elif not soil_rows.empty:

        selected = soil_rows
        profile_source = "soil"

    else:

        selected = rows
        profile_source = "all_crop_records"

    profile = {

        "crop":
            rows["CROPS"].iloc[0],

        "profile_source":
            profile_source,

        "source_rows_used":
            int(len(selected)),
    }

    numeric_columns = [

        "SOIL_PH",
        "SOIL_PH_HIGH",

        "TEMP",
        "MAX_TEMP",

        "WATERREQUIRED",
        "WATERREQUIRED_MAX",

        "RELATIVE_HUMIDITY",
        "RELATIVE_HUMIDITY_MAX",

        "N",
        "N_MAX",

        "P",
        "P_MAX",

        "K",
        "K_MAX",
    ]

    for column in numeric_columns:

        profile[column] = selected[column].median()

    categorical_columns = [

        "SOIL",
        "SEASON",

        "N_requirement_level",
        "P_requirement_level",
        "K_requirement_level",
    ]

    for column in categorical_columns:

        mode = (
            selected[column]
            .dropna()
            .mode()
        )

        if mode.empty:
            profile[column] = None
        else:
            profile[column] = mode.iloc[0]

    all_seasons = sorted(
        {
            season_name
            for value in rows["SEASON"].dropna()
            for season_name in split_values(value)
        }
    )

    profile["available_seasons"] = "|".join(
        all_seasons
    )

    profile["season_match_available"] = bool(
        season_value
        and season_value in all_seasons
    )

    return pd.Series(profile)


def build_crop_profiles(
    soil_type,
    season
):

    profiles = []

    for crop_name, rows in CROP_DATA.groupby(
        "CROPS",
        sort=False
    ):

        profiles.append(
            select_crop_profile(
                rows,
                soil_type,
                season
            )
        )

    return pd.DataFrame(profiles).reset_index(
        drop=True
    )


# ============================================================
# SCORE ONE CROP
# ============================================================

def score_crop(
    crop,
    user_data
):

    components = {}

    components["soil"] = categorical_match(
        user_data["soil_type"],
        crop["SOIL"]
    )

    components["nitrogen"] = nutrient_level_score(
        user_data["nitrogen"],
        crop["N_requirement_level"]
    )

    components["phosphorus"] = nutrient_level_score(
        user_data["phosphorus"],
        crop["P_requirement_level"]
    )

    components["potassium"] = nutrient_level_score(
        user_data["potassium"],
        crop["K_requirement_level"]
    )

    components["ph"] = ph_compatibility_score(
        user_data["ph_level"],
        crop["SOIL_PH"],
        crop["SOIL_PH_HIGH"]
    )

    components["temperature"] = range_score(
        user_data["temperature_c"],
        crop["TEMP"],
        crop["MAX_TEMP"]
    )

    components["humidity"] = range_score(
        user_data["humidity_pct"],
        crop["RELATIVE_HUMIDITY"],
        crop["RELATIVE_HUMIDITY_MAX"]
    )

    # --------------------------------------------------------
    # V1.11 WATER MODEL
    #
    # Use seasonal effective rainfall against the crop's
    # reported water requirement.
    #
    # Root-zone storage is NOT used for this comparison.
    # --------------------------------------------------------

    components["water"] = water_score(
        user_data[
            "seasonal_effective_rainfall_mm"
        ],
        crop["WATERREQUIRED"],
        crop["WATERREQUIRED_MAX"]
    )

    # Informational only because weight = 0.
    components["season"] = categorical_match(
        user_data["season"],
        crop["SEASON"]
    )

    weights = BASE_WEIGHTS.copy()

    weights["nitrogen"] *= quality_factor(
        user_data["N_quality"]
    )

    weights["phosphorus"] *= quality_factor(
        user_data["P_quality"]
    )

    weights["potassium"] *= quality_factor(
        user_data["K_quality"]
    )

    weights["ph"] *= quality_factor(
        user_data["pH_quality"]
    )

    weighted_score = 0.0
    active_weight = 0.0

    for component, weight in weights.items():

        if weight <= 0:
            continue

        value = components[component]

        if value is None:
            continue

        weighted_score += (
            float(value) * weight
        )

        active_weight += weight

    if active_weight <= 0:

        score = 0.0

    else:

        score = (
            weighted_score
            / active_weight
            * 100
        )

    return {

        "crop":
            str(crop["crop"]),

        "score":
            round(score, 2),

        "confidence_like":
            round(score / 100, 4),

        "profile_source":
            str(crop["profile_source"]),

        "source_rows_used":
            int(crop["source_rows_used"]),

        "season_match":
            bool(
                crop.get(
                    "season_match_available",
                    False
                )
            ),

        "available_seasons":
            str(
                crop.get(
                    "available_seasons",
                    ""
                )
            ),

        "components": {
            key:
                (
                    None
                    if value is None
                    else round(
                        float(value),
                        3
                    )
                )
            for key, value
            in components.items()
        },

        "data_quality": {

            "nitrogen":
                user_data["N_quality"],

            "phosphorus":
                user_data["P_quality"],

            "potassium":
                user_data["K_quality"],

            "pH":
                user_data["pH_quality"],

            "overall":
                user_data["overall_quality"],
        },
    }


# ============================================================
# CRITICAL CONDITIONS
# ============================================================

def assess_critical_conditions(
    result,
    user_data
):

    components = result.get(
        "components",
        {}
    )

    critical = []
    warnings = []

    water = components.get("water")

    if water is not None:

        if water < 0.25:

            critical.append(
                "Very low seasonal rainfall-based "
                "water suitability."
            )

        elif water < 0.50:

            warnings.append(
                "Seasonal rainfall-based water suitability "
                "is below the preferred level."
            )

    temperature = components.get(
        "temperature"
    )

    if temperature is not None:

        if temperature < 0.25:

            critical.append(
                "Current temperature is far outside "
                "the crop's preferred range."
            )

        elif temperature < 0.50:

            warnings.append(
                "Current temperature is not a strong "
                "match for the crop."
            )

    ph = components.get("ph")

    if ph is not None:

        if ph < 0.25:

            critical.append(
                "Soil pH is a severe mismatch for "
                "the crop requirement."
            )

        elif ph < 0.50:

            warnings.append(
                "Soil pH is not a strong match "
                "for the crop requirement."
            )

    soil = components.get("soil")

    if soil is not None and soil < 0.25:

        warnings.append(
            "Soil type has low compatibility "
            "with the crop."
        )

    if not result.get("season_match", False):

        warnings.append(
            f"The crop does not have a "
            f"{user_data['season']} season match "
            f"in the available crop records."
        )

    critical = list(
        dict.fromkeys(critical)
    )

    warnings = list(
        dict.fromkeys(warnings)
    )

    return {

        "has_critical_constraint":
            len(critical) > 0,

        "critical_constraints":
            critical,

        "warnings":
            warnings,
    }


# ============================================================
# CONSERVATIVE ASSESSMENT
# ============================================================

def apply_conservative_assessment(
    result
):

    assessment = result.get(
        "assessment",
        "Moderate candidate"
    )

    critical = result.get(
        "critical_conditions",
        {}
    )

    if not critical.get(
        "has_critical_constraint",
        False
    ):
        return assessment

    score = float(
        result.get("score", 0)
    )

    if score >= 70:
        return "Good candidate with critical limitation"

    if score >= 50:
        return "Moderate candidate with critical limitation"

    return "Lower suitability with critical limitation"


# ============================================================
# WATER ASSESSMENT V1.11
# ============================================================

def build_water_assessment(
    result,
    user_data
):

    component = (
        result.get(
            "components",
            {}
        ).get("water")
    )

    farm_status = user_data.get(
        "water_status"
    )

    root_zone_water = user_data.get(
        "estimated_root_zone_water_mm"
    )

    root_zone_pct = user_data.get(
        "root_zone_water_pct"
    )

    seasonal_rainfall = user_data.get(
        "seasonal_rainfall_mm"
    )

    seasonal_effective_rainfall = user_data.get(
        "seasonal_effective_rainfall_mm"
    )

    seasonal_et0 = user_data.get(
        "seasonal_et0_mm"
    )

    if component is None:

        suitability = "Unknown"

        message = (
            "Seasonal rainfall-based crop water "
            "suitability could not be determined."
        )

    elif component >= 0.80:

        suitability = "Good"

        message = (
            "Seasonal effective rainfall provides "
            "good adequacy relative to this crop's "
            "reported water requirement."
        )

    elif component >= 0.50:

        suitability = "Moderate"

        message = (
            "Seasonal effective rainfall provides "
            "partial adequacy relative to this "
            "crop's reported water requirement."
        )

    elif component > 0:

        suitability = "Low"

        message = (
            "Seasonal effective rainfall is below "
            "the crop's reported water requirement."
        )

    else:

        suitability = "Very Low"

        message = (
            "Very little seasonal rainfall adequacy "
            "is indicated for this crop."
        )

    return {

        "farm_water_status":
            farm_status,

        "crop_water_suitability":
            suitability,

        "crop_water_score":
            (
                None
                if component is None
                else round(
                    float(component),
                    3
                )
            ),

        "seasonal_rainfall_mm":
            seasonal_rainfall,

        "seasonal_effective_rainfall_mm":
            seasonal_effective_rainfall,

        "seasonal_et0_mm":
            seasonal_et0,

        # Kept separately as farm/current soil-water information.
        "estimated_root_zone_water_mm":
            root_zone_water,

        "root_zone_water_pct":
            root_zone_pct,

        "message":
            message,
    }


# ============================================================
# EXPLANATIONS
# ============================================================

def build_recommendation_explanation(
    result,
    user_data
):

    strengths = []
    limitations = []

    components = result.get(
        "components",
        {}
    )

    if result.get("season_match"):

        strengths.append(
            f"Suitable for the current "
            f"{user_data['season']} season."
        )

    else:

        limitations.append(
            f"The crop's available season records "
            f"do not match the current "
            f"{user_data['season']} season."
        )

    soil = components.get("soil")

    if soil is not None:

        if soil >= 0.8:
            strengths.append(
                "Good soil-type compatibility."
            )

        elif soil >= 0.5:
            limitations.append(
                "Moderate soil-type compatibility."
            )

        else:
            limitations.append(
                "Low soil-type compatibility."
            )

    nitrogen = components.get("nitrogen")

    if nitrogen is None:

        limitations.append(
            "Nitrogen evidence is unavailable "
            "or ambiguous for this village."
        )

    elif nitrogen >= 0.8:

        strengths.append(
            "Good nitrogen compatibility."
        )

    elif nitrogen < 0.5:

        limitations.append(
            "Nitrogen level does not closely "
            "match the crop requirement."
        )

    phosphorus = components.get("phosphorus")

    if phosphorus is not None:

        if phosphorus >= 0.8:

            strengths.append(
                "Good phosphorus compatibility."
            )

        elif phosphorus < 0.5:

            limitations.append(
                "Phosphorus level is not a strong "
                "match for the crop requirement."
            )

    potassium = components.get("potassium")

    if potassium is not None:

        if potassium >= 0.8:

            strengths.append(
                "Good potassium compatibility."
            )

        elif potassium < 0.5:

            limitations.append(
                "Potassium level is not a strong "
                "match for the crop requirement."
            )

    ph = components.get("ph")

    if ph is not None:

        if ph >= 0.8:

            strengths.append(
                "Good soil-pH compatibility."
            )

        elif ph < 0.5:

            limitations.append(
                "Soil pH is not a strong match "
                "for the crop requirement."
            )

    temperature = components.get(
        "temperature"
    )

    if temperature is not None:

        if temperature >= 0.8:

            strengths.append(
                "Current temperature is well "
                "within the crop's preferred range."
            )

        elif temperature < 0.5:

            limitations.append(
                "Current temperature is outside "
                "the crop's preferred range."
            )

    humidity = components.get("humidity")

    if humidity is not None:

        if humidity >= 0.8:

            strengths.append(
                "Current humidity is compatible "
                "with the crop."
            )

        elif humidity < 0.5:

            limitations.append(
                "Current humidity is not a strong "
                "match for the crop."
            )

    # --------------------------------------------------------
    # V1.11 WATER EXPLANATION
    # --------------------------------------------------------

    water = components.get("water")

    if water is not None:

        if water >= 0.8:

            strengths.append(
                "Seasonal rainfall provides good "
                "water adequacy for the crop."
            )

        elif water < 0.5:

            limitations.append(
                "Seasonal rainfall is below the crop's "
                "reported water requirement."
            )

    water_status = user_data.get(
        "water_status"
    )

    if (
        water_status
        and normalize_text(water_status)
        == "adequate"
    ):

        strengths.append(
            "Overall estimated root-zone water "
            "status is Adequate."
        )

    elif (
        water_status
        and normalize_text(water_status)
        in {
            "low",
            "deficit",
            "insufficient",
        }
    ):

        limitations.append(
            "Overall estimated root-zone water "
            "status indicates water stress."
        )

    strengths = list(
        dict.fromkeys(strengths)
    )

    limitations = list(
        dict.fromkeys(limitations)
    )

    if not strengths:

        strengths.append(
            "No major strong compatibility "
            "signal was identified."
        )

    if not limitations:

        limitations.append(
            "No major limitation was identified "
            "from the available inputs."
        )

    score = float(
        result.get("score", 0)
    )

    if score >= 70:
        assessment = "Strong candidate"

    elif score >= 55:
        assessment = "Good candidate"

    elif score >= 40:
        assessment = "Moderate candidate"

    else:
        assessment = "Lower suitability"

    return {

        "assessment":
            assessment,

        "strengths":
            strengths,

        "limitations":
            limitations,
    }


# ============================================================
# MAIN RECOMMENDATION FUNCTION
# ============================================================

def recommend_crops(
    state,
    district,
    village,
    soil_type,
    weather,
    top_n=5
):

    if not isinstance(weather, dict):

        raise ValueError(
            "weather must be a dictionary returned "
            "by weather_service.get_weather_features()"
        )

    # --------------------------------------------------------
    # AUTOMATIC SEASON
    # --------------------------------------------------------

    season = weather.get("season")

    if not season:

        season = get_season_info()["season"]

    season = str(season).strip()

    # --------------------------------------------------------
    # SEASON WINDOW
    # --------------------------------------------------------

    season_window = {

        "start":
            weather.get(
                "season_start_date"
            ),

        "end":
            weather.get(
                "season_end_date"
            ),

        "months":
            weather.get(
                "season_analysis_months"
            ),
    }

    if not season_window["months"]:

        season_key = normalize_text(season)

        if season_key == "kharif":

            season_window["months"] = [
                6, 7, 8, 9
            ]

        elif season_key == "rabi":

            season_window["months"] = [
                10, 11, 12, 1
            ]

        elif season_key == "zaid":

            season_window["months"] = [
                2, 3, 4, 5
            ]

    # --------------------------------------------------------
    # SOIL SOURCE
    # --------------------------------------------------------

    village_soil_row = get_village_soil(
        state,
        district,
        village
    )

    if village_soil_row is not None:

        soil_profile = build_village_soil_profile(
            village_soil_row,
            soil_type
        )

    else:

        district_soil_row = get_district_soil(
            state,
            district
        )

        if district_soil_row is None:

            raise ValueError(
                f"Location soil data not found: "
                f"{state} / {district}"
            )

        soil_profile = build_district_soil_profile(
            district_soil_row,
            soil_type
        )

    # --------------------------------------------------------
    # ROOT-ZONE WATER
    #
    # Retained only as farm/current water status.
    # It is NOT used for crop water suitability.
    # --------------------------------------------------------

    root_zone_water = weather.get(
        "estimated_root_zone_water_mm"
    )

    if root_zone_water is None:

        root_zone_water = weather.get(
            "available_water_mm"
        )

    # --------------------------------------------------------
    # SEASONAL WATER EVIDENCE
    # --------------------------------------------------------

    seasonal_rainfall = weather.get(
        "seasonal_rainfall_mm"
    )

    seasonal_effective_rainfall = weather.get(
        "seasonal_effective_rainfall_mm"
    )

    seasonal_et0 = weather.get(
        "seasonal_et0_mm"
    )

    # --------------------------------------------------------
    # USER DATA
    # --------------------------------------------------------

    user_data = {

        "soil_type":
            soil_type,

        "nitrogen":
            soil_profile["nitrogen"],

        "phosphorus":
            soil_profile["phosphorus"],

        "potassium":
            soil_profile["potassium"],

        "ph_level":
            soil_profile["ph_level"],

        "N_quality":
            soil_profile["N_quality"],

        "P_quality":
            soil_profile["P_quality"],

        "K_quality":
            soil_profile["K_quality"],

        "pH_quality":
            soil_profile["pH_quality"],

        "overall_quality":
            soil_profile["data_quality"],

        "temperature_c":
            weather.get("temperature_c"),

        "humidity_pct":
            weather.get("humidity_pct"),

        # Current/farm water status.
        "estimated_root_zone_water_mm":
            root_zone_water,

        "root_zone_water_pct":
            weather.get(
                "root_zone_water_pct"
            ),

        # Short-term diagnostics retained.
        "water_balance_7d_mm":
            weather.get(
                "water_balance_7d_mm"
            ),

        "water_balance_30d_mm":
            weather.get(
                "water_balance_30d_mm"
            ),

        # Seasonal water evidence.
        "seasonal_rainfall_mm":
            seasonal_rainfall,

        "seasonal_effective_rainfall_mm":
            seasonal_effective_rainfall,

        "seasonal_et0_mm":
            seasonal_et0,

        "seasonal_water_balance_mm":
            weather.get(
                "seasonal_water_balance_mm"
            ),

        "water_status":
            weather.get(
                "water_status"
            ),

        "season":
            season,
    }

    # --------------------------------------------------------
    # BUILD UNIQUE CROP PROFILES
    # --------------------------------------------------------

    profiles = build_crop_profiles(
        soil_type,
        season
    )

    results = []

    for _, crop in profiles.iterrows():

        results.append(
            score_crop(
                crop,
                user_data
            )
        )

    # --------------------------------------------------------
    # GUARANTEE UNIQUE CROPS
    # --------------------------------------------------------

    unique_results = {}

    for result in results:

        key = normalize_text(
            result["crop"]
        )

        if (
            key not in unique_results
            or result["score"]
            > unique_results[key]["score"]
        ):

            unique_results[key] = result

    ranked = list(
        unique_results.values()
    )

    # --------------------------------------------------------
    # V1.11 SEASON PRIORITY
    # --------------------------------------------------------
    #
    # Season still contributes 0 points.
    #
    # Separate ranking layer:
    #
    #   1. In-season crops first
    #   2. Higher suitability score
    #   3. Alphabetical deterministic tie-break
    #
    # Off-season crops are NOT deleted.
    # --------------------------------------------------------

    ranked.sort(
        key=lambda item: (
            not item.get(
                "season_match",
                False
            ),
            -item["score"],
            item["crop"].casefold(),
        )
    )

    # --------------------------------------------------------
    # ENRICH RESULTS
    # --------------------------------------------------------

    for result in ranked:

        result["explanation"] = (
            build_recommendation_explanation(
                result,
                user_data
            )
        )

        result["water_assessment"] = (
            build_water_assessment(
                result,
                user_data
            )
        )

        result["critical_conditions"] = (
            assess_critical_conditions(
                result,
                user_data
            )
        )

        result["assessment"] = (
            result["explanation"]["assessment"]
        )

        result["strengths"] = (
            result["explanation"]["strengths"]
        )

        result["limitations"] = (
            result["explanation"]["limitations"]
        )

        result["original_assessment"] = (
            result["assessment"]
        )

        result["assessment"] = (
            apply_conservative_assessment(
                result
            )
        )

        if result[
            "critical_conditions"
        ][
            "has_critical_constraint"
        ]:

            result["limitations"].extend(
                result[
                    "critical_conditions"
                ][
                    "critical_constraints"
                ]
            )

            result["limitations"] = list(
                dict.fromkeys(
                    result["limitations"]
                )
            )

    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {

        "location": {

            "state":
                state,

            "district":
                district,

            "village":
                village,
        },

        "soil": {

            "source_level":
                soil_profile["source_level"],

            "state_name":
                soil_profile.get(
                    "state_name"
                ),

            "district_name":
                soil_profile.get(
                    "district_name"
                ),

            "block_name":
                soil_profile.get(
                    "block_name"
                ),

            "village_name":
                soil_profile.get(
                    "village_name"
                ),

            "village_code":
                soil_profile.get(
                    "village_code"
                ),

            "soil_type":
                soil_type,

            "nitrogen":
                soil_profile["nitrogen"],

            "phosphorus":
                soil_profile["phosphorus"],

            "potassium":
                soil_profile["potassium"],

            "ph_level":
                soil_profile["ph_level"],

            "N_quality":
                soil_profile["N_quality"],

            "P_quality":
                soil_profile["P_quality"],

            "K_quality":
                soil_profile["K_quality"],

            "pH_quality":
                soil_profile["pH_quality"],

            "data_quality":
                soil_profile["data_quality"],

            "complete_NPK_pH_profile":
                soil_profile[
                    "complete_NPK_pH_profile"
                ],
        },

        "weather":
            weather,

        "season":
            season,

        "season_source":
            "automatic",

        "season_window":
            season_window,

        # ----------------------------------------------------
        # WATER EVIDENCE
        # ----------------------------------------------------

        "water": {

            # Current/farm water status.
            "estimated_root_zone_water_mm":
                root_zone_water,

            "root_zone_water_pct":
                weather.get(
                    "root_zone_water_pct"
                ),

            # Short-term diagnostics.
            "water_balance_7d_mm":
                weather.get(
                    "water_balance_7d_mm"
                ),

            "water_balance_30d_mm":
                weather.get(
                    "water_balance_30d_mm"
                ),

            # Seasonal crop-water evidence.
            "seasonal_rainfall_mm":
                seasonal_rainfall,

            "seasonal_effective_rainfall_mm":
                seasonal_effective_rainfall,

            "seasonal_et0_mm":
                seasonal_et0,

            # Diagnostic only.
            "seasonal_water_balance_mm":
                weather.get(
                    "seasonal_water_balance_mm"
                ),

            "status":
                weather.get(
                    "water_status"
                ),
        },

        "farm_conditions": {

            "season":
                season,

            "season_source":
                "automatic",

            "season_window":
                season_window,

            "soil_source_level":
                soil_profile[
                    "source_level"
                ],

            "soil": {

                "state_name":
                    soil_profile.get(
                        "state_name"
                    ),

                "district_name":
                    soil_profile.get(
                        "district_name"
                    ),

                "block_name":
                    soil_profile.get(
                        "block_name"
                    ),

                "village_name":
                    soil_profile.get(
                        "village_name"
                    ),

                "village_code":
                    soil_profile.get(
                        "village_code"
                    ),

                "soil_type":
                    soil_type,

                "nitrogen":
                    soil_profile["nitrogen"],

                "phosphorus":
                    soil_profile["phosphorus"],

                "potassium":
                    soil_profile["potassium"],

                "ph_level":
                    soil_profile["ph_level"],

                "N_quality":
                    soil_profile["N_quality"],

                "P_quality":
                    soil_profile["P_quality"],

                "K_quality":
                    soil_profile["K_quality"],

                "pH_quality":
                    soil_profile["pH_quality"],

                "overall_data_quality":
                    soil_profile["data_quality"],
            },

            "water": {

                "status":
                    weather.get(
                        "water_status"
                    ),

                # Current/farm status.
                "estimated_root_zone_water_mm":
                    root_zone_water,

                "root_zone_water_pct":
                    weather.get(
                        "root_zone_water_pct"
                    ),

                # Short-term diagnostics.
                "water_balance_7d_mm":
                    weather.get(
                        "water_balance_7d_mm"
                    ),

                "water_balance_30d_mm":
                    weather.get(
                        "water_balance_30d_mm"
                    ),

                # Seasonal evidence.
                "seasonal_rainfall_mm":
                    seasonal_rainfall,

                "seasonal_effective_rainfall_mm":
                    seasonal_effective_rainfall,

                "seasonal_et0_mm":
                    seasonal_et0,

                "seasonal_water_balance_mm":
                    weather.get(
                        "seasonal_water_balance_mm"
                    ),
            },

            "weather": {

                "temperature_c":
                    weather.get(
                        "temperature_c"
                    ),

                "humidity_pct":
                    weather.get(
                        "humidity_pct"
                    ),

                "timezone":
                    weather.get(
                        "timezone"
                    ),
            },
        },

        "crop_count_evaluated":
            len(ranked),

        "recommendations":
            ranked[:top_n],
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("AGRONEXUS CROP RECOMMENDATION V1.11")
    print("=" * 70)

    print(
        "Crop rows:",
        len(CROP_DATA)
    )

    print(
        "Unique crops:",
        CROP_DATA["CROPS"].nunique()
    )

    print(
        "District soil rows:",
        len(SOIL_DATA)
    )

    print(
        "Village soil rows:",
        len(VILLAGE_SOIL_DATA)
    )

    print(
        "\nV1.11 loaded successfully."
    )

    print(
        "\nWeights:",
        BASE_WEIGHTS
    )

    print(
        "Weight total:",
        sum(BASE_WEIGHTS.values())
    )

    print(
        "\nWater model:"
    )

    print(
        "Seasonal effective rainfall"
        " -> crop WATERREQUIRED"
    )

    print(
        "Root-zone water is retained separately"
        " as farm/current status."
    )

    print(
        "\nPublic function:"
    )

    print(
        "recommend_crops("
        "state, district, village, soil_type, weather, top_n=5"
        ")"
    )