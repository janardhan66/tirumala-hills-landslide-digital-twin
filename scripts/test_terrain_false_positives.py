
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs" / "validation_analysis" / "terrain_per_patch.csv"
OUTPUT = ROOT / "outputs" / "validation_analysis" / "terrain_statistical_tests.csv"

df = pd.read_csv(INPUT)

empty = df[df["group"].isin([
    "Empty GT - false positive",
    "Empty GT - no prediction"
])].copy()

false_group = "Empty GT - false positive"
correct_group = "Empty GT - no prediction"

results = []

for feature in ["slope", "dem"]:
    feature_df = empty[empty["feature"] == feature].copy()

    false_values = feature_df.loc[
        feature_df["group"] == false_group, "patch_mean"
    ].dropna().to_numpy(dtype=float)

    correct_values = feature_df.loc[
        feature_df["group"] == correct_group, "patch_mean"
    ].dropna().to_numpy(dtype=float)

    if len(false_values) == 0 or len(correct_values) == 0:
        raise ValueError(f"Missing data for {feature}")

    test = mannwhitneyu(
        false_values,
        correct_values,
        alternative="two-sided"
    )

    # Cliff's delta using ranks; avoids covariance calculations.
    combined = np.concatenate([false_values, correct_values])
    ranks = pd.Series(combined).rank(method="average").to_numpy()

    n1 = len(false_values)
    n2 = len(correct_values)
    u_stat = ranks[:n1].sum() - n1 * (n1 + 1) / 2
    superiority = u_stat / (n1 * n2)
    cliffs_delta = 2 * superiority - 1

    # Spearman correlation calculated as Pearson correlation
    # of average ranks, without calling scipy.stats.spearmanr.
    x = feature_df["patch_mean"].astype(float).rank(method="average")
    y = feature_df["pred_pixels_at_0.5"].astype(float).rank(method="average")

    # Compute correlation using centered vectors and dot products.
    xr = x.to_numpy() - x.mean()
    yr = y.to_numpy() - y.mean()
    denominator = np.sqrt(np.dot(xr, xr) * np.dot(yr, yr))

    rho = (
        float(np.dot(xr, yr) / denominator)
        if denominator > 0 else np.nan
    )

    results.append({
        "feature": feature,
        "false_positive_patches": n1,
        "correct_empty_patches": n2,
        "false_positive_mean": false_values.mean(),
        "correct_empty_mean": correct_values.mean(),
        "mean_difference": false_values.mean() - correct_values.mean(),
        "mann_whitney_U": float(test.statistic),
        "p_value": float(test.pvalue),
        "cliffs_delta": float(cliffs_delta),
        "spearman_rho_predicted_pixels": rho,
    })

result_df = pd.DataFrame(results)

# Holm correction for the two Mann-Whitney tests.
p_values = result_df["p_value"].to_numpy()
order = np.argsort(p_values)
adjusted = np.empty(len(p_values))
running_max = 0.0

for rank, index in enumerate(order):
    adjusted_p = min(1.0, (len(p_values) - rank) * p_values[index])
    running_max = max(running_max, adjusted_p)
    adjusted[index] = running_max

result_df["holm_adjusted_p_value"] = adjusted

result_df.to_csv(OUTPUT, index=False)

print("\nTerrain statistical tests:")
print(result_df.round(5).to_string(index=False))
print(f"\nSaved results to: {OUTPUT}")
