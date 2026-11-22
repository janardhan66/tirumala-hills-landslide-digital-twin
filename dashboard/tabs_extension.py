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
from datetime import datetime
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
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 58, 138, 0.45) 50%, rgba(15, 23, 42, 0.95) 100%);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
        }
        .twin-hero-title {
            font-size: 23px;
            font-weight: 800;
            background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
            letter-spacing: -0.3px;
        }
        .twin-badge-container {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .twin-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            color: #f1f5f9;
        }
        .twin-pill.live {
            border-color: #10b981;
            color: #34d399;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.25);
        }
        </style>

        <div class="twin-hero-banner">
            <div class="twin-hero-title">🏔️ TIRUMALA HILLS LANDSLIDE DIGITAL TWIN & MONITORING DASHBOARD</div>
            <div style="color: #94a3b8; font-size: 13.5px;">InSAR observations, NASA GPM precipitation, and evidence-based risk assessment</div>
            <div class="twin-badge-container">
                <span class="twin-pill">Background monitoring runs only while its scheduler is running</span>
                <span class="twin-pill">🛰️ Sentinel-1 InSAR (80m)</span>
                <span class="twin-pill">🌧️ NASA GPM IMERG</span>
                <span class="twin-pill">⚠️ Compound Risk Engine</span>
                <span class="twin-pill">🌐 CesiumJS WebGL 3D</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Study Area: Tirumala Hills, Tirupati District, Andhra Pradesh, India "
        f"({STUDY_AREA.bbox_south:.3f}°N–{STUDY_AREA.bbox_north:.3f}°N, {STUDY_AREA.bbox_west:.3f}°E–{STUDY_AREA.bbox_east:.3f}°E)"
    )

    db = get_db()
    counts = db.get_table_counts()

    # Top KPI cards
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Spatial Grid Nodes", f"{counts.get('spatial_evidence_grid', 0):,}", help="80m analytical grid in EPSG:32644")
    with k2:
        st.metric("Observation Records", f"{counts.get('observation_snapshots', 0):,}", help="Timestamped evidence snapshots")
    with k3:
        st.metric("Rainfall History", f"{counts.get('rainfall_records', 0)} Days", help="Daily NASA GPM IMERG records")
    with k4:
        st.metric("Active Alerts", f"{counts.get('alerts', 0)}", help="Decision-support alerts requiring review")

    with st.expander("⚡ Monitoring workflow and current operating limits", expanded=False):
        st.markdown(
            r"""
            The scheduler must be running separately from this dashboard. Product
            discovery, downloads, raster preprocessing, InSAR processing, risk
            assessment, and viewer synchronization have separate statuses below.
            A catalog result or local baseline is not evidence that a new product
            was downloaded or processed. InSAR processing is unavailable until a
            configured processor and valid scene pair are available.
            """
        )

    st.markdown("---")

    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.markdown("#### 🛰️ Data Availability & Telemetry Status")
        status_data = [
            {"Source": "Copernicus Sentinel-1 SAR", "Product": "IW SLC Descending", "Latest Date": db.get_latest_processed_insar_date() or "Not processed", "Status": "From processed InSAR pairs", "Quality": "LOS is not vertical displacement"},
            {"Source": "Copernicus GLO-30 DEM", "Product": "Digital Elevation & Horn Slope", "Latest Date": "Static Baseline", "Status": "Local baseline", "Quality": "Elevation and slope inputs"},
            {"Source": "NASA GPM IMERG", "Product": "Final Daily Precipitation (V07C)", "Latest Date": db.get_latest_rainfall_date() or "No observations", "Status": "Local records", "Quality": "Daily + Rolling 1-14d"},
            {"Source": "Historical Landslide Inventory", "Product": "GSI Figure 3.2 digitized records", "Latest Date": "Historical", "Status": "Active", "Quality": "15 hazard points mapped"},
            {"Source": "Evidence Risk Engine", "Product": "Relative evidence scoring", "Latest Date": (db.get_risk_summary().get("observation_date") or "Not assessed"), "Status": "Latest stored assessment", "Quality": "Not a calibrated probability"},
        ]
        st.dataframe(pd.DataFrame(status_data), use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("#### ⚖️ Overall Hazard Breakdown")
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
            hole=0.6,
            marker_colors=["#10b981", "#f59e0b", "#ef4444"],
            textinfo="label+percent",
            hoverinfo="label+value+percent",
        )])
        fig_donut.update_layout(
            showlegend=False,
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=250,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_donut, use_container_width=True, config={"displaylogo": False})

    # Interactive Google Gemini Intelligent Agent
    render_gemini_assistant()


# -----------------------------------------------------------------------------
# INTERACTIVE GEMINI AGENT COMPONENT
# -----------------------------------------------------------------------------
def render_gemini_assistant():
    st.markdown("---")
    st.markdown("### 🤖 Ask Google Gemini Intelligent Agent")
    st.caption("Ask questions about Tirumala Hills landslide hazard zones, InSAR line-of-sight displacement, rainfall thresholds, or mitigation measures.")

    # Preset quick question buttons
    q_cols = st.columns(3)
    preset_q = None
    with q_cols[0]:
        if st.button("📍 Vulnerable Ghat Road Zones", use_container_width=True):
            preset_q = "What are the most vulnerable slope zones along Ghat Road 1 and Ghat Road 2 in Tirumala Hills?"
    with q_cols[1]:
        if st.button("🌧️ Rainfall Hazard Thresholds", use_container_width=True):
            preset_q = "How does 3-day accumulated rainfall affect landslide risk in the Tirumala region?"
    with q_cols[2]:
        if st.button("📐 InSAR Displacement & Coherence", use_container_width=True):
            preset_q = "Explain why InSAR coherence gamma >= 0.50 is critical for verifying ground displacement."

    col_input, col_ask = st.columns([5, 1])
    with col_input:
        default_val = preset_q if preset_q else ""
        user_query = st.text_input(
            "Question for Intelligent Agent",
            value=default_val,
            placeholder="Ask anything about Tirumala landslide monitoring...",
            label_visibility="collapsed",
        )
    with col_ask:
        trigger_ask = st.button("💬 Ask AI", type="primary", use_container_width=True) or (preset_q is not None)

    if trigger_ask and user_query:
        with st.spinner("🤖 Gemini Intelligent Agent formulating response..."):
            try:
                from google import genai
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    st.error("GEMINI_API_KEY is not set in .env.")
                    return
                client = genai.Client(api_key=api_key)

                # Ground live project facts in fixed, read-only database queries.
                db = get_db()
                with db.cursor() as cur:
                    latest_discovered = cur.execute(
                        "SELECT acquisition_date, download_status, satellite "
                        "FROM acquisitions ORDER BY created_at DESC LIMIT 1"
                    ).fetchone()
                    latest_downloaded = cur.execute(
                        "SELECT acquisition_date, satellite FROM acquisitions "
                        "WHERE download_status = 'DOWNLOADED' "
                        "ORDER BY acquisition_date DESC LIMIT 1"
                    ).fetchone()
                latest_rain = db.get_latest_rainfall_date()
                rain_rec = db.get_rainfall_range(latest_rain, latest_rain) if latest_rain else []
                rain_3d = rain_rec[0].get("rolling_3day_mm") if rain_rec else None
                rain_7d = rain_rec[0].get("rolling_7day_mm") if rain_rec else None
                risk_summary = db.get_risk_summary()
                active_alerts = db.get_active_alerts()
                alert_count = len(active_alerts)
                alert_titles = ", ".join(
                    a.get("trigger_rule", "") for a in active_alerts[:3]
                ) or "None"
                processed_pairs = db.get_insar_pairs(status="PROCESSED")
                latest_pair = processed_pairs[0] if processed_pairs else None
                unavailable = "Not available"
                documentation = []
                for document in (PATHS.root / "README.md", PATHS.root / "PROJECT_AUDIT.md"):
                    if document.is_file():
                        documentation.append(
                            f"--- {document.name} ---\n"
                            + document.read_text(encoding="utf-8")[:5000]
                        )
                project_docs = "\n\n".join(documentation)

                system_context = (
                    "You are the Intelligent Landslide Monitoring Agent for Tirumala Hills, Tirupati, Andhra Pradesh, India.\n"
                    "Treat the current database telemetry and supplied project documentation as evidence. "
                    "Report missing values as unavailable; do not infer missing data or claim prediction certainty.\n"
                    "Current database telemetry:\n"
                    f"- Latest discovered catalog entry: {dict(latest_discovered) if latest_discovered else unavailable}\n"
                    f"- Latest downloaded product: {dict(latest_downloaded) if latest_downloaded else unavailable}\n"
                    f"- Latest rainfall observation: {latest_rain or unavailable}; "
                    f"3-day={rain_3d if rain_3d is not None else unavailable} mm; "
                    f"7-day={rain_7d if rain_7d is not None else unavailable} mm\n"
                    f"- Latest stored risk assessment: {risk_summary.get('observation_date') or unavailable}; "
                    f"high-evidence share={risk_summary.get('high_pct') if risk_summary.get('total_cells') else unavailable}% "
                    f"of {risk_summary.get('total_cells', 0)} cells\n"
                    f"- Pending human-review alerts: {alert_count} ({alert_titles})\n"
                    f"- Latest processed InSAR pair: {latest_pair or unavailable}\n"
                    "Project documentation excerpts:\n"
                    f"{project_docs}\n\n"
                    "Answer using the evidence above. Do not execute SQL or modify monitoring records."
                )

                res = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents=f"{system_context}\n\nUser Question: {user_query}",
                )
                if res and res.text:
                    st.markdown(
                        f"""
                        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid #38bdf8; border-radius: 10px; padding: 18px 22px; margin-top: 14px; box-shadow: 0 4px 20px rgba(56, 189, 248, 0.15);">
                            <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #38bdf8; font-size: 15px; margin-bottom: 8px;">
                                <span>🤖 Gemini Intelligent Agent:</span>
                            </div>
                            <div style="color: #f1f5f9; font-size: 14px; line-height: 1.65;">
                                {escape(res.text).replace(chr(10), '<br>')}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            except Exception as e:
                st.error(f"Error querying Gemini Agent: {e}")


# -----------------------------------------------------------------------------
# TAB 2: INTERACTIVE 3D DIGITAL TWIN
# -----------------------------------------------------------------------------
def render_tab_3d_digital_twin(base_dir, create_terrain_figure_func, overlays_list):
    st.subheader("🏔️ Realistic 3D Digital Twin of Tirumala Hills")
    st.caption("Geospatially registered multi-layer environment combining real terrain elevation, InSAR fringes, slope, and historical hazards.")

    twin_mode = st.radio(
        "Select Visualization Engine",
        ["🛰️ CesiumJS 3D Geospatial Globe (WebGL)", "🏔️ Analytical Plotly 3D Surface Mesh", "🗺️ 2D Interactive Leaflet GIS Map"],
        horizontal=True,
    )

    if twin_mode == "🛰️ CesiumJS 3D Geospatial Globe (WebGL)":
        st.info(
            "🛰️ **CesiumJS 3D Globe Viewer:** Drapes satellite basemaps and project rasters over genuine 3D terrain elevation. "
            "Click anywhere on the mountain surface to raycast real-time elevation, slope angle, InSAR displacement, and risk."
        )
        c_btn1, c_btn2 = st.columns([1, 4])
        with c_btn1:
            st.link_button("🚀 Fullscreen 3D Viewer", "http://localhost:8088", type="primary")
        with c_btn2:
            st.caption("The viewer refreshes exported data while open; background monitoring requires the separate scheduler.")

        components.iframe("http://localhost:8088/index.html", height=680, scrolling=True)

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
        st.caption("Inspect acquisitions requiring attention. If credentials were added to .env, click below to retry downloads.")

        with db.cursor() as cur:
            failed_pending = cur.execute(
                "SELECT acquisition_id, satellite, acquisition_date, download_status, error_message FROM acquisitions "
                "WHERE download_status IN ('FAILED', 'PENDING') ORDER BY acquisition_date DESC"
            ).fetchall()

        c_retry1, c_retry2 = st.columns([2, 4])
        with c_retry1:
            if st.button("🔁 Retry Pending / Failed Downloads", type="primary", use_container_width=True):
                with st.spinner("Retrying downloads from CDSE..."):
                    from scripts.download_sentinel1 import Sentinel1Downloader
                    from scripts.download_sentinel2 import Sentinel2Downloader
                    s1 = Sentinel1Downloader()
                    res1 = s1.retry_pending_and_failed()
                    s2 = Sentinel2Downloader()
                    res2 = s2.retry_pending_and_failed()
                    st.info(f"Retry result — S1: {res1.get('downloaded',0)} downloaded, {res1.get('failed',0)} failed. S2: {res2.get('downloaded',0)} downloaded, {res2.get('failed',0)} failed.")
                    st.rerun()

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
    st.subheader("⚠️ Multi-Criteria Relative Landslide Evidence Assessment")
    st.caption("Evidence synthesis combines available slope (40%), terrain geometry (25%), InSAR displacement (20%), and temporal pair difference (15%). Rainfall is shown separately because the available rainfall values are not spatially resolved.")

    db = get_db()
    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown("#### Methodology & Indicator Weights")
        st.markdown(
            r"""
            $$\text{Risk Score} = 0.40 \times \text{Slope Pct} + 0.25 \times \text{Terrain Flag} + 0.20 \times \text{InSAR Flag} + 0.15 \times \text{Temporal Flag}$$
            - **Slope Component (40%):** Local percentile rank of Horn's slope angle ($0^\circ–47.3^\circ$).
            - **Terrain Component (25%):** High elevation ($>500\text{ m}$) and steep terrain ($>25^\circ$).
            - **InSAR Component (20%):** Significant LOS displacement ($>15\text{ mm}$) with coherence $\gamma \ge 0.65$.
            - **Temporal Component (15%):** Upper-quartile differential displacement between Pair 1 and Pair 2.
            """
        )

    with c2:
        st.markdown("#### Evidence Score Thresholds")
        st.markdown(
            r"""
            - 🟢 **Low Evidence:** Score $< 33.33$
            - 🟡 **Medium Evidence:** $33.33 \le \text{Score} < 66.67$
            - 🔴 **High Evidence:** $\text{Score} \ge 66.67$
            """
        )

    st.markdown("---")
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
            start_date = (datetime.utcnow() - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
            res = s1_dl.run(start_date, datetime.utcnow().strftime("%Y-%m-%d"))
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
    st.caption("Compound hazard condition alerts generated automatically for human expert review and field verification.")

    db = get_db()
    alerts = db.get_all_alerts(limit=50)

    if not alerts:
        st.success("✅ No active hazard alerts triggered at this time.")
        return

    st.markdown(f"**Total Registered Alerts:** {len(alerts)}")

    for al in alerts:
        sev = al.get("severity", "INFO")
        status = al.get("verification_status", "PENDING")
        badge = "🔴 CRITICAL" if sev == "CRITICAL" else "🟡 WARNING" if sev == "WARNING" else "🔵 INFO"

        with st.expander(f"{badge} | {al.get('trigger_rule')} ({al.get('alert_timestamp', '')[:16]}) - Status: {status}"):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"**Summary:** {al.get('summary_text')}")
                st.write(f"**Recommended Action:** {al.get('recommended_action')}")
                st.caption(f"Affected Cells: {al.get('affected_cells_count')} | Max Score: {al.get('max_risk_score', 0):.1f} | Center: {al.get('center_latitude', 0):.4f}°N, {al.get('center_longitude', 0):.4f}°E")
                if al.get("triggering_indicators"):
                    try:
                        ind = json.loads(al.get("triggering_indicators"))
                        st.json(ind)
                    except Exception:
                        pass
            with col_b:
                st.write(f"**Current Status:** `{status}`")
                if status == "PENDING":
                    if st.button("Mark Verified", key=f"ver_{al['alert_id']}", use_container_width=True):
                        db.update_alert_status(al["alert_id"], "VERIFIED", verified_by="Expert User", notes="Verified by operator")
                        st.rerun()
                    if st.button("False Alarm", key=f"fa_{al['alert_id']}", use_container_width=True):
                        db.update_alert_status(al["alert_id"], "FALSE_ALARM", verified_by="Expert User", notes="Deemed atmospheric/decorrelation noise")
                        st.rerun()

    st.markdown("---")
    st.caption("⚖️ **Notice:** All alerts are automated decision-support outputs. They do not constitute official disaster declarations without verification by Geological Survey of India (GSI) or local authorities.")
