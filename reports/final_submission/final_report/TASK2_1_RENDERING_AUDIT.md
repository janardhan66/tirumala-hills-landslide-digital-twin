# Task 2.1 Mermaid Rendering Audit

## Syntax validation

All four Mermaid source files passed basic syntax inspection:

- Block delimiters and arrows were inspected.
- Subgraphs, labels and quoted text were checked.
- The corrected architecture scheduler edge uses Mermaid-compatible dotted-edge syntax.
- No source contains an unsupported or malformed edge label.

The Kroki rendering service successfully parsed and rendered all four sources, providing stronger syntax validation than static text inspection.

## Rendered file paths

| Diagram | SVG | PNG | PNG dimensions |
|---|---|---|---|
| System Architecture | `visual_evidence/diagrams/SYSTEM_ARCHITECTURE.svg` | `visual_evidence/diagrams/SYSTEM_ARCHITECTURE.png` | 1920 × 577 |
| Data Processing Workflow | `visual_evidence/diagrams/DATA_PROCESSING_WORKFLOW.svg` | `visual_evidence/diagrams/DATA_PROCESSING_WORKFLOW.png` | 2100 × 418 |
| Empirical Risk Assessment | `visual_evidence/diagrams/EMPIRICAL_RISK_ASSESSMENT.svg` | `visual_evidence/diagrams/EMPIRICAL_RISK_ASSESSMENT.png` | 936 × 816 |
| AI/ML Experimental Workflow | `visual_evidence/diagrams/AI_ML_EXPERIMENTAL_WORKFLOW.svg` | `visual_evidence/diagrams/AI_ML_EXPERIMENTAL_WORKFLOW.png` | 1166 × 374 |

All SVG files passed XML parsing. All PNG files passed PIL opening and integrity checks.

## Visual inspection

- The data-processing workflow was inspected and has a clear horizontal A4-friendly layout.
- The architecture, risk and AI/ML diagrams were rendered successfully with readable node boxes and directed arrows.
- The source labels were checked against implemented project terminology.
- No node was identified as clipped in the SVG viewBox.
- The risk diagram clearly separates weights, missing-factor handling and category thresholds.

## Project accuracy

- GPM IMERG is shown as rainfall context, not a per-cell risk formula input.
- Gemini is shown as a project assistant, separate from the empirical risk engine.
- RF and U-Net are shown as benchmark-only workflows.
- The exact weights of 40%, 25%, 20% and 15% are preserved.
- Low/Medium/High thresholds are preserved.
- Monitoring remains described as periodic or event-driven.

## Report references updated

The report List of Figures was updated to reference:

- `Figure 13.1 – System architecture`
- `Figure 18.1 – Data processing workflow`
- `Figure 21.1 – Empirical risk assessment workflow`
- `Figure 22.1 – AI/ML experimental workflow`

Each reference points to an existing PNG file.

## Resolved report paths

The following relative paths resolve correctly from `reports/final_submission/final_report/FINAL_PROJECT_REPORT.md`:

- `../visual_evidence/diagrams/SYSTEM_ARCHITECTURE.png`
- `../visual_evidence/diagrams/DATA_PROCESSING_WORKFLOW.png`
- `../visual_evidence/diagrams/EMPIRICAL_RISK_ASSESSMENT.png`
- `../visual_evidence/diagrams/AI_ML_EXPERIMENTAL_WORKFLOW.png`

## Remaining issues

- The AI/ML workflow retains small text if printed at a large reduction; it is landscape-oriented and readable at normal A4 width.
- The architecture and data-processing SVG dimensions are wide and are best placed across the full report page or in landscape presentation slides.

No application code, database, model, dataset, configuration or risk formula was modified.
