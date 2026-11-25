# Final Report Accuracy Audit

## 1. Facts checked

| Fact | Verified value | Source |
|---|---:|---|
| Grid | 69 × 110 = 7,590 | Config and raster metadata |
| CRS | EPSG:32644 | Raster and source reports |
| Resolution | 80 m | Raster metadata |
| DEM valid | 4,083 | Raster audit |
| Slope valid | 3,692 | Raster audit |
| Aspect valid | 4,083 | Raster audit |
| November quality-valid LOS/coherence | 5,034 | Phase 6 report |
| GSI points | 15 | GeoJSON and feature inventory |
| HDF5 patches | 3,799 | Dataset audit |
| RF v3 rows | 190,644 | RF audit |
| RF v3 duplicates | 12,388 | RF audit |
| RF accuracy | 0.5626637 | Reproduced evaluation |
| RF balanced accuracy | 0.5623652 | Reproduced evaluation |
| RF precision | 0.5575985 | Reproduced evaluation |
| RF recall | 0.5423923 | Reproduced evaluation |
| RF F1 | 0.5498903 | Reproduced evaluation |
| InSAR job | `3889d809-88a3-4a93-89a5-258821932737` | Database and Phase 6 |
| Pair dates | 2026-11-09 to 2026-11-21 | Database and Phase 6 |
| LOS range | -0.1119190753 to -0.0537146255 m | Phase 6 |
| Alerts | 33 | Database/browser audit |
| Observation snapshots | 45,554 | Database audit |
| Notification deliveries | 0 | Database audit |
| Relevant tests | 23 passed, 8 warnings | Task 2/3 reruns |
| Full suite | 150 passed, 12 warnings, 6 subtests | Final rerun |

## 2. Deliberately excluded or qualified claims

- No Tirumala RF local accuracy claim.
- No U-Net Tirumala validation claim.
- No calibrated landslide probability claim.
- No vertical displacement claim.
- No cumulative displacement or velocity claim.
- No claim of continuous second-by-second monitoring.
- No claim of successful Telegram/SMTP delivery.
- No claim that GSI points are surveyed ground truth.
- No claim that rainfall is per-cell pixel data.
- No claim that absence of historical landslide records proves safe terrain.

## 3. Unresolved information requiring student/guide confirmation

1. Student name, roll number and academic year.
2. Department, college and university.
3. Project guide name.
4. Exact GSI report title and bibliographic details.
5. Any institution-mandated report format or citation style.
6. Exact final approved certificate/declaration wording.
7. Approved references for COOLR and GSI material.

## 4. Document-generation audit

- Markdown report: created.
- DOCX report: not created because the `python-docx` package is unavailable.
- No package installation was performed.
- Existing project reports were preserved.
- No source code, database, model, risk formula or configuration was modified.

## 5. Academic review audit

- Grammar and repetitive text were reduced.
- The abstract was condensed and kept technically limited.
- The problem statement, scope and methodology were clarified.
- Figure references were checked against the visual evidence folder.
- Mermaid diagrams are documented as editable sources, not as rendered figures.
- Bibliography entries do not contain inferred authors or publication metadata.
- GSI and COOLR bibliographic details remain unresolved and are marked for manual verification.

## 6. Task 1.1 consistency corrections

- Corrected the List of Figures to list actual embedded screenshots and source-only Mermaid files.
- Removed unsupported spatial-grid and InSAR workflow images from the figure list.
- Standardized embedded figure numbering to chapter-based Figure 23.1 and Figure 23.2.
- Added explicit titles for spatial-grid, risk, RF, results, test and appendix tables.
- Verified rainfall reconciliation and retained the unresolved 27-record status.
- Clarified RF v2 reproduction against the v3 patch-grouped split.
- Confirmed that no application or project-data file is changed by report editing.
