# Presentation Content Audit

## Output

- File: `FINAL_PROJECT_PRESENTATION.pptx`
- Slides: 15
- Format: Widescreen 16:9
- Images embedded: 8

## Source documents inspected

- `FINAL_PROJECT_REPORT.md`
- `FINAL_REPORT_ACCURACY_AUDIT.md`
- `TASK2_1_RENDERING_AUDIT.md`
- `TASK1_1_FINAL_CONSISTENCY_AUDIT.md`

## Evidence assets used

- `visual_evidence/diagrams/SYSTEM_ARCHITECTURE.png`
- `visual_evidence/diagrams/DATA_PROCESSING_WORKFLOW.png`
- `visual_evidence/diagrams/EMPIRICAL_RISK_ASSESSMENT.png`
- `visual_evidence/diagrams/AI_ML_EXPERIMENTAL_WORKFLOW.png`
- `visual_evidence/07_cesium_3d_terrain_polished.png`
- `visual_evidence/01_dashboard_overview.png`
- `visual_evidence/02_risk_assessment.png`
- `visual_evidence/06_gemini_assistant.png`

## Slide verification

| Slide | Topic | Verified content |
|---|---|---|
| 1 | Title | Project title and unresolved institutional fields retained as placeholders |
| 2 | Introduction | Landslide context, Tirumala monitoring and digital-twin role |
| 3 | Problem Statement | Conventional limitations and need for aligned evidence |
| 4 | Objectives | Five requested implementation objectives |
| 5 | Study Area and Datasets | Tirumala, Sentinel-1, DEM, GPM, GSI and Landslide4Sense |
| 6 | System Architecture | Actual rendered architecture PNG |
| 7 | Data Processing Workflow | Actual rendered workflow PNG |
| 8 | Digital Twin | Actual CesiumJS screenshot and verified layer description |
| 9 | Risk Assessment | Actual rendered diagram; 40/25/20/15 weights and relative-index disclaimer |
| 10 | Monitoring Dashboard | Actual Streamlit screenshots and implemented capabilities |
| 11 | AI/ML Experimental Work | Actual benchmark workflow; benchmark-only disclaimers |
| 12 | Intelligent Assistant | Actual Gemini screenshot; no independent prediction claim |
| 13 | Results and Testing | Verified grid, CRS, resolution, InSAR pair and test totals |
| 14 | Limitations and Future Scope | Report-audit limitations and proposed enhancements |
| 15 | Conclusion and Q&A | Project summary and Thank You / Questions |

## Claim verification

- Grid is `69 × 110`, at `80 m` resolution, in `EPSG:32644`.
- November InSAR pair: `2026-11-09` to `2026-11-21`.
- Quality-valid LOS/coherence cells: `5,034`.
- LOS is described as line-of-sight displacement, not vertical displacement.
- Test suite: `150 passed, 12 warnings, 6 subtests passed`.
- Risk weights: Slope percentile `40%`, terrain evidence `25%`, InSAR evidence `20%`, temporal evidence `15%`.
- Random Forest and U-Net are explicitly benchmark-only and do not drive the live map.
- GSI locations are identified as approximate.
- Alert notifications are identified as not configured.

## Structural validation

- Exact slide count: 15; required slide count: 15.
- All embedded image paths exist and use `contain`-style fitting.
- No image is stretched: every image is proportionally fitted within its frame.
- Shape-boundary check: passed; no shapes extend outside slide boundaries.
- Student name, roll number, department, college, guide and academic year remain placeholders where unknown.
- No application, database, dataset, model, configuration or risk formula was modified.

## Notes

- Mermaid diagrams are included through their verified PNG renderings.
- Dashboard and Cesium screenshots are actual project screenshots.
- No new performance claims or calibrated probability claims were introduced.
