"""Multi-temporal Sentinel-1 acquisition and InSAR pair management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class CandidatePair:
    pair_id: str
    reference_acquisition_id: str
    secondary_acquisition_id: str
    reference_date: str
    secondary_date: str
    temporal_baseline_days: int
    orbit_direction: str
    relative_orbit: int
    spatial_overlap_percent: float
    selection_reason: str


def calculate_temporal_baseline(reference_date: str, secondary_date: str) -> int:
    reference = datetime.strptime(reference_date, "%Y-%m-%d")
    secondary = datetime.strptime(secondary_date, "%Y-%m-%d")
    baseline = (secondary - reference).days
    if baseline <= 0:
        raise ValueError("Secondary acquisition date must follow the reference date.")
    return baseline


def orbit_compatible(reference: dict, secondary: dict) -> bool:
    reference_direction = str(reference.get("orbit_direction") or "").upper()
    secondary_direction = str(secondary.get("orbit_direction") or "").upper()
    if reference_direction != secondary_direction:
        return False

    reference_relative = reference.get("relative_orbit")
    secondary_relative = secondary.get("relative_orbit")
    if reference_relative is None or secondary_relative is None:
        return False
    if int(reference_relative) != int(secondary_relative):
        return False

    reference_mode = str(reference.get("sensor_mode") or "").upper()
    secondary_mode = str(secondary.get("sensor_mode") or "").upper()
    if reference_mode and secondary_mode and reference_mode != secondary_mode:
        return False
    return True


def spatial_overlap_percent(reference: dict, secondary: dict, aoi_wkt: str) -> float:
    """Approximate overlap using WKT footprints and the study-area polygon."""
    from shapely import wkt
    from shapely.geometry import shape

    aoi = wkt.loads(aoi_wkt)
    overlap = 0.0
    footprints = []
    for acquisition in (reference, secondary):
        raw = acquisition.get("footprint_wkt")
        if not raw:
            continue
        try:
            if raw.startswith("geography"):
                raw = raw.split(";", 1)[1] if ";" in raw else raw
            raw = raw.strip().rstrip("'\"")
            footprints.append(wkt.loads(raw))
        except Exception:
            continue

    if len(footprints) != 2:
        return 0.0
    reference_area = footprints[0].intersection(aoi)
    secondary_area = footprints[1].intersection(aoi)
    if reference_area.is_empty or secondary_area.is_empty:
        return 0.0
    intersection = reference_area.intersection(secondary_area)
    denominator = min(reference_area.area, secondary_area.area)
    if denominator <= 0:
        return 0.0
    overlap = 100.0 * intersection.area / denominator
    return round(overlap, 2)


class PairManager:
    """Safe pair-selection and pair-persistence helper."""

    def __init__(
        self,
        db,
        minimum_baseline_days: int = 6,
        maximum_baseline_days: int = 36,
        minimum_overlap_percent: float = 90.0,
    ):
        self.db = db
        self.minimum_baseline_days = minimum_baseline_days
        self.maximum_baseline_days = maximum_baseline_days
        self.minimum_overlap_percent = minimum_overlap_percent

    def existing_pair_exists(
        self, reference_acquisition_id: str, secondary_acquisition_id: str
    ) -> bool:
        with self.db.cursor() as cur:
            row = cur.execute(
                "SELECT 1 FROM insar_pairs "
                "WHERE reference_acq_id = ? AND secondary_acq_id = ?",
                (reference_acquisition_id, secondary_acquisition_id),
            ).fetchone()
        return row is not None

    def select_next_connected_pairs(
        self,
        acquisitions: Iterable[dict],
        aoi_wkt: str,
        maximum_pairs: int = 1,
    ) -> List[CandidatePair]:
        import zipfile

        candidates = [
            row for row in acquisitions
            if row.get("satellite") == "Sentinel-1"
            and row.get("product_type") in {"SLC", "IW_SLC__1S", "IW_SLC"}
            and row.get("acquisition_date")
            and row.get("orbit_direction")
            and row.get("relative_orbit") is not None
            and row.get("download_status") == "DOWNLOADED"
            and row.get("file_path")
            and Path(str(row["file_path"])).is_file()
            and (
                Path(str(row["file_path"])).suffix.lower() != ".zip"
                or zipfile.is_zipfile(Path(str(row["file_path"])))
            )
        ]
        candidates.sort(
            key=lambda row: (
                str(row.get("acquisition_date")),
                str(row.get("start_time") or ""),
                str(row.get("acquisition_id")),
            )
        )

        selected: List[CandidatePair] = []
        for secondary in reversed(candidates):
            if len(selected) >= maximum_pairs:
                break
            for reference in reversed(candidates[: candidates.index(secondary)]):
                if not orbit_compatible(reference, secondary):
                    continue
                try:
                    baseline = calculate_temporal_baseline(
                        reference["acquisition_date"],
                        secondary["acquisition_date"],
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                if baseline < self.minimum_baseline_days:
                    continue
                if baseline > self.maximum_baseline_days:
                    continue
                if self.existing_pair_exists(
                    reference["acquisition_id"], secondary["acquisition_id"]
                ):
                    continue
                overlap = spatial_overlap_percent(reference, secondary, aoi_wkt)
                if overlap < self.minimum_overlap_percent:
                    continue

                pair_id = (
                    f"PAIR_{datetime.strptime(reference['acquisition_date'], '%Y-%m-%d'):%Y%m%d}_"
                    f"{datetime.strptime(secondary['acquisition_date'], '%Y-%m-%d'):%Y%m%d}"
                )
                selected.append(CandidatePair(
                    pair_id=pair_id,
                    reference_acquisition_id=reference["acquisition_id"],
                    secondary_acquisition_id=secondary["acquisition_id"],
                    reference_date=reference["acquisition_date"],
                    secondary_date=secondary["acquisition_date"],
                    temporal_baseline_days=baseline,
                    orbit_direction=str(reference["orbit_direction"]).upper(),
                    relative_orbit=int(reference["relative_orbit"]),
                    spatial_overlap_percent=overlap,
                    selection_reason=(
                        "Connected chronological pair: same relative orbit and "
                        "direction, baseline within configured limits, "
                        f"{overlap:.2f}% AOI overlap."
                    ),
                ))
                break
        return selected

    def register_selected_pair(
        self,
        candidate: CandidatePair,
        processing_status: str = "CANDIDATE",
    ) -> str:
        with self.db.cursor() as cur:
            existing = cur.execute(
                "SELECT pair_id FROM insar_pairs WHERE pair_id = ?",
                (candidate.pair_id,),
            ).fetchone()
        if existing:
            return candidate.pair_id

        self.db.add_insar_pair(
            pair_id=candidate.pair_id,
            reference_acq_id=candidate.reference_acquisition_id,
            secondary_acq_id=candidate.secondary_acquisition_id,
            reference_date=candidate.reference_date,
            secondary_date=candidate.secondary_date,
            temporal_baseline_days=candidate.temporal_baseline_days,
            processing_mode="hyp3",
            processing_status=processing_status,
            orbit_direction=candidate.orbit_direction,
            relative_orbit=candidate.relative_orbit,
            spatial_overlap_percent=candidate.spatial_overlap_percent,
            quality_status="PENDING",
            selection_method=candidate.selection_reason,
        )
        return candidate.pair_id
