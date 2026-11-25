import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.backend_integration import (
    build_actual_alert_payload,
    build_risk_explanation,
    get_acquisition_history,
    get_pair_history,
    validate_rasters,
)
from src.data.db import DatabaseManager
from src.risk_assessment import build_spatial_risk


class TestBackendRiskIntegration(unittest.TestCase):
    def test_missing_factors_are_excluded_not_zeroed(self):
        frame = pd.DataFrame({
            "cell_id": ["A"],
            "slope_deg": [20.0],
            "terrain_high_evidence": [None],
            "insar_high_evidence": [None],
            "temporal_evidence_flag": [None],
        })
        scored, _ = build_spatial_risk(frame)
        self.assertEqual(scored.loc[0, "risk_evidence_coverage"], 40.0)

    def test_existing_formula_weights_are_preserved(self):
        from src.risk_assessment import WEIGHTS
        self.assertEqual(
            WEIGHTS,
            {
                "slope_component": 0.40,
                "terrain_component": 0.25,
                "insar_component": 0.20,
                "temporal_component": 0.15,
            },
        )


class TestBackendDatabaseIntegration(unittest.TestCase):
    def test_database_history_is_readable(self):
        from src.data.db import get_db
        db = get_db()
        acquisitions = get_acquisition_history(db)
        pairs = get_pair_history(db)
        self.assertGreaterEqual(len(acquisitions), 1)
        self.assertGreaterEqual(len(pairs), 3)
        live = next(
            (pair for pair in pairs if pair["pair_id"] == "PAIR_20261109_20261121"),
            None,
        )
        self.assertIsNotNone(live)
        self.assertEqual(live["hyp3_job_id"], "3889d809-88a3-4a93-89a5-258821932737")

    def test_risk_explanation_is_not_calibrated(self):
        from src.data.db import get_db
        payload = build_risk_explanation(get_db(), limit=10)
        self.assertEqual(payload["calibration_status"], "NOT_CALIBRATED")
        self.assertIn("Missing factors are excluded", " ".join(payload["limitations"]))
        self.assertIn("No cumulative displacement", " ".join(payload["limitations"]))

    def test_alert_payload_uses_database_and_not_external_delivery(self):
        from src.data.db import get_db
        payload = build_actual_alert_payload(get_db())
        self.assertIn("observation_date", payload)
        self.assertEqual(payload["delivery_status"], "NOT_TESTED_EXTERNAL_DELIVERY")
        self.assertIsInstance(payload["actual_database_alert_records"], list)

    def test_real_rasters_align_and_preserve_nodata(self):
        result = validate_rasters()
        self.assertTrue(result["valid"])
        self.assertIn("insar_los", result["datasets"])
        self.assertIn("insar_coherence", result["datasets"])
        for dataset in result["datasets"].values():
            self.assertTrue(dataset["source_unchanged"])

    def test_backend_status_does_not_mutate_real_database(self):
        from src.data.db import get_db
        db = get_db()
        before = db.get_table_counts()
        before_alerts = db.get_all_alerts(limit=100)
        build_actual_alert_payload(db)
        after = db.get_table_counts()
        after_alerts = db.get_all_alerts(limit=100)
        self.assertEqual(before, after)
        self.assertEqual(len(before_alerts), len(after_alerts))


class TestBackendExport(unittest.TestCase):
    def test_backend_status_export_is_strict_json(self):
        from src.backend_integration import export_backend_status
        from src.data.db import get_db
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "backend_status.json"
            payload = export_backend_status(get_db(), output)
            loaded = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], loaded["status"])
        self.assertEqual(payload["calibration_status"], "NOT_CALIBRATED")


if __name__ == "__main__":
    unittest.main()
