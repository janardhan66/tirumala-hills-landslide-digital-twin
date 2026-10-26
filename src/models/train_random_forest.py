import os
import joblib
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    balanced_accuracy_score
)

INPUT_FILE = "data/features/landslide4sense_rf_training_v3.csv"
MODEL_FILE = "models/landslide_random_forest_v2.joblib"

print("=" * 70)
print("PATCH-LEVEL RANDOM FOREST TRAINING")
print("=" * 70)

# ---------------------------------------------------------
# Load dataset
# ---------------------------------------------------------

df = pd.read_csv(INPUT_FILE)

print("Dataset shape:", df.shape)
print("Unique patches:", df["patch_id"].nunique())

# ---------------------------------------------------------
# Create patch-level train/test split
# ---------------------------------------------------------

patch_ids = df["patch_id"].unique()

train_patches, test_patches = train_test_split(
    patch_ids,
    test_size=0.20,
    random_state=42
)

train_df = df[df["patch_id"].isin(train_patches)].copy()
test_df = df[df["patch_id"].isin(test_patches)].copy()

print()
print("Training patches:", len(train_patches))
print("Testing patches:", len(test_patches))

print("Training samples:", len(train_df))
print("Testing samples:", len(test_df))

# ---------------------------------------------------------
# Features and labels
# ---------------------------------------------------------

X_train = train_df[["slope", "elevation"]]
y_train = train_df["label"]

X_test = test_df[["slope", "elevation"]]
y_test = test_df["label"]

print()
print("Training class distribution:")
print(y_train.value_counts())

print()
print("Testing class distribution:")
print(y_test.value_counts())

# ---------------------------------------------------------
# Random Forest
# ---------------------------------------------------------

model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    n_jobs=-1,
    class_weight="balanced"
)

print()
print("Training Random Forest...")

model.fit(X_train, y_train)

print("Training completed.")

# ---------------------------------------------------------
# Prediction
# ---------------------------------------------------------

y_pred = model.predict(X_test)

# ---------------------------------------------------------
# Metrics
# ---------------------------------------------------------

accuracy = accuracy_score(y_test, y_pred)
balanced_accuracy = balanced_accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred, zero_division=0)
recall = recall_score(y_test, y_pred, zero_division=0)
f1 = f1_score(y_test, y_pred, zero_division=0)

cm = confusion_matrix(y_test, y_pred)

print()
print("=" * 70)
print("MODEL PERFORMANCE")
print("=" * 70)

print(f"Accuracy          : {accuracy:.4f}")
print(f"Balanced Accuracy : {balanced_accuracy:.4f}")
print(f"Precision         : {precision:.4f}")
print(f"Recall            : {recall:.4f}")
print(f"F1-score          : {f1:.4f}")

print()
print("Confusion Matrix:")
print(cm)

print()
print("Classification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        zero_division=0
    )
)

# ---------------------------------------------------------
# Feature importance
# ---------------------------------------------------------

print("Feature Importance:")

for feature, importance in zip(
    X_train.columns,
    model.feature_importances_
):
    print(f"{feature}: {importance:.4f}")

# ---------------------------------------------------------
# Verify patch separation
# ---------------------------------------------------------

overlap = set(train_patches).intersection(
    set(test_patches)
)

print()
print("Patch overlap between train/test:", len(overlap))

# ---------------------------------------------------------
# Save model
# ---------------------------------------------------------

os.makedirs(
    os.path.dirname(MODEL_FILE),
    exist_ok=True
)

joblib.dump(
    model,
    MODEL_FILE
)

print()
print("MODEL SAVED")
print("Saved:", MODEL_FILE)

print("=" * 70)