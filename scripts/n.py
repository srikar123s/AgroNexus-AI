import os
import pandas as pd

import os

PROJECT_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

BACKEND_DATA_DIR = os.path.join(
    PROJECT_DIR,
    "backend",
    "data"
)

INPUT_FILE = os.path.join(
    BACKEND_DATA_DIR,
    "South_India_Soil_Nutrient_Analysis.csv"
)

OUTPUT_FILE = os.path.join(
    BACKEND_DATA_DIR,
    "agronexus_village_soil_master_v4.csv"
)

DETAIL_FILE = os.path.join(
    BACKEND_DATA_DIR,
    "agronexus_village_soil_level_aggregates_v4.csv"
)
# ============================================================
# AgroNexus - Village Soil Master V4 Builder
# ============================================================
#
# INPUT:
#   South_India_Soil_Nutrient_Analysis.csv
#
# OUTPUT:
#   agronexus_village_soil_master_v4.csv
#
# The source has village-level rows:
# state -> district -> block -> village -> nutrient -> level -> value
#
# IMPORTANT:
# "value" is treated as the amount/count associated with a
# nutrient-level category. We do NOT interpret it as an exact
# N/P/K concentration.
#
# The dominant nutrient level is therefore determined from
# summed category values, not by row count.
# ============================================================



REQUIRED_COLUMNS = [
    "year",
    "state_name",
    "state_code",
    "district_name",
    "district_code",
    "block_name",
    "block_code",
    "village_name",
    "village_code",
    "nutrient_type",
    "nutrient_name",
    "nutrient_level",
    "value",
]


NUTRIENT_MAP = {
    "nitrogen": "N",
    "phosphorus": "P",
    "potassium": "K",
    "soil ph": "pH",
    "ph": "pH",
}


QUALITY_RANK = {
    "Unavailable": 0,
    "Weak": 1,
    "Ambiguous": 1,
    "Low confidence": 2,
    "Usable": 3,
}


def normalize(value):

    if pd.isna(value):
        return ""

    return str(
        value
    ).strip().casefold()


def classify_quality(
    total_value,
    nonzero_rows,
    total_rows,
    dominance_pct,
    number_of_winners,
):
    """
    Quality is intentionally conservative.

    Unavailable:
        no positive source value.

    Weak:
        very little non-zero evidence.

    Ambiguous:
        exact tie between category totals.

    Low confidence:
        evidence exists but no category dominates strongly.

    Usable:
        sufficient evidence with a clear dominant category.
    """

    if total_value <= 0:
        return "Unavailable"

    if nonzero_rows == 0:
        return "Unavailable"

    nonzero_pct = (
        nonzero_rows / total_rows * 100
        if total_rows
        else 0
    )

    if nonzero_pct < 10:
        return "Weak"

    if number_of_winners > 1:
        return "Ambiguous"

    if dominance_pct < 40:
        return "Low confidence"

    return "Usable"


def main():

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_FILE}\n\n"
            "Put South_India_Soil_Nutrient_Analysis.csv "
            "inside backend/data/"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # Normalize fields
    # --------------------------------------------------------

    df["nutrient_key"] = (
        df["nutrient_name"]
        .map(normalize)
        .map(NUTRIENT_MAP)
    )

    df = df[
        df["nutrient_key"].notna()
    ].copy()

    df["value"] = pd.to_numeric(
        df["value"],
        errors="coerce"
    ).fillna(0)

    df["nutrient_level_norm"] = (
        df["nutrient_level"]
        .map(normalize)
    )

    # --------------------------------------------------------
    # Village identity
    # --------------------------------------------------------

    village_keys = [
        "state_name",
        "state_code",
        "district_name",
        "district_code",
        "block_name",
        "block_code",
        "village_name",
        "village_code",
    ]

    # --------------------------------------------------------
    # Aggregate category values
    # --------------------------------------------------------

    detail = (
        df.groupby(
            village_keys
            + [
                "nutrient_key",
                "nutrient_level_norm",
            ],
            dropna=False,
        )
        .agg(
            value_sum=(
                "value",
                "sum",
            ),
            row_count=(
                "value",
                "size",
            ),
            nonzero_count=(
                "value",
                lambda s:
                    int(
                        (s != 0).sum()
                    ),
            ),
        )
        .reset_index()
    )

    # --------------------------------------------------------
    # Determine village nutrient profile
    # --------------------------------------------------------

    profile_rows = []

    profile_keys = (
        village_keys
        + ["nutrient_key"]
    )

    for key, group in detail.groupby(
        profile_keys,
        dropna=False,
    ):

        group = group.copy()

        total_value = float(
            group["value_sum"].sum()
        )

        max_value = float(
            group["value_sum"].max()
        )

        winners = group[
            group["value_sum"]
            == max_value
        ]["nutrient_level_norm"].tolist()

        total_rows = int(
            group["row_count"].sum()
        )

        nonzero_rows = int(
            group["nonzero_count"].sum()
        )

        dominance_pct = (
            max_value
            / total_value
            * 100
            if total_value > 0
            else 0
        )

        nonzero_pct = (
            nonzero_rows
            / total_rows
            * 100
            if total_rows > 0
            else 0
        )

        quality = classify_quality(
            total_value,
            nonzero_rows,
            total_rows,
            dominance_pct,
            len(winners),
        )

        dominant_level = (
            winners[0].title()
            if len(winners) == 1
            else "Tie"
        )

        row = dict(
            zip(
                profile_keys,
                key,
            )
        )

        row.update({

            "dominant_level":
                dominant_level,

            "dominant_value_sum":
                round(
                    max_value,
                    4,
                ),

            "total_value_sum":
                round(
                    total_value,
                    4,
                ),

            "dominance_pct":
                round(
                    dominance_pct,
                    2,
                ),

            "row_count":
                total_rows,

            "nonzero_count":
                nonzero_rows,

            "nonzero_pct":
                round(
                    nonzero_pct,
                    2,
                ),

            "data_quality":
                quality,
        })

        profile_rows.append(
            row
        )

    profile = pd.DataFrame(
        profile_rows
    )

    # --------------------------------------------------------
    # Pivot N/P/K/pH into one village row
    # --------------------------------------------------------

    master = (
        profile[village_keys]
        .drop_duplicates()
        .copy()
    )

    for nutrient, prefix in [
        ("N", "N"),
        ("P", "P"),
        ("K", "K"),
        ("pH", "pH"),
    ]:

        subset = profile[
            profile["nutrient_key"]
            == nutrient
        ][
            village_keys
            + [
                "dominant_level",
                "dominant_value_sum",
                "total_value_sum",
                "dominance_pct",
                "row_count",
                "nonzero_count",
                "nonzero_pct",
                "data_quality",
            ]
        ].copy()

        subset = subset.rename(
            columns={

                "dominant_level":
                    f"{prefix}_level",

                "dominant_value_sum":
                    f"{prefix}_dominant_value_sum",

                "total_value_sum":
                    f"{prefix}_total_value_sum",

                "dominance_pct":
                    f"{prefix}_dominance_pct",

                "row_count":
                    f"{prefix}_row_count",

                "nonzero_count":
                    f"{prefix}_nonzero_count",

                "nonzero_pct":
                    f"{prefix}_nonzero_pct",

                "data_quality":
                    f"{prefix}_data_quality",
            }
        )

        master = master.merge(
            subset,
            on=village_keys,
            how="left",
        )

    # --------------------------------------------------------
    # Overall quality
    # --------------------------------------------------------

    def overall_quality(row):

        qualities = [
            row.get("N_data_quality"),
            row.get("P_data_quality"),
            row.get("K_data_quality"),
            row.get("pH_data_quality"),
        ]

        ranks = [
            QUALITY_RANK.get(
                quality,
                0,
            )
            for quality in qualities
        ]

        minimum = min(
            ranks
        ) if ranks else 0

        if minimum >= 3:
            return "Good"

        if minimum >= 2:
            return "Moderate"

        if minimum >= 1:
            return "Caution"

        return "Poor"

    master[
        "overall_soil_data_quality"
    ] = master.apply(
        overall_quality,
        axis=1,
    )

    # --------------------------------------------------------
    # Coverage fields
    # --------------------------------------------------------

    master[
        "complete_NPK_pH_profile"
    ] = (
        master[
            [
                "N_level",
                "P_level",
                "K_level",
                "pH_level",
            ]
        ]
        .notna()
        .all(axis=1)
    )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    master = master.sort_values(
        [
            "state_name",
            "district_name",
            "block_name",
            "village_name",
        ]
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    os.makedirs(
        os.path.dirname(
            OUTPUT_FILE
        ),
        exist_ok=True,
    )

    master.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    detail.to_csv(
        DETAIL_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    print("=" * 70)
    print("AGRONEXUS VILLAGE SOIL MASTER V4")
    print("=" * 70)

    print(
        "Source rows:",
        len(df),
    )

    print(
        "Unique villages:",
        len(master),
    )

    print(
        "Unique districts:",
        master[
            "district_code"
        ].nunique(),
    )

    print(
        "Unique blocks:",
        master[
            "block_code"
        ].nunique(),
    )

    print(
        "\nOverall quality:"
    )

    print(
        master[
            "overall_soil_data_quality"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print(
        "\nComplete NPK+pH profiles:",
        int(
            master[
                "complete_NPK_pH_profile"
            ].sum()
        ),
    )

    print(
        "\nN quality:"
    )

    print(
        master[
            "N_data_quality"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print(
        "\nP quality:"
    )

    print(
        master[
            "P_data_quality"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print(
        "\nK quality:"
    )

    print(
        master[
            "K_data_quality"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print(
        "\npH quality:"
    )

    print(
        master[
            "pH_data_quality"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    # --------------------------------------------------------
    # Wayanad sample
    # --------------------------------------------------------

    wayanad = master[
        (
            master[
                "state_name"
            ]
            .astype(str)
            .str.casefold()
            == "kerala"
        )
        &
        (
            master[
                "district_name"
            ]
            .astype(str)
            .str.casefold()
            == "wayanad"
        )
    ]

    print(
        "\nWayanad villages:",
        len(wayanad),
    )

    if not wayanad.empty:

        print(
            wayanad[
                [
                    "block_name",
                    "village_name",
                    "village_code",
                    "N_level",
                    "P_level",
                    "K_level",
                    "pH_level",
                    "overall_soil_data_quality",
                ]
            ]
            .head(20)
            .to_string(
                index=False
            )
        )

    print(
        "\nOUTPUT:"
    )

    print(
        OUTPUT_FILE
    )

    print(
        DETAIL_FILE
    )


if __name__ == "__main__":
    main()
