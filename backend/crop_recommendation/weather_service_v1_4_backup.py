import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


# ============================================================
# ESTIMATED ROOT-ZONE WATER-HOLDING CAPACITY
# ============================================================
#
# Approximate available-water capacity for a 0-100 cm
# effective root zone.
#
# These are MODEL ASSUMPTIONS, not direct measurements.
#
SOIL_WATER_CAPACITY_MM = {
    "sandy": 100,
    "sandy loam": 130,
    "loam": 170,
    "silt loam": 180,
    "clay loam": 200,
    "clay": 220,

    "laterite": 120,

    "red": 140,
    "red soil": 140,
    "red loam": 150,
    "red loamy": 150,

    "black": 200,
    "black soil": 200,

    "alluvial": 180,
    "alluvial soil": 180,

    "forest": 160,
    "forest soil": 160,
}


# ============================================================
# TIMEZONE
# ============================================================

def _get_timezone_name(latitude, longitude):

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m",
        "timezone": "auto",
    }

    response = requests.get(
        OPEN_METEO_URL,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "timezone",
        "Asia/Kolkata"
    )


# ============================================================
# DAILY WEATHER
# ============================================================

def _fetch_daily_weather(
    latitude,
    longitude,
    start_date,
    end_date,
):

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "daily": (
            "precipitation_sum,"
            "et0_fao_evapotranspiration"
        ),

        "timezone": "auto",

        "start_date": start_date,
        "end_date": end_date,
    }

    response = requests.get(
        OPEN_METEO_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# SOIL WATER CAPACITY
# ============================================================

def _get_soil_capacity(soil_type):

    if not soil_type:
        return 150.0

    soil = str(
        soil_type
    ).strip().casefold()

    if soil in SOIL_WATER_CAPACITY_MM:

        return float(
            SOIL_WATER_CAPACITY_MM[soil]
        )

    # Handle names such as:
    # "Laterite Soil", "Red Loamy Soil", etc.
    for name, capacity in SOIL_WATER_CAPACITY_MM.items():

        if name in soil:

            return float(
                capacity
            )

    # Generic fallback.
    return 150.0


# ============================================================
# EFFECTIVE RAINFALL
# ============================================================

def _effective_rainfall(
    rainfall_mm
):

    # Initial model assumption:
    # 80% of rainfall becomes effective
    # root-zone rainfall.
    #
    # The remaining 20% represents approximate
    # runoff/interception/deep loss.
    #
    # This can later be improved using:
    # slope + rainfall intensity + land cover +
    # infiltration characteristics.

    return max(
        0.0,
        float(rainfall_mm) * 0.80
    )


# ============================================================
# ROOT-ZONE WATER MODEL
# ============================================================

def _estimate_root_zone_water(
    capacity_mm,
    effective_rainfall_mm,
    et0_mm,
):
    """
    Estimate root-zone available water using a simple
    soil-water bucket model.

    Because we do not have measured initial soil moisture,
    we assume 50% initial storage.

    This is an ESTIMATE, not measured soil moisture.
    """

    initial_storage = (
        capacity_mm * 0.50
    )

    storage = (
        initial_storage
        + effective_rainfall_mm
        - et0_mm
    )

    storage = max(
        0.0,
        min(
            capacity_mm,
            storage
        )
    )

    return storage


# ============================================================
# WATER STATUS
# ============================================================

def _water_status(
    percentage
):

    if percentage >= 70:

        return "Adequate"

    if percentage >= 40:

        return "Moderate"

    if percentage >= 20:

        return "Low"

    return "Very Low"


# ============================================================
# MAIN WEATHER FUNCTION
# ============================================================

def get_weather_features(
    latitude,
    longitude,
    soil_type="",
):

    """
    Get current weather and 30-day water indicators.

    Outputs include:

    Current:
        temperature_c
        humidity_pct

    Recent:
        rainfall_7d_mm
        et0_7d_mm
        water_balance_7d_mm

    30-day:
        rainfall_30d_mm
        et0_30d_mm
        effective_rainfall_30d_mm
        water_balance_30d_mm

    Root zone:
        estimated_root_zone_water_mm
        estimated_root_zone_capacity_mm
        root_zone_water_pct
        water_status

    IMPORTANT:
        Root-zone water is an estimate based on:
        - 30-day rainfall
        - ET0
        - soil-class capacity
        - 50% assumed initial storage
    """

    # --------------------------------------------------------
    # 1. Location timezone
    # --------------------------------------------------------

    timezone_name = _get_timezone_name(
        latitude,
        longitude
    )

    try:

        local_timezone = ZoneInfo(
            timezone_name
        )

    except Exception:

        local_timezone = ZoneInfo(
            "Asia/Kolkata"
        )

        timezone_name = (
            "Asia/Kolkata"
        )

    today = datetime.now(
        local_timezone
    ).date()

    start_30 = (
        today
        - timedelta(days=29)
    )

    # --------------------------------------------------------
    # 2. Fetch 30-day weather
    # --------------------------------------------------------

    weather_data = _fetch_daily_weather(
        latitude,
        longitude,
        start_30.isoformat(),
        today.isoformat(),
    )

    daily = weather_data.get(
        "daily",
        {}
    )

    dates = daily.get(
        "time",
        []
    )

    rainfall = daily.get(
        "precipitation_sum",
        []
    )

    et0 = daily.get(
        "et0_fao_evapotranspiration",
        []
    )

    if not dates:

        raise RuntimeError(
            "Weather API returned no daily data."
        )

    # --------------------------------------------------------
    # 3. Build daily records
    # --------------------------------------------------------

    records = []

    for index, date_value in enumerate(
        dates
    ):

        rain = (
            rainfall[index]
            if index < len(rainfall)
            else 0
        )

        evapotranspiration = (
            et0[index]
            if index < len(et0)
            else 0
        )

        try:

            rain = float(
                rain or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            rain = 0.0

        try:

            evapotranspiration = float(
                evapotranspiration or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            evapotranspiration = 0.0

        records.append({

            "date":
                date_value,

            "rainfall_mm":
                rain,

            "et0_mm":
                evapotranspiration,
        })

    # --------------------------------------------------------
    # 4. 30-day totals
    # --------------------------------------------------------

    rainfall_30 = sum(
        row["rainfall_mm"]
        for row in records
    )

    et0_30 = sum(
        row["et0_mm"]
        for row in records
    )

    effective_rainfall_30 = (
        _effective_rainfall(
            rainfall_30
        )
    )

    water_balance_30 = (
        effective_rainfall_30
        - et0_30
    )

    # --------------------------------------------------------
    # 5. 7-day trend
    # --------------------------------------------------------

    recent_records = records[-7:]

    rainfall_7 = sum(
        row["rainfall_mm"]
        for row in recent_records
    )

    et0_7 = sum(
        row["et0_mm"]
        for row in recent_records
    )

    effective_rainfall_7 = (
        _effective_rainfall(
            rainfall_7
        )
    )

    water_balance_7 = (
        effective_rainfall_7
        - et0_7
    )

    # --------------------------------------------------------
    # 6. Soil root-zone capacity
    # --------------------------------------------------------

    capacity = _get_soil_capacity(
        soil_type
    )

    # --------------------------------------------------------
    # 7. Estimated root-zone water
    # --------------------------------------------------------

    root_zone_water = (
        _estimate_root_zone_water(
            capacity,
            effective_rainfall_30,
            et0_30,
        )
    )

    root_zone_percentage = (
        root_zone_water
        / capacity
        * 100
        if capacity > 0
        else 0
    )

    status = _water_status(
        root_zone_percentage
    )

    # --------------------------------------------------------
    # 8. Current weather
    # --------------------------------------------------------

    current_params = {

        "latitude":
            latitude,

        "longitude":
            longitude,

        "current":
            (
                "temperature_2m,"
                "relative_humidity_2m"
            ),

        "timezone":
            "auto",
    }

    response = requests.get(
        OPEN_METEO_URL,
        params=current_params,
        timeout=20,
    )

    response.raise_for_status()

    current_data = response.json()

    current = current_data.get(
        "current",
        {}
    )

    temperature = current.get(
        "temperature_2m"
    )

    humidity = current.get(
        "relative_humidity_2m"
    )

    # --------------------------------------------------------
    # 9. Final result
    # --------------------------------------------------------

    return {

        "temperature_c":
            round(
                float(temperature),
                2
            )
            if temperature is not None
            else None,

        "humidity_pct":
            round(
                float(humidity),
                2
            )
            if humidity is not None
            else None,

        # ------------------------------
        # 7-day recent trend
        # ------------------------------

        "rainfall_7d_mm":
            round(
                rainfall_7,
                2
            ),

        "et0_7d_mm":
            round(
                et0_7,
                2
            ),

        "water_balance_7d_mm":
            round(
                water_balance_7,
                2
            ),

        # ------------------------------
        # 30-day baseline
        # ------------------------------

        "rainfall_30d_mm":
            round(
                rainfall_30,
                2
            ),

        "et0_30d_mm":
            round(
                et0_30,
                2
            ),

        "effective_rainfall_30d_mm":
            round(
                effective_rainfall_30,
                2
            ),

        "water_balance_30d_mm":
            round(
                water_balance_30,
                2
            ),

        # ------------------------------
        # Root-zone estimate
        # ------------------------------

        "estimated_root_zone_water_mm":
            round(
                root_zone_water,
                2
            ),

        "estimated_root_zone_capacity_mm":
            round(
                capacity,
                2
            ),

        "root_zone_water_pct":
            round(
                root_zone_percentage,
                2
            ),

        "water_status":
            status,

        # ------------------------------
        # Compatibility
        # ------------------------------

        "water_balance_mm":
            round(
                water_balance_30,
                2
            ),

        "available_water_mm":
            round(
                root_zone_water,
                2
            ),

        "water_estimate_note":
            (
                "Estimated root-zone water based on "
                "30-day rainfall and ET0, soil-class "
                "water-holding capacity, and a 50% "
                "initial-storage assumption. It is not "
                "a direct soil-moisture measurement."
            ),

        "timezone":
            timezone_name,
    }