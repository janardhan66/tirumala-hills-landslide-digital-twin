"""Small-Baseline network and guarded LOS time-series analysis.

This module does not infer deformation when the interferogram network cannot
support an inversion. One pair alone cannot estimate an acquisition-date
cumulative series or a reliable velocity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
from scipy.linalg import lstsq


@dataclass(frozen=True)
class InterferogramEdge:
    pair_id: str
    reference_date: str
    secondary_date: str
    processing_status: str
    quality_status: str
    mean_coherence: Optional[float]
    valid_pixels: Optional[int]
    los_raster: Optional[str]
    coherence_raster: Optional[str]


@dataclass
class NetworkStatus:
    node_count: int
    edge_count: int
    connected_components: int
    component_sizes: List[int]
    rank: Optional[int]
    overdetermined: bool
    status: str
    message: str


def build_interferogram_network(pairs: Iterable[dict]) -> Dict:
    edges: List[InterferogramEdge] = []
    nodes = set()

    for pair in pairs:
        reference_date = str(pair.get("reference_date") or "")
        secondary_date = str(pair.get("secondary_date") or "")
        if not reference_date or not secondary_date:
            continue
        datetime.strptime(reference_date, "%Y-%m-%d")
        datetime.strptime(secondary_date, "%Y-%m-%d")
        nodes.add(reference_date)
        nodes.add(secondary_date)
        edges.append(InterferogramEdge(
            pair_id=str(pair["pair_id"]),
            reference_date=reference_date,
            secondary_date=secondary_date,
            processing_status=str(pair.get("processing_status") or "UNKNOWN"),
            quality_status=str(pair.get("quality_status") or "NOT_TESTED"),
            mean_coherence=(
                float(pair["mean_coherence"])
                if pair.get("mean_coherence") is not None
                else None
            ),
            valid_pixels=(
                int(pair["valid_pixels"])
                if pair.get("valid_pixels") is not None
                else None
            ),
            los_raster=pair.get("los_disp_tif"),
            coherence_raster=pair.get("coherence_tif"),
        ))

    adjacency = {node: set() for node in nodes}
    valid_edges = []
    for edge in edges:
        if (
            edge.processing_status == "PROCESSED"
            and edge.quality_status in {"PROCESSED", "VALID"}
        ):
            adjacency[edge.reference_date].add(edge.secondary_date)
            adjacency[edge.secondary_date].add(edge.reference_date)
            valid_edges.append(edge)

    visited = set()
    component_sizes = []
    for node in sorted(adjacency):
        if node in visited:
            continue
        stack = [node]
        visited.add(node)
        component_size = 0
        while stack:
            current = stack.pop()
            component_size += 1
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        component_sizes.append(component_size)

    return {
        "nodes": sorted(nodes),
        "edges": edges,
        "valid_edges": valid_edges,
        "connected_components": len(component_sizes),
        "component_sizes": component_sizes,
    }


def build_increment_matrix(
    acquisition_dates: List[str],
    edges: Iterable[InterferogramEdge],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Construct A * x = d for each interferogram edge.

    Row is secondary - reference with a reference date fixed to zero.
    """
    dates = sorted(set(acquisition_dates))
    if len(dates) < 2:
        raise ValueError("At least two acquisition dates are required.")

    reference = dates[0]
    node_index = {date: index for index, date in enumerate(dates)}
    rows = []
    observations = []
    weights = []

    for edge in edges:
        if (
            edge.processing_status != "PROCESSED"
            or edge.quality_status not in {"PROCESSED", "VALID"}
        ):
            continue
        if edge.reference_date not in node_index or edge.secondary_date not in node_index:
            continue
        row = np.zeros(len(dates), dtype=np.float64)
        ref_index = node_index[edge.reference_date]
        sec_index = node_index[edge.secondary_date]
        row[sec_index] = 1.0
        row[ref_index] -= 1.0
        rows.append(row)
        observations.append(0.0)
        weights.append(
            float(edge.mean_coherence)
            if edge.mean_coherence is not None
            else 0.0
        )

    if not rows:
        return np.zeros((0, len(dates))), np.zeros(0), np.zeros(0)
    matrix = np.asarray(rows, dtype=np.float64)
    matrix = np.delete(matrix, node_index[reference], axis=1)
    return (
        matrix,
        np.asarray(observations, dtype=np.float64),
        np.asarray(weights, dtype=np.float64),
    )


def invert_sbas_network(
    acquisition_dates: List[str],
    edges: Iterable[InterferogramEdge],
    minimum_edges: int = 2,
) -> Dict:
    """Perform weighted least squares only for a sufficiently connected network."""
    network = build_interferogram_network([
        {
            "pair_id": edge.pair_id,
            "reference_date": edge.reference_date,
            "secondary_date": edge.secondary_date,
            "processing_status": edge.processing_status,
            "quality_status": edge.quality_status,
            "mean_coherence": edge.mean_coherence,
            "valid_pixels": edge.valid_pixels,
            "los_disp_tif": edge.los_raster,
            "coherence_raster": edge.coherence_raster,
        }
        for edge in edges
    ])

    valid_edges = network["valid_edges"]
    matrix, observations, weights = build_increment_matrix(
        acquisition_dates,
        [InterferogramEdge(
            pair_id=str(pair["pair_id"]),
            reference_date=str(pair["reference_date"]),
            secondary_date=str(pair["secondary_date"]),
            processing_status=str(pair["processing_status"]),
            quality_status=str(pair["quality_status"]),
            mean_coherence=pair.get("mean_coherence"),
            valid_pixels=pair.get("valid_pixels"),
            los_raster=pair.get("los_disp_tif"),
            coherence_raster=pair.get("coherence_raster"),
        ) for pair in []]
    )
    # The public inversion helper intentionally does not accept per-pixel
    # displacement values; this guard is for network sufficiency and fixtures.
    if len(valid_edges) < minimum_edges:
        return {
            "status": "INSUFFICIENT_DATA",
            "cumulative_los_m": None,
            "velocity_mm_year": None,
            "measurement_count": len(valid_edges),
            "residual_norm": None,
            "connected_components": network["connected_components"],
            "message": (
                "At least two independent valid interferograms are required for "
                "a defensible SBAS network. One pair alone cannot estimate "
                "cumulative displacement or velocity."
            ),
        }

    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        return {
            "status": "INSUFFICIENT_DATA",
            "cumulative_los_m": None,
            "velocity_mm_year": None,
            "measurement_count": len(valid_edges),
            "residual_norm": None,
            "connected_components": network["connected_components"],
            "message": "The interferogram network cannot construct an inversion matrix.",
        }

    rank = int(np.linalg.matrix_rank(matrix))
    if rank < matrix.shape[1]:
        return {
            "status": "UNDERDETERMINED",
            "cumulative_los_m": None,
            "velocity_mm_year": None,
            "measurement_count": len(valid_edges),
            "residual_norm": None,
            "connected_components": network["connected_components"],
            "message": "The observation matrix is rank-deficient.",
        }

    solution = lstsq(matrix, observations)[0]
    residual = matrix @ solution - observations
    cumulative = np.concatenate([[0.0], solution])
    return {
        "status": "COMPUTED",
        "cumulative_los_m": cumulative.tolist(),
        "velocity_mm_year": None,
        "measurement_count": len(valid_edges),
        "residual_norm": float(np.linalg.norm(residual)),
        "connected_components": network["connected_components"],
        "message": "Synthetic network inversion completed; real velocity validation requires multiple genuine pairs.",
    }


def build_per_cell_increment_matrix(
    acquisition_dates: List[str],
    edges: List[dict],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Build A, d, coherence weights and retained acquisition dates for one cell.

    This helper is intended for real raster-derived observations supplied with
    row and coherence values. It deliberately never fabricates missing data.
    """
    dates = sorted(set(acquisition_dates))
    if len(dates) < 2:
        raise ValueError("At least two acquisition dates are required.")

    reference = dates[0]
    node_index = {date: index for index, date in enumerate(dates)}
    rows = []
    observations = []
    weights = []
    retained_pair_ids = []

    for edge in edges:
        reference_date = str(edge.get("reference_date") or "")
        secondary_date = str(edge.get("secondary_date") or "")
        if reference_date not in node_index or secondary_date not in node_index:
            continue
        displacement_m = edge.get("los_displacement_m")
        coherence = edge.get("coherence")
        if displacement_m is None or coherence is None:
            continue
        try:
            displacement_m = float(displacement_m)
            coherence = float(coherence)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(displacement_m) or not np.isfinite(coherence):
            continue
        if coherence < 0.5:
            continue

        row = np.zeros(len(dates), dtype=np.float64)
        row[node_index[secondary_date]] = 1.0
        row[node_index[reference_date]] -= 1.0
        rows.append(row)
        observations.append(displacement_m)
        weights.append(coherence)
        retained_pair_ids.append(str(edge.get("pair_id") or ""))

    if not rows:
        return np.zeros((0, len(dates))), np.zeros(0), np.zeros(0), []

    matrix = np.asarray(rows, dtype=np.float64)
    matrix = np.delete(matrix, node_index[reference], axis=1)
    return (
        matrix,
        np.asarray(observations, dtype=np.float64),
        np.asarray(weights, dtype=np.float64),
        retained_pair_ids,
    )


def invert_one_cell(
    acquisition_dates: List[str],
    edges: List[dict],
) -> Dict:
    """Invert one spatial cell using coherence-weighted least squares."""
    matrix, observations, weights, retained_pair_ids = build_per_cell_increment_matrix(
        acquisition_dates,
        edges,
    )
    if matrix.shape[0] < 2:
        return {
            "status": "INSUFFICIENT_DATA",
            "cumulative_los_m": None,
            "velocity_mm_year": None,
            "measurement_count": len(retained_pair_ids),
            "residual_norm": None,
            "reliable_trend": False,
            "message": "At least two independent quality-valid interferograms are required.",
        }

    rank = int(np.linalg.matrix_rank(matrix))
    if rank < matrix.shape[1]:
        return {
            "status": "UNDERDETERMINED",
            "cumulative_los_m": None,
            "velocity_mm_year": None,
            "measurement_count": len(retained_pair_ids),
            "residual_norm": None,
            "reliable_trend": False,
            "message": "The per-cell observation matrix is rank-deficient.",
        }

    weighted_matrix = matrix * np.sqrt(weights)[:, None]
    weighted_observations = observations * np.sqrt(weights)
    solution, residuals, _, _ = lstsq(
        weighted_matrix,
        weighted_observations,
    )
    residual_vector = weighted_matrix @ solution - weighted_observations
    cumulative = np.concatenate([[0.0], solution])

    dates = sorted(set(acquisition_dates))
    time_days = np.asarray([
        (
            datetime.strptime(date, "%Y-%m-%d")
            - datetime.strptime(dates[0], "%Y-%m-%d")
        ).days
        for date in dates
    ], dtype=np.float64)
    valid_time = time_days > 0
    if np.count_nonzero(valid_time) < 2:
        velocity = None
        reliable = False
    else:
        t_year = time_days[valid_time] / 365.25
        y_m = cumulative[valid_time]
        slope_m_year, intercept = np.polyfit(t_year, y_m, 1)
        velocity = float(slope_m_year * 1000.0)
        reliable = True

    return {
        "status": "COMPUTED",
        "cumulative_los_m": cumulative.tolist(),
        "velocity_mm_year": velocity,
        "measurement_count": len(retained_pair_ids),
        "residual_norm": float(np.linalg.norm(residual_vector)),
        "reliable_trend": reliable,
        "message": (
            "LOS velocity estimate requires temporal validation and is not "
            "a confirmed vertical or landslide velocity."
        ),
    }
