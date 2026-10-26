import os
import pandas as pd


# =========================================================
# INPUT FILES
# =========================================================

SPATIAL_FILE = (
    r"data\features"
    r"\tirumala_insar_terrain_features_gsi_aoi.csv"
)

RAINFALL_FILE = (
    r"data\processed\rainfall\tirumala"
    r"\tirumala_daily_rainfall_20260801_20260829.csv"
)


# =========================================================
# OUTPUT FILE
# =========================================================

OUTPUT_FILE = (
    r"data\features"
    r"\tirumala_insar_pair_analysis.csv"
)


# =========================================================
# READ DATA
# =========================================================

spatial = pd.read_csv(SPATIAL_FILE)
rainfall = pd.read_csv(RAINFALL_FILE)

rainfall["date"] = pd.to_datetime(rainfall["date"])

rainfall = rainfall.sort_values("date").reset_index(drop=True)


# =========================================================
# CHECK SPATIAL DATA
# =========================================================

required_spatial = [
    "row",
    "col",
    "elevation_m",
    "slope_deg",
    "correlation",
    "los_disp_m",
    "los_abs_m"
]

missing = [
    col for col in required_spatial
    if col not in spatial.columns
]

if missing:
    raise RuntimeError(
        f"Missing spatial columns: {missing}"
    )


# =========================================================
# RAINFALL HELPER
# =========================================================

def rainfall_before(date, days):
    """
    Calculate rainfall strictly BEFORE the given date.

    Example:
    date = 2026-08-17
    days = 3

    Uses Aug 14, 15 and 16.
    """

    end_date = date - pd.Timedelta(days=1)
    start_date = date - pd.Timedelta(days=days)

    values = rainfall[
        (rainfall["date"] >= start_date)
        & (rainfall["date"] <= end_date)
    ]["rainfall_mean_mm"]

    if len(values) != days:
        raise RuntimeError(
            f"Insufficient rainfall data before {date.date()} "
            f"for {days}-day window."
        )

    return {
        "total": values.sum(),
        "max_daily": values.max(),
        "mean_daily": values.mean()
    }


# =========================================================
# SENTINEL-1 ACQUISITION DATES
# =========================================================

date1 = pd.Timestamp("2026-08-17")
date2 = pd.Timestamp("2026-08-29")


# =========================================================
# CALCULATE ANTECEDENT RAINFALL
# =========================================================

r1_3 = rainfall_before(date1, 3)
r1_7 = rainfall_before(date1, 7)
r1_14 = rainfall_before(date1, 14)

r2_3 = rainfall_before(date2, 3)
r2_7 = rainfall_before(date2, 7)
r2_14 = rainfall_before(date2, 14)


# =========================================================
# PRINT RAINFALL SUMMARY
# =========================================================

print("\n========================================")
print("ANTECEDENT RAINFALL")
print("========================================")

print("\nBefore 17 August 2026:")
print(f"3-day total  : {r1_3['total']:.1f} mm")
print(f"7-day total  : {r1_7['total']:.1f} mm")
print(f"14-day total : {r1_14['total']:.1f} mm")

print("\nBefore 29 August 2026:")
print(f"3-day total  : {r2_3['total']:.1f} mm")
print(f"7-day total  : {r2_7['total']:.1f} mm")
print(f"14-day total : {r2_14['total']:.1f} mm")


# =========================================================
# ADD PAIR-LEVEL FEATURES TO EVERY SPATIAL OBSERVATION
# =========================================================

result = spatial.copy()


# Observation dates
result["insar_start_date"] = date1.strftime("%Y-%m-%d")
result["insar_end_date"] = date2.strftime("%Y-%m-%d")


# ---------------------------------------------------------
# Rainfall before first acquisition
# ---------------------------------------------------------

result["rainfall_before_start_3day_mm"] = r1_3["total"]
result["rainfall_before_start_7day_mm"] = r1_7["total"]
result["rainfall_before_start_14day_mm"] = r1_14["total"]

result["max_daily_rain_before_start_3day_mm"] = r1_3["max_daily"]
result["max_daily_rain_before_start_7day_mm"] = r1_7["max_daily"]
result["max_daily_rain_before_start_14day_mm"] = r1_14["max_daily"]


# ---------------------------------------------------------
# Rainfall before second acquisition
# ---------------------------------------------------------

result["rainfall_before_end_3day_mm"] = r2_3["total"]
result["rainfall_before_end_7day_mm"] = r2_7["total"]
result["rainfall_before_end_14day_mm"] = r2_14["total"]

result["max_daily_rain_before_end_3day_mm"] = r2_3["max_daily"]
result["max_daily_rain_before_end_7day_mm"] = r2_7["max_daily"]
result["max_daily_rain_before_end_14day_mm"] = r2_14["max_daily"]


# =========================================================
# RAINFALL CHANGE
# =========================================================

result["rainfall_change_3day_mm"] = (
    r2_3["total"] - r1_3["total"]
)

result["rainfall_change_7day_mm"] = (
    r2_7["total"] - r1_7["total"]
)

result["rainfall_change_14day_mm"] = (
    r2_14["total"] - r1_14["total"]
)


# =========================================================
# SAVE
# =========================================================

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True
)

result.to_csv(
    OUTPUT_FILE,
    index=False
)


# =========================================================
# FINAL SUMMARY
# =========================================================

print("\n========================================")
print("INSAR PAIR DATASET CREATED")
print("========================================")

print(f"Rows: {len(result)}")
print(f"Columns: {len(result.columns)}")

print("\nOutput:")
print(OUTPUT_FILE)

print("\nFirst five rows:")
print(result.head().to_string(index=False))

print("\nMissing values:")
print(result.isna().sum().sum())