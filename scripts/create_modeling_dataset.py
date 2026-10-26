import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

# --------------------------------------------------
# Input files
# --------------------------------------------------

insar_file = PROJECT / "data" / "features" / \
    "tirumala_insar_pair_analysis.csv"

rainfall_file = PROJECT / "data" / "processed" / "rainfall" / "tirumala" / \
    "tirumala_rainfall_features_20260801_20260829.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_modeling_dataset.csv"

# --------------------------------------------------
# Read datasets
# --------------------------------------------------

insar = pd.read_csv(insar_file)
rain = pd.read_csv(rainfall_file)

print("InSAR observations:", len(insar))
print("Rainfall records:", len(rain))

print("\nRainfall columns:")
print(list(rain.columns))

# --------------------------------------------------
# Convert date
# --------------------------------------------------

rain["date"] = pd.to_datetime(rain["date"])

start_date = pd.to_datetime(
    insar["insar_start_date"].iloc[0]
)

end_date = pd.to_datetime(
    insar["insar_end_date"].iloc[0]
)

print("\nInSAR period:")
print("Start:", start_date.date())
print("End:", end_date.date())

# --------------------------------------------------
# Calculate strictly antecedent rainfall
#
# Acquisition date itself is excluded.
# --------------------------------------------------

def get_antecedent(date, days):

    end = date - pd.Timedelta(days=1)

    start = date - pd.Timedelta(days=days)

    subset = rain[
        (rain["date"] >= start) &
        (rain["date"] <= end)
    ]

    return subset["rainfall_mean_mm"].sum()


def get_max_daily(date, days):

    end = date - pd.Timedelta(days=1)

    start = date - pd.Timedelta(days=days)

    subset = rain[
        (rain["date"] >= start) &
        (rain["date"] <= end)
    ]

    return subset["rainfall_mean_mm"].max()


rainfall_values = {}

for label, date in [
    ("start", start_date),
    ("end", end_date)
]:

    for days in [3, 7, 14]:

        rainfall_values[
            f"rain_{days}d_before_{label}_mm"
        ] = get_antecedent(date, days)

        rainfall_values[
            f"max_daily_rain_{days}d_before_{label}_mm"
        ] = get_max_daily(date, days)

# --------------------------------------------------
# Display rainfall
# --------------------------------------------------

print("\nAntecedent rainfall:")

for key, value in rainfall_values.items():
    print(f"{key}: {value:.2f} mm")

# --------------------------------------------------
# Spatial InSAR + terrain features
# --------------------------------------------------

features = [
    "row",
    "col",
    "elevation_m",
    "slope_deg",
    "correlation",
    "los_disp_m",
    "los_abs_m"
]

model = insar[features].copy()

# --------------------------------------------------
# Add rainfall variables
# --------------------------------------------------

for key, value in rainfall_values.items():
    model[key] = value

# --------------------------------------------------
# Acquisition dates
# --------------------------------------------------

model["insar_start_date"] = start_date.strftime(
    "%Y-%m-%d"
)

model["insar_end_date"] = end_date.strftime(
    "%Y-%m-%d"
)

# --------------------------------------------------
# Quality indicators
# --------------------------------------------------

model["terrain_available"] = (
    model["elevation_m"].notna()
    & model["slope_deg"].notna()
)

model["insar_quality_pass"] = (
    model["correlation"] >= 0.5
)

model["los_available"] = (
    model["los_disp_m"].notna()
)

# --------------------------------------------------
# Save
# --------------------------------------------------

output_file.parent.mkdir(
    parents=True,
    exist_ok=True
)

model.to_csv(
    output_file,
    index=False
)

# --------------------------------------------------
# Summary
# --------------------------------------------------

print("\nMODELING DATASET")
print("================")

print("Rows:", len(model))
print("Columns:", len(model.columns))

print(
    "Terrain-valid observations:",
    int(model["terrain_available"].sum())
)

print(
    "InSAR-quality-pass observations:",
    int(model["insar_quality_pass"].sum())
)

print(
    "LOS-available observations:",
    int(model["los_available"].sum())
)

print("\nMissing values:")
print(model.isna().sum())

print("\nOutput:")
print(output_file)