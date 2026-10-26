import pandas as pd
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]

input_file = PROJECT / "data" / "features" / \
    "tirumala_modeling_dataset.csv"

output_file = PROJECT / "data" / "features" / \
    "tirumala_insar_monitoring_component.csv"


df = pd.read_csv(input_file)

print("Input observations:", len(df))


# Absolute LOS displacement
# This represents displacement magnitude in the
# radar line-of-sight direction.

los_abs = df["los_abs_m"]

minimum = los_abs.min()
maximum = los_abs.max()

df["los_magnitude_norm"] = (
    (los_abs - minimum) /
    (maximum - minimum)
)


# Relative monitoring classes
df["insar_monitoring_class"] = pd.qcut(
    df["los_magnitude_norm"],
    q=3,
    labels=[
        "Low",
        "Moderate",
        "High"
    ],
    duplicates="drop"
)


result = df[
    [
        "row",
        "col",
        "los_disp_m",
        "los_abs_m",
        "correlation",
        "los_magnitude_norm",
        "insar_monitoring_class"
    ]
].copy()


output_file.parent.mkdir(
    parents=True,
    exist_ok=True
)

result.to_csv(
    output_file,
    index=False
)


print("\nINSAR MONITORING COMPONENT")
print("==========================")

print(
    f"LOS displacement range: "
    f"{df['los_disp_m'].min():.6f} to "
    f"{df['los_disp_m'].max():.6f} m"
)

print(
    f"LOS magnitude range: "
    f"{minimum:.6f} to {maximum:.6f} m"
)

print("\nMonitoring classes:")
print(
    result["insar_monitoring_class"]
    .value_counts()
    .sort_index()
)

print("\nOutput:")
print(output_file)