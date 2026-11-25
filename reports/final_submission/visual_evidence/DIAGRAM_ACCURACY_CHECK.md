# Diagram Accuracy Check

## Editable Mermaid sources

| Diagram | Source |
|---|---|
| Overall system architecture | `diagrams/SYSTEM_ARCHITECTURE.mmd` |
| Data processing workflow | `diagrams/DATA_PROCESSING_WORKFLOW.mmd` |
| Empirical risk assessment | `diagrams/EMPIRICAL_RISK_ASSESSMENT.mmd` |
| AI/ML experimental workflow | `diagrams/AI_ML_EXPERIMENTAL_WORKFLOW.mmd` |

## Accuracy review

### System architecture

- Sentinel-1/HyP3 is separated from DEM and rainfall/GSI context.
- CRS/grid alignment and quality filtering occur before evidence scoring.
- SQLite is the storage tier.
- Streamlit and Cesium are separate presentation surfaces.
- Gemini is grounded in database telemetry.
- The scheduler/alerts are connected to database/audit flow.
- Benchmark RF/U-Net branches are explicitly disconnected from the live risk map.

### Data workflow

- Acquisition, preprocessing, CRS alignment, NoData/coherence filtering and feature extraction are represented.
- Rainfall and GSI remain contextual and uncertain.
- Database storage precedes visualization.

### Empirical risk

- Weights remain 40/25/20/15.
- Missing factors are excluded and available weights are renormalized.
- Low/Medium/High thresholds match the implementation.
- Output is explicitly labeled relative and not calibrated.

### AI/ML

- Landslide4Sense HDF5 data drives RF/U-Net experiments.
- RF/U-Net outputs remain benchmark-only.
- No diagram or source suggests Tirumala validation or live dashboard integration.

## Rendering status

PNG/SVG rendering support was not available. Mermaid source files were preserved because `mmdc` and Graphviz `dot` were unavailable. No package installation was performed.
