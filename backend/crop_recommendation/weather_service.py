"""
AgroNexus Weather Service V1.11
--------------------------------

Purpose:
    Retrieve historical AgERA5 v2 weather data for a farm location
    using the official Copernicus CDS AgERA5 time-series product.

Seasonal evidence window:

    PRE-SEASON  : 1 month before season
    MAIN SEASON : complete agricultural season
    POST-SEASON : 1 month after season

Example Kharif:
    2025-05-01 -> 2025-10-31

Important:
    This module does NOT yet convert crop WATERREQUIRED into
    irrigation requirement.

It only produces scientifically meaningful weather evidence.

Primary source:
    AgERA5 v2 time-series
    Copernicus Climate Data Store
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import calendar
import json
import sys

# pyrefly: ignore [missing-import]
import cdsapi
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

CACHE_DIR = BASE_DIR / "weather_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

AGERA5_DATASET = "sis-agrometeorological-indicators-timeseries"


# ============================================================
# TEST LOCATION
# ============================================================

# Achooranam / Wayanad test location.
#
# IMPORTANT:
# Replace these coordinates with the exact coordinates from
# your village master once confirmed.
#
# These are only the initial validation coordinates.

TEST_LOCATION = {
    "name": "Achooranam",
    "latitude": 11.60,
    "longitude": 76.08,
}


# ============================================================
# SEASON DEFINITIONS
# ============================================================

SEASON_MONTHS = {
    "kharif": (6, 9),
    "rabi": (10, 1),
    "zaid": (2, 5),
}


# ============================================================
# DATE HELPERS
# ============================================================

def last_day_of_month(year: int, month: int) -> date:
    """Return last calendar day of a month."""
    return date(
        year,
        month,
        calendar.monthrange(year, month)[1],
    )


def add_months(year: int, month: int, offset: int) -> tuple[int, int]:
    """
    Add/subtract whole calendar months.
    """
    total = year * 12 + (month - 1) + offset

    new_year = total // 12
    new_month = total % 12 + 1

    return new_year, new_month


def month_window(
    year: int,
    month: int,
) -> tuple[date, date]:
    """Return first and last date of a month."""
    return (
        date(year, month, 1),
        last_day_of_month(year, month),
    )


# ============================================================
# SEASON WINDOW
# ============================================================

def get_season_window(
    season: str,
    season_year: int,
) -> dict:
    """
    Build:

        pre-season  = 1 month before
        main season = agricultural season
        post-season = 1 month after

    season_year convention:

        Kharif 2025 -> Jun-Sep 2025
        Rabi 2026   -> Oct 2025-Jan 2026
        Zaid 2026   -> Feb-May 2026
    """

    season_key = season.strip().lower()

    if season_key == "kharif":
        main_start = date(season_year, 6, 1)
        main_end = date(season_year, 9, 30)

    elif season_key == "rabi":
        main_start = date(season_year - 1, 10, 1)
        main_end = date(season_year, 1, 31)

    elif season_key == "zaid":
        main_start = date(season_year, 2, 1)
        main_end = date(season_year, 5, 31)

    else:
        raise ValueError(
            f"Unknown season: {season}. "
            f"Use Kharif, Rabi or Zaid."
        )

    # One month before main season
    pre_year, pre_month = add_months(
        main_start.year,
        main_start.month,
        -1,
    )

    pre_start, pre_end = month_window(
        pre_year,
        pre_month,
    )

    # One month after main season
    post_year, post_month = add_months(
        main_end.year,
        main_end.month,
        1,
    )

    post_start, post_end = month_window(
        post_year,
        post_month,
    )

    return {
        "pre_start": pre_start,
        "pre_end": pre_end,

        "main_start": main_start,
        "main_end": main_end,

        "post_start": post_start,
        "post_end": post_end,

        "overall_start": pre_start,
        "overall_end": post_end,
    }


# ============================================================
# CDS REQUEST
# ============================================================

def build_cds_request(
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Build the AgERA5 v2 time-series CDS request.

    A small area is requested instead of an exact point because
    AgERA5 is provided on a 0.1-degree grid.

    The requested farm/village coordinate is used later to select
    the nearest available AgERA5 grid point.
    """

    variables = [
        "2m_temperature_24_hour_mean",
        "2m_temperature_24_hour_minimum",
        "2m_temperature_24_hour_maximum",
        "precipitation_flux",
        "reference_evapotranspiration",
        "derived_2m_relative_humidity_24_hour_minimum",
        "derived_2m_relative_humidity_24_hour_maximum",
        "vapour_pressure_deficit_at_maximum_temperature",
        "solar_radiation_flux",
        "10m_wind_speed_24_hour_mean",
    ]

    # --------------------------------------------------------
    # AgERA5 is a 0.1-degree grid.
    #
    # Request a small box around the target location rather
    # than requiring the exact user coordinate to exist.
    # --------------------------------------------------------

    half_width = 0.06

    north = latitude + half_width
    west = longitude - half_width
    south = latitude - half_width
    east = longitude + half_width

    request = {
        "variable": variables,

        "date": [
            start_date.isoformat(),
            end_date.isoformat(),
        ],

        "area": [
            north,
            west,
            south,
            east,
        ],

        "data_format": "csv",
    }

    return request
# ============================================================
# DOWNLOAD
# ============================================================

def download_agera5(
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
    output_file: Path,
) -> Path:

    print()
    print("=" * 70)
    print("AGRONEXUS - AgERA5 v2 TIME-SERIES DOWNLOAD")
    print("=" * 70)

    print(f"Latitude  : {latitude}")
    print(f"Longitude : {longitude}")
    print(f"Start     : {start_date}")
    print(f"End       : {end_date}")
    print(f"Output    : {output_file}")

    if output_file.exists():
        print()
        print("Using cached file:")
        print(output_file)
        return output_file

    request = build_cds_request(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
    )

    print()
    print("Variables:")
    for variable in request["variable"]:
        print(f"  - {variable}")

    print()
    print("Connecting to Copernicus CDS...")

    client = cdsapi.Client()

    print("Submitting AgERA5 time-series request...")

    client.retrieve(
        AGERA5_DATASET,
        request,
        str(output_file),
    )

    if not output_file.exists():
        raise RuntimeError(
            "CDS request completed but output file "
            "was not created."
        )

    print()
    print("Download completed:")
    print(output_file)

    return output_file


# ============================================================
# CSV NORMALIZATION
# ============================================================

def find_column(
    columns,
    candidates,
):
    """
    Find a matching column ignoring case,
    spaces and punctuation.
    """

    normalized = {}

    for column in columns:
        key = (
            str(column)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        normalized[key] = column

    for candidate in candidates:

        key = (
            candidate
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        if key in normalized:
            return normalized[key]

    return None


def load_agera5_csv(csv_file: Path) -> pd.DataFrame:
    """
    Load and normalize the AgERA5 CSV.

    Because CDS CSV column naming can contain metadata,
    we inspect the columns rather than assuming one exact
    capitalization.
    """

    print()
    print("Reading AgERA5 CSV...")

    df = pd.read_csv(csv_file)

    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    print()
    print("Raw columns:")

    for column in df.columns:
        print(f"  {column}")

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_column = find_column(
        df.columns,
        [
            "valid_time",
            "date",
            "time",
            "datetime",
        ],
    )

    if date_column is None:
        raise ValueError(
            "Could not identify date column.\n"
            f"Available columns: {list(df.columns)}"
        )

    df["date"] = pd.to_datetime(
        df[date_column],
        errors="coerce",
    )

    df = df.dropna(
        subset=["date"]
    ).copy()

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    for column in df.columns:

        if column == "date":
            continue

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    return df


# ============================================================
# VARIABLE IDENTIFICATION
# ============================================================

def identify_weather_columns(df: pd.DataFrame) -> dict:
    """
    Identify the actual AgERA5 CSV columns returned by CDS.
    """

    columns = df.columns

    mapping = {}

    mapping["temperature_mean"] = find_column(
        columns,
        [
            "Temperature_Air_2m_Mean_24h",
        ],
    )

    mapping["temperature_min"] = find_column(
        columns,
        [
            "Temperature_Air_2m_Min_24h",
        ],
    )

    mapping["temperature_max"] = find_column(
        columns,
        [
            "Temperature_Air_2m_Max_24h",
        ],
    )

    mapping["humidity_min"] = find_column(
        columns,
        [
            "Derived_Relative_Humidity_2m_Min_24h",
        ],
    )

    mapping["humidity_max"] = find_column(
        columns,
        [
            "Derived_Relative_Humidity_2m_Max_24h",
        ],
    )

    mapping["precipitation"] = find_column(
        columns,
        [
            "Precipitation_Flux",
        ],
    )

    mapping["et0"] = find_column(
        columns,
        [
            "ReferenceET_PenmanMonteith_FAO56",
        ],
    )

    mapping["vpd"] = find_column(
        columns,
        [
            "Vapour_Pressure_Deficit_at_Maximum_Temperature",
        ],
    )

    mapping["solar"] = find_column(
        columns,
        [
            "Solar_Radiation_Flux",
        ],
    )

    mapping["wind"] = find_column(
        columns,
        [
            "Wind_Speed_10m_Mean_24h",
        ],
    )

    return mapping
# ============================================================
# UNIT NORMALIZATION
# ============================================================

def normalize_units(
    df: pd.DataFrame,
    columns: dict,
) -> pd.DataFrame:

    df = df.copy()

    # --------------------------------------------------------
    # Temperature
    #
    # AgERA5 temperature variables are provided in Kelvin.
    # Convert to Celsius.
    # --------------------------------------------------------

    for key in (
        "temperature_mean",
        "temperature_min",
        "temperature_max",
    ):

        column = columns.get(key)

        if column is None:
            continue

        # Kelvin values are generally > 200.
        # Do not convert if already Celsius.
        median_value = df[column].median()

        if pd.notna(median_value) and median_value > 100:

            df[column] = (
                df[column] - 273.15
            )

    # --------------------------------------------------------
    # Other AgERA5 variables already have useful units:
    #
    # precipitation       mm/day
    # ET0                  mm/day
    # humidity             %
    # VPD                  hPa
    # solar radiation      J/m2/day
    # wind                 m/s
    # --------------------------------------------------------

    return df


# ============================================================
# DATE FILTERING
# ============================================================

def filter_period(
    df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:

    mask = (
        (df["date"].dt.date >= start_date)
        &
        (df["date"].dt.date <= end_date)
    )

    return df.loc[mask].copy()


# ============================================================
# PERIOD SUMMARY
# ============================================================

def summarize_period(
    df: pd.DataFrame,
    columns: dict,
    name: str,
) -> dict:

    result = {
        "period": name,
        "days": int(len(df)),
    }

    if df.empty:
        return result

    # --------------------------------------------------------
    # Rainfall
    # --------------------------------------------------------

    precipitation = columns.get(
        "precipitation"
    )

    if precipitation:
        rain = df[precipitation].dropna()

        result["rainfall_total_mm"] = float(
            rain.sum()
        )

        result["rainfall_mean_mm_day"] = float(
            rain.mean()
        )

        result["rainy_days"] = int(
            (rain > 1.0).sum()
        )

        result["heavy_rain_days"] = int(
            (rain >= 20.0).sum()
        )

        result["max_daily_rainfall_mm"] = float(
            rain.max()
        )

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    for key, output_name in [
        (
            "temperature_mean",
            "temperature_mean_c",
        ),
        (
            "temperature_min",
            "temperature_min_c",
        ),
        (
            "temperature_max",
            "temperature_max_c",
        ),
    ]:

        column = columns.get(key)

        if column:
            result[output_name] = float(
                df[column].mean()
            )

    # --------------------------------------------------------
    # ET0
    # --------------------------------------------------------

    et0_column = columns.get("et0")

    if et0_column:
        et0 = df[et0_column].dropna()

        result["et0_total_mm"] = float(
            et0.sum()
        )

        result["et0_mean_mm_day"] = float(
            et0.mean()
        )

    # --------------------------------------------------------
    # RH
    # --------------------------------------------------------

    for key, output_name in [
        (
            "humidity_min",
            "humidity_min_mean_pct",
        ),
        (
            "humidity_max",
            "humidity_max_mean_pct",
        ),
    ]:

        column = columns.get(key)

        if column:
            result[output_name] = float(
                df[column].mean()
            )

    # --------------------------------------------------------
    # VPD
    # --------------------------------------------------------

    vpd_column = columns.get("vpd")

    if vpd_column:
        vpd = df[vpd_column].dropna()

        result["vpd_mean_hpa"] = float(
            vpd.mean()
        )

        result["vpd_max_hpa"] = float(
            vpd.max()
        )

    # --------------------------------------------------------
    # Rainfall - ET0
    #
    # This is NOT crop water availability.
    #
    # It is only an atmospheric/precipitation balance indicator.
    # --------------------------------------------------------

    if (
        "rainfall_total_mm" in result
        and "et0_total_mm" in result
    ):

        result["rainfall_minus_et0_mm"] = (
            result["rainfall_total_mm"]
            -
            result["et0_total_mm"]
        )

    return result


# ============================================================
# COMPLETE SEASON ANALYSIS
# ============================================================

def analyze_season(
    df: pd.DataFrame,
    columns: dict,
    season: str,
    season_year: int,
) -> dict:

    window = get_season_window(
        season,
        season_year,
    )

    pre_df = filter_period(
        df,
        window["pre_start"],
        window["pre_end"],
    )

    main_df = filter_period(
        df,
        window["main_start"],
        window["main_end"],
    )

    post_df = filter_period(
        df,
        window["post_start"],
        window["post_end"],
    )

    overall_df = filter_period(
        df,
        window["overall_start"],
        window["overall_end"],
    )

    result = {
        "location": TEST_LOCATION["name"],
        "latitude": TEST_LOCATION["latitude"],
        "longitude": TEST_LOCATION["longitude"],

        "season": season,
        "season_year": season_year,

        "window": {
            key: value.isoformat()
            for key, value in window.items()
        },

        "pre_season": summarize_period(
            pre_df,
            columns,
            "pre-season",
        ),

        "main_season": summarize_period(
            main_df,
            columns,
            "main-season",
        ),

        "post_season": summarize_period(
            post_df,
            columns,
            "post-season",
        ),

        "overall": summarize_period(
            overall_df,
            columns,
            "overall",
        ),
    }

    return result


# ============================================================
# PRINT REPORT
# ============================================================

def print_summary(result: dict):

    print()
    print("=" * 70)
    print("AGRONEXUS - SEASONAL WEATHER EVIDENCE")
    print("=" * 70)

    print(
        f"Location : {result['location']}"
    )

    print(
        f"Coordinates : "
        f"{result['latitude']}, "
        f"{result['longitude']}"
    )

    print(
        f"Season : "
        f"{result['season']} "
        f"{result['season_year']}"
    )

    print()
    print("WINDOW")

    for key, value in result["window"].items():
        print(
            f"  {key:15s}: {value}"
        )

    print()

    for section in (
        "pre_season",
        "main_season",
        "post_season",
        "overall",
    ):

        data = result[section]

        print("-" * 70)
        print(
            f"{data['period'].upper()}"
        )
        print("-" * 70)

        for key, value in data.items():

            if key == "period":
                continue

            if isinstance(value, float):
                print(
                    f"{key:35s}: "
                    f"{value:.2f}"
                )

            else:
                print(
                    f"{key:35s}: "
                    f"{value}"
                )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # TEST:
    #
    # Kharif 2025
    #
    # May 2025       = pre-season
    # Jun-Sep 2025   = main season
    # Oct 2025       = post-season
    # --------------------------------------------------------

    season = "kharif"
    season_year = 2025

    window = get_season_window(
        season,
        season_year,
    )

    print()
    print("Season window:")
    print(
        json.dumps(
            {
                key: value.isoformat()
                for key, value in window.items()
            },
            indent=2,
        )
    )

    cache_name = (
        f"agera5_"
        f"{TEST_LOCATION['name'].lower()}_"
        f"{window['overall_start']}_"
        f"{window['overall_end']}.csv"
    )

    output_file = CACHE_DIR / cache_name

    try:

        csv_file = download_agera5(
            latitude=TEST_LOCATION["latitude"],
            longitude=TEST_LOCATION["longitude"],
            start_date=window["overall_start"],
            end_date=window["overall_end"],
            output_file=output_file,
        )

        df = load_agera5_csv(
            csv_file
        )

        columns = identify_weather_columns(
            df
        )

        print()
        print("=" * 70)
        print("IDENTIFIED VARIABLES")
        print("=" * 70)

        for key, value in columns.items():
            print(
                f"{key:25s}: {value}"
            )

        df = normalize_units(
            df,
            columns,
        )

        result = analyze_season(
            df,
            columns,
            season,
            season_year,
        )

        print_summary(
            result
        )

        # ----------------------------------------------------
        # Save JSON report
        # ----------------------------------------------------

        report_file = CACHE_DIR / (
            f"season_report_"
            f"{TEST_LOCATION['name'].lower()}_"
            f"{season}_"
            f"{season_year}.json"
        )

        with open(
            report_file,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                result,
                f,
                indent=2,
            )

        print()
        print("=" * 70)
        print("REPORT SAVED")
        print("=" * 70)

        print(report_file)

    except Exception as exc:

        print()
        print("=" * 70)
        print("AGERA5 DOWNLOAD/PROCESSING FAILED")
        print("=" * 70)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        print()
        print(
            "IMPORTANT:"
        )

        print(
            "If the CDS rejects the request, "
            "do NOT change the variables randomly."
        )

        print(
            "Send me the complete error output "
            "and we will correct the exact CDS "
            "request schema."
        )

        raise


# ============================================================
# CROP RECOMMENDATION INTEGRATION
# ============================================================

def get_weather_features(
    latitude: float,
    longitude: float,
    season: str = "kharif",
    season_year: int = 2025,
) -> dict:
    """
    Return weather evidence in the format expected by
    crop_recommendation.py V1.11.

    Current validation mode:
        - Uses cached AgERA5 data when available.
        - Uses 1 month pre-season + main season + 1 month
          post-season.
        - Seasonal rainfall is the primary water evidence.

    IMPORTANT:
        seasonal_effective_rainfall_mm is currently a simple
        conservative estimate for V1.11 validation:

            effective rainfall = 80% of main-season rainfall

        This is NOT the final scientific effective-rainfall
        model. It will be replaced after multi-year validation.
    """

    # --------------------------------------------------------
    # Build season window
    # --------------------------------------------------------

    window = get_season_window(
        season,
        season_year,
    )

    # --------------------------------------------------------
    # Cache filename
    # --------------------------------------------------------

    location_name = TEST_LOCATION["name"].lower()

    cache_name = (
        f"agera5_"
        f"{location_name}_"
        f"{window['overall_start']}_"
        f"{window['overall_end']}.csv"
    )

    cache_file = CACHE_DIR / cache_name

    # --------------------------------------------------------
    # Use existing AgERA5 cache.
    #
    # If cache does not exist, download it.
    # --------------------------------------------------------

    if cache_file.exists():

        csv_file = cache_file

    else:

        csv_file = download_agera5(
            latitude=latitude,
            longitude=longitude,
            start_date=window["overall_start"],
            end_date=window["overall_end"],
            output_file=cache_file,
        )

    # --------------------------------------------------------
    # Load AgERA5
    # --------------------------------------------------------

    df = load_agera5_csv(
        csv_file
    )

    columns = identify_weather_columns(
        df
    )

    df = normalize_units(
        df,
        columns,
    )

    # --------------------------------------------------------
    # Analyze complete agricultural season
    # --------------------------------------------------------

    result = analyze_season(
        df,
        columns,
        season,
        season_year,
    )

    pre = result["pre_season"]
    main = result["main_season"]
    post = result["post_season"]
    overall = result["overall"]

    # --------------------------------------------------------
    # Main-season rainfall
    #
    # This is the primary rainfall evidence for crop
    # suitability.
    # --------------------------------------------------------

    seasonal_rainfall_mm = float(
        main.get(
            "rainfall_total_mm",
            0.0,
        )
    )

    # --------------------------------------------------------
    # Temporary effective rainfall estimate
    #
    # This is deliberately kept separate from raw rainfall.
    #
    # 80% is a validation placeholder, NOT the final
    # scientific effective-rainfall model.
    # --------------------------------------------------------

    seasonal_effective_rainfall_mm = (
        seasonal_rainfall_mm * 0.80
    )

    # --------------------------------------------------------
    # Main-season ET0
    # --------------------------------------------------------

    seasonal_et0_mm = float(
        main.get(
            "et0_total_mm",
            0.0,
        )
    )

    # --------------------------------------------------------
    # Main-season climate indicators
    # --------------------------------------------------------

    temperature_mean_c = main.get(
        "temperature_mean_c"
    )

    temperature_min_c = main.get(
        "temperature_min_c"
    )

    temperature_max_c = main.get(
        "temperature_max_c"
    )

    humidity_min_pct = main.get(
        "humidity_min_mean_pct"
    )

    humidity_max_pct = main.get(
        "humidity_max_mean_pct"
    )

    vpd_mean_hpa = main.get(
        "vpd_mean_hpa"
    )

    vpd_max_hpa = main.get(
        "vpd_max_hpa"
    )

    # --------------------------------------------------------
    # Return interface expected by crop_recommendation.py
    # --------------------------------------------------------

    return {
        # ----------------------------------------------------
        # Season
        # ----------------------------------------------------

        "season": season,
        "season_year": season_year,

        # ----------------------------------------------------
        # Location
        # ----------------------------------------------------

        "latitude": latitude,
        "longitude": longitude,

        # ----------------------------------------------------
        # Main-season water evidence
        # ----------------------------------------------------

        "seasonal_rainfall_mm": seasonal_rainfall_mm,

        "seasonal_effective_rainfall_mm": (
            seasonal_effective_rainfall_mm
        ),

        "seasonal_et0_mm": seasonal_et0_mm,

        # ----------------------------------------------------
        # Climate evidence
        # ----------------------------------------------------

        "temperature_mean_c": temperature_mean_c,
        "temperature_min_c": temperature_min_c,
        "temperature_max_c": temperature_max_c,

        "humidity_min_pct": humidity_min_pct,
        "humidity_max_pct": humidity_max_pct,

        "vpd_mean_hpa": vpd_mean_hpa,
        "vpd_max_hpa": vpd_max_hpa,

        # ----------------------------------------------------
        # Root-zone water is intentionally NOT estimated here.
        #
        # It is a different concept from seasonal rainfall.
        # V1.11 keeps it separate from crop-cycle water
        # suitability.
        # ----------------------------------------------------

        "estimated_root_zone_water_mm": None,

        # ----------------------------------------------------
        # Detailed seasonal evidence
        # ----------------------------------------------------

        "weather_evidence": {
            "pre_season": pre,
            "main_season": main,
            "post_season": post,
            "overall": overall,
        },

        # ----------------------------------------------------
        # Data provenance
        # ----------------------------------------------------

        "source": "AgERA5 v2 / Copernicus CDS",
        "cache_file": str(csv_file),
        "evidence_type": "historical_seasonal",
    }

if __name__ == "__main__":
    main()