# Final Critical Issues

## P0 - Prevents operation or risks data loss

No P0 issue was identified. SQLite integrity is `ok`, the project database was backed up, and no production records were changed.

## P1 - Breaks an important feature or final demonstration

1. **Streamlit server not reachable at the audit endpoint**
   - Smallest fix: start the existing Streamlit app and verify `http://localhost:8501`.

2. **Cesium server not reachable at port 8088**
   - Smallest fix: start the existing Cesium server and verify `layers_manifest.json` and browser controls.

3. **External notification delivery unverified**
   - Notification deliveries: 0.
   - Smallest fix: verify existing Telegram/SMTP configuration without adding a new delivery system.

4. **Gemini assistant not runtime-verified**
   - Smallest fix: confirm the existing Gemini credential and run one read-only query.

5. **Rainfall integration remains inconsistent**
   - Multiple daily/rollup files disagree in source coverage and cannot provide pixel-level rainfall.
   - Smallest fix: document as aggregate context and reconcile only existing matched database records.

## P2 - Cosmetic or documentation issue

1. Test warnings include a Gemini test that returns a boolean instead of an assertion.
2. UTC `datetime.utcnow()` deprecation warnings remain.
3. Submission documents should clearly identify live-server limitations.

## P3 - Future enhancement

1. Acquire independent Tirumala positive and negative ground truth.
2. Reconcile pixel-level rainfall or acquire a valid raster.
3. Complete Sentinel-2/land-cover predictor acquisition.
4. Add geographically blocked local ML validation.
5. Add calibrated uncertainty and explainability.

## Smallest safe next fixes

1. Start existing web servers.
2. Verify one Gemini request.
3. Verify alert delivery configuration.
4. Correct dashboard status messaging only if runtime evidence proves a mismatch.
5. Do not modify ML artifacts, risk formula or historical data.
