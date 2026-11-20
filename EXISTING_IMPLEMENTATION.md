# EXISTING IMPLEMENTATION DEEP DIVE: TIRUMALA DIGITAL TWIN

**Document Version:** 1.0  
**Project Study Area:** Tirumala Hills, Tirupati District, Andhra Pradesh, India  
**Geographic Extent:** $79.337^\circ\text{E}$ to $79.423^\circ\text{E}$, $13.639^\circ\text{N}$ to $13.693^\circ\text{N}$  
**Projected Coordinate System:** WGS 84 / UTM Zone 44N (EPSG:32644)  

---

## 1. End-to-End Existing Data Flow

The existing system transforms multi-source remote-sensing and in-situ records into spatial feature tables, risk classifications, and visualization layers through the following pipeline:

```text
[ Sentinel-1 SAR HyP3 SLCs ] ──> Pair 1 (05-17 Aug) & Pair 2 (17-29 Aug)
                                         │
[ Copernicus / GLO-30 DEM ] ───> 80 m DEM (EPSG:32644) ──> Horn's Slope (deg)
                                         │
[ NASA GPM/IMERG Daily ] ──────> Daily precip & 1d, 3d, 7d, 14d rolling sums
                                         │
[ GSI Report Fig 3.2 ] ────────> 15 Approximate Historical Landslide Points
                                         │
                                         v
               [ scripts/create_final_agent_evidence.py ]
                                         │
     ┌───────────────────────────────────┴───────────────────────────────────┐
     v                                                                       v
[ Spatial Evidence Table ]                                     [ Temporal InSAR Table ]
2,650 valid grid records                                       2,569 common-coherence records
(Elevation, Slope, LOS, Corr, Dist)                            (LOS Pair 1, LOS Pair 2, ΔLOS)
     │                                                                       │
     └───────────────────────────────────┬───────────────────────────────────┘
                                         v
                         [ src/risk_assessment.py ]
                     Weighted Relative Evidence Scoring
                     (Slope 40%, Terrain 25%, InSAR 20%, Temporal 15%)
                                         │
     ┌───────────────────────────────────┴───────────────────────────────────┐
     v                                                                       v
[ 2D Leaflet GIS Map ]                                         [ 3D Plotly Terrain Mesh ]
Folium HTML with InSAR overlay                                 Georeferenced UTM surface
and GSI marker tooltips                                        with 4 multi-layer colormaps
     │                                                                       │
     └───────────────────────────────────┬───────────────────────────────────┘
                                         v
                      [ Canonical Streamlit Dashboard ]
                      dashboard/app.py (Running on Port 8501)
```

---

## 2. InSAR Processing & Remote Sensing Baseline

The InSAR analysis was generated from Sentinel-1 descending orbit interferometric wide-swath (IW) single-look complex (SLC) acquisitions processed using ASF HyP3 with GLO-30 DEM, adaptive phase filtering (`adf`, parameter 0.6), and minimum cost flow (MCF) phase unwrapping at 80 m spatial resolution.

### Sentinel-1 Pair Specifications

| Parameter | Pair 1 (Baseline Period) | Pair 2 (Monitoring Period) |
| :--- | :--- | :--- |
| **Acquisition Dates** | 05 August 2026 – 17 August 2026 | 17 August 2026 – 29 August 2026 |
| **Temporal Baseline** | 12 days | 12 days |
| **Perpendicular Baseline** | $-14.39\text{ m}$ | $+66.97\text{ m}$ |
| **Phase Reference Point** | $13.3218^\circ\text{N},\ 78.6698^\circ\text{E}$ | $14.1223^\circ\text{N},\ 78.6950^\circ\text{E}$ |
| **Reference Distance** | ~89 km apart | ~89 km apart |
| **Grid Dimensions** | $110 \times 69$ pixels (80 m cell size) | $110 \times 69$ pixels (80 m cell size) |
| **Coordinate System** | EPSG:32644 (UTM Zone 44N) | EPSG:32644 (UTM Zone 44N) |
| **Valid Pixels ($\gamma \ge 0.5$)** | 3,085 pixels | 2,957 pixels |

> [!IMPORTANT]
> **Scientific Caveat Preserved in Repository:**  
> Because the two HyP3 interferograms use independent phase reference points located 89 km apart, the raw arithmetic difference ($\Delta\text{LOS} = \text{LOS}_2 - \text{LOS}_1$) contains differential phase offsets and residual orbital/atmospheric ramps. It is treated as an exploratory indicator rather than a calibrated millimetric ground displacement time series.

---

## 3. Feature Datasets and Schema Specifications

The project maintains two core tabular datasets in `data/features/`:

### 3.1 Spatial Evidence Dataset (`tirumala_final_agent_evidence.csv`)
- **Total Records:** 2,650 rows
- **Spatial Resolution:** 80 m grid pixels inside the GSI-AOI boundary
- **Columns:**
  - `row`, `col`: Integer raster matrix indices ($[0..68], [0..109]$).
  - `x_utm`, `y_utm`: Easting and Northing coordinates in meters (EPSG:32644).
  - `latitude`, `longitude`: WGS84 geographic coordinates for mapping.
  - `elevation_m`: Terrain height above sea level (meters). Range: $192.4\text{ m}$ to $884.2\text{ m}$.
  - `slope_deg`: Surface inclination calculated using Horn's algorithm. Range: $0.8^\circ$ to $47.3^\circ$.
  - `correlation`: Coherence of Pair 2 ($\gamma$). Range: $0.50$ to $0.98$ (quality screened).
  - `los_disp_m`: Line-of-sight displacement in Pair 2 (meters). Range: $-0.048\text{ m}$ to $+0.012\text{ m}$.
  - `dist_to_gsi_km`: Euclidean distance to nearest historical GSI landslide point.
  - `terrain_high_evidence`: Boolean flag ($\text{slope} \ge 25^\circ \land \text{elevation} \ge 500\text{ m}$).
  - `insar_high_evidence`: Boolean flag ($|\text{LOS}| \ge 15\text{ mm} \land \gamma \ge 0.65$).
  - `agent_evidence_score`: Composite relative score ($0–100$).
  - `agent_evidence_category`: Discrete category (`Low`, `Medium`, `High`).

### 3.2 Temporal Evidence Dataset (`tirumala_temporal_insar_features.csv`)
- **Total Records:** 2,569 rows (pixels with valid coherence in both Pair 1 and Pair 2)
- **Columns:**
  - `row`, `col`: Grid cell spatial key for joining with spatial records.
  - `los_05_17_m`: LOS displacement in Pair 1 (meters).
  - `los_17_29_m`: LOS displacement in Pair 2 (meters).
  - `los_change_m`: Direct differential change ($\text{LOS}_{\text{Pair 2}} - \text{LOS}_{\text{Pair 1}}$).
  - `abs_los_change_m`: Magnitude of differential change (meters).
  - `corr_05_17`: Coherence during Pair 1.
  - `corr_17_29`: Coherence during Pair 2.
  - `temporal_evidence_flag`: Binary indicator of high relative differential shift.

---

## 4. Topographic & Rainfall Processing

### 4.1 Digital Elevation Model (DEM) and Slope
- **Source:** Copernicus GLO-30 DEM resampled to 80 m spatial resolution.
- **Raster File:** `data/processed/dinsar/tirumala/gsi_aoi/tirumala_dem_80m_gsi_aoi.tif`
- **Bounds:** Left: $319,720.0\text{ m}$, Bottom: $1,508,840.0\text{ m}$, Right: $328,520.0\text{ m}$, Top: $1,514,360.0\text{ m}$.
- **Slope Calculation:** Implemented in `src/features/calculate_slope.py` using Horn's finite-difference gradient:
  $$\text{Slope} = \arctan\left(\sqrt{\left(\frac{\partial z}{\partial x}\right)^2 + \left(\frac{\partial z}{\partial y}\right)^2}\right) \times \frac{180}{\pi}$$

### 4.2 NASA GPM/IMERG Rainfall
- **Source:** NASA GPM IMERG Final Daily Product (`3B-DAY-L.GIS.IMERG.V07C`)
- **Coverage:** 11 August 2026 through 29 August 2026 (19 daily GeoTIFF files)
- **Features Extracted:** Implemented in `scripts/calculate_rainfall_features.py`:
  - Daily mean precipitation ($\text{mm/day}$).
  - 3-day antecedent rainfall ($\text{mm}$).
  - 7-day cumulative rainfall ($\text{mm}$).
  - 14-day cumulative rainfall ($\text{mm}$).
- **Role in Model:** Serves as temporal hazard context for the entire study area; not used as a pixel-specific spatial predictor.

---

## 5. Machine Learning & Deep Learning Implementation

### 5.1 PyTorch 14-Channel U-Net Architecture
- **Source Code:** `src/models/landslide_segmentation.py`
- **Saved Checkpoint:** `models/landslide_unet_14channel_best.pth` (7.5 MB)
- **Input Shape:** `(Batch, 14, 128, 128)`
- **Output Shape:** `(Batch, 1, 128, 128)` (logits thresholded at 0.50 via Sigmoid)
- **14 Input Channels:**
  - Channels 0–11: Multi-spectral optical bands (Sentinel-2 L2A equivalents).
  - Channel 12: Topographic Slope.
  - Channel 13: Digital Elevation Model (DEM).
- **Network Depth:** 4-stage encoder ($32 \to 64 \to 128 \to 256$ bottleneck) and 4-stage decoder with transposed convolutions and skip concatenations.
- **Trained Benchmark Metrics (Landslide4Sense test split):**
  - Checkpoint Batch Overlap Dice: **0.6561**
  - Checkpoint Batch Overlap IoU: **0.5101**
  - Epoch: 3
- **Inference Verification:** The checkpoint was verified by running inference on `image_5.h5` and `image_100.h5`, producing binary segmentation masks and prediction confidence overlays.

### 5.2 Random Forest Models
- **Files:** `models/landslide_random_forest.joblib` (147 MB) and `models/landslide_random_forest_v2.joblib` (1.2 GB)
- **Input Features:** Only `slope` and `elevation`.
- **Status:** Trained strictly on Landslide4Sense patch samples. It is intentionally omitted from the canonical dashboard to prevent unvalidated spatial predictions across Tirumala Hills.

---

## 6. Multi-Criteria Risk Assessment Engine

Implemented in `src/risk_assessment.py`, the evidence index synthesizes multi-modal observations into a continuous score ($0–100$) using relative percentile ranking and normalized feature weights:

$$\text{Risk Score} = \frac{\sum_{i} w_i \cdot c_i}{\sum_{i} w_i}$$

Where the weights and components are:
1. **Slope Component ($w_1 = 0.40$):** Percentile rank of terrain slope within the Tirumala AOI ($0–100\%$).
2. **Terrain Component ($w_2 = 0.25$):** Binary flag for high elevation ($>500\text{ m}$) and steep slope ($>25^\circ$).
3. **InSAR Component ($w_3 = 0.20$):** Significant LOS displacement ($>15\text{ mm}$) with high coherence ($\gamma \ge 0.65$).
4. **Temporal Component ($w_4 = 0.15$):** Upper-quartile differential displacement between Pair 1 and Pair 2.

### Classification Bands:
- **Low Risk:** $\text{Score} < 33.33$
- **Medium Risk:** $33.33 \le \text{Score} < 66.67$
- **High Risk:** $\text{Score} \ge 66.67$

---

## 7. Interactive Digital Twin Implementations

The project currently provides two complementary Digital Twin interfaces:

### 7.1 2D Folium/Leaflet GIS Map
- **File:** `results/digital_twin/tirumala_final_digital_twin.html` (3.0 MB)
- **Basemaps:** Esri World Imagery (Satellite) and OpenStreetMap.
- **Layers:**
  - Study Area Boundary (Red polygon with centroid at $13.6768^\circ\text{N}, 79.3738^\circ\text{E}$).
  - InSAR LOS Displacement semi-transparent georeferenced raster image overlay.
  - Historical GSI landslide point markers with interactive popup metadata.
  - Quality mask and monitoring zone boundary overlays.
  - Collapsible custom CSS legend and layer toggle control.

### 7.2 3D Plotly Elevation Mesh
- **File:** `src/digital_twin/terrain_3d.py`
- **Underlying Grid:** 80 m UTM Zone 44N grid ($110 \times 69$ nodes).
- **Supported Visualizations:**
  1. **Elevation Surface:** Colored using `Earth` colormap ($192\text{ m}$ to $884\text{ m}$).
  2. **Slope Surface:** Colored using `Turbo` colormap ($0^\circ$ to $50^\circ$).
  3. **Pair 2 Coherence Surface:** Colored using `Viridis` colormap ($0.0$ to $1.0$).
  4. **Pair 2 LOS Displacement Surface:** Colored using symmetric `RdBu` colormap.
- **Interactive Controls:** Dynamic vertical exaggeration slider ($1.0\times$ to $10.0\times$), camera orbital rotation, coordinate readouts on hover, and full responsive container stretching.

---

## 8. Canonical Dashboard Architecture

- **Primary Entrypoint:** `dashboard/app.py` (Streamlit 1.x / 2.0 compatible)
- **Port:** `8501`
- **Sections:**
  1. **Header & Context:** Title, study area metadata, research disclaimer.
  2. **System Health Metrics:** Total spatial records (2,650), temporal records (2,569), historical points (15), rainfall accumulation.
  3. **HDF5 U-Net Inference Workspace:** Drag-and-drop 14-channel patch upload, segmentation mask rendering, threshold slider ($0.10–0.90$), and timestamped CSV reporting in `outputs/reports/`.
  4. **Evidence Class Distribution:** Distribution of Low/Medium/High classes.
  5. **Rainfall Context Panel:** Antecedent precipitation time series.
  6. **Reference Region Screening Diagnostics:** Moran's I permutation tests and Region 1 stability analysis.
  7. **Digital Twin Workspace:** Two dedicated side-by-side tabs:
     - `🗺️ 2D Digital Twin (GIS Map)`: Embedded Folium HTML iframe.
     - `🏔️ 3D Digital Twin (Terrain Mesh)`: Live Plotly 3D elevation mesh with overlay switcher.
  8. **Intelligent Agent Q&A Interface:** Deterministic keyword-driven query answering engine supporting queries regarding project methodology, data limitations, and monitoring suggestions.
