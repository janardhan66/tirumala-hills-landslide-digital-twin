# Phase 7 – Checkpoint 1: Random Forest and AI/ML Risk Audit

**Audit date:** 23 November 2026  
**Audit status:** PASS WITH LIMITATIONS  
**Scope:** Inspection, read-only model/dataset analysis, evidence tracing, test execution and reporting. No model training or implementation changes were made.

## 1. Executive summary

The repository contains two separate Random Forest artifacts and several Landslide4Sense-derived datasets, but neither trained Random Forest is the source of the Tirumala dashboard's current spatial risk map.

- Patch-level training code in `src/models/train_random_forest.py` trains a `sklearn.ensemble.RandomForestClassifier` on Landslide4Sense patch pixels using only `slope` and `elevation`.
- `models/landslide_random_forest_v2.joblib` is the artifact associated with that patch-level training.
- `models/landslide_random_forest.joblib` is a 100-tree model with the same two features. A separate script applies it to Moghalrajpuram slope/elevation data.
- The canonical Tirumala dashboard calls `src/risk_assessment.py::build_spatial_risk`, which creates a relative empirical evidence index from:
  - slope percentile (40%);
  - terrain evidence flag (25%);
  - InSAR evidence flag (20%);
  - temporal evidence flag (15%);
- Rainfall is intentionally excluded from the per-cell empirical formula.
- No Random Forest output was found in `observation_snapshots`, risk history, Cesium exports or the canonical Tirumala dashboard.
- The patch-level model is external-benchmark-derived and has not been validated for Tirumala. It is not scientifically validated for local landslide risk assessment.

## 2. Existing AI/ML architecture

### Machine-learning components

| Component | Location | Actual role |
|---|---|---|
| Patch dataset extractor | `src/features/extract_landslide4sense_rf_data.py` | Randomly extracts Landslide4Sense pixels for slope/elevation RF training |
| RF training | `src/models/train_random_forest.py` | Trains and saves a patch-level RF using v3 CSV |
| RF model v2 | `models/landslide_random_forest_v2.joblib` | 200-tree balanced patch-level Landslide4Sense classifier |
| Earlier RF model | `models/landslide_random_forest.joblib` | 100-tree unbalanced RF for Moghalrajpuram susceptibility |
| Moghalrajpuram prediction | `src/models/predict_moghalrajpuram_susceptibility.py` | Produces Moghalrajpuram probabilities and classes |
| Moghalrajpuram evidence risk | `src/models/calculate_moghalrajpuram_risk.py` | Separate 50% terrain / 50% absolute LOS evidence classification |
| Tirumala empirical risk | `src/risk_assessment.py` | Weighted relative evidence index used by the Tirumala dashboard |
| U-Net demonstration | `models/landslide_unet_14channel_*` | Separate 14-channel Landslide4Sense benchmark segmentation workflow |

The U-Net is not Random Forest evidence and is not integrated as Tirumala RF predictions.

## 3. Random Forest model details

### v2 patch-level model

- Exact path: `C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin\models\landslide_random_forest_v2.joblib`
- Format: joblib-pickled scikit-learn estimator
- Algorithm: `sklearn.ensemble.RandomForestClassifier`
- Training script: `src/models/train_random_forest.py`
- Dataset: `data/features/landslide4sense_rf_training_v3.csv`
- Features: exactly `["slope", "elevation"]`
- Target: `label`
- Classes: `[0, 1]`
- Number of features: 2
- Serialization: `joblib.dump`
- Hyperparameters:
  - `n_estimators=200`
  - `random_state=42`
  - `n_jobs=-1`
  - `class_weight="balanced"`
  - default Gini criterion
  - default maximum depth
  - default maximum features (`sqrt`)
  - default minimum split/leaf values
- Preprocessing: direct numeric slope/elevation values; no scaler or normalizer found
- Missing-value handling: no explicit handling in training code; source CSV contains no missing values
- Saved feature importances:
  - slope: 0.16940565450939088
  - elevation: 0.8305943454906091

**Serialization compatibility:** Loading the artifact produced a scikit-learn warning because the model was serialized with estimator code from scikit-learn 1.9.0 while the active environment is 1.7.2. Predictions and properties were readable, but this version mismatch should be recorded as a reproducibility risk.

### Earlier/Moghalrajpuram model

- Exact path: `C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin\models\landslide_random_forest.joblib`
- Algorithm: `sklearn.ensemble.RandomForestClassifier`
- Prediction script: `src/models/predict_moghalrajpuram_susceptibility.py`
- Input: `data/features/moghalrajpuram_spatial_features_clean.csv`
- Input rows: 2,305
- Features: exactly `["slope", "elevation"]`, renamed internally to `["slope", "elevation"]`
- Target: UNKNOWN. No training script for this artifact was identified.
- Classes: `[0, 1]`
- Number of features: 2
- Hyperparameters visible from serialization:
  - `n_estimators=100`
  - `random_state=42`
  - `n_jobs=-1`
  - `class_weight=None`
- Saved feature importances:
  - slope: 0.12065879661401599
  - elevation: 0.8793412033859841
- Training dataset for this model: UNKNOWN
- Training samples: UNKNOWN
- Training split: UNKNOWN
- Evaluation metrics: UNKNOWN

## 4. Training dataset details

### Landslide4Sense v3

- Path: `data/features/landslide4sense_rf_training_v3.csv`
- Shape: 190,644 rows × 4 columns
- Columns: `patch_id`, `slope`, `elevation`, `label`
- Unique patches: 3,799
- Class distribution:
  - class 0: 98,774
  - class 1: 91,870
- Missing values: none
- Exact duplicate rows: 12,388
- Source: Landslide4Sense H5 image/mask patches under `data/raw/landslide4sense/TrainData`
- Image files: 3,799
- Mask files: 3,799
- Patch shape: image `(128, 128, 14)`, mask `(128, 128)`
- Extracted features:
  - slope = H5 channel index 12
  - elevation = H5 channel index 13
- Labels: `mask == 1` is landslide/positive; `mask == 0` is non-landslide/negative
- Geography: external Landslide4Sense benchmark training data, not Tirumala training data
- Coordinate reference system: UNKNOWN for individual patch pixels
- Spatial resolution: patch is 128 × 128, but a ground-cell resolution/CRS is not established

### Older RF datasets

| File | Shape | Patches | Class distribution | Duplicate rows |
|---|---:|---:|---|---:|
| `landslide4sense_rf_training.csv` | 200,000 × 3 | UNKNOWN | 100,000 / 100,000 | 123,219 |
| `landslide4sense_rf_training_v2.csv` | 200,000 × 4 | 203 | 100,000 / 100,000 | 92,270 |
| `landslide4sense_rf_training_v3.csv` | 190,644 × 4 | 3,799 | 98,774 / 91,870 | 12,388 |

The v1/v2 datasets do not establish Tirumala ground truth.

## 5. Complete feature inventory

### Features actually used by the Random Forest

| Feature | Used by RF? | Source | Resolution | CRS | Preprocessing | Missing treatment | Tirumala availability | Temporal alignment |
|---|---|---|---|---|---|---|---|---|
| Slope | YES | Landslide4Sense H5 channel 12 for training; renamed Moghalrajpuram `slope_deg` for prediction | 128×128 patch pixels; Moghalrajpuram row data is georeferenced in separate files | Training patch CRS UNKNOWN; Moghalrajpuram uses UTM metadata and WGS84 longitude/latitude columns | Direct numeric value | No explicit RF imputation; H5 CSV generation produced no missing v3 values | Tirumala slope raster exists at 80 m | Not temporally aligned to the RF training labels |
| Elevation | YES | Landslide4Sense H5 channel 13 for training; Moghalrajpuram `elevation_m` for prediction | 128×128 patch pixels / Moghalrajpuram pixel rows | Training patch CRS UNKNOWN; Moghalrajpuram uses UTM/WGS84 columns | Direct numeric value | No explicit RF imputation; H5 CSV generation produced no missing v3 values | Tirumala DEM raster exists at 80 m | Not temporally aligned to the RF training labels |

### Features that exist but are not used by either RF

| Feature | RF used? | Evidence |
|---|---|---|
| Aspect | NO | Not selected in training or Moghalrajpuram prediction code |
| InSAR LOS displacement | NO | RF feature arrays contain only slope/elevation |
| InSAR coherence | NO | RF feature arrays contain only slope/elevation |
| Rainfall | NO | No rainfall column in RF training/prediction arrays |
| Distance to GSI historical locations | NO | Not used by RF training or prediction |
| Terrain evidence flag | NO | Used only by the separate Tirumala empirical formula |
| Temporal evidence flag | NO | Used only by the separate Tirumala empirical formula |

### Tirumala raster inventory

- Grid: 69 × 110 = 7,590 cells
- Canonical spatial CRS: EPSG:32644
- Canonical resolution: 80 m
- DEM valid cells: 4,083
- InSAR quality-valid cells for the November pair: 5,034
- Rainfall: 29 study-area aggregate records
- GSI points: 15 approximate map-derived locations

## 6. Training and validation audit

### Reproduced v2/v3 evaluation

The existing v2 artifact was evaluated against the v3 data using the same patch-grouped split strategy and seed documented in `train_random_forest.py`. No model fitting was performed.

- Training patches: 3,039
- Testing patches: 760
- Patch overlap: 0
- Training samples: 151,706
- Testing samples: 38,938
- Test class distribution: 19,760 class 0; 19,178 class 1
- Accuracy: 0.5626637218141661
- Balanced accuracy: 0.5623651906093479
- Precision: 0.5575984990619137
- Recall: 0.5423923245385337
- F1: 0.5498903074035895
- Confusion matrix: `[[11507, 8253], [8776, 10402]]`

These metrics reproduce for the current serialized v2 artifact on the declared v3 test split.

### Leakage and overlap concerns

- Patch IDs are separated between train/test in the script, so no patch-ID overlap occurs.
- Duplicate pixel feature combinations/rows remain across or within the v3 dataset.
- Because the dataset has no geographic coordinates, geographic overlap cannot be established.
- Random patch-level holdout does not replace independent spatial or geography-grouped validation.
- Terrain and mask label extraction comes from the same H5 patch. This is valid for patch segmentation benchmarking, but it is not a separate Tirumala ground-truth validation.
- Class counts are mildly imbalanced in v3 and are handled by `class_weight="balanced"`.

### Moghalrajpuram model

- 2,305 prediction/input rows
- No missing values in slope/elevation
- Zero exact duplicate rows
- Training data and metrics for the serialized model are UNKNOWN
- It is a separate project area and is not evidence of Tirumala model performance.

## 7. Prediction pipeline

### Landslide4Sense RF pipeline

1. Read Landslide4Sense H5 image/mask pairs.
2. Extract channel 12 as slope and channel 13 as elevation.
3. Randomly sample landslide and non-landslide pixels.
4. Split by unique patch ID using a 20% test fraction and seed 42.
5. Fit `RandomForestClassifier`.
6. Predict class labels on test pixels.
7. Save the estimator as a joblib artifact.

No separate pixel probability export from v2 to SQLite or Cesium was found.

### Moghalrajpuram RF pipeline

1. Load `landslide_random_forest.joblib`.
2. Read Moghalrajpuram spatial features.
3. Submit `slope_deg`, `elevation_m` as RF `slope`, `elevation`.
4. Generate `predict_proba(...)[,1]`.
5. Assign Low/Moderate/High/Very High at thresholds 0.25, 0.50 and 0.75.
6. Save `moghalrajpuram_susceptibility.csv`.

It is not present in the canonical Tirumala dashboard or Cesium integration.

### Tirumala empirical pipeline

1. Load canonical spatial evidence records.
2. Rank slope percentile within the current study-area observations.
3. Score terrain evidence as 0/100.
4. Score InSAR LOS/coherence evidence as 0/100.
5. Score temporal evidence as 0/100.
6. Renormalize available weights.
7. Produce `risk_score` and Low/Medium/High category.
8. Store observation snapshots and risk history in SQLite.
9. Export empirical risk zones and status to Cesium.

This is not Random Forest output.

## 8. Risk classification methodology

The empirical formula is:

- slope: 40%;
- terrain: 25%;
- InSAR: 20%;
- temporal: 15%.

Classification thresholds:

- Low: `<33.3333`
- Medium: `>=33.3333` and `<66.6667`
- High: `>=66.6667`

Missing factors are excluded and the available weights are renormalized. This output is explicitly relative evidence, not a calibrated landslide probability.

The separate Moghalrajpuram RF probabilities use 0.25/0.50/0.75 thresholds but are not calibrated Tirumala probabilities.

## 9. Dashboard and Cesium integration

- Canonical Streamlit dashboard: `dashboard/app.py`
- It imports `build_spatial_risk` and uses the empirical formula.
- Dashboard risk maps use empirical `risk_score` and `risk_category`, not RF `predict_proba`.
- Tirumala SQLite observations and risk history contain empirical evidence fields and scores.
- Cesium imports and exports empirical risk raster/zone assets.
- The RF models are not stored in the Tirumala observation or risk-history tables.
- Cesium is therefore integrated with empirical Tirumala evidence, not machine-learning RF predictions.

## 10. Scientific validity assessment for Tirumala

### Findings

- The patch RF is trained on Landslide4Sense benchmark patches, not Tirumala ground truth.
- The second RF is used for Moghalrajpuram, not Tirumala.
- No independent Tirumala RF validation data or local labels were identified.
- No Tirumala prediction output from RF was identified.
- Tirumala Slope and DEM exist, but matching each external RF patch feature to the Tirumala 69 × 110 grid has not been established.
- The RF omits InSAR LOS/coherence, rainfall and GSI distance.
- The RF output is binary susceptibility plus probability in its Moghalrajpuram usage, not the current Tirumala empirical categories.
- Reproduced patch metrics are moderate and cannot support local operational claims.
- Tirumala empirical risk is not a calibrated probability.

**Scientific conclusion:** Neither Random Forest is scientifically validated for Tirumala Hills.

## 11. Explainability assessment

### Currently available

- Serialized RF feature importances are available in both artifacts.
- The training script prints feature importances.
- The empirical formula provides per-factor availability and factor component explanations.
- Cesium/dashboard display data-quality and limitation text.

### Missing

- No SHAP implementation found.
- No per-prediction RF probability/contribution export found.
- No persistent RF confidence/uncertainty report found.
- No local RF calibration or conformal uncertainty found.
- No geographically structured RF cross-validation found.
- No Random Forest predictions in Tirumala SQLite.

### Recommended future explainability

For a future Tirumala RF, use permutation importance only with spatially blocked validation plus SHAP summary and per-cell SHAP values after a local, geographically representative model is established. Preserve quality flags and report out-of-domain status for InSAR NoData and other missing features.

## 12. Data-quality issues and blockers

- One live November InSAR pair is quality-validated.
- Cumulative displacement and velocity are not established.
- 7,590 grid cells exist; DEM valid cells are 4,083.
- 5,034 InSAR-quality-valid cells exist for the November pair.
- Rainfall rollups remain unresolved and rainfall is aggregate context only.
- U-Net is Landslide4Sense benchmark-derived and locally unvalidated.
- RF training data is external benchmark data.
- No Tirumala RF ground-truth labels were identified.
- RF patch coordinates/CRS are unknown.
- V3 has 12,388 duplicate full rows.
- The Moghalrajpuram training dataset and metrics are unknown.
- Serialized RFs use scikit-learn 1.9.0 while the active environment reports 1.7.2.
- RF artifact usage is disconnected from Tirumala risk storage and Cesium.

## 13. Recommended implementation plan for Checkpoint 2

Checkpoint 2 should require explicit approval and should begin only after scope approval:

1. Decide whether the objective is a new Tirumala RF or only modernization of the existing benchmark RF.
2. Acquire or digitize independent Tirumala ground-truth landslide/non-landslide labels.
3. Define a 69×110-cell predictor table with EPSG:32644 alignment.
4. Verify local DEM, slope, aspect, InSAR LOS/coherence, rainfall and GSI-distance availability.
5. Establish missing-value and NoData semantics.
6. Use spatial or patch-blocked train/test separation rather than random row or patch holdout only.
7. Pre-register hyperparameters and random seed.
8. Add reproducible class metrics, confusion matrix, ROC/PR curves and calibration analysis.
9. Quantify spatially blocked cross-validation and independent Tirumala test performance.
10. Add SHAP/permutation explainability and confidence or out-of-domain reporting.
11. Integrate model outputs separately from the empirical risk index.
12. Preserve existing empirical scores and database/Cesium behavior unless separately approved.

## 14. Files inspected

- `src/models/train_random_forest.py`
- `src/features/extract_landslide4sense_rf_data.py`
- `src/models/predict_moghalrajpuram_susceptibility.py`
- `src/models/calculate_moghalrajpuram_risk.py`
- `src/risk_assessment.py`
- `src/features/risk_engine.py`
- `src/models/evaluate_full_validation.py`
- `scripts/extract_features.py`
- `dashboard/app.py`
- `config/settings.py`
- `tests/test_risk_engine.py`
- `tests/test_emergency_final_integration.py`
- `tests/test_backend_integration.py`
- Model artifacts: `models/landslide_random_forest.joblib`, `models/landslide_random_forest_v2.joblib`
- RF datasets: `data/features/landslide4sense_rf_training*.csv`
- Moghalrajpuram datasets: `data/features/moghalrajpuram_*.csv`

## 15. Database backup details

- Backup path: `C:\Users\yarra\OneDrive\Desktop\landslide_digital_twin\database\backups\monitoring_phase7_checkpoint1_20261123T042431Z.db`
- SQLite integrity check: `ok`
- Observation snapshots: 45,554
- Production database was not modified by the audit.

## 16. Tests and verification results

- Relevant Phase 7 tests: **23 passed**, 8 warnings.
- Full `tests/` suite: **150 passed**, 6 warnings, 6 subtests passed.
- The full suite has no failures.
- No source code was modified to satisfy tests.
- No synthetic observations were inserted.
- No historical predictions or risk scores were overwritten.
- No paid HyP3 job or large satellite download was initiated.
