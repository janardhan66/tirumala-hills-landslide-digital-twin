import pytest

from src.analysis.temporal_insar import (
    InterferogramEdge,
    build_interferogram_network,
    build_per_cell_increment_matrix,
    invert_one_cell,
)


def test_single_real_pair_is_insufficient_for_deformation_time_series():
    edge = InterferogramEdge(
        pair_id="PAIR_20261109_20261121",
        reference_date="2026-11-09",
        secondary_date="2026-11-21",
        processing_status="PROCESSED",
        quality_status="VALID",
        mean_coherence=0.5894,
        valid_pixels=5034,
        los_raster="tirumala_live_los_disp_80m.tif",
        coherence_raster="tirumala_live_coherence_80m.tif",
    )
    result = invert_one_cell(
        ["2026-11-09", "2026-11-21"],
        [{
            "pair_id": edge.pair_id,
            "reference_date": edge.reference_date,
            "secondary_date": edge.secondary_date,
            "los_displacement_m": -0.08,
            "coherence": 0.7,
        }],
    )
    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["cumulative_los_m"] is None
    assert result["velocity_mm_year"] is None


def test_interferogram_network_reports_three_node_two_edge_network():
    pairs = [
        {
            "pair_id": "PAIR_A",
            "reference_date": "2026-01-01",
            "secondary_date": "2026-01-13",
            "processing_status": "PROCESSED",
            "quality_status": "VALID",
        },
        {
            "pair_id": "PAIR_B",
            "reference_date": "2026-01-13",
            "secondary_date": "2026-01-25",
            "processing_status": "PROCESSED",
            "quality_status": "VALID",
        },
    ]
    network = build_interferogram_network(pairs)
    assert network["nodes"] == ["2026-01-01", "2026-01-13", "2026-01-25"]
    assert len(network["valid_edges"]) == 2
    assert network["connected_components"] == 1


def test_synthetic_weighted_inversion_recovers_linear_velocity():
    acquisition_dates = ["2026-01-01", "2026-04-01", "2026-07-01"]
    edges = [
        {
            "pair_id": "PAIR_1",
            "reference_date": "2026-01-01",
            "secondary_date": "2026-04-01",
            "los_displacement_m": 0.010,
            "coherence": 0.8,
        },
        {
            "pair_id": "PAIR_2",
            "reference_date": "2026-04-01",
            "secondary_date": "2026-07-01",
            "los_displacement_m": 0.010,
            "coherence": 0.8,
        },
    ]
    result = invert_one_cell(acquisition_dates, edges)
    assert result["status"] == "COMPUTED"
    assert result["measurement_count"] == 2
    assert result["cumulative_los_m"][0] == 0.0
    assert result["cumulative_los_m"][1] == pytest.approx(0.010)
    assert result["cumulative_los_m"][2] == pytest.approx(0.020)
    assert result["velocity_mm_year"] == pytest.approx(40.0, abs=3.0)
    assert result["reliable_trend"] is True


def test_missing_edge_is_not_replaced_with_zero_displacement():
    matrix, observations, weights, pair_ids = build_per_cell_increment_matrix(
        ["2026-01-01", "2026-01-13", "2026-01-25"],
        [{
            "pair_id": "PAIR_MISSING",
            "reference_date": "2026-01-01",
            "secondary_date": "2026-01-13",
            "los_displacement_m": None,
            "coherence": 0.8,
        }],
    )
    assert matrix.shape == (0, 3)
    assert observations.size == 0
    assert weights.size == 0
    assert pair_ids == []


def test_low_coherence_edge_is_excluded():
    matrix, observations, weights, pair_ids = build_per_cell_increment_matrix(
        ["2026-01-01", "2026-01-13"],
        [{
            "pair_id": "PAIR_LOW",
            "reference_date": "2026-01-01",
            "secondary_date": "2026-01-13",
            "los_displacement_m": -0.02,
            "coherence": 0.49,
        }],
    )
    assert matrix.shape == (0, 2)
    assert pair_ids == []
