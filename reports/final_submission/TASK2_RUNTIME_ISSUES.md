# Task 2: Runtime Issues

## P0

No P0 issue was identified. Both applications are reachable and no data loss or unsafe production operation occurred.

## P1

1. **External notification delivery is not configured or verified**
   - Telegram and SMTP settings are unavailable.
   - Notification delivery count is zero.
   - Smallest safe fix: configure existing credentials only after approval and verify locally without sending to real users.

2. **Gemini browser conversational test was not submitted**
   - Live API connectivity succeeded.
   - The browser UI response path was not exercised with a real question.
   - Smallest fix: submit one safe read-only question in the existing UI.

3. **Cesium cell raycast inspector was not click-verified**
   - Inspector controls rendered.
   - Actual terrain-cell raycast was not completed.
   - Smallest fix: perform one no-state-change terrain click in browser verification.

## P2

1. Streamlit browser console has invalid theme sidebar color warnings.
2. Streamlit logs recommend replacing deprecated `use_container_width` usages.
3. Cesium has an absent `favicon.ico`, resulting in HTTP 404.

## P3

1. Consolidate browser console/config warnings.
2. Add a local no-credential fallback for Gemini UI status.
3. Improve static browser console diagnostics.

## Proposed fixes

No source changes were made during Task 2.

- Add the missing favicon if a small static asset fix is approved.
- Replace deprecated Streamlit width arguments only if a later UI cleanup is approved.
- Investigate existing theme values if a cosmetic warning cleanup is approved.

No fix is required for:

- core server startup,
- Cesium manifest loading,
- core Streamlit tab loading,
- database connectivity,
- Gemini API connectivity.
