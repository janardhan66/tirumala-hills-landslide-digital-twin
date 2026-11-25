"""
Tirumala Hills Landslide Digital Twin — 6-Tab Extended Dashboard Views

Implements the 6 core dashboard views:
  1. Project Overview & Interactive Gemini AI Assistant
  2. Interactive 3D Digital Twin (CesiumJS WebGL & Plotly 3D Surface)
  3. Continuous Remote Sensing & IMERG Rainfall Monitoring
  4. Multi-Criteria Evidence Risk Assessment & What-If Simulator
  5. Automation Status (APScheduler Telemetry & Master Pipeline)
  6. Decision-Support Alerts & Human Verification
"""

from __future__ import annotations

import json
import os
import csv
from html import escape
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from config.settings import PATHS, RISK, STUDY_AREA
from src.data.db import get_db

load_dotenv()


@st.cache_data(ttl=5)
def _read_scheduler_telemetry():
    """Return scheduler state only when the recorded process is still alive."""
    status_path = PATHS.logs_dir / "scheduler_status.json"
    lock_path = PATHS.logs_dir / "scheduler.lock"
    if not status_path.is_file() or not lock_path.is_file():
        return {"running": False, "next_pipeline_run": None, "interval_hours": None}

    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        pid = int(status.get("pid", 0))
        if not status.get("running") or pid <= 0 or int(lock.get("pid", 0)) != pid:
            raise ValueError("Scheduler lock and status do not match.")
        if os.name == "nt":
            process_list = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            process_running = any(
                len(row) > 1 and row[1] == str(pid)
                for row in csv.reader(process_list.stdout.splitlines())
            )
        else:
            os.kill(pid, 0)
            process_running = True
        if not process_running:
            raise ValueError("Scheduler process is not running.")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"running": False, "next_pipeline_run": None, "interval_hours": None}

    return {
        "running": True,
        "next_pipeline_run": status.get("next_pipeline_run"),
        "interval_hours": status.get("interval_hours"),
    }


@st.cache_data(ttl=5)
def _read_pipeline_telemetry():
    status_path = PATHS.logs_dir / "pipeline_status.json"
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _freshness_age(value):
    """Return a data-record age without asserting a domain-specific freshness threshold."""
    if not value:
        return "Unavailable"
    try:
        observed = datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return "Unavailable"
    return f"{(datetime.now().date() - observed).days} days old"


# -----------------------------------------------------------------------------
# TAB 1: PROJECT OVERVIEW & GEMINI AGENT
# -----------------------------------------------------------------------------
def render_tab_overview(df, temporal_df, rainfall_df, gsi_df):
    st.markdown(
        """
        <style>
        .twin-hero-banner {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 58, 138, 0.35) 50%, rgba(15, 23, 42, 0.95) 100%);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 14px;
            padding: 22px 26px;
            margin-bottom: 22px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4), 0 0 20px rgba(56, 189, 248, 0.08);
        }
        .twin-hero-title {
            font-size: 24px;
            font-weight: 800;
            background: linear-gradient(90deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
            letter-spacing: -0.4px;
        }
        .twin-badge-container {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 12px;
        }
        .twin-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.12);
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            color: #f1f5f9;
        }
        .twin-pill.live {
            border-color: rgba(16, 185, 129, 0.6);
            color: #34d399;
            background: rgba(16, 185, 129, 0.12);
            box-shadow: 0 0 12px rgba(16, 185, 129, 0.25);
        }
        .twin-pill.auth {
            border-color: rgba(56, 189, 248, 0.5);
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.12);
        }
        .kpi-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.65) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        </style>

        <div class="twin-hero-banner">
            <div class="twin-hero-title">🏔️ TIRUMALA HILLS LANDSLIDE DIGITAL TWIN & MONITORING DASHBOARD</div>
            <div style="color: #94a3b8; font-size: 13.5px;">Multi-temporal InSAR ground deformation, NASA GPM rainfall telemetry, and AI-assisted risk decision support.</div>
            <div class="twin-badge-container">
                <span class="twin-pill live"><span style="width:7px; height:7px; border-radius:50%; background:#10b981; display:inline-block;"></span> Active Monitoring System</span>
                <span class="twin-pill auth">🛰️ CDSE Authenticated</span>
                <span class="twin-pill auth">🌧️ NASA Earthdata Authenticated</span>
                <span class="twin-pill">📐 80m Analytical Matrix</span>
                <span class="twin-pill">🌐 CesiumJS WebGL 3D</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "📍 **Study Area:** Tirumala Hills, Tirupati District, Andhra Pradesh, India "
        f"({STUDY_AREA.bbox_south:.3f}°N–{STUDY_AREA.bbox_north:.3f}°N, {STUDY_AREA.bbox_west:.3f}°E–{STUDY_AREA.bbox_east:.3f}°E) · Projected CRS: EPSG:32644 (UTM Zone 44N)"
    )

    db = get_db()
    counts = db.get_table_counts()

    # Top KPI cards with styled metrics
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(
            "Spatial Grid Nodes",
            f"{counts.get('spatial_evidence_grid', 0):,}",
            help="80m analytical grid in EPSG:32644 covering the entire Tirumala Hills AOI"
        )
    with k2:
        st.metric(
            "Observation Snapshots",
            f"{counts.get('observation_snapshots', 0):,}",
            help="Timestamped evidence snapshots across Sentinel-1 observation epochs"
        )
    with k3:
        st.metric(
            "Rainfall History",
            f"{counts.get('rainfall_records', 0)} Days",
            help="Daily and rolling antecedent NASA GPM IMERG records"
        )
    with k4:
        st.metric(
            "Active Alerts",
            f"{counts.get('alerts', 0)}",
            help="Decision-support alerts requiring review and verification"
        )

    st.markdown("---")

    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.markdown("#### 🛰️ Data Availability & Telemetry Status")
        status_data = [
            {"Source": "Copernicus Sentinel-1 SAR", "Product": "IW SLC Descending", "Latest Date": db.get_latest_processed_insar_date() or "Not processed", "Status": "From processed InSAR pairs", "Quality": "LOS is relative ground displacement"},
            {"Source": "Copernicus GLO-30 DEM", "Product": "Digital Elevation & Horn Slope", "Latest Date": "Static Baseline", "Status": "Local baseline", "Quality": "80m terrain elevation & slope"},
            {"Source": "NASA GPM IMERG", "Product": "Final Daily Precipitation (V07C)", "Latest Date": db.get_latest_rainfall_date() or "No observations", "Status": "Authenticated API", "Quality": "Daily + Rolling 1-14d"},
            {"Source": "Historical Landslide Inventory", "Product": "GSI Figure 3.2 digitized records", "Latest Date": "Historical", "Status": "Active", "Quality": "15 hazard points mapped"},
            {"Source": "Evidence Risk Engine", "Product": "Relative evidence scoring", "Latest Date": (db.get_risk_summary().get("observation_date") or "Not assessed"), "Status": "Latest stored assessment", "Quality": "Compound multi-criteria score"},
        ]
        st.dataframe(pd.DataFrame(status_data), use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("#### ⚖️ Overall Hazard Evidence Breakdown")
        risk_hist = db.get_risk_history()
        if risk_hist:
            latest_rh = risk_hist[-1]
            tot = latest_rh.get("total_cells", 0)
            low_c = latest_rh.get("low_count", 0)
            med_c = latest_rh.get("medium_count", 0)
            high_c = latest_rh.get("high_count", 0)
        elif not df.empty and "agent_evidence_category" in df.columns:
            vc = df["agent_evidence_category"].value_counts()
            tot = len(df)
            low_c = vc.get("Low", 0)
            med_c = vc.get("Medium", 0)
            high_c = vc.get("High", 0)
        else:
            tot, low_c, med_c, high_c = 0, 0, 0, 0

        # Interactive Plotly Donut Chart
        fig_donut = go.Figure(data=[go.Pie(
            labels=["Low Evidence", "Medium Evidence", "High Evidence"],
            values=[low_c, med_c, high_c],
            hole=0.62,
            marker_colors=["#10b981", "#f59e0b", "#ef4444"],
            textinfo="label+percent",
            hoverinfo="label+value+percent",
        )])
        fig_donut.update_layout(
            showlegend=False,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=260,
            margin=dict(l=10, r=10, t=10, b=10),
            annotations=[
                dict(text=f"<b>{tot:,}</b><br><span style='font-size:11px;color:#94a3b8;'>CELLS</span>",
                     x=0.5, y=0.5, font_size=16, font_color="#f8fafc", showarrow=False)
            ]
        )
        st.plotly_chart(fig_donut, use_container_width=True, config={"displaylogo": False})


# -----------------------------------------------------------------------------
# TAB 2: INTERACTIVE 3D DIGITAL TWIN
# -----------------------------------------------------------------------------
def render_tab_3d_digital_twin(base_dir, create_terrain_figure_func, overlays_list):
    st.subheader("🏔️ Realistic 3D Digital Twin of Tirumala Hills")
    st.caption("Interactive 80 m UTM 44N terrain environment with DEM, Sentinel-1 InSAR evidence, Horn's slope, rainfall context and GSI historical locations.")
    st.warning(
        "Scientific scope: the risk index is an empirical relative evidence index, "
        "InSAR LOS is 1-D line-of-sight displacement rather than vertical subsidence, "
        "and the viewer does not issue confirmed landslide warnings."
    )

    # 3D Quick Command Deck Bar
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.8) 100%);
                    border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 14px; padding: 14px 20px; margin-bottom: 18px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 20px;">🎮</span>
                    <div>
                        <div style="font-weight: 700; color: #f8fafc; font-size: 13.5px;">Interactive 3D Navigation Controls:</div>
                        <div style="font-size: 12px; color: #94a3b8;">
                            🔄 <b>Left-Click:</b> Rotate & Orbit · 🔍 <b>Right-Click / Scroll:</b> Zoom · 📐 <b>Middle-Click:</b> Tilt Angle · 📍 <b>Click Mountain:</b> Raycast Ground Data
                        </div>
                    </div>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span style="background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 12px;">80m DEM MESH</span>
                    <span style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 12px;">InSAR FRINGES</span>
                    <span style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); color: #fbbf24; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 12px;">15 GSI HAZARDS</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    twin_mode = st.radio(
        "Select Visualization Engine",
        ["🛰️ CesiumJS 3D Geospatial Globe (WebGL)", "🏔️ Analytical Plotly 3D Surface Mesh", "🗺️ 2D Interactive Leaflet GIS Map"],
        horizontal=True,
    )

    if twin_mode == "🛰️ CesiumJS 3D Geospatial Globe (WebGL)":
        c_btn1, c_btn2 = st.columns([1, 3])
        with c_btn1:
            st.link_button("🚀 Open Full-Screen 3D Cesium Studio", "http://localhost:8088", type="primary", use_container_width=True)
        with c_btn2:
            st.caption("Active local 3D server: `http://localhost:8088` · Real 80m SRTM DEM GLB Mesh · Layer opacity sliders · 360° Drone Tour · Raycast Terrain Inspector")

        st.markdown(
            """
            <div style="border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 14px; overflow: hidden;
                        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6), 0 0 25px rgba(56, 189, 248, 0.12);">
            """,
            unsafe_allow_html=True,
        )
        components.iframe("http://localhost:8088/index.html", height=720, scrolling=True)
        st.markdown("</div>", unsafe_allow_html=True)

    elif twin_mode == "🏔️ Analytical Plotly 3D Surface Mesh":
        c_ov, c_ex = st.columns(2)
        with c_ov:
            selected_overlay = st.selectbox("Color terrain surface by", overlays_list)
        with c_ex:
            vert_exag = st.slider("Vertical Exaggeration", 1.0, 10.0, 3.0, 0.5)

        try:
            fig = create_terrain_figure_func(base_dir, selected_overlay, vert_exag)
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
        except Exception as e:
            st.error(f"Error rendering Plotly 3D surface: {e}")

    else:
        leaflet_path = base_dir / "results" / "digital_twin" / "tirumala_final_digital_twin.html"
        if leaflet_path.exists():
            components.html(leaflet_path.read_text(encoding="utf-8"), height=650, scrolling=True)
        else:
            st.warning(f"Leaflet HTML map not found at {leaflet_path}")


# -----------------------------------------------------------------------------
# TAB 3: CONTINUOUS MONITORING
# -----------------------------------------------------------------------------
def render_tab_monitoring():
    st.subheader("🛰️ Continuous Remote Sensing & Meteorological Monitoring")
    st.caption("Automated tracking of Sentinel-1 acquisitions, multi-temporal InSAR baseline pairs, and NASA GPM IMERG rainfall time series.")

    db = get_db()

    scheduler = _read_scheduler_telemetry()
    pipeline_state = _read_pipeline_telemetry()
    # Data discovery, download, processing, and rainfall are reported separately.
    with db.cursor() as cur:
        latest_discovered = cur.execute(
            "SELECT MAX(acquisition_date) FROM acquisitions WHERE satellite='Sentinel-1'"
        ).fetchone()[0]
        dl_cnt = cur.execute(
            "SELECT COUNT(*) FROM acquisitions WHERE download_status='DOWNLOADED'"
        ).fetchone()[0]
        pen_cnt = cur.execute(
            "SELECT COUNT(*) FROM acquisitions WHERE download_status='PENDING'"
        ).fetchone()[0]
        fail_cnt = cur.execute(
            "SELECT COUNT(*) FROM acquisitions WHERE download_status='FAILED'"
        ).fetchone()[0]
        latest_downloaded = cur.execute(
            "SELECT MAX(acquisition_date) FROM acquisitions "
            "WHERE satellite='Sentinel-1' AND download_status='DOWNLOADED'"
        ).fetchone()[0]
        latest_discovery_time = cur.execute(
            "SELECT completed_at FROM pipeline_logs WHERE stage_name='satellite_check' "
            "ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
        latest_successful_discovery = cur.execute(
            "SELECT completed_at FROM pipeline_logs WHERE stage_name='satellite_check' "
            "AND status IN ('SUCCESS', 'WARNING') AND message LIKE 'Satellite check:%searched%' "
            "ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
        latest_log = cur.execute(
            "SELECT stage_name, status, completed_at, message FROM pipeline_logs "
            "ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
        latest_successful_insar = cur.execute(
            "SELECT MAX(secondary_date) FROM insar_pairs WHERE processing_status='PROCESSED'"
        ).fetchone()[0]
    latest_rain = db.get_latest_rainfall_date()

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Latest S1 Acquisition Found", latest_discovered or "None", delta=_freshness_age(latest_discovered), delta_color="off")
    m2.metric("Latest S1 Downloaded", latest_downloaded or "None", delta=_freshness_age(latest_downloaded), delta_color="off")
    m3.metric("Pending Ingestion", f"{pen_cnt} Queued")
    m4.metric("Failed Downloads", f"{fail_cnt}")
    m5.metric("Latest Rainfall Observation", latest_rain or "None", delta=_freshness_age(latest_rain), delta_color="off")
    m6.metric("Latest Successful InSAR", latest_successful_insar or "None")

    try:
        stage5_status_path = PATHS.viewer_data / "stage5_monitoring_status.json"
        stage5_status = json.loads(stage5_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stage5_status = {}

    s1, s2, s3, s4 = st.columns(4)
    s1.metric(
        "Stage 5 Status",
        stage5_status.get("overall_status", "NOT_TESTED"),
    )
    s2.metric(
        "New Discovery",
        stage5_status.get("discovery", {}).get("new_acquisitions", 0),
    )
    s3.metric(
        "Candidate Pairs",
        stage5_status.get("processing", {}).get("candidate_pairs", 0),
    )
    s4.metric(
        "Valid SBAS Edges",
        stage5_status.get("network", {}).get("valid_edge_count", 0),
    )
    st.caption(
        "Discovery status: "
        f"{stage5_status.get('discovery', {}).get('status', 'NOT_TESTED')} · "
        "Real SBAS: "
        f"{'READY' if stage5_status.get('sbas', {}).get('real_ready') else 'INSUFFICIENT_DATA'} · "
        "Velocity: "
        f"{stage5_status.get('sbas', {}).get('velocity', 'VELOCITY_NOT_AVAILABLE')} · "
        "Latest processed: "
        f"{stage5_status.get('processing', {}).get('latest_processed_acquisition') or 'None'}"
    )

    try:
        phase6_status_path = PATHS.viewer_data / "master_phase6_status.json"
        phase6_status = json.loads(phase6_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        phase6_status = {}

    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Phase 6 Status", phase6_status.get("overall_status", "NOT_TESTED"))
    q2.metric(
        "Quality-Valid LOS Cells",
        phase6_status.get("live_pair", {}).get("quality_valid_pixel_count", 0),
    )
    q3.metric(
        "Valid Temporal Edges",
        phase6_status.get("network", {}).get("valid_edge_count", 0),
    )
    q4.metric(
        "Connected Components",
        phase6_status.get("network", {}).get("connected_components", 0),
    )
    st.caption(
        "Temporal inversion: "
        f"{phase6_status.get('temporal_inversion', {}).get('status', 'NOT_TESTED')} · "
        "Cumulative LOS: "
        f"{phase6_status.get('temporal_inversion', {}).get('cumulative_displacement_status', 'NOT_RELIABLE_WITH_SINGLE_PAIR')} · "
        "Velocity: "
        f"{phase6_status.get('temporal_inversion', {}).get('velocity_status', 'NOT_RELIABLE_WITH_SINGLE_PAIR')} · "
        "No synthetic deformation is shown."
    )

    try:
        final_status_path = PATHS.viewer_data / "master_final_status.json"
        final_status = json.loads(final_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        final_status = {}

    f1, f2, f3, f4 = st.columns(4)
    f1.metric(
        "Final Project Status",
        final_status.get("overall_status", "DEMONSTRATION_READY_WITH_LIMITATIONS"),
    )
    f2.metric(
        "Latest S1 Discovery",
        (
            final_status.get("monitoring_history", {})
            .get("latest_discovered_acquisition")
            or "None"
        ),
    )
    f3.metric(
        "Historical Alerts",
        final_status.get("monitoring_history", {}).get("alert_count", 0),
    )
    f4.metric(
        "Empirical Risk Cells",
        final_status.get("risk", {}).get("count", 0),
    )
    st.caption(
        "Risk is an empirical evidence index, not calibrated probability. "
        "Rainfall is study-area aggregate context and is not used as per-cell missing-zero data."
    )
    factor_availability = final_status.get("factor_availability", {})
    if factor_availability:
        with st.expander("Environmental factor availability"):
            st.json(factor_availability)

    try:
        phase5_status_path = PATHS.viewer_data / "master_phase5_status.json"
        phase5_status = json.loads(phase5_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        phase5_status = {}

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Phase 5 Status", phase5_status.get("overall_status", "WAITING_FOR_NEW_DATA"))
    p2.metric(
        "Selected Product",
        len(phase5_status.get("discovery", {}).get("selected_products", []))
        and phase5_status["discovery"]["selected_products"][0].get("acquisition_id", "None")
        or "None",
    )
    p3.metric(
        "Preprocessing Ready",
        phase5_status.get("preprocessing", {}).get("ready_product_count", 0),
    )
    p4.metric(
        "Automatic Download",
        phase5_status.get("download", {}).get("automatic_download", "DISABLED"),
    )
    st.caption(
        "Phase 5 pipeline: "
        f"CDSE={phase5_status.get('cdse', {}).get('status', 'NOT_TESTED')} · "
        f"download={phase5_status.get('download', {}).get('status', 'WAITING_FOR_NEW_DATA')} · "
        f"preprocessing={phase5_status.get('preprocessing', {}).get('status', 'NOT_TESTED')} · "
        "No HyP3 submission or credits used."
    )

    try:
        stage4_status_path = PATHS.viewer_data / "stage4_status.json"
        stage4_status = json.loads(stage4_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stage4_status = {}
    st.info(
        "Stage 4 acquisition/network status: "
        f"{stage4_status.get('overall_status', 'NOT_TESTED')} — "
        f"new acquisitions={stage4_status.get('discovery', {}).get('new_acquisition_count', 0)}, "
        f"candidate pairs={stage4_status.get('discovery', {}).get('candidate_pair_count', 0)}, "
        f"completed jobs={stage4_status.get('completed_hyp3_jobs', 0)}, "
        f"valid network edges={stage4_status.get('network', {}).get('valid_edge_count', 0)}."
    )
    try:
        phase3_status_path = PATHS.viewer_data / "phase3_gis_status.json"
        phase3_status = json.loads(
            phase3_status_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        phase3_status = {}
    st.info(
        "Phase 3 GIS evidence status: "
        f"{phase3_status.get('status', 'NOT_TESTED')} — "
        f"raster alignment={phase3_status.get('gis_alignment', {}).get('valid', False)}, "
        f"GSI points={phase3_status.get('gsi_inventory', {}).get('record_count', 0)}, "
        "LOS/Coherence/DEM/slope/aspect remain separate source layers."
    )

    st.caption(
        f"Last discovery attempt: {latest_discovery_time[0] if latest_discovery_time else 'Never'} · "
        f"Last successful data discovery: {latest_successful_discovery[0] if latest_successful_discovery else 'Never'} · "
        f"Latest acquisition record: {latest_discovered or 'None'} · "
        f"Scheduler: {'Running' if scheduler['running'] else 'Not running'} · "
        f"Next scheduled pipeline: {scheduler['next_pipeline_run'] or 'Unknown'} · "
        f"Current pipeline stage/status: "
        f"{pipeline_state.get('stage', latest_log['stage_name'] if latest_log else 'Not run')} — "
        f"{pipeline_state.get('status', latest_log['status'] if latest_log else 'Unknown')} · "
        f"{pipeline_state.get('message', '')}"
        if latest_log or pipeline_state else
        f"Last discovery attempt: {latest_discovery_time[0] if latest_discovery_time else 'Never'} · "
        f"Last successful data discovery: {latest_successful_discovery[0] if latest_successful_discovery else 'Never'} · "
        f"Latest acquisition record: {latest_discovered or 'None'} · "
        f"Scheduler: {'Running' if scheduler['running'] else 'Not running'} · "
        f"Next scheduled pipeline: {scheduler['next_pipeline_run'] or 'Unknown'} · "
        "No pipeline stage has run."
    )

    sub1, sub2, sub3, sub4 = st.tabs(["🌧️ Rainfall Time Series", "📐 InSAR Baseline Pairs", "📡 Satellite Acquisition History", "⚠️ Download & Retry Queue"])

    with sub1:
        st.markdown("#### NASA GPM IMERG Daily & Cumulative Antecedent Rainfall")
        with db.cursor() as cur:
            rain_rows = cur.execute(
                "SELECT record_date, daily_mean_mm, rolling_1day_mm, rolling_3day_mm, rolling_7day_mm, rolling_14day_mm "
                "FROM rainfall_records ORDER BY record_date"
            ).fetchall()
            if rain_rows:
                rdf = pd.DataFrame([dict(r) for r in rain_rows])
                rdf["record_date"] = pd.to_datetime(rdf["record_date"])

                fig_rain = go.Figure()
                fig_rain.add_trace(go.Bar(x=rdf["record_date"], y=rdf["daily_mean_mm"], name="Daily Mean (mm)", marker_color="#38bdf8"))
                fig_rain.add_trace(go.Scatter(x=rdf["record_date"], y=rdf["rolling_3day_mm"], name="3-Day Rolling (mm)", line=dict(color="#fbbf24", width=2.5)))
                fig_rain.add_trace(go.Scatter(x=rdf["record_date"], y=rdf["rolling_7day_mm"], name="7-Day Rolling (mm)", line=dict(color="#f97316", width=2.5)))
                fig_rain.add_trace(go.Scatter(x=rdf["record_date"], y=rdf["rolling_14day_mm"], name="14-Day Rolling (mm)", line=dict(color="#ef4444", width=3)))

                fig_rain.update_layout(
                    title="Antecedent Rainfall Time Series (GPM IMERG V07C)",
                    template="plotly_dark",
                    paper_bgcolor="rgba(15, 23, 42, 0.6)",
                    plot_bgcolor="rgba(15, 23, 42, 0.6)",
                    hovermode="x unified",
                    height=360,
                    margin=dict(l=20, r=20, t=40, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig_rain, use_container_width=True, config={"displaylogo": False})
                st.dataframe(rdf.sort_values("record_date", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("No rainfall records found in database.")

    with sub2:
        st.markdown("#### Multi-Temporal InSAR Pairs")
        st.write("Processed pairs for differential line-of-sight (LOS) displacement tracking.")
        pairs = db.get_insar_pairs()
        if pairs:
            st.dataframe(pd.DataFrame(pairs)[["pair_id", "reference_date", "secondary_date", "temporal_baseline_days", "perpendicular_baseline_m", "mean_coherence", "valid_pixels", "processing_status", "quality_notes"]], use_container_width=True, hide_index=True)
        else:
            st.info("No InSAR pairs registered yet.")

        st.caption("⚠️ **Scientific Caveat:** InSAR line-of-sight (LOS) displacement is measured relative to an unwrapped phase reference point. Differential pair subtraction must consider atmospheric phase screen variations and spatial baseline decorrelation.")

    with sub3:
        st.markdown("#### Sentinel-1 and Sentinel-2 Acquisition Catalog")
        with db.cursor() as cur:
            acqs = cur.execute("SELECT acquisition_id, satellite, product_type, sensor_mode, orbit_direction, acquisition_date, download_status, processing_status FROM acquisitions ORDER BY acquisition_date DESC").fetchall()
            if acqs:
                st.dataframe(pd.DataFrame([dict(r) for r in acqs]), use_container_width=True, hide_index=True)
            else:
                st.info("No satellite acquisitions registered in SQLite yet.")

    with sub4:
        st.markdown("#### ⚠️ Ingestion Status & Manual Retry Queue")
        st.caption(
            "Inspect acquisitions requiring attention. Downloads require explicit "
            "`S1_DOWNLOAD_ENABLED=true` approval and are never started by scheduler discovery."
        )

        with db.cursor() as cur:
            failed_pending = cur.execute(
                "SELECT acquisition_id, satellite, acquisition_date, download_status, error_message FROM acquisitions "
                "WHERE download_status IN ('FAILED', 'PENDING') ORDER BY acquisition_date DESC"
            ).fetchall()

        c_retry1, c_retry2 = st.columns([2, 4])
        with c_retry1:
            if st.button("🔎 Check Download Eligibility", type="primary", use_container_width=True):
                import os
                enabled = os.environ.get("S1_DOWNLOAD_ENABLED", "").strip().lower() in {"1", "true", "yes"}
                if enabled:
                    st.warning(
                        "Explicit approval is set. Use the controlled download CLI "
                        "for a selected product; the dashboard does not submit HyP3 jobs."
                    )
                else:
                    st.info(
                        "Automatic/manual dashboard downloads are blocked until "
                        "S1_DOWNLOAD_ENABLED=true is configured."
                    )

        with c_retry2:
            st.markdown(
                """
                > **Tip:** If downloads show `FAILED (CDSE credentials not configured)`, register a free account at [dataspace.copernicus.eu](https://dataspace.copernicus.eu/) and set `CDSE_USERNAME` and `CDSE_PASSWORD` in your project `.env` file.
                """
            )

        if failed_pending:
            st.dataframe(pd.DataFrame([dict(r) for r in failed_pending]), use_container_width=True, hide_index=True)
        else:
            st.info("No products are currently pending or failed in the download queue.")


# -----------------------------------------------------------------------------
# TAB 4: RISK ASSESSMENT & INTERACTIVE WHAT-IF SIMULATOR
# -----------------------------------------------------------------------------
def render_tab_risk_assessment(df):
    st.markdown("### 🎛️ Interactive 'What-If' Compound Risk Simulator")
    st.caption("Sensitivity analysis recalculates categories from the current spatial evidence; it is not a calibrated prediction. Missing indicators are excluded per cell.")

    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        w_slope = st.slider("⛰️ Horn's Slope Weight (%)", 0, 100, 40, step=5)
        w_dem = st.slider("📐 Terrain Elevation Weight (%)", 0, 100, 25, step=5)
    with sim_col2:
        w_insar = st.slider("📡 InSAR LOS Displacement Weight (%)", 0, 100, 20, step=5)
        w_temporal = st.slider("🕒 Temporal Evidence Weight (%)", 0, 100, 15, step=5)

    tot_weight = w_slope + w_dem + w_insar + w_temporal
    if tot_weight == 0:
        st.warning("Total weight must be greater than 0%.")
    else:
        from src.risk_assessment import build_spatial_risk

        simulated, _ = build_spatial_risk(
            df,
            weights={
                "slope_component": w_slope / 100,
                "terrain_component": w_dem / 100,
                "insar_component": w_insar / 100,
                "temporal_component": w_temporal / 100,
            },
        )
        if simulated.empty:
            st.info("No usable spatial evidence is available for this sensitivity analysis.")
        else:
            counts_by_category = simulated["risk_category"].value_counts()
            categories = ["Low", "Medium", "High"]
            values = [int(counts_by_category.get(category, 0)) for category in categories]
            total = sum(values)
            fig_sim = go.Figure(data=[go.Bar(
                x=[f"{category} Evidence" for category in categories],
                y=values,
                marker_color=["#10b981", "#f59e0b", "#ef4444"],
                text=[f"{count:,} cells ({count / total * 100:.1f}%)" for count in values],
                textposition="auto",
            )])
            fig_sim.update_layout(
                title=f"Re-scored Current Evidence (Total Weight: {tot_weight}%)",
                template="plotly_dark",
                paper_bgcolor="rgba(15, 23, 42, 0.6)",
                plot_bgcolor="rgba(15, 23, 42, 0.6)",
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_sim, use_container_width=True, config={"displaylogo": False})

    st.markdown("---")
    st.markdown("#### Historical Assessment Epochs & Transitions")
    db = get_db()
    hist = db.get_risk_history()
    if hist:
        hdf = pd.DataFrame(hist)
        cols_show = ["observation_date", "total_cells", "low_count", "medium_count", "high_count", "mean_risk_score", "max_risk_score", "persistent_high_cells"]
        cols_present = [c for c in cols_show if c in hdf.columns]
        st.dataframe(hdf[cols_present], use_container_width=True, hide_index=True)
    else:
        st.info("No historical assessment epochs stored in SQLite yet.")


# -----------------------------------------------------------------------------
# TAB 5: AUTOMATION STATUS
# -----------------------------------------------------------------------------
def render_tab_automation():
    st.subheader("⚙️ Background Automation & APScheduler Telemetry")
    st.caption("Status of recurring background ingestion workers, pipeline triggers, and operational audit trail.")

    db = get_db()

    scheduler = _read_scheduler_telemetry()
    pipeline_state = _read_pipeline_telemetry()
    with db.cursor() as cur:
        latest_acq = cur.execute(
            "SELECT MAX(acquisition_date) FROM acquisitions WHERE satellite='Sentinel-1'"
        ).fetchone()[0]
        latest_rain = db.get_latest_rainfall_date()
        latest_insar = db.get_latest_processed_insar_date()
        last_success_row = cur.execute(
            "SELECT completed_at FROM pipeline_logs WHERE stage_name='risk_assessment' "
            "AND status='SUCCESS' ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
        last_success_time = last_success_row[0] if last_success_row else "Never"
        latest_dl = cur.execute(
            "SELECT acquisition_id, acquisition_date FROM acquisitions "
            "WHERE download_status = 'DOWNLOADED' ORDER BY acquisition_date DESC LIMIT 1"
        ).fetchone()
        latest_dl_info = f"{latest_dl[0][:12]} ({latest_dl[1]})" if latest_dl else "None"
        pending_count = cur.execute("SELECT COUNT(*) FROM acquisitions WHERE download_status = 'PENDING'").fetchone()[0]
        failed_count = cur.execute("SELECT COUNT(*) FROM acquisitions WHERE download_status = 'FAILED'").fetchone()[0]
        latest_log = cur.execute(
            "SELECT run_id, stage_name, status, completed_at, message FROM pipeline_logs "
            "ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
        discovery_attempt = cur.execute(
            "SELECT completed_at, status FROM pipeline_logs WHERE stage_name='satellite_check' "
            "ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
        discovery_success = cur.execute(
            "SELECT completed_at FROM pipeline_logs WHERE stage_name='satellite_check' "
            "AND status IN ('SUCCESS', 'WARNING') AND message LIKE 'Satellite check:%searched%' "
            "ORDER BY log_id DESC LIMIT 1"
        ).fetchone()
        discovery_time = discovery_attempt["completed_at"] if discovery_attempt else None
        twin_sync = cur.execute(
            "SELECT completed_at FROM pipeline_logs WHERE stage_name='refresh_viewer' "
            "AND status='SUCCESS' ORDER BY log_id DESC LIMIT 1"
        ).fetchone()

    # The viewer marker is written only after export stages complete.
    sync_status_path = PATHS.viewer_data / "sync_status.json"
    try:
        sync_status = json.loads(sync_status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        sync_status = {}

    cdse_configured = bool(
        os.environ.get("CDSE_USERNAME") and os.environ.get("CDSE_PASSWORD")
    )
    earthdata_configured = bool(
        (
            os.environ.get("EARTHDATA_USERNAME")
            and os.environ.get("EARTHDATA_PASSWORD")
        )
        or (
            os.environ.get("HYP3_USERNAME")
            and os.environ.get("HYP3_PASSWORD")
        )
    )
    hyp3_configured = earthdata_configured
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8088/", timeout=1.5) as response:
            cesium_available = response.status == 200
    except Exception:
        cesium_available = False

    def _provider_card(title, icon, configured, detail):
        state = "CONFIGURED" if configured else "NOT CONFIGURED"
        border = "16, 185, 129" if configured else "245, 158, 11"
        state_color = "#34d399" if configured else "#fbbf24"
        return (
            '<div style="background: rgba(15, 23, 42, 0.8); '
            f'border: 1px solid rgba({border}, 0.45); border-radius: 12px; '
            'padding: 14px 16px;">'
            '<div style="display: flex; align-items: center; justify-content: space-between;">'
            f'<span style="font-weight: 700; color: {state_color}; font-size: 13px;">'
            f'{icon} {escape(title)}</span>'
            f'<span style="background: {state_color}; color: #082f49; '
            f'font-size: 10px; font-weight: 800; padding: 2px 7px; '
            f'border-radius: 10px;">{state}</span></div>'
            f'<div style="font-size: 11.5px; color: #94a3b8; margin-top: 5px;">'
            f'{escape(detail)}</div></div>'
        )

    st.markdown(
        '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-bottom: 18px;">'
        + _provider_card(
            "Copernicus CDSE",
            "🛰️",
            cdse_configured,
            "Sentinel-1/2 discovery; configuration does not confirm authentication.",
        )
        + _provider_card(
            "NASA Earthdata",
            "🌧️",
            earthdata_configured,
            "IMERG and Earthdata access; GES DISC status remains separate.",
        )
        + _provider_card(
            "ASF HyP3",
            "⚡",
            hyp3_configured,
            "InSAR cloud processing; existing verified pair is preserved.",
        )
        + """
            <div style="background: rgba(15, 23, 42, 0.8);
                        border: 1px solid rgba(56, 189, 248, 0.45); border-radius: 12px; padding: 14px 16px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-weight: 700; color: #38bdf8; font-size: 13px;">🌐 Cesium 3D Server</span>
                    <span style="background: """ + ("#34d399" if cesium_available else "#fbbf24") + """; color: #082f49; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 10px;">""" + ("ONLINE" if cesium_available else "OFFLINE") + """</span>
                </div>
                <div style="font-size: 11.5px; color: #94a3b8; margin-top: 5px;">
                    Host: <b style="color: #f1f5f9;">http://localhost:8088</b><br>
                    Existing real 80 m DEM WebGL Terrain Studio
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    a1, a2, a3, a4 = st.columns(4)
    scheduler_label = (
        f"Running ({scheduler['interval_hours']}h)"
        if scheduler["running"] else "Not running"
    )
    a1.metric("Scheduler State", scheduler_label)
    a2.metric("Last Successful Risk Assessment", last_success_time)
    a3.metric("Latest Downloaded", latest_dl_info)
    a4.metric("Download Queue", f"{pending_count} PENDING", f"{failed_count} FAILED" if failed_count > 0 else "0 FAILED", delta_color="inverse")
    st.caption(
        f"Last discovery attempt: "
        f"{discovery_attempt['completed_at'] if discovery_attempt else 'Never'}"
        f" ({discovery_attempt['status'] if discovery_attempt else 'No status'}) · "
        f"Last successful data discovery: "
        f"{discovery_success[0] if discovery_success else 'Never'} · "
        f"Next scheduled pipeline: {scheduler['next_pipeline_run'] or 'Unknown'} · "
        f"Last successful Digital Twin synchronization: "
        f"{twin_sync[0] if twin_sync else 'Never'} · "
        f"Viewer export status: {sync_status.get('status', 'Unknown')} · "
        f"Latest processed observation: {sync_status.get('latest_observation_date') or 'None'}"
    )
    if latest_log:
        st.info(
            f"Current pipeline stage/status: "
            f"{pipeline_state.get('stage', latest_log['stage_name'])} — "
            f"{pipeline_state.get('status', latest_log['status'])}. "
            f"{pipeline_state.get('message', latest_log['message'] or '')}"
        )
    elif pipeline_state:
        st.info(
            f"Current pipeline stage/status: {pipeline_state.get('stage', 'Unknown')} — "
            f"{pipeline_state.get('status', 'Unknown')}. {pipeline_state.get('message', '')}"
        )

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        if st.button("🚀 Trigger Master Pipeline Now", type="primary", use_container_width=True):
            from automation.pipeline import MasterPipeline
            pipe = MasterPipeline(dry_run=False)
            res = pipe.run_all()
            status_messages = [
                f"{name}: {stage['status']} — {stage['message'] or stage['error']}"
                for name, stage in res.stages.items()
                if stage["status"] not in {"SUCCESS", "SKIPPED"}
            ]
            if res.success:
                st.success(f"Pipeline completed successfully. Run ID: {res.run_id}")
            else:
                st.error(
                    f"Pipeline completed with blocked or failed stages. Run ID: {res.run_id}"
                )
                for message in status_messages:
                    st.warning(message)
            st.rerun()
    with b2:
        if st.button("📡 Check Satellite Data", use_container_width=True):
            from scripts.download_sentinel1 import Sentinel1Downloader
            s1_dl = Sentinel1Downloader(dry_run=True)
            end_date = datetime.now(timezone.utc)
            start_date = (end_date - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            res = s1_dl.run(start_date, end_date.strftime("%Y-%m-%d"))
            st.info(f"Satellite check: {res.get('searched',0)} products found.")
    with b3:
        if st.button("🔄 Sync Database & Export 3D", use_container_width=True):
            from src.digital_twin.layer_exporter import export_all_gis_layers
            from scripts.update_database import export_cesium_lookups
            export_all_gis_layers(PATHS.root, PATHS.viewer_cesium, db=db)
            sync = export_cesium_lookups(db)
            st.success(f"Viewer export status: {sync.get('status', 'Unknown')}")
            st.rerun()
    with b4:
        if st.button("🔁 Retry Failed Downloads", use_container_width=True):
            from scripts.download_sentinel1 import Sentinel1Downloader
            from scripts.download_sentinel2 import Sentinel2Downloader
            s1 = Sentinel1Downloader()
            s1.retry_pending_and_failed()
            s2 = Sentinel2Downloader()
            s2.retry_pending_and_failed()
            st.info("Download retry attempt completed.")
            st.rerun()

    st.markdown("---")
    st.markdown("#### Operational Component Status Matrix")
    status_matrix = [
        {"Stage": "Satellite discovery", "Status": "Recorded" if discovery_time else "Not run", "Current State": f"Latest Sentinel-1 acquisition date: {latest_acq or 'None'}"},
        {"Stage": "Satellite download", "Status": f"{pending_count} pending / {failed_count} failed", "Current State": f"Latest downloaded product: {latest_dl_info}"},
        {"Stage": "Rainfall ingestion", "Status": "Available" if latest_rain else "No records", "Current State": f"Latest observation: {latest_rain or 'None'}"},
        {"Stage": "Preprocessing", "Status": "See latest stage log", "Current State": "Downloaded archives are not marked processed until preprocessing succeeds"},
        {"Stage": "InSAR", "Status": "Processed baseline available" if latest_insar else "No processed pairs", "Current State": f"Latest processed secondary date: {latest_insar or 'None'}"},
        {"Stage": "U-Net", "Status": "Experimental; requires complete optical input", "Current State": "Landslide4Sense benchmark is not Tirumala validation"},
        {"Stage": "Risk assessment", "Status": "Latest stored result", "Current State": f"Observation date: {db.get_risk_summary().get('observation_date') or 'None'}"},
        {"Stage": "3D Digital Twin", "Status": sync_status.get("status", "Unknown"), "Current State": f"Last successful export: {twin_sync[0] if twin_sync else 'Never'}"},
        {"Stage": "Alerts", "Status": f"{len(db.get_active_alerts())} pending human review", "Current State": "Notification configuration is shown below"},
    ]
    st.dataframe(pd.DataFrame(status_matrix), use_container_width=True, hide_index=True)
    notification_missing = []
    if not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_CHAT_ID"):
        notification_missing.append("Telegram bot token/chat ID")
    if not os.environ.get("SMTP_USERNAME") or not os.environ.get("SMTP_PASSWORD") or not os.environ.get("ALERT_EMAIL_TO"):
        notification_missing.append("SMTP username/password/recipient")
    st.caption(
        "Missing notification configuration: "
        + (", ".join(notification_missing) if notification_missing else "None")
    )

    st.markdown("---")
    st.markdown("#### Pipeline Execution Log History")
    logs = db.get_pipeline_logs(limit=30)
    if logs:
        st.dataframe(pd.DataFrame(logs)[["run_id", "stage_name", "status", "started_at", "duration_seconds", "records_processed", "message"]], use_container_width=True, hide_index=True)
    else:
        st.info("No pipeline execution logs recorded yet.")


# -----------------------------------------------------------------------------
# TAB 6: ALERTS & REPORTS
# -----------------------------------------------------------------------------
def render_tab_alerts():
    st.subheader("🚨 Intelligent Decision-Support Alert System")
    st.caption("Compound hazard condition alerts generated automatically for human expert review, geotechnical validation, and field verification.")

    db = get_db()
    alerts = db.get_all_alerts(limit=50)

    if not alerts:
        st.success("✅ No active hazard alerts triggered at this time.")
        return

    crit_cnt = sum(1 for a in alerts if a.get("severity") == "CRITICAL")
    warn_cnt = sum(1 for a in alerts if a.get("severity") == "WARNING")
    info_cnt = sum(1 for a in alerts if a.get("severity") == "INFO")

    st.markdown(
        f"""
        <div style="display: flex; gap: 12px; margin-bottom: 18px; flex-wrap: wrap;">
            <div style="background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 10px; padding: 10px 18px;">
                <span style="color: #ef4444; font-weight: 800; font-size: 16px;">{crit_cnt}</span>
                <span style="color: #fca5a5; font-size: 12.5px; font-weight: 600; margin-left: 6px;">Critical Alerts</span>
            </div>
            <div style="background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 10px; padding: 10px 18px;">
                <span style="color: #f59e0b; font-weight: 800; font-size: 16px;">{warn_cnt}</span>
                <span style="color: #fde68a; font-size: 12.5px; font-weight: 600; margin-left: 6px;">Warning Alerts</span>
            </div>
            <div style="background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 10px; padding: 10px 18px;">
                <span style="color: #38bdf8; font-weight: 800; font-size: 16px;">{info_cnt}</span>
                <span style="color: #bae6fd; font-size: 12.5px; font-weight: 600; margin-left: 6px;">Advisory Alerts</span>
            </div>
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 10px 18px;">
                <span style="color: #f8fafc; font-weight: 800; font-size: 16px;">{len(alerts)}</span>
                <span style="color: #94a3b8; font-size: 12.5px; font-weight: 600; margin-left: 6px;">Total Registered</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for al in alerts:
        sev = al.get("severity", "INFO")
        status = al.get("verification_status", "PENDING")
        badge = "🔴 CRITICAL" if sev == "CRITICAL" else "🟡 WARNING" if sev == "WARNING" else "🔵 INFO"
        border_color = "#ef4444" if sev == "CRITICAL" else "#f59e0b" if sev == "WARNING" else "#38bdf8"
        bg_tint = "rgba(239, 68, 68, 0.05)" if sev == "CRITICAL" else "rgba(245, 158, 11, 0.05)" if sev == "WARNING" else "rgba(56, 189, 248, 0.05)"

        with st.expander(f"{badge} | {al.get('trigger_rule')} ({al.get('alert_timestamp', '')[:16]}) — Status: {status}"):
            st.markdown(
                f"""
                <div style="background: {bg_tint}; border-left: 4px solid {border_color}; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;">
                    <div style="font-weight: 700; color: #f8fafc; font-size: 14px; margin-bottom: 4px;">{al.get('summary_text')}</div>
                    <div style="color: #94a3b8; font-size: 12.5px; line-height: 1.5;"><b>Recommended Action:</b> {al.get('recommended_action')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.caption(f"📍 Affected Cells: {al.get('affected_cells_count')} | Max Score: {al.get('max_risk_score', 0):.1f} | Center: {al.get('center_latitude', 0):.4f}°N, {al.get('center_longitude', 0):.4f}°E")
                if al.get("triggering_indicators"):
                    try:
                        ind = json.loads(al.get("triggering_indicators"))
                        st.json(ind)
                    except Exception:
                        pass
            with col_b:
                st.write(f"**Verification:** `{status}`")
                if status == "PENDING":
                    if st.button("Mark Verified", key=f"ver_{al['alert_id']}", use_container_width=True):
                        db.update_alert_status(al["alert_id"], "VERIFIED", verified_by="Expert User", notes="Verified by operator")
                        st.rerun()
                    if st.button("False Alarm", key=f"fa_{al['alert_id']}", use_container_width=True):
                        db.update_alert_status(al["alert_id"], "FALSE_ALARM", verified_by="Expert User", notes="Deemed atmospheric/decorrelation noise")
                        st.rerun()

    st.markdown("---")
    st.caption("⚖️ **Notice:** All alerts are automated decision-support outputs. They do not constitute official disaster declarations without verification by Geological Survey of India (GSI) or local authorities.")
