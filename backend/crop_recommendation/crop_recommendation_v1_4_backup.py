import os
import pandas as pd
import numpy as np


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

    actual_level = LEVELS.get(
        normalize_text(actual)
    )

    required_level = LEVELS.get(
        normalize_text(required)
    )

    if (
        actual_level is None
        or required_level is None
    ):
        return 0.5

    difference = abs(
        actual_level
        - required_level
    )

    if difference == 0:
        return 1.0

    if difference == 1:
        return 0.5

    return 0.0


# ============================================================
# NUMERIC RANGE MATCH
# ============================================================

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
    root_zone_water_mm,
    crop_minimum,
    crop_maximum
):
    """
    Compare estimated root-zone water with
    the crop's water requirement.

    root_zone_water_mm:
        Estimated water currently available
        in the root zone.

    This is NOT direct measured soil moisture.
    """

    if (
        root_zone_water_mm is None
        or pd.isna(root_zone_water_mm)
        or crop_minimum is None
        or pd.isna(crop_minimum)
    ):
        return 0.5

    available = float(
        root_zone_water_mm
    )

    minimum = max(
        float(crop_minimum),
        0.0
    )

    if (
        crop_maximum is not None
        and not pd.isna(crop_maximum)
    ):
        maximum = float(
            crop_maximum
        )
    else:
        maximum = minimum

    # No crop water requirement.
    if minimum <= 0:
        return 1.0

    # Enough root-zone water for minimum need.
    if available >= minimum:
        return 1.0

    # Some water available but below requirement.
    if available > 0:

        return max(
            0.0,
            min(
                1.0,
                available / minimum
            )
        )

    return 0.0


# ============================================================
# DATA QUALITY FACTOR
# ============================================================

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
    # Nitrogen
    # --------------------------------------------------------

    components["nitrogen"] = nutrient_level_score(
        user_data["nitrogen"],
        crop["N_requirement_level"]
    )

    # --------------------------------------------------------
    # Phosphorus
    # --------------------------------------------------------

    components["phosphorus"] = nutrient_level_score(
        user_data["phosphorus"],
        crop["P_requirement_level"]
    )

    # --------------------------------------------------------
    # Potassium
    # --------------------------------------------------------

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
    # Temperature
    # --------------------------------------------------------

    components["temperature"] = range_score(
        user_data["temperature_c"],
        crop["TEMP"],
        crop["MAX_TEMP"]
    )

    # --------------------------------------------------------
    # Humidity
    # --------------------------------------------------------

    components["humidity"] = range_score(
        user_data["humidity_pct"],
        crop["RELATIVE_HUMIDITY"],
        crop["RELATIVE_HUMIDITY_MAX"]
    )

    # --------------------------------------------------------
    # WATER
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # Use estimated root-zone water from the
    # 30-day water model.
    #
    components["water"] = water_score(
        user_data[
            "estimated_root_zone_water_mm"
        ],
        crop["WATERREQUIRED"],
        crop["WATERREQUIRED_MAX"]
    )

    # --------------------------------------------------------
    # Season
    # --------------------------------------------------------

    components["season"] = categorical_match(
        user_data["season"],
        crop["SEASON"]
    )

    # --------------------------------------------------------
    # Base weights
    # --------------------------------------------------------

    weights = BASE_WEIGHTS.copy()

    # Reduce influence of weak soil evidence.
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

    # --------------------------------------------------------
    # Calculate normalized score
    # --------------------------------------------------------

    weighted_score = 0.0
    active_weight = 0.0

    for component, weight in weights.items():

        if weight <= 0:
            continue

        weighted_score += (
            components[component]
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
            str(crop["crop"]),

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
                round(
                    float(value),
                    3
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


# ============================================================
# MAIN RECOMMENDATION FUNCTION
# ============================================================

def recommend_crops(
    state,
    district,
    soil_type,
    weather,
    season=None,
    top_n=5
):

    district_soil = get_district_soil(
        state,
        district
    )

    profiles = build_crop_profiles(
        soil_type,
        season
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Root-zone water is now preferred.
    #
    # Older weather service versions may still provide
    # available_water_mm, so we keep a fallback.
    # --------------------------------------------------------

    root_zone_water = weather.get(
        "estimated_root_zone_water_mm"
    )

    if root_zone_water is None:

        root_zone_water = weather.get(
            "available_water_mm"
        )

    user_data = {

        "soil_type":
            soil_type,

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
                "N_data_quality"
            ),

        "P_quality":
            district_soil.get(
                "P_data_quality"
            ),

        "K_quality":
            district_soil.get(
                "K_data_quality"
            ),

        "pH_quality":
            district_soil.get(
                "pH_data_quality"
            ),

        "overall_quality":
            district_soil.get(
                "overall_soil_data_quality"
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

        "water_balance_7d_mm":
            weather.get(
                "water_balance_7d_mm"
            ),

        "water_balance_30d_mm":
            weather.get(
                "water_balance_30d_mm"
            ),

        "season":
            season
    }

    # --------------------------------------------------------
    # Score all unique crop profiles
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
    # Return final result
    # --------------------------------------------------------

    return {

        "location": {

            "state":
                state,

            "district":
                district
        },

        "soil": {

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

            "data_quality":
                user_data[
                    "overall_quality"
                ]
        },

        "water": {

            "estimated_root_zone_water_mm":
                root_zone_water,

            "water_balance_7d_mm":
                user_data[
                    "water_balance_7d_mm"
                ],

            "water_balance_30d_mm":
                user_data[
                    "water_balance_30d_mm"
                ],

            "status":
                weather.get(
                    "water_status"
                )
        },

        "weather":
            weather,

        "season":
            season,

        "crop_count_evaluated":
            len(ranked),

        "recommendations":
            ranked[:top_n]
    }