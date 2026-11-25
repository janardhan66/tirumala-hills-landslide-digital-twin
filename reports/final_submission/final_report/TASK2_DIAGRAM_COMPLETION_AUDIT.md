# Task 2 Diagram Completion Audit

## Diagrams improved

The following editable Mermaid source files were updated with a consistent academic layout, readable labels and directional flow:

1. `SYSTEM_ARCHITECTURE.mmd`
2. `DATA_PROCESSING_WORKFLOW.mmd`
3. `EMPIRICAL_RISK_ASSESSMENT.mmd`
4. `AI_ML_EXPERIMENTAL_WORKFLOW.mmd`

## Exact file paths

- `reports/final_submission/visual_evidence/diagrams/SYSTEM_ARCHITECTURE.mmd`
- `reports/final_submission/visual_evidence/diagrams/DATA_PROCESSING_WORKFLOW.mmd`
- `reports/final_submission/visual_evidence/diagrams/EMPIRICAL_RISK_ASSESSMENT.mmd`
- `reports/final_submission/visual_evidence/diagrams/AI_ML_EXPERIMENTAL_WORKFLOW.mmd`

No rendered PNG or SVG diagram files were created.

## Rendering status

- Mermaid CLI: unavailable in the existing environment.
- Graphviz: unavailable.
- Global/preinstalled Mermaid package: unavailable.
- No package installation or download was performed.
- Editable Mermaid source files are complete and suitable for later rendering.

## Implementation accuracy

### System architecture

The architecture separates:

- Sentinel-1/HyP3 input;
- DEM and terrain derivatives;
- GPM IMERG rainfall context;
- GSI historical locations;
- preprocessing and 80 m EPSG:32644 alignment;
- SQLite storage;
- empirical risk assessment;
- Streamlit and Cesium presentation;
- Gemini assistant; and
- periodic/event-driven scheduler and alert records.

The Gemini assistant is shown outside the risk computation engine.

### Data processing workflow

The source shows acquisition, preprocessing, coordinate alignment, grid generation, quality filtering, feature extraction, scoring, SQLite storage and visualization.

### Empirical risk

The source preserves the exact factor weights:

- Slope percentile: 40%.
- Terrain evidence: 25%.
- InSAR evidence: 20%.
- Temporal evidence: 15%.

Missing factors are excluded and available weights are renormalized. The output is labeled as a relative empirical evidence index, not a calibrated probability.

### AI/ML experiments

The Random Forest and U-Net branches are separate benchmark workflows based on Landslide4Sense data. Both are explicitly labeled experimental and not validated Tirumala prediction models.

## Report references updated

The report List of Figures now distinguishes embedded PNG figures from source-only Mermaid files. No Mermaid source file is represented as a rendered figure.

## Unresolved issues

- Rendered PNG/SVG versions require an existing Mermaid CLI or institution-provided rendering tool.
- The report should not claim that source-only Mermaid diagrams are displayed as rendered images until files are generated.

## Application modification confirmation

No application code, database, trained model, dataset, configuration or risk formula was modified.
