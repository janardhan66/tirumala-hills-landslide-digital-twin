import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

spatial_file = PROJECT / "data" / "features" / "tirumala_agent_evidence.csv"
temporal_file = PROJECT / "data" / "features" / "tirumala_temporal_agent_evidence.csv"

spatial = pd.read_csv(spatial_file)
temporal = pd.read_csv(temporal_file)

print("\nAGENT SPATIAL ALIGNMENT DIAGNOSTIC")
print("==================================")

print("\nSpatial dataset")
print("----------------")
print("Rows:", len(spatial))
print("Columns:", len(spatial.columns))
print("Row range:", spatial["row"].min(), "to", spatial["row"].max())
print("Col range:", spatial["col"].min(), "to", spatial["col"].max())

print("\nTemporal dataset")
print("-----------------")
print("Rows:", len(temporal))
print("Columns:", len(temporal.columns))
print("Row range:", temporal["row"].min(), "to", temporal["row"].max())
print("Col range:", temporal["col"].min(), "to", temporal["col"].max())

# Unique coordinate pairs
spatial_keys = set(zip(spatial["row"], spatial["col"]))
temporal_keys = set(zip(temporal["row"], temporal["col"]))

common = spatial_keys & temporal_keys

print("\nCoordinate-key comparison")
print("--------------------------")
print("Unique spatial keys :", len(spatial_keys))
print("Unique temporal keys:", len(temporal_keys))
print("Common keys         :", len(common))
print("Temporal-only keys  :", len(temporal_keys - spatial_keys))
print("Spatial-only keys   :", len(spatial_keys - temporal_keys))

# Duplicate keys
spatial_duplicates = spatial.duplicated(["row", "col"]).sum()
temporal_duplicates = temporal.duplicated(["row", "col"]).sum()

print("\nDuplicate coordinate pairs")
print("--------------------------")
print("Spatial duplicates :", spatial_duplicates)
print("Temporal duplicates:", temporal_duplicates)

# Show examples of unmatched temporal coordinates
unmatched = list(temporal_keys - spatial_keys)

print("\nExample temporal-only coordinates:")
for item in sorted(unmatched)[:20]:
    print(item)

print("\nDiagnostic complete.")