import os
import pandas as pd


# =========================================================
# PATHS
# =========================================================

INPUT_FILE = (
    r"data\processed\rainfall\tirumala"
    r"\tirumala_daily_rainfall_20260801_20260829.csv"
)

OUTPUT_FILE = (
    r"data\processed\rainfall\tirumala"
    r"\tirumala_rainfall_features_20260801_20260829.csv"
)


# =========================================================
# READ DAILY RAINFALL
# =========================================================

df = pd.read_csv(INPUT_FILE)

df["date"] = pd.to_datetime(df["date"])

df = df.sort_values("date").reset_index(drop=True)


# =========================================================
# CHECK DATA
# =========================================================

expected_dates = pd.date_range(
    "2026-08-01",
    "2026-08-29",
    freq="D"
)

if len(df) != 29:
    raise RuntimeError(
        f"Expected 29 rainfall records, found {len(df)}."
    )

if not df["date"].equals(
    pd.Series(expected_dates, name="date")
):
    raise RuntimeError(
        "Rainfall dates are not continuous from "
        "2026-08-01 to 2026-08-29."
    )


# =========================================================
# RAINFALL FEATURES
# =========================================================

rain = df["rainfall_mean_mm"]

# Rainfall accumulated over the current day and
# previous N-1 days.
df["rainfall_3day_mm"] = (
    rain.rolling(window=3, min_periods=3).sum()
)

df["rainfall_7day_mm"] = (
    rain.rolling(window=7, min_periods=7).sum()
)

df["rainfall_14day_mm"] = (
    rain.rolling(window=14, min_periods=14).sum()
)


# Maximum single-day rainfall within each window

df["max_daily_rainfall_3day_mm"] = (
    rain.rolling(window=3, min_periods=3).max()
)

df["max_daily_rainfall_7day_mm"] = (
    rain.rolling(window=7, min_periods=7).max()
)

df["max_daily_rainfall_14day_mm"] = (
    rain.rolling(window=14, min_periods=14).max()
)


# =========================================================
# SAVE
# =========================================================

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True
)

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# =========================================================
# DISPLAY
# =========================================================

print("\n========================================")
print("Rainfall feature calculation completed.")
print("========================================")

print("\nOutput:")
print(OUTPUT_FILE)

print("\nNumber of records:")
print(len(df))

print("\nRainfall features:")
print(
    df[
        [
            "date",
            "rainfall_mean_mm",
            "rainfall_3day_mm",
            "rainfall_7day_mm",
            "rainfall_14day_mm",
            "max_daily_rainfall_3day_mm",
            "max_daily_rainfall_7day_mm",
            "max_daily_rainfall_14day_mm",
        ]
    ].to_string(index=False)
)


# =========================================================
# IMPORTANT DATES
# =========================================================

print("\n========================================")
print("17 AUGUST 2026 - SENTINEL-1 ACQUISITION")
print("========================================")

row = df[df["date"] == "2026-08-17"]

print(
    row[
        [
            "date",
            "rainfall_mean_mm",
            "rainfall_3day_mm",
            "rainfall_7day_mm",
            "rainfall_14day_mm",
            "max_daily_rainfall_3day_mm",
            "max_daily_rainfall_7day_mm",
            "max_daily_rainfall_14day_mm",
        ]
    ].to_string(index=False)
)


print("\n========================================")
print("25 AUGUST 2026")
print("========================================")

row = df[df["date"] == "2026-08-25"]

print(
    row[
        [
            "date",
            "rainfall_mean_mm",
            "rainfall_3day_mm",
            "rainfall_7day_mm",
            "rainfall_14day_mm",
            "max_daily_rainfall_3day_mm",
            "max_daily_rainfall_7day_mm",
            "max_daily_rainfall_14day_mm",
        ]
    ].to_string(index=False)
)