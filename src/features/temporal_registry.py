"""
Temporal Observation Registry

Indexes all observation epochs (InSAR pairs, rainfall periods, model runs),
supports date range queries, and exports registry for CesiumJS timeline.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config.settings import PATHS, setup_logging
from src.data.db import get_db

logger = setup_logging("temporal_registry")


class ObservationEpoch:
    def __init__(self, date, source, description="", metadata=None):
        self.date = date
        self.source = source
        self.description = description
        self.metadata = metadata or {}

    def to_dict(self):
        return {
            "date": self.date,
            "source": self.source,
            "description": self.description,
            "metadata": self.metadata,
        }


class TemporalRegistry:
    """Indexes and queries all observation epochs in the monitoring system."""

    def __init__(self, db=None):
        self.db = db or get_db()
        self._epochs: List[Dict] = []
        self._insar_pairs: List[Dict] = []

    def build_registry(self) -> List[Dict]:
        """Build the full temporal registry from all data sources."""
        self._epochs = []
        self._insar_pairs = []

        # 1. InSAR pairs
        self._add_insar_epochs()

        # 2. Rainfall records
        self._add_rainfall_epochs()

        # 3. Observation snapshots
        self._add_observation_epochs()

        # 4. Static known epochs from existing data
        self._add_known_epochs()

        for epoch in self._epochs:
            try:
                datetime.strptime(epoch["date"], "%Y-%m-%d")
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Invalid observation date in temporal registry: {epoch!r}") from error

        self._epochs.sort(key=lambda epoch: (epoch["date"], epoch["source"]))

        # Remove duplicates by date+source
        seen = set()
        unique = []
        for ep in self._epochs:
            key = f"{ep['date']}_{ep['source']}"
            if key not in seen:
                seen.add(key)
                unique.append(ep)
        self._epochs = unique

        logger.info("Temporal registry: %d epochs.", len(self._epochs))
        return self._epochs

    def _add_known_epochs(self):
        """Use project-known dates only when the corresponding database data is absent."""
        known = [
            {
                "date": "2026-08-05",
                "source": "Sentinel-1 (Pair 1 Reference)",
                "description": "S1 descending SLC acquisition — first pair reference.",
                "type": "insar",
            },
            {
                "date": "2026-08-17",
                "source": "Sentinel-1 (Pair 1 Secondary / Pair 2 Reference)",
                "description": "S1 acquisition — shared date between Pair 1 and Pair 2.",
                "type": "insar",
            },
            {
                "date": "2026-08-29",
                "source": "Sentinel-1 (Pair 2 Secondary)",
                "description": "S1 descending SLC acquisition — second pair secondary.",
                "type": "insar",
            },
        ]
        if not self._insar_pairs:
            self._epochs.extend(known)

        if any(epoch.get("type") == "rainfall" for epoch in self._epochs):
            return

        rain_csv = PATHS.processed_rainfall / "tirumala_rainfall_features_20260801_20260829.csv"
        if rain_csv.exists():
            import pandas as pd

            try:
                df = pd.read_csv(rain_csv)
            except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
                logger.warning("Could not read rainfall fallback CSV %s: %s", rain_csv, error)
                return
            date_columns = [column for column in df.columns if "date" in column.lower()]
            if not date_columns:
                logger.warning("Rainfall fallback CSV has no date column: %s", rain_csv)
                return
            for date_value in df[date_columns[0]].dropna().unique():
                self._epochs.append({
                    "date": str(date_value)[:10],
                    "source": "NASA GPM IMERG",
                    "description": "Daily rainfall observation.",
                    "type": "rainfall",
                })

    def _add_insar_epochs(self):
        """Add InSAR pair epochs from database."""
        pairs = self.db.get_insar_pairs()
        self._insar_pairs = sorted(
            pairs,
            key=lambda pair: (pair["reference_date"], pair["secondary_date"], pair["pair_id"]),
        )
        for pair in self._insar_pairs:
            self._epochs.append({
                "date": pair["reference_date"],
                "source": f"InSAR Reference ({pair['pair_id']})",
                "description": f"Pair reference date. Baseline: {pair.get('temporal_baseline_days', '?')} days.",
                "type": "insar",
                "pair_id": pair["pair_id"],
            })
            self._epochs.append({
                "date": pair["secondary_date"],
                "source": f"InSAR Secondary ({pair['pair_id']})",
                "description": f"Pair secondary date. Status: {pair.get('processing_status', '?')}.",
                "type": "insar",
                "pair_id": pair["pair_id"],
            })

    def _add_rainfall_epochs(self):
        """Add rainfall observation epochs from database."""
        with self.db.cursor() as cur:
            rows = cur.execute(
                "SELECT record_date, daily_mean_mm, rolling_3day_mm "
                "FROM rainfall_records ORDER BY record_date"
            ).fetchall()
            for row in rows:
                self._epochs.append({
                    "date": row["record_date"],
                    "source": "NASA GPM IMERG",
                    "description": f"Daily: {row['daily_mean_mm']:.1f} mm, "
                                   f"3-day: {row['rolling_3day_mm']:.1f} mm" if row["rolling_3day_mm"] else "",
                    "type": "rainfall",
                })

    def _add_observation_epochs(self):
        """Add observation snapshot dates from database."""
        dates = self.db.get_observation_dates()
        for observation_date in dates:
            self._epochs.append({
                "date": observation_date,
                "source": "Risk Assessment",
                "description": "Database assessment snapshot date; not necessarily a satellite acquisition.",
                "type": "assessment",
            })

    def get_date_range(self) -> Optional[Dict]:
        """Get the earliest and latest observation dates."""
        if not self._epochs:
            self.build_registry()
        if not self._epochs:
            return None
        return {
            "earliest": self._epochs[0]["date"],
            "latest": self._epochs[-1]["date"],
            "total_epochs": len(self._epochs),
        }

    def get_epochs_in_range(self, start: str, end: str) -> List[Dict]:
        """Get epochs between two inclusive ISO dates."""
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError("Temporal range endpoints must use YYYY-MM-DD.") from error
        if start_date > end_date:
            raise ValueError("Temporal range start must not be after its end.")
        if not self._epochs:
            self.build_registry()
        return [e for e in self._epochs if start <= e["date"] <= end]

    def get_epochs_by_type(self, epoch_type: str) -> List[Dict]:
        """Get epochs filtered by type (insar, rainfall, assessment)."""
        if not self._epochs:
            self.build_registry()
        return [e for e in self._epochs if e.get("type") == epoch_type]

    def export_for_cesium(self, output_path: Optional[str] = None) -> str:
        """Export registry as JSON for CesiumJS timeline widget."""
        if not self._epochs:
            self.build_registry()

        cesium_data = {
            "study_area": "Tirumala Hills",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_epochs": len(self._epochs),
            "date_range": self.get_date_range(),
            "epochs": self._epochs,
            "insar_pairs": [
                {
                    "pair_id": pair["pair_id"],
                    "reference_date": pair["reference_date"],
                    "secondary_date": pair["secondary_date"],
                    "temporal_baseline_days": pair.get("temporal_baseline_days"),
                    "processing_status": pair.get("processing_status"),
                    "valid_pixels": pair.get("valid_pixels"),
                    "mean_coherence": pair.get("mean_coherence"),
                }
                for pair in self._insar_pairs
            ],
            "comparison_note": (
                "Each InSAR pair is relative to its own phase reference; "
                "cross-pair displacement differences are not exported."
            ),
        }

        out_path = output_path or str(PATHS.viewer_data / "temporal_registry.json")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(cesium_data, f, indent=2)

        logger.info("Exported temporal registry: %s (%d epochs).", out_path, len(self._epochs))
        return out_path
