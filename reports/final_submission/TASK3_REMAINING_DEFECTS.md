# Task 3: Remaining Defects

## P0

No P0 defect identified.

## P1

1. **External notification delivery**
   - Telegram and SMTP are unconfigured.
   - Database delivery count is zero.
   - This is not a project-breaking defect because no real-user delivery was requested.

2. **Cesium terrain inspector not fully automated**
   - The inspector UI renders and accepts its panel state.
   - A reproducible automated terrain raycast was not completed.
   - The existing source has raycast logic, so this needs browser geometry verification rather than a database or model change.

## P2

1. **Reset View may be obstructed by expanded HUD overlays**
   - Browser automation could not reliably click Reset View while panels/inspector overlays occupied the toolbar area.
   - Proposed fix: add a small z-index/pointer-area correction after approval.

2. **Missing Cesium favicon**
   - Server logs show `/favicon.ico` returns 404.
   - Proposed fix: add an existing project favicon or remove the browser favicon reference.

3. **Streamlit theme/deprecation warnings**
   - Sidebar theme values trigger browser console warnings.
   - Streamlit 1.55 logs repeated `use_container_width` deprecation warnings.
   - Proposed fixes are cosmetic and should be done only in a later approved cleanup.

## P3

1. Add browser-level automated navigation tests.
2. Add inspector raycast test coordinates.
3. Add screenshot capture automation.
4. Improve notification configuration diagnostics.

## Fixes performed

No fixes were performed. The task found no clear P1 source defect that could be safely corrected without further UI geometry or configuration approval.
