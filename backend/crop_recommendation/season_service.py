from datetime import date
import calendar


# ============================================================
# AGRONEXUS AUTOMATIC AGRICULTURAL SEASON
# ============================================================
#
# Kharif : June - September
# Rabi   : October - January
# Zaid   : February - May
#
# Season is determined automatically from the current date.
# The farmer does NOT enter season manually.
# ============================================================


SEASONS = {
    "Kharif": {
        "start_month": 6,
        "end_month": 9,
    },
    "Rabi": {
        "start_month": 10,
        "end_month": 1,
    },
    "Zaid": {
        "start_month": 2,
        "end_month": 5,
    },
}


def get_current_season(
    current_date=None
):
    """
    Determine the current agricultural season.

    If current_date is omitted, today's system date is used.
    """

    if current_date is None:
        current_date = date.today()

    month = current_date.month

    if 6 <= month <= 9:
        return "Kharif"

    if month == 10 or month == 11 or month == 12 or month == 1:
        return "Rabi"

    return "Zaid"


def get_season_info(
    current_date=None
):
    """
    Return complete information about the current season.
    """

    if current_date is None:
        current_date = date.today()

    season = get_current_season(
        current_date
    )

    config = SEASONS[
        season
    ]

    start_month = config[
        "start_month"
    ]

    end_month = config[
        "end_month"
    ]

    return {
        "season": season,
        "season_source": "automatic",
        "analysis_period_months": 4,
        "start_month": start_month,
        "end_month": end_month,
        "current_date": current_date.isoformat(),
    }


def get_season_months(
    season
):
    """
    Return the four calendar months belonging
    to the agricultural season.
    """

    season = str(
        season
    ).strip().casefold()

    if season == "kharif":
        return [6, 7, 8, 9]

    if season == "rabi":
        return [10, 11, 12, 1]

    if season == "zaid":
        return [2, 3, 4, 5]

    raise ValueError(
        f"Unknown agricultural season: {season}"
    )


if __name__ == "__main__":

    info = get_season_info()

    print("=" * 60)
    print("AGRONEXUS AUTOMATIC SEASON")
    print("=" * 60)

    print(
        "Current date:",
        info["current_date"]
    )

    print(
        "Season:",
        info["season"]
    )

    print(
        "Source:",
        info["season_source"]
    )

    print(
        "Analysis period:",
        info["analysis_period_months"],
        "months"
    )

    print(
        "Months:",
        get_season_months(
            info["season"]
        )
    )