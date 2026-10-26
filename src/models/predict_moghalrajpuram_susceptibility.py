import os
import joblib
import pandas as pd

MODEL_FILE = "models/landslide_random_forest.joblib"

INPUT_FILE = "data/features/moghalrajpuram_spatial_features_clean.csv"

OUTPUT_FILE = "data/features/moghalrajpuram_susceptibility.csv"

# --------------------------------------------------
# 1. Load trained model
# --------------------------------------------------

model = joblib.load(MODEL_FILE)

print("=" * 70)
print("MOGHALRAJPURAM LANDSLIDE SUSCEPTIBILITY")
print("=" * 70)

print("Model loaded successfully.")

# --------------------------------------------------
# 2. Load Moghalrajpuram spatial features
# --------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print("Input rows:", len(df))

# --------------------------------------------------
# 3. Select model features
# --------------------------------------------------

X = df[["slope_deg", "elevation_m"]].copy()

X.columns = ["slope", "elevation"]

# --------------------------------------------------
# 4. Predict susceptibility probability
# --------------------------------------------------

probability = model.predict_proba(X)[:, 1]

df["susceptibility_probability"] = probability

# --------------------------------------------------
# 5. Create susceptibility classes
# --------------------------------------------------

def classify_risk(probability):

    if probability < 0.25:
        return "Low"

    elif probability < 0.50:
        return "Moderate"

    elif probability < 0.75:
        return "High"

    else:
        return "Very High"


df["susceptibility_class"] = (
    df["susceptibility_probability"]
    .apply(classify_risk)
)

# --------------------------------------------------
# 6. Save result
# --------------------------------------------------

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True
)

df.to_csv(
    OUTPUT_FILE,
    index=False
)

# --------------------------------------------------
# 7. Print summary
# --------------------------------------------------

print()
print("Susceptibility statistics:")

print(
    df["susceptibility_probability"].describe()
)

print()
print("Susceptibility class distribution:")

print(
    df["susceptibility_class"].value_counts()
)

print()
print("Output rows:", len(df))

print()
print("Saved:", OUTPUT_FILE)

print("=" * 70)