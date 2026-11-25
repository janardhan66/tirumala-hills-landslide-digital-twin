import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.process_insar import HyP3Processor
from src.data.db import DatabaseManager


class TestHyP3Processor(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db = DatabaseManager(Path(self.temp_dir.name) / "insar.db")
        self.addCleanup(self.db.close)
        self.processor = HyP3Processor(
            db=self.db,
            output_dir=Path(self.temp_dir.name) / "products",
        )

    def _add_acquisition(self, acquisition_id, date):
        self.db.add_acquisition(
            acquisition_id=acquisition_id,
            satellite="Sentinel-1",
            product_type="SLC",
            acquisition_date=date,
        )

    def _add_pair(self, pair_id, ref_id, sec_id, ref_date, sec_date, job_id):
        self._add_acquisition(ref_id, ref_date)
        self._add_acquisition(sec_id, sec_date)
        self.db.add_insar_pair(
            pair_id=pair_id,
            reference_acq_id=ref_id,
            secondary_acq_id=sec_id,
            reference_date=ref_date,
            secondary_date=sec_date,
            temporal_baseline_days=12,
            processing_mode="hyp3",
            processing_status="SUBMITTED",
            hyp3_job_id=job_id,
        )

    def test_submit_pair_requires_catalogued_acquisitions(self):
        with patch("scripts.process_insar.CREDENTIALS.earthdata_username", "user"), patch(
            "scripts.process_insar.CREDENTIALS.earthdata_password", "password"
        ):
            with self.assertRaisesRegex(ValueError, "not in the local catalog"):
                self.processor.submit_pair(
                    "missing-ref",
                    "missing-sec",
                    "2026-08-05",
                    "2026-08-17",
                )

    def test_submit_pair_registers_successful_job(self):
        self._add_acquisition("ref", "2026-08-05")
        self._add_acquisition("sec", "2026-08-17")
        job = types.SimpleNamespace(job_id="job-1")
        sdk = types.SimpleNamespace(
            HyP3=Mock(
                return_value=types.SimpleNamespace(
                    submit_insar_job=Mock(
                        return_value=types.SimpleNamespace(jobs=[job])
                    )
                )
            )
        )
        with patch.dict(sys.modules, {"hyp3_sdk": sdk}), patch(
            "scripts.process_insar.CREDENTIALS.earthdata_username", "user"
        ), patch("scripts.process_insar.CREDENTIALS.earthdata_password", "password"):
            pair_id = self.processor.submit_pair(
                "ref", "sec", "2026-08-05", "2026-08-17"
            )

        self.assertEqual(pair_id, "PAIR_20260805_20260817")
        pair = self.db.get_insar_pairs(status="SUBMITTED")[0]
        self.assertEqual(pair["hyp3_job_id"], "job-1")
        self.assertEqual(pair["temporal_baseline_days"], 12)

    def test_status_check_only_processes_requested_pair(self):
        self._add_pair(
            "PAIR_20260805_20260817", "ref1", "sec1",
            "2026-08-05", "2026-08-17", "job-1",
        )
        self._add_pair(
            "PAIR_20260817_20260829", "ref2", "sec2",
            "2026-08-17", "2026-08-29", "job-2",
        )
        hyp3 = types.SimpleNamespace(
            get_job_by_id=Mock(
                return_value=types.SimpleNamespace(
                    status_code="RUNNING",
                    job_id="job-2",
                )
            )
        )
        sdk = types.SimpleNamespace(HyP3=Mock(return_value=hyp3))

        with patch.dict(sys.modules, {"hyp3_sdk": sdk}), patch(
            "scripts.process_insar.CREDENTIALS.earthdata_username", "user"
        ), patch("scripts.process_insar.CREDENTIALS.earthdata_password", "password"):
            result = self.processor.check_and_download("PAIR_20260817_20260829")

        self.assertEqual(result, [])
        hyp3.get_job_by_id.assert_called_once_with("job-2")

    def test_successful_job_with_no_files_is_not_marked_processed(self):
        pair_id = "PAIR_20260805_20260817"
        self._add_pair(
            pair_id, "ref", "sec", "2026-08-05", "2026-08-17", "job-1"
        )
        job = types.SimpleNamespace(
            status_code="SUCCEEDED",
            job_id="job-1",
            download_files=Mock(return_value=[]),
        )
        sdk = types.SimpleNamespace(
            HyP3=Mock(return_value=types.SimpleNamespace(get_job_by_id=Mock(return_value=job)))
        )

        with patch.dict(sys.modules, {"hyp3_sdk": sdk}), patch(
            "scripts.process_insar.CREDENTIALS.earthdata_username", "user"
        ), patch("scripts.process_insar.CREDENTIALS.earthdata_password", "password"):
            result = self.processor.check_and_download(pair_id)

        self.assertEqual(result, [])
        pair = self.db.get_insar_pairs()[0]
        self.assertEqual(pair["processing_status"], "FAILED")
        self.assertIn("returned no files", pair["error_message"])

    def test_job_submission_requires_explicit_approval(self):
        with self.assertRaisesRegex(PermissionError, "explicit approval"):
            self.processor.submit_approved_pair(
                "missing-ref",
                "missing-sec",
                "2026-08-05",
                "2026-08-17",
                approval_granted=False,
            )

    def test_hyp3_status_history_persists_across_restart(self):
        self._add_pair(
            "PAIR_20260805_20260817",
            "ref",
            "sec",
            "2026-08-05",
            "2026-08-17",
            "job-history",
        )
        self.db.record_hyp3_status(
            "PAIR_20260805_20260817",
            "job-history",
            "RUNNING",
            payload={"status_code": "RUNNING"},
        )
        restarted = DatabaseManager(Path(self.temp_dir.name) / "insar.db")
        history = restarted.get_hyp3_status_history("job-history")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "RUNNING")
        restarted.close()


if __name__ == "__main__":
    unittest.main()
