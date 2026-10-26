import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_modeling_dataset.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_rainfall_trigger_component.csv"

df = pd.read_csv(input_file)

print("Input observations:", len(df))

# The rainfall values are event-level variables.
# They are therefore constant across the spatial
# observations for each InSAR pair.

rainfall_data = {
    "insar_date": [
        "2026-08-17",
        "2026-08-29"
    ],
    "rain_3d_before_mm": [
        2.30,
        0.20
    ],
    "rain_7d_before_mm": [
        6.70,
        9.30
    ],
    "rain_14d_before_mm": [
        20.00,
        12.70
    ]
}

rain = pd.DataFrame(rainfall_data)

print("\nRAINFALL TRIGGER INFORMATION")
print("============================")
print(rain.to_string(index=False))

# Save event-level rainfall component
output_file.parent.mkdir(
    parents=True,
    exist_ok=True
)

rain.to_csv(
    output_file,
    index=False
)

print("\nOutput:")
print(output_file)