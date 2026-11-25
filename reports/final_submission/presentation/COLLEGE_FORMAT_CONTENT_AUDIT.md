# College-Format Presentation Content Audit

## Final output

- Original master: `JANA_MINI_PPT.pptx`
- Updated output: `FINAL_PROJECT_PRESENTATION_COLLEGE_FORMAT.pptx`
- Original slide count retained: 52
- Required master structure: retained in-place; slides were updated rather than recreated.

## Structure retained

The 52-slide master was retained as the source package and its original slide order, layouts, slide-number placeholders and theme elements were preserved.

The project sequence is represented in the master positions, including:

- Title, abstract, domain, SDG, aim, research questions and objectives
- Scope, timeline, introduction, literature studies and gap analysis
- SDLC and Agile rationale
- Use case, activity, sequence and requirements
- Dataset, collection, preprocessing and feature extraction
- Architecture and modules
- Algorithms, setup, dashboard and results
- Digital twin, InSAR, assistant, comparison, conclusion and references

## Visual design retained

- Original PPT theme, fonts, title placement, footer/slide numbering, table styles and layout positions are inherited from the master.
- Four rendered diagrams and verified screenshots were inserted proportionally into relevant original slide image areas.
- Images were fitted by aspect ratio and were not stretched.

## Verified image placements

- System architecture: rendered `SYSTEM_ARCHITECTURE.png`
- Data processing: rendered `DATA_PROCESSING_WORKFLOW.png`
- Empirical risk: rendered `EMPIRICAL_RISK_ASSESSMENT.png`
- AI/ML benchmark: rendered `AI_ML_EXPERIMENTAL_WORKFLOW.png`
- Dashboard overview: `01_dashboard_overview.png`
- Risk assessment: `02_risk_assessment.png`
- Cesium terrain: `07_cesium_3d_terrain.png` and polished variant
- Cesium InSAR epochs: `09_cesium_insar_epochs.png`
- Cesium layers: `08_cesium_layers.png`
- Gemini assistant: `06_gemini_assistant.png`

## Technical fact verification

- Study area: Tirumala Hills, Tirupati, Andhra Pradesh.
- Grid: 69 × 110; resolution: 80 m; CRS: EPSG:32644.
- November InSAR pair: 9–21 November 2026.
- Quality-valid LOS/coherence cells: 5,034.
- LOS is documented as line-of-sight displacement, not vertical displacement.
- GPM IMERG is contextual and excluded from the per-cell risk formula.
- GSI locations are approximate map-derived locations.
- Landslide4Sense is an external benchmark dataset.
- SQLite, Streamlit, CesiumJS and Gemini are implemented components.
- APScheduler is described as periodic/event-driven.
- Full suite: 150 passed, 12 warnings, 6 subtests passed.

## Risk methodology

- Slope percentile: 40%
- Terrain evidence: 25%
- InSAR evidence: 20%
- Temporal evidence: 15%
- Missing factors are excluded and remaining weights are renormalized.
- Low: below 33.3333
- Medium: 33.3333 to below 66.6667
- High: 66.6667 and above
- The output is explicitly a relative empirical evidence index, not calibrated probability.

## Unsupported claims removed or qualified

- No 238-pixel or 1.45% U-Net predicted-area claim.
- No 82.06% predicted-positive claim.
- No 0.6561 Dice or 0.5101 IoU claim.
- RF and U-Net metrics are benchmark-only and not Tirumala-validated.
- No autonomous continuous real-time monitoring claim.
- No operational early-warning claim.
- Gemini is not presented as an independent landslide predictor.
- No configured Telegram/SMTP alert delivery claim.
- GSI locations are not presented as surveyed ground truth.

## Text and slide validation

- Slide count: 52
- Shape-boundary check: passed
- Long text boxes requiring manual review: [(23, 'TextBox 5', 986)]
- Original slide numbering and captions remain in the master package.

## Placeholder status

Institutional details already supplied in the master are preserved:

- Y. Janardhan Reddy – 238W1A5466
- B. Meghana – 248W5A5402
- R. Hariteja – 238W1A5452
- K. Charishma – 248W5A5406
- Guide: Dr. P. Ramesh Kumar
- VR Siddhartha Engineering College, Vijayawada
- Department of Artificial Intelligence and Data Science
- Batch No: 25

No unprovided academic-year or approval placeholders were invented.

## Modification scope

No application code, datasets, models, database, configuration or risk formula was modified.
