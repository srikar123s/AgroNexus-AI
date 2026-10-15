import os
import pandas as pd
import numpy as np

from season_service import get_season_info


# ============================================================
# FILE PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

CROP_FILE = os.path.join(
    DATA_DIR,
    "Crop recommendation dataset.csv"
)

SOIL_FILE = os.path.join(
    DATA_DIR,
    "agronexus_district_soil_master_v3.csv"
)

VILLAGE_SOIL_FILE = os.path.join(
    DATA_DIR,
    "agronexus_village_soil_master_v4.csv"
)


# ============================================================
# BASE WEIGHTS
# ============================================================

BASE_WEIGHTS = {
    "soil": 15,
    "nitrogen": 10,
    "phosphorus": 10,
    "potassium": 10,
    "ph": 10,
    "temperature": 15,
    "humidity": 5,
    "water": 20,
    "season": 5,
}


LEVELS = {
    "low": 0,
    "medium": 1,
    "high": 2
}


# ============================================================
# LOAD CROP DATA
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
        "K_MAX"
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
        "K_MAX"
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    return df


# ============================================================
# LOAD SOIL MASTER
# ============================================================

def load_soil_data():

    if not os.path.exists(SOIL_FILE):
        raise FileNotFoundError(
            f"Soil master not found: {SOIL_FILE}"
        )

    return pd.read_csv(
        SOIL_FILE
    )


CROP_DATA = load_crop_data()
SOIL_DATA = load_soil_data()


def load_village_soil_data():
    """
    Load the 40,402-row village-level V4 soil master.
    V3 district data remains the fallback.
    """

    if not os.path.exists(VILLAGE_SOIL_FILE):
        raise FileNotFoundError(
            f"Village soil master not found: {VILLAGE_SOIL_FILE}"
        )

    return pd.read_csv(
        VILLAGE_SOIL_FILE
    )


VILLAGE_SOIL_DATA = load_village_soil_data()


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(value):

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(
        value
    ).strip().casefold()


def split_values(value):

    if value is None or pd.isna(value):
        return []

    return [
        item.strip().casefold()
        for item in str(value).split("|")
        if item.strip()
    ]


# ============================================================
# CROP NUTRIENT LEVELS
# ============================================================

def prepare_crop_levels(df):

    df = df.copy()

    for nutrient in ["N", "P", "K"]:

        midpoint = (
            df[nutrient]
            + df[f"{nutrient}_MAX"]
        ) / 2

        q1 = midpoint.quantile(
            1 / 3
        )

        q2 = midpoint.quantile(
            2 / 3
        )

        df[
            f"{nutrient}_requirement_level"
        ] = pd.cut(
            midpoint,
            bins=[
                -np.inf,
                q1,
                q2,
                np.inf
            ],
            labels=[
                "Low",
                "Medium",
                "High"
            ]
        )

    return df


CROP_DATA = prepare_crop_levels(
    CROP_DATA
)


# ============================================================
# CATEGORICAL MATCH
# ============================================================

def categorical_match(
    actual,
    requirement
):

    actual_value = normalize_text(
        actual
    )

    if not actual_value:
        return 0.5

    requirements = split_values(
        requirement
    )

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


def nutrient_level_score(
    actual,
    required
):
    """
    Compare a village nutrient level with the crop's
    derived requirement level.

    Tie/Ambiguous/Missing is treated as uncertain rather
    than being converted to Low/Medium/High.
    """

    actual_text = normalize_text(
        actual
    )

    required_text = normalize_text(
        required
    )

    if actual_text in {
        "",
        "tie",
        "ambiguous",
        "unknown",
        "unavailable"
    }:
        return None

    actual_level = LEVELS.get(
        actual_text
    )

    required_level = LEVELS.get(
        required_text
    )

    if (
        actual_level is None
        or required_level is None
    ):
        return None

    difference = abs(
        actual_level
        - required_level
    )

    if difference == 0:
        return 1.0

    if difference == 1:
        return 0.5

    return 0.0


def range_score(
    value,
    minimum,
    maximum
):

    if (
        value is None
        or minimum is None
        or maximum is None
        or pd.isna(value)
        or pd.isna(minimum)
        or pd.isna(maximum)
    ):
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

        distance = (
            minimum - value
        )

    else:

        distance = (
            value - maximum
        )

    score = (
        1.0
        - distance / width
    )

    return max(
        0.0,
        min(
            1.0,
            score
        )
    )


# ============================================================
# pH COMPATIBILITY
# ============================================================

def ph_compatibility_score(
    ph_level,
    minimum,
    maximum
):

    level = normalize_text(
        ph_level
    )

    if not level:
        return 0.5

    if (
        minimum is None
        or maximum is None
        or pd.isna(minimum)
        or pd.isna(maximum)
    ):
        return 0.5

    minimum = float(
        minimum
    )

    maximum = float(
        maximum
    )

    if level == "acidic":

        district_min = 0.0
        district_max = 6.5

    elif level == "neutral":

        district_min = 6.0
        district_max = 7.5

    elif level == "alkaline":

        district_min = 7.5
        district_max = 14.0

    else:

        return 0.5

    if (
        district_max >= minimum
        and district_min <= maximum
    ):
        return 1.0

    return 0.0


# ============================================================
# WATER SUITABILITY
# ============================================================


def water_score(
    seasonal_effective_rainfall_mm,
    seasonal_days_available,
    root_zone_water_pct,
    recent_water_balance_mm,
    crop_minimum,
    crop_maximum,
    season_days=120
):
    """
    Estimate rainfall-supported water suitability.

    The crop dataset's WATERREQUIRED is treated as a
    crop-period requirement, not as a direct soil-moisture
    target.

    Signals:
      1. Seasonal effective rainfall relative to the
         crop requirement expected by the current point
         in the four-month season.
      2. Current root-zone water percentage.
      3. Recent 7-day water balance.

    This is a suitability estimate, not an irrigation
    recommendation or direct soil-moisture measurement.
    """

    if (
        crop_minimum is None
        or pd.isna(crop_minimum)
    ):
        return 0.5

    minimum = max(
        float(crop_minimum),
        0.0
    )

    if minimum <= 0:
        return 1.0

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

    crop_target = (
        minimum + maximum
    ) / 2.0

    try:
        seasonal_effective = max(
            0.0,
            float(
                seasonal_effective_rainfall_mm
            )
        )
    except (
        TypeError,
        ValueError
    ):
        seasonal_effective = 0.0

    try:
        days = max(
            1,
            min(
                int(seasonal_days_available),
                season_days
            )
        )
    except (
        TypeError,
        ValueError
    ):
        days = 1

    # Requirement expected by the current point
    # in the four-month season.
    expected_requirement_to_date = (
        crop_target
        * days
        / season_days
    )

    if expected_requirement_to_date > 0:
        rainfall_support = min(
            1.0,
            seasonal_effective
            / expected_requirement_to_date
        )
    else:
        rainfall_support = 1.0

    # Root-zone condition is a secondary signal.
    try:
        root_pct = float(
            root_zone_water_pct
        )
        root_score = max(
            0.0,
            min(
                1.0,
                root_pct / 100.0
            )
        )
    except (
        TypeError,
        ValueError
    ):
        root_score = 0.5

    # Recent trend:
    # positive balance = supportive,
    # strongly negative = warning.
    try:
        recent_balance = float(
            recent_water_balance_mm
        )
        trend_score = max(
            0.0,
            min(
                1.0,
                0.5
                + recent_balance / 100.0
            )
        )
    except (
        TypeError,
        ValueError
    ):
        trend_score = 0.5

    return max(
        0.0,
        min(
            1.0,
            (
                0.60 * rainfall_support
                + 0.30 * root_score
                + 0.10 * trend_score
            )
        )
    )


def quality_factor(
    quality
):

    quality = normalize_text(
        quality
    )

    if quality == "good":
        return 1.00

    if quality == "moderate":
        return 0.75

    if quality == "caution":
        return 0.50

    if quality in [
        "weak",
        "ambiguous"
    ]:
        return 0.35

    if quality == "unavailable":
        return 0.00

    return 0.50



# ============================================================
# VILLAGE SOIL HELPERS
# ============================================================

def _valid_soil_level(
    value
):
    """
    Only a real Low/Medium/High or Acidic/Neutral/Alkaline
    level is usable for scoring. Tie is ambiguous.
    """

    value = normalize_text(
        value
    )

    return value in {
        "low",
        "medium",
        "high",
        "acidic",
        "neutral",
        "alkaline"
    }


def _soil_level_or_none(
    value
):

    if not _valid_soil_level(
        value
    ):
        return None

    return str(
        value
    ).strip().title()


def _get_village_quality(
    row,
    column
):

    value = row.get(
        column
    )

    if value is None or pd.isna(value):
        return "Unavailable"

    return str(
        value
    ).strip()


def get_village_soil(
    state,
    district,
    village
):
    """
    Exact State + District + Village lookup.

    The V4 file contains block information, but the public
    recommendation input does not require block selection.
    Therefore we use exact village matching and fall back
    to district V3 when the village cannot be resolved.
    """

    if VILLAGE_SOIL_DATA.empty:
        return None

    state_key = normalize_text(
        state
    )

    district_key = normalize_text(
        district
    )

    village_key = normalize_text(
        village
    )

    if not village_key:
        return None

    data = VILLAGE_SOIL_DATA

    matches = data[
        (
            data["state_name"]
            .map(normalize_text)
            == state_key
        )
        &
        (
            data["district_name"]
            .map(normalize_text)
            == district_key
        )
        &
        (
            data["village_name"]
            .map(normalize_text)
            == village_key
        )
    ]

    if matches.empty:
        return None

    # Prefer a complete profile if duplicate village rows exist.
    if "complete_NPK_pH_profile" in matches.columns:
        complete = matches[
            matches[
                "complete_NPK_pH_profile"
            ]
            .fillna(False)
            .astype(bool)
        ]

        if not complete.empty:
            matches = complete

    return matches.iloc[0]


def build_village_soil_profile(
    row
):
    """
    Convert V4 row to the common soil structure.
    """

    return {
        "soil_source_level":
            "village",

        "state_name":
            row.get(
                "state_name"
            ),

        "district_name":
            row.get(
                "district_name"
            ),

        "block_name":
            row.get(
                "block_name"
            ),

        "village_name":
            row.get(
                "village_name"
            ),

        "village_code":
            row.get(
                "village_code"
            ),

        "nitrogen":
            _soil_level_or_none(
                row.get(
                    "N_level"
                )
            ),

        "phosphorus":
            _soil_level_or_none(
                row.get(
                    "P_level"
                )
            ),

        "potassium":
            _soil_level_or_none(
                row.get(
                    "K_level"
                )
            ),

        "ph_level":
            _soil_level_or_none(
                row.get(
                    "pH_level"
                )
            ),

        "N_quality":
            _get_village_quality(
                row,
                "N_data_quality"
            ),

        "P_quality":
            _get_village_quality(
                row,
                "P_data_quality"
            ),

        "K_quality":
            _get_village_quality(
                row,
                "K_data_quality"
            ),

        "pH_quality":
            _get_village_quality(
                row,
                "pH_data_quality"
            ),

        "overall_quality":
            str(
                row.get(
                    "overall_soil_data_quality",
                    "Unknown"
                )
            ),

        "complete_NPK_pH_profile":
            bool(
                row.get(
                    "complete_NPK_pH_profile",
                    False
                )
            )
    }


# ============================================================
# DISTRICT SOIL LOOKUP
# ============================================================

def get_district_soil(
    state,
    district
):

    state_value = normalize_text(
        state
    )

    district_value = normalize_text(
        district
    )

    result = SOIL_DATA[
        SOIL_DATA[
            "state_name"
        ]
        .astype(str)
        .str.strip()
        .str.casefold()
        == state_value
    ]

    result = result[
        result[
            "district_name"
        ]
        .astype(str)
        .str.strip()
        .str.casefold()
        == district_value
    ]

    if result.empty:

        raise ValueError(
            f"District not found in soil master: "
            f"{state} / {district}"
        )

    return result.iloc[0]


# ============================================================
# SELECT RELEVANT CROP RECORDS
# ============================================================

def select_crop_profile(
    crop_rows,
    soil_type,
    season
):

    rows = crop_rows.copy()

    soil_value = normalize_text(
        soil_type
    )

    season_value = normalize_text(
        season
    )

    def soil_matches(series):

        return series.astype(str).map(
            lambda value:
                (
                    soil_value
                    in split_values(value)
                )
                or
                (
                    soil_value
                    in normalize_text(value)
                )
        )

    def season_matches(series):

        return series.astype(str).map(
            lambda value:
                (
                    season_value
                    in split_values(value)
                )
                or
                (
                    season_value
                    in normalize_text(value)
                )
        )

    soil_rows = (
        rows[
            soil_matches(
                rows["SOIL"]
            )
        ]
        if soil_value
        else pd.DataFrame()
    )

    season_rows = (
        rows[
            season_matches(
                rows["SEASON"]
            )
        ]
        if season_value
        else pd.DataFrame()
    )

    if (
        not soil_rows.empty
        and not season_rows.empty
    ):

        both_rows = rows[
            soil_matches(
                rows["SOIL"]
            )
            &
            season_matches(
                rows["SEASON"]
            )
        ]

    else:

        both_rows = pd.DataFrame()

    if not both_rows.empty:

        selected = both_rows

        profile_source = (
            "soil_and_season"
        )

    elif not soil_rows.empty:

        selected = soil_rows

        profile_source = "soil"

    elif not season_rows.empty:

        selected = season_rows

        profile_source = "season"

    else:

        selected = rows

        profile_source = (
            "all_crop_records"
        )

    profile = {

        "crop":
            rows["CROPS"].iloc[0],

        "profile_source":
            profile_source,

        "source_rows_used":
            int(len(selected))
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
        "K_MAX"
    ]

    for column in numeric_columns:

        profile[column] = (
            selected[column].median()
        )

    categorical_columns = [

        "SOIL",
        "SEASON",

        "N_requirement_level",
        "P_requirement_level",
        "K_requirement_level"
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

            profile[column] = (
                mode.iloc[0]
            )

    return pd.Series(
        profile
    )


# ============================================================
# BUILD UNIQUE CROP PROFILES
# ============================================================

def build_crop_profiles(
    soil_type,
    season
):

    profiles = []

    for crop_name, rows in CROP_DATA.groupby(
        "CROPS",
        sort=False
    ):

        profile = select_crop_profile(
            rows,
            soil_type,
            season
        )

        profiles.append(
            profile
        )

    return pd.DataFrame(
        profiles
    ).reset_index(
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

    # --------------------------------------------------------
    # Soil type
    # --------------------------------------------------------

    components["soil"] = categorical_match(
        user_data["soil_type"],
        crop["SOIL"]
    )

    # --------------------------------------------------------
    # Nitrogen / Phosphorus / Potassium
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # pH
    # --------------------------------------------------------

    components["ph"] = ph_compatibility_score(
        user_data["ph_level"],
        crop["SOIL_PH"],
        crop["SOIL_PH_HIGH"]
    )

    # --------------------------------------------------------
    # Temperature / humidity
    # --------------------------------------------------------

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
    # Water
    # --------------------------------------------------------

    components["water"] = water_score(
        user_data[
            "seasonal_effective_rainfall_mm"
        ],
        user_data[
            "season_days_available"
        ],
        user_data[
            "root_zone_water_pct"
        ],
        user_data[
            "water_balance_7d_mm"
        ],
        crop["WATERREQUIRED"],
        crop["WATERREQUIRED_MAX"]
    )

    # --------------------------------------------------------
    # Automatic season
    # --------------------------------------------------------

    components["season"] = categorical_match(
        user_data["season"],
        crop["SEASON"]
    )

    # --------------------------------------------------------
    # Base weights
    # --------------------------------------------------------

    weights = BASE_WEIGHTS.copy()

    # Ambiguous/missing nutrient data should not receive
    # the normal nutrient weight.
    for nutrient in [
        "nitrogen",
        "phosphorus",
        "potassium"
    ]:

        if components[nutrient] is None:

            weights[nutrient] = 0

        else:

            quality_key = {
                "nitrogen": "N_quality",
                "phosphorus": "P_quality",
                "potassium": "K_quality"
            }[nutrient]

            weights[nutrient] *= quality_factor(
                user_data[
                    quality_key
                ]
            )

    # pH can also be ambiguous.
    if (
        components["ph"] is None
        or user_data["ph_level"] is None
    ):

        weights["ph"] = 0

    else:

        weights["ph"] *= quality_factor(
            user_data["pH_quality"]
        )

    # --------------------------------------------------------
    # Weighted score
    # --------------------------------------------------------

    weighted_score = 0.0
    active_weight = 0.0

    for component, weight in weights.items():

        if weight <= 0:
            continue

        value = components[
            component
        ]

        if value is None:
            continue

        weighted_score += (
            float(value)
            * weight
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
            str(
                crop["crop"]
            ),

        "score":
            round(
                score,
                2
            ),

        "confidence_like":
            round(
                score / 100,
                4
            ),

        "profile_source":
            str(
                crop[
                    "profile_source"
                ]
            ),

        "source_rows_used":
            int(
                crop[
                    "source_rows_used"
                ]
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
                user_data[
                    "overall_quality"
                ]
        }
    }



def recommend_crops(
    state,
    district,
    village,
    soil_type,
    weather,
    top_n=5
):
    """
    AgroNexus V1.5 recommendation engine.

    Inputs:
        state
        district
        village
        soil_type
        weather

    Season is ALWAYS taken from weather["season"].
    The farmer does not provide season manually.

    Soil hierarchy:
        exact village V4
        -> district V3 fallback

    The V4 file contains block information, but because
    the public input does not ask the farmer for a block,
    exact village matching is used. District V3 is the
    fallback when village matching fails.
    """

    # --------------------------------------------------------
    # Automatic season
    # --------------------------------------------------------

    season = weather.get(
        "season"
    )

    if not season:

        raise ValueError(
            "Automatic season is missing from weather data. "
            "Call get_weather_features() first."
        )

    season = str(
        season
    ).strip()

    # --------------------------------------------------------
    # Village soil first
    # --------------------------------------------------------

    village_row = get_village_soil(
        state,
        district,
        village
    )

    if village_row is not None:

        soil = build_village_soil_profile(
            village_row
        )

    else:

        # District V3 fallback.
        district_soil = get_district_soil(
            state,
            district
        )

        soil = {

            "soil_source_level":
                "district",

            "state_name":
                district_soil.get(
                    "state_name"
                ),

            "district_name":
                district_soil.get(
                    "district_name"
                ),

            "block_name":
                None,

            "village_name":
                village,

            "village_code":
                None,

            "nitrogen":
                district_soil.get(
                    "N_level"
                ),

            "phosphorus":
                district_soil.get(
                    "P_level"
                ),

            "potassium":
                district_soil.get(
                    "K_level"
                ),

            "ph_level":
                district_soil.get(
                    "pH_level"
                ),

            "N_quality":
                district_soil.get(
                    "N_data_quality",
                    "Unknown"
                ),

            "P_quality":
                district_soil.get(
                    "P_data_quality",
                    "Unknown"
                ),

            "K_quality":
                district_soil.get(
                    "K_data_quality",
                    "Unknown"
                ),

            "pH_quality":
                district_soil.get(
                    "pH_data_quality",
                    "Unknown"
                ),

            "overall_quality":
                district_soil.get(
                    "overall_soil_data_quality",
                    "Unknown"
                ),

            "complete_NPK_pH_profile":
                True
        }

    # --------------------------------------------------------
    # Crop profiles
    # --------------------------------------------------------

    profiles = build_crop_profiles(
        soil_type,
        season
    )

    # --------------------------------------------------------
    # Weather / water fields
    # --------------------------------------------------------

    root_zone_water = weather.get(
        "estimated_root_zone_water_mm"
    )

    root_zone_pct = weather.get(
        "root_zone_water_pct"
    )

    if root_zone_pct is None:

        capacity = weather.get(
            "estimated_root_zone_capacity_mm"
        )

        if (
            capacity
            and root_zone_water is not None
        ):

            root_zone_pct = (
                float(root_zone_water)
                / float(capacity)
                * 100
            )

    seasonal_effective = weather.get(
        "seasonal_effective_rainfall_mm"
    )

    if seasonal_effective is None:

        seasonal_effective = weather.get(
            "seasonal_rainfall_mm"
        )

    season_days_available = weather.get(
        "season_days_available",
        0
    )

    water_balance_7d = weather.get(
        "water_balance_7d_mm"
    )

    user_data = {

        "soil_type":
            soil_type,

        "nitrogen":
            soil.get(
                "nitrogen"
            ),

        "phosphorus":
            soil.get(
                "phosphorus"
            ),

        "potassium":
            soil.get(
                "potassium"
            ),

        "ph_level":
            soil.get(
                "ph_level"
            ),

        "N_quality":
            soil.get(
                "N_quality",
                "Unknown"
            ),

        "P_quality":
            soil.get(
                "P_quality",
                "Unknown"
            ),

        "K_quality":
            soil.get(
                "K_quality",
                "Unknown"
            ),

        "pH_quality":
            soil.get(
                "pH_quality",
                "Unknown"
            ),

        "overall_quality":
            soil.get(
                "overall_quality",
                "Unknown"
            ),

        "temperature_c":
            weather.get(
                "temperature_c"
            ),

        "humidity_pct":
            weather.get(
                "humidity_pct"
            ),

        "estimated_root_zone_water_mm":
            root_zone_water,

        "root_zone_water_pct":
            root_zone_pct,

        "seasonal_effective_rainfall_mm":
            seasonal_effective,

        "season_days_available":
            season_days_available,

        "water_balance_7d_mm":
            water_balance_7d,

        "season":
            season
    }

    # --------------------------------------------------------
    # Score all unique crops
    # --------------------------------------------------------

    results = []

    for _, crop in profiles.iterrows():

        results.append(
            score_crop(
                crop,
                user_data
            )
        )

    # --------------------------------------------------------
    # Guarantee unique crop names
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

    ranked = sorted(
        unique_results.values(),
        key=lambda item: (
            -item["score"],
            item["crop"].casefold()
        )
    )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {

        "location": {

            "state":
                state,

            "district":
                district,

            "village":
                village
        },

        "soil": {

            "source_level":
                soil.get(
                    "soil_source_level"
                ),

            "state_name":
                soil.get(
                    "state_name"
                ),

            "district_name":
                soil.get(
                    "district_name"
                ),

            "block_name":
                soil.get(
                    "block_name"
                ),

            "village_name":
                soil.get(
                    "village_name"
                ),

            "village_code":
                soil.get(
                    "village_code"
                ),

            "soil_type":
                soil_type,

            "nitrogen":
                user_data[
                    "nitrogen"
                ],

            "phosphorus":
                user_data[
                    "phosphorus"
                ],

            "potassium":
                user_data[
                    "potassium"
                ],

            "ph_level":
                user_data[
                    "ph_level"
                ],

            "N_quality":
                user_data[
                    "N_quality"
                ],

            "P_quality":
                user_data[
                    "P_quality"
                ],

            "K_quality":
                user_data[
                    "K_quality"
                ],

            "pH_quality":
                user_data[
                    "pH_quality"
                ],

            "data_quality":
                user_data[
                    "overall_quality"
                ],

            "complete_NPK_pH_profile":
                soil.get(
                    "complete_NPK_pH_profile"
                )
        },

        "water": {

            "estimated_root_zone_water_mm":
                root_zone_water,

            "root_zone_water_pct":
                root_zone_pct,

            "water_balance_7d_mm":
                weather.get(
                    "water_balance_7d_mm"
                ),

            "water_balance_30d_mm":
                weather.get(
                    "water_balance_30d_mm"
                ),

            "seasonal_rainfall_mm":
                weather.get(
                    "seasonal_rainfall_mm"
                ),

            "seasonal_effective_rainfall_mm":
                weather.get(
                    "seasonal_effective_rainfall_mm"
                ),

            "seasonal_et0_mm":
                weather.get(
                    "seasonal_et0_mm"
                ),

            "seasonal_water_balance_mm":
                weather.get(
                    "seasonal_water_balance_mm"
                ),

            "status":
                weather.get(
                    "water_status"
                )
        },

        "season": season,

        "season_source":
            "automatic",

        "season_analysis_period_months":
            4,

        "season_start_date":
            weather.get(
                "season_start_date"
            ),

        "season_end_date":
            weather.get(
                "season_end_date"
            ),

        "crop_count_evaluated":
            len(ranked),

        "recommendations":
            ranked[:top_n]
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    from weather_service import (
        get_weather_features
    )

    print("=" * 70)
    print("AGRONEXUS CROP RECOMMENDATION V1.5")
    print("=" * 70)

    test_state = "Kerala"
    test_district = "Wayanad"
    test_village = "Achooranam"
    test_soil_type = "Laterite"

    print(
        "\nLoading live weather..."
    )

    weather = get_weather_features(
        11.6854,
        76.1320,
        test_soil_type
    )

    print(
        "Season:",
        weather.get(
            "season"
        )
    )

    print(
        "Season window:",
        weather.get(
            "season_start_date"
        ),
        "to",
        weather.get(
            "season_end_date"
        )
    )

    result = recommend_crops(
        test_state,
        test_district,
        test_village,
        test_soil_type,
        weather,
        top_n=5
    )

    print(
        "\nSOIL:"
    )

    print(
        result["soil"]
    )

    print(
        "\nWATER:"
    )

    print(
        result["water"]
    )

    print(
        "\nCROPS EVALUATED:",
        result[
            "crop_count_evaluated"
        ]
    )

    print(
        "\nTOP 5:"
    )

    for index, item in enumerate(
        result["recommendations"],
        start=1
    ):

        print(
            index,
            item["crop"],
            "=",
            item["score"],
            "components=",
            item["components"]
        )
