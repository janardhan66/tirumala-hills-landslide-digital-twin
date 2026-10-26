import os
import pandas as pd

OUT_DIR = r"data\processed\landslide_inventory"
os.makedirs(OUT_DIR, exist_ok=True)

data = [
    {
        "chainage_start_km": 0,
        "chainage_end_km": 2,
        "landslide_count": 1,
        "evidence_source": "GSI Tirumala Hills Report 43764"
    },
    {
        "chainage_start_km": 2,
        "chainage_end_km": 6,
        "landslide_count": 6,
        "evidence_source": "GSI Tirumala Hills Report 43764"
    },
    {
        "chainage_start_km": 6,
        "chainage_end_km": 8,
        "landslide_count": 7,
        "evidence_source": "GSI Tirumala Hills Report 43764"
    },
    {
        "chainage_start_km": 8,
        "chainage_end_km": 10,
        "landslide_count": 15,
        "evidence_source": "GSI Tirumala Hills Report 43764"
    },
    {
        "chainage_start_km": 10,
        "chainage_end_km": 16,
        "landslide_count": 18,
        "evidence_source": "GSI Tirumala Hills Report 43764"
    },
    {
        "chainage_start_km": 16,
        "chainage_end_km": 18,
        "landslide_count": 1,
        "evidence_source": "GSI Tirumala Hills Report 43764"
    }
]

df = pd.DataFrame(data)

out_file = os.path.join(
    OUT_DIR,
    "gsi_tirumala_landslide_inventory.csv"
)

df.to_csv(out_file, index=False)

print("=" * 70)
print("GSI TIRUMALA LANDSLIDE INVENTORY")
print("=" * 70)

print(df.to_string(index=False))

print()
print("Total landslide incidences:",
      df["landslide_count"].sum())

print("Saved:", out_file)