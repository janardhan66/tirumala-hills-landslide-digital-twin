from pathlib import Path
import pandas as pd
import numpy as np

root = Path(".")
reports_path = root / "data/raw/landslide_inventory/coolr_landslide_reports.csv"
gsi_path = root / "data/processed/landslide_inventory/gsi_tirumala_landslide_inventory.csv"

reports = pd.read_csv(reports_path, low_memory=False)
gsi = pd.read_csv(gsi_path)

print("GSI columns:", gsi.columns.tolist())
print("\nGSI reference records:")
print(gsi.to_string(index=False))

# Convert report coordinates to numeric values.
reports["Latitude"] = pd.to_numeric(reports["Latitude"], errors="coerce")
reports["Longitude"] = pd.to_numeric(reports["Longitude"], errors="coerce")

# Approximate Tirumala reference coordinate from the historical report.
ref_lat, ref_lon = 13.653, 79.344

valid = reports.dropna(subset=["Latitude", "Longitude"]).copy()

# Haversine distance in kilometres.
lat1 = np.radians(ref_lat)
lat2 = np.radians(valid["Latitude"].to_numpy())
dlat = lat2 - lat1
dlon = np.radians(valid["Longitude"].to_numpy()) - np.radians(ref_lon)

a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
valid["Distance_km_from_Tirumala_reference"] = (
    6371 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
)

nearby = valid[valid["Distance_km_from_Tirumala_reference"] <= 25].copy()
nearby = nearby.sort_values("Distance_km_from_Tirumala_reference")

columns = [
    c for c in [
        "Event Title", "Location Description", "Event Date",
        "Latitude", "Longitude", "Distance_km_from_Tirumala_reference",
        "Location Accuracy", "Landslide Category", "Landslide Trigger",
        "Link to Information Source", "Citation"
    ] if c in nearby.columns
]

print("\nCOOLR reports within 25 km of the reference coordinate:", len(nearby))
if len(nearby):
    print(nearby[columns].head(30).to_string(index=False))

out = Path("outputs/validation_analysis/coolr_reports_near_tirumala.csv")
out.parent.mkdir(parents=True, exist_ok=True)
nearby[columns].to_csv(out, index=False)
print("\nSaved:", out)
