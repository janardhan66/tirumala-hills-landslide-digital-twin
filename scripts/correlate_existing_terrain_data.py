
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "outputs/validation_analysis/terrain_per_patch.csv"
OUTPUT = ROOT / "outputs/validation_analysis/terrain_correlations_existing.csv"


def rank_values(values):
    """Average ranks for ties, without calling correlation functions."""
    return pd.Series(values).rank(method="average").to_numpy(dtype=float)


def manual_spearman(x, y):
    """Spearman correlation using explicit rank calculations."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]

    if len(x) < 3:
        return np.nan

    rx = rank_values(x)
    ry = rank_values(y)

    # Avoid numpy.corrcoef, pandas.Series.corr, and numpy.cov.
    dx = rx - sum(rx) / len(rx)
    dy = ry - sum(ry) / len(ry)

    numerator = sum(float(a) * float(b) for a, b in zip(dx, dy))
    sum_x2 = sum(float(a) * float(a) for a in dx)
    sum_y2 = sum(float(b) * float(b) for b in dy)

    denominator = (sum_x2 * sum_y2) ** 0.5
    if denominator == 0:
        return np.nan

    return numerator / denominator


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT}")

    df = pd.read_csv(INPUT)

    required = {
        "sample_id", "group", "feature", "patch_mean",
        "patch_median", "patch_p90", "gt_pixels",
        "pred_pixels_at_0.5",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    # Pivot terrain statistics so each patch has slope and DEM columns.
    wide = df.pivot(
        index=["sample_id", "group", "gt_pixels", "pred_pixels_at_0.5"],
        columns="feature",
        values=["patch_mean", "patch_median", "patch_p90"],
    ).reset_index()

    wide.columns = [
        "_".join(str(part) for part in col if str(part) != "")
        if isinstance(col, tuple) else str(col)
        for col in wide.columns
    ]

    # Select patches whose ground-truth mask is empty.
    empty = wide[wide["gt_pixels"] == 0].copy()
    target = "pred_pixels_at_0.5"

    features = [
        "patch_mean_slope",
        "patch_median_slope",
        "patch_p90_slope",
        "patch_mean_dem",
        "patch_median_dem",
        "patch_p90_dem",
    ]

    rows = []

    for feature in features:
        if feature not in empty.columns:
            print(f"Skipping missing feature: {feature}")
            continue

        subset = empty[[feature, target]].dropna()
        rho = manual_spearman(
            subset[feature].to_numpy(),
            subset[target].to_numpy(),
        )

        rows.append({
            "terrain_feature": feature,
            "empty_gt_patch_count": len(empty),
            "patches_used": len(subset),
            "spearman_rho_with_false_positive_pixels": rho,
        })

    results = pd.DataFrame(rows)

    if not results.empty:
        results["absolute_rho"] = results[
            "spearman_rho_with_false_positive_pixels"
        ].abs()
        results = results.sort_values(
            "absolute_rho", ascending=False, na_position="last"
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT, index=False)

    print("\n=== TERRAIN CORRELATIONS ===")
    print(results.to_string(
        index=False, float_format=lambda value: f"{value:.4f}"
    ))
    print(f"\nSaved to: {OUTPUT}")


if __name__ == "__main__":
    main()
