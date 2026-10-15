import pandas as pd
import os

# ============================================================
# FILE PATHS
# ============================================================

INPUT_FILE = r"C:\Users\srikar\OneDrive\Desktop\all projects\AgroNexus-AI\data\processed\South_India_Soil_Nutrient_Analysis.csv"

OUTPUT_FILE = r"C:\Users\srikar\OneDrive\Desktop\all projects\AgroNexus-AI\data\processed\South_India_Soil_Profiles.csv"

SUMMARY_FILE = r"C:\Users\srikar\OneDrive\Desktop\all projects\AgroNexus-AI\data\processed\South_India_Soil_Coverage.csv"


# ============================================================
# LOCATION COLUMNS
# ============================================================

LOCATION_COLUMNS = [
    "state_name",
    "district_name",
    "block_name",
    "village_name",
    "year"
]


# ============================================================
# READ DATA
# ============================================================

print("Reading South India soil data...")

df = pd.read_csv(INPUT_FILE)

print(f"Total rows loaded: {len(df):,}")


# ============================================================
# SHOW BASIC INFORMATION
# ============================================================

print("\nColumns:")
print(df.columns.tolist())

print("\nNutrient names:")
print(df["nutrient_name"].value_counts())


# ============================================================
# CREATE NUTRIENT STATUS COLUMNS
# ============================================================

# We DON'T convert the values into fake numeric N/P/K values.
#
# Instead, we preserve the nutrient category counts:
#
# Nitrogen → Low / Medium / High
# Phosphorus → Low / Medium / High
# Potassium → Low / Medium / High
# pH → Acidic / Neutral / Alkaline


# ============================================================
# PIVOT DATA
# ============================================================

print("\nCreating location-level profiles...")

profile = df.pivot_table(
    index=LOCATION_COLUMNS,
    columns=["nutrient_name", "nutrient_level"],
    values="value",
    aggfunc="sum",
    fill_value=0
)


# ============================================================
# FLATTEN COLUMN NAMES
# ============================================================

profile.columns = [
    f"{nutrient}_{level}"
    .replace(" ", "_")
    .replace("-", "_")
    .lower()
    for nutrient, level in profile.columns
]


profile = profile.reset_index()


# ============================================================
# EXPECTED CATEGORIES
# ============================================================

expected_columns = [
    "nitrogen_low",
    "nitrogen_medium",
    "nitrogen_high",

    "phosphorus_low",
    "phosphorus_medium",
    "phosphorus_high",

    "potassium_low",
    "potassium_medium",
    "potassium_high",

    "soil_ph_acidic",
    "soil_ph_neutral",
    "soil_ph_alkaline"
]


# Add missing columns if a category doesn't exist
for column in expected_columns:

    if column not in profile.columns:
        profile[column] = 0


# ============================================================
# DETERMINE DOMINANT SOIL STATUS
# ============================================================

def get_status(row, columns):

    values = row[columns]

    if values.sum() == 0:
        return "Unknown"

    return values.idxmax().split("_")[-1].title()


profile["N_status"] = profile.apply(
    lambda row: get_status(
        row,
        [
            "nitrogen_low",
            "nitrogen_medium",
            "nitrogen_high"
        ]
    ),
    axis=1
)


profile["P_status"] = profile.apply(
    lambda row: get_status(
        row,
        [
            "phosphorus_low",
            "phosphorus_medium",
            "phosphorus_high"
        ]
    ),
    axis=1
)


profile["K_status"] = profile.apply(
    lambda row: get_status(
        row,
        [
            "potassium_low",
            "potassium_medium",
            "potassium_high"
        ]
    ),
    axis=1
)


profile["pH_status"] = profile.apply(
    lambda row: get_status(
        row,
        [
            "soil_ph_acidic",
            "soil_ph_neutral",
            "soil_ph_alkaline"
        ]
    ),
    axis=1
)


# ============================================================
# CALCULATE CONFIDENCE
# ============================================================

def calculate_confidence(row, columns):

    total = row[columns].sum()

    if total == 0:
        return 0

    return round(row[columns].max() / total, 4)


profile["N_confidence"] = profile.apply(
    lambda row: calculate_confidence(
        row,
        [
            "nitrogen_low",
            "nitrogen_medium",
            "nitrogen_high"
        ]
    ),
    axis=1
)


profile["P_confidence"] = profile.apply(
    lambda row: calculate_confidence(
        row,
        [
            "phosphorus_low",
            "phosphorus_medium",
            "phosphorus_high"
        ]
    ),
    axis=1
)


profile["K_confidence"] = profile.apply(
    lambda row: calculate_confidence(
        row,
        [
            "potassium_low",
            "potassium_medium",
            "potassium_high"
        ]
    ),
    axis=1
)


profile["pH_confidence"] = profile.apply(
    lambda row: calculate_confidence(
        row,
        [
            "soil_ph_acidic",
            "soil_ph_neutral",
            "soil_ph_alkaline"
        ]
    ),
    axis=1
)


# ============================================================
# CHECK COMPLETE PROFILES
# ============================================================

profile["complete_soil_profile"] = (
    (profile["N_status"] != "Unknown")
    &
    (profile["P_status"] != "Unknown")
    &
    (profile["K_status"] != "Unknown")
    &
    (profile["pH_status"] != "Unknown")
)


# ============================================================
# SAVE CLEAN PROFILE DATASET
# ============================================================

profile.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# CREATE STATE COVERAGE SUMMARY
# ============================================================

summary = []

for state, group in profile.groupby("state_name"):

    total_profiles = len(group)

    complete_profiles = group["complete_soil_profile"].sum()

    summary.append({

        "state": state,

        "total_profiles": total_profiles,

        "complete_profiles": complete_profiles,

        "incomplete_profiles":
            total_profiles - complete_profiles,

        "districts":
            group["district_name"].nunique(),

        "blocks":
            group["block_name"].nunique(),

        "villages":
            group["village_name"].nunique(),

        "years":
            ", ".join(
                sorted(
                    group["year"]
                    .dropna()
                    .astype(str)
                    .unique()
                )
            ),

        "complete_profile_percentage":
            round(
                complete_profiles /
                total_profiles * 100,
                2
            )
            if total_profiles > 0
            else 0
    })


summary_df = pd.DataFrame(summary)


# ============================================================
# SAVE SUMMARY
# ============================================================

summary_df.to_csv(
    SUMMARY_FILE,
    index=False
)


# ============================================================
# FINAL REPORT
# ============================================================

print("\n==============================================")
print("SOIL PROFILE PROCESSING COMPLETE")
print("==============================================")

print(f"\nInput rows:")
print(f"{len(df):,}")

print("\nLocation-level profiles:")
print(f"{len(profile):,}")

print("\nComplete N + P + K + pH profiles:")
print(
    f"{profile['complete_soil_profile'].sum():,}"
)

print("\nState coverage:")
print(
    summary_df.to_string(index=False)
)

print("\n----------------------------------------------")

print("Profile file:")
print(OUTPUT_FILE)

print("\nCoverage file:")
print(SUMMARY_FILE)

print("\n==============================================")