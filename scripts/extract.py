import pandas as pd
import os

# ============================================================
# FILE PATHS
# ============================================================

INPUT_FILE = r"C:\Users\srikar\OneDrive\Desktop\all projects\AgroNexus-AI\data\soil-nutrient-analysis.csv"

OUTPUT_FILE = r"C:\Users\srikar\OneDrive\Desktop\all projects\AgroNexus-AI\data\processed\South_India_Soil_Nutrient_Analysis.csv"


# ============================================================
# FIVE SOUTH INDIAN STATES
# ============================================================

STATES = {
    "Andhra Pradesh",
    "Karnataka",
    "Kerala",
    "Tamil Nadu",
    "Telangana"
}


# ============================================================
# NUTRIENTS WE NEED
# ============================================================

NUTRIENTS = {
    "Nitrogen",
    "Phosphorus",
    "Potassium",
    "Soil Ph"
}


# ============================================================
# CHUNK SIZE
# ============================================================

CHUNK_SIZE = 500_000


# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True
)


# ============================================================
# PROCESS CSV
# ============================================================

first_chunk = True
total_rows = 0

for chunk_number, chunk in enumerate(
    pd.read_csv(
        INPUT_FILE,
        chunksize=CHUNK_SIZE
    ),
    start=1
):

    # Keep only our five states
    # AND only N, P, K and pH records

    filtered = chunk[
        chunk["state_name"].isin(STATES)
        &
        chunk["nutrient_name"].isin(NUTRIENTS)
    ]

    if not filtered.empty:

        filtered.to_csv(
            OUTPUT_FILE,
            mode="w" if first_chunk else "a",
            header=first_chunk,
            index=False
        )

        first_chunk = False

        total_rows += len(filtered)

    print(
        f"Chunk {chunk_number} | "
        f"Rows saved: {total_rows:,}"
    )


# ============================================================
# FINISHED
# ============================================================

print("\n========================================")
print("PROCESSING COMPLETE")
print("========================================")

print(f"Total rows: {total_rows:,}")

print(f"Output file:")
print(OUTPUT_FILE)