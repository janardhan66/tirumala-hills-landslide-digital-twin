/**
 * Tirumala Hills 3D Digital Twin: CesiumJS Multi-Layer GIS Evidence Controller
 */

// Study Area Geographic Anchor
const TIRUMALA_CENTER = {
    lon: 79.373845,
    lat: 13.668008,
    baseElev: 180.0
};

let viewer = null;
let terrainPrimitives = {};
let layerManifest = null;
let spatialGridData = [];
let gsiPointsDataSource = null;
let aoiDataSource = null;
let currentExaggeration = 2.0;
let terrainBaseElevation = null;
let terrainVectorSamples = [];
let temporalPairs = [];
let temporalLosModels = {};
let activeInsarPair = null;
let activeAlertsData = null;
let alertDataSource = null;
let temporalRegistryData = [];
let currentEpochIndex = 0;
let isTimelinePlaying = false;
let timelinePlayTimer = null;

function cacheBustedUrl(url) {
    const separator = url.includes("?") ? "&" : "?";
    return `${url}${separator}_t=${Date.now()}`;
}

// Initialize Cesium Application
async function initCesiumTwin() {
    try {
        Cesium.Ion.defaultAccessToken = "";

        // Base Imagery: Global Satellite Imagery (Esri World Imagery)
        const imageryProvider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
            "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer"
        );

        viewer = new Cesium.Viewer("cesiumContainer", {
            baseLayer: false,
            terrainProvider: new Cesium.EllipsoidTerrainProvider(),
            baseLayerPicker: false,
            geocoder: false,
            homeButton: false,
            infoBox: false,
            selectionIndicator: false,
            navigationHelpButton: false,
            timeline: false,
            animation: false,
            sceneModePicker: false,
            shadows: false
        });
        viewer.imageryLayers.addImageryProvider(imageryProvider);

        // Visual Beauty & Atmospheric Realism
        viewer.scene.highDynamicRange = true;
        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.depthTestAgainstTerrain = true;
        viewer.scene.fog.enabled = true;
        viewer.scene.fog.density = 0.00012;
        viewer.scene.globe.atmosphereBrightnessShift = 0.12;
        viewer.scene.globe.atmosphereHueShift = -0.01;
        viewer.scene.globe.atmosphereSaturationShift = 0.22;
        viewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2026-08-20T06:30:00Z");

        flyToViewpoint("overview");

        // 1. Load elevation samples used to place vectors on the DEM mesh
        await loadSpatialGridData();

        // 2. Load georeferenced terrain meshes and their layer controls
        await loadDynamicGISLayers();

        // 3. Load pair-specific LOS terrain models and initialize the timeline
        await loadTemporalInSARModels();
        setupTemporalControls();

        // 4. Place vector layers on the DEM-derived terrain surface
        await loadVectorLayers();

        // 5. Load Active Early Warning Alerts
        await loadActiveAlerts();

        // 6. Load Temporal Registry & Timeline Scrubber
        await loadTemporalRegistry();

        // 7. Setup User Interactions
        setupClickInspector();
        setupControls();

        // Poll the atomic sync marker; refresh layers only after a new export.
        await checkLiveSync(true);
        await checkStage4Status();
        await checkStage5Status();
        await checkPhase3Status();
        await checkFinalStatus();
        setInterval(async () => {
            await checkLiveSync(false);
            await checkStage5Status();
            await checkPhase3Status();
            await checkFinalStatus();
        }, 10000);

        console.log("Tirumala 3D evidence viewer initialized.");
    } catch (error) {
        console.error("Cesium initialization error:", error);
        document.getElementById("statusText").innerText = "Viewer Error (Check Console)";
    }
}

let lastSeenSyncUtc = null;

async function checkPhase3Status() {
    try {
        const resp = await fetch(cacheBustedUrl("./data/phase3_gis_status.json"));
        if (!resp.ok) return;
        const status = await resp.json();
        const statusEl = document.getElementById("statusText");
        if (statusEl) {
            statusEl.innerText =
                `Phase 3 GIS: ${status.status || "NOT_TESTED"} · ` +
                `GSI: ${status.gsi_inventory?.record_count || 0} approximate points`;
        }
    } catch (err) {
        console.warn("Phase 3 GIS status notice:", err);
    }
}

async function checkStage5Status() {
    try {
        const resp = await fetch(cacheBustedUrl("./data/stage5_monitoring_status.json"));
        if (!resp.ok) return;
        const status = await resp.json();
        const statusEl = document.getElementById("statusText");
        if (statusEl) {
            statusEl.innerText =
                `Stage 5: ${status.overall_status || "NOT_TESTED"} · ` +
                `Discovery: ${status.discovery?.status || "NOT_TESTED"} · ` +
                `SBAS: ${status.sbas?.real_ready ? "READY" : "INSUFFICIENT_DATA"}`;
        }
    } catch (err) {
        console.warn("Stage 5 status notice:", err);
    }
}

async function checkFinalStatus() {
    try {
        const resp = await fetch(cacheBustedUrl("./data/master_final_status.json"));
        if (!resp.ok) return;
        const status = await resp.json();
        const statusEl = document.getElementById("statusText");
        if (statusEl) {
            statusEl.innerText =
                `Final: ${status.overall_status || "DEMONSTRATION_READY_WITH_LIMITATIONS"} · ` +
                `Risk: ${status.project?.risk_model || "EMPIRICAL_EVIDENCE_INDEX"} · ` +
                `InSAR: ${status.project?.temporal_inversion || "NOT_RELIABLE_WITH_SINGLE_PAIR"}`;
        }
    } catch (err) {
        console.warn("Final integration status notice:", err);
    }
}

async function checkStage4Status() {
    try {
        const resp = await fetch(cacheBustedUrl("./data/stage4_status.json"));
        if (!resp.ok) {
            return;
        }
        const status = await resp.json();
        const statusEl = document.getElementById("statusText");
        if (statusEl) {
            const state = status.overall_status || "NOT_TESTED";
            const processed = status.latest_processed_acquisition || "None";
            statusEl.innerText =
                `Stage 4: ${state} · Processed: ${processed} · ` +
                `Valid edges: ${status.network?.valid_edge_count ?? 0}`;
        }
    } catch (err) {
        console.warn("Stage 4 status notice:", err);
    }
}

// Dynamic In-Memory Refresh without Full Page Reload
async function checkLiveSync(force = false) {
    try {
        const resp = await fetch(cacheBustedUrl("./data/sync_status.json"));
        if (!resp.ok) {
            document.getElementById("statusText").innerText = "Sync status unavailable";
            return;
        }
        const data = await resp.json();
        const obsDate = data.latest_observation_date || "No processed observation";
        const syncUtc = data.last_sync_utc || "";
        const timeStr = syncUtc.length >= 19 ? syncUtc.substring(11, 19) + " UTC" : "Just now";

        const statusEl = document.getElementById("statusText");
        if (statusEl) {
            statusEl.innerText = `${data.status || "Unknown"} · Obs: ${obsDate} · Sync: ${timeStr}`;
        }

        const changed = Boolean(lastSeenSyncUtc && syncUtc && lastSeenSyncUtc !== syncUtc);
        if (changed) {
            await reloadDynamicTerrainLayers();
        }
        if (force || changed) {
            await loadActiveAlerts();
            await loadSpatialGridData();
            await loadTemporalRegistry();
        }
        lastSeenSyncUtc = syncUtc;
    } catch (err) {
        console.warn("Live sync poll notice:", err);
    }
}

// Build model matrix in East-North-Up frame
function getModelMatrix(verticalScale = 1.0) {
    const position = Cesium.Cartesian3.fromDegrees(
        TIRUMALA_CENTER.lon,
        TIRUMALA_CENTER.lat,
        TIRUMALA_CENTER.baseElev
    );
    const transform = Cesium.Transforms.eastNorthUpToFixedFrame(position);
    if (verticalScale !== 1.0) {
        const scaleMatrix = Cesium.Matrix4.fromScale(new Cesium.Cartesian3(1.0, 1.0, verticalScale));
        return Cesium.Matrix4.multiply(transform, scaleMatrix, new Cesium.Matrix4());
    }
    return transform;
}

// Load each evidence layer as a textured copy of the DEM mesh.
async function loadDynamicGISLayers() {
    const resp = await fetch(cacheBustedUrl("./layers_manifest.json"));
    if (!resp.ok) {
        throw new Error(`Could not load GIS layer manifest (${resp.status}).`);
    }
    layerManifest = await resp.json();
    if (!layerManifest.terrain || !Array.isArray(layerManifest.layers)) {
        throw new Error("GIS layer manifest is missing terrain metadata or layers.");
    }
    terrainBaseElevation = Number(layerManifest.terrain.base_elevation_m);
    if (!Number.isFinite(terrainBaseElevation)) {
        throw new Error("GIS layer manifest has invalid terrain elevation metadata.");
    }

    const container = document.getElementById("dynamicLayersContainer");
    if (!container) {
        throw new Error("GIS layer control container is missing.");
    }
    container.innerHTML = "";

    for (const layer of layerManifest.layers) {
        if (!layer.model_url) {
            throw new Error(`GIS layer "${layer.id}" is missing its terrain model URL.`);
        }

        const model = await Cesium.Model.fromGltfAsync({
            url: cacheBustedUrl(layer.model_url),
            modelMatrix: getModelMatrix(currentExaggeration),
            scale: 1.0,
            upAxis: Cesium.Axis.Z,
            forwardAxis: Cesium.Axis.Y,
            id: `terrain_${layer.id}`
        });
        model.show = layer.default_visible;
        model.color = Cesium.Color.WHITE.withAlpha(layer.default_opacity);
        viewer.scene.primitives.add(model);
        terrainPrimitives[layer.id] = model;

        const row = document.createElement("div");
        row.className = "layer-row";
        row.innerHTML = `
            <div class="layer-header-row">
                <label class="control-label">
                    <input type="checkbox" id="chk_${layer.id}" ${layer.default_visible ? "checked" : ""}>
                    <span>${layer.name}</span>
                </label>
                <span class="opacity-label" id="lbl_op_${layer.id}">${Math.round(layer.default_opacity * 100)}%</span>
            </div>
            <div class="slider-row">
                <input type="range" class="opacity-slider" id="slider_${layer.id}" min="0" max="100" value="${Math.round(layer.default_opacity * 100)}">
            </div>
        `;
        container.appendChild(row);

        const checkbox = row.querySelector(`#chk_${layer.id}`);
        checkbox.addEventListener("change", (event) => {
            if (layer.id === "los" && activeInsarPair) {
                for (const [pairId, pairModel] of Object.entries(temporalLosModels)) {
                    pairModel.show = event.target.checked && pairId === activeInsarPair.pair_id;
                }
            } else {
                model.show = event.target.checked;
            }
            if (event.target.checked && layer.legend) {
                updateLegendFromLayer(layer);
            }
        });

        const slider = row.querySelector(`#slider_${layer.id}`);
        const opacityLabel = row.querySelector(`#lbl_op_${layer.id}`);
        slider.addEventListener("input", (event) => {
            const alpha = Number(event.target.value) / 100.0;
            if (layer.id === "los" && Object.keys(temporalLosModels).length > 0) {
                for (const pairModel of Object.values(temporalLosModels)) {
                    pairModel.color = Cesium.Color.WHITE.withAlpha(alpha);
                }
            } else {
                model.color = Cesium.Color.WHITE.withAlpha(alpha);
            }
            opacityLabel.innerText = `${event.target.value}%`;
        });

        if (layer.default_visible && layer.legend) {
            updateLegendFromLayer(layer);
        }
    }

    // Wire up quick layer preset buttons
    const presetButtons = document.querySelectorAll(".btn-layer-preset");
    presetButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.dataset.layer;
            presetButtons.forEach(b => b.classList.toggle("active", b === btn));
            
            // Set target layer visible, others hidden
            for (const layer of layerManifest.layers) {
                const isTarget = layer.id === targetId;
                const chk = document.getElementById(`chk_${layer.id}`);
                if (chk) chk.checked = isTarget;
                
                if (layer.id === "los" && activeInsarPair) {
                    for (const [pairId, pairModel] of Object.entries(temporalLosModels)) {
                        pairModel.show = isTarget && pairId === activeInsarPair.pair_id;
                    }
                } else if (terrainPrimitives[layer.id]) {
                    terrainPrimitives[layer.id].show = isTarget;
                }
                
                if (isTarget && layer.legend) {
                    updateLegendFromLayer(layer);
                }
            }
        });
    });
}

async function loadTemporalInSARModels() {
    temporalPairs = layerManifest.temporal?.insar_pairs || [];
    if (temporalPairs.length === 0) return;

    const losLayer = layerManifest.layers.find((layer) => layer.id === "los");
    if (!losLayer || !terrainPrimitives.los) {
        throw new Error("Temporal InSAR pairs require the base LOS layer.");
    }

    for (const pair of temporalPairs) {
        if (!pair.pair_id || !pair.model_url) {
            throw new Error("Temporal InSAR pair metadata is missing its ID or model URL.");
        }

        let model;
        if (pair.model_url === losLayer.model_url) {
            model = terrainPrimitives.los;
        } else {
            model = await Cesium.Model.fromGltfAsync({
                url: cacheBustedUrl(pair.model_url),
                modelMatrix: getModelMatrix(currentExaggeration),
                scale: 1.0,
                upAxis: Cesium.Axis.Z,
                forwardAxis: Cesium.Axis.Y,
                id: `terrain_los_${pair.pair_id}`
            });
            viewer.scene.primitives.add(model);
        }
        model.show = false;
        model.color = Cesium.Color.WHITE.withAlpha(losLayer.default_opacity);
        temporalLosModels[pair.pair_id] = model;
    }
}

async function reloadDynamicTerrainLayers() {
    const models = new Set([
        ...Object.values(terrainPrimitives),
        ...Object.values(temporalLosModels)
    ]);
    for (const model of models) {
        viewer.scene.primitives.remove(model);
    }
    terrainPrimitives = {};
    temporalLosModels = {};
    temporalPairs = [];
    activeInsarPair = null;

    await loadDynamicGISLayers();
    await loadTemporalInSARModels();
    setupTemporalControls();
}

function setupTemporalControls() {
    const panel = document.getElementById("temporalControlPanel");
    const slider = document.getElementById("insarPairSlider");
    if (!panel || !slider) {
        throw new Error("InSAR timeline controls are missing from the viewer page.");
    }
    slider.oninput = null;
    document.getElementById("btnPrevInSARPair").onclick = null;
    document.getElementById("btnNextInSARPair").onclick = null;
    if (temporalPairs.length === 0) {
        panel.hidden = true;
        return;
    }

    slider.min = "0";
    slider.max = String(temporalPairs.length - 1);
    slider.step = "1";
    slider.oninput = () => {
        selectTemporalPair(Number(slider.value), true);
    };
    document.getElementById("btnPrevInSARPair").onclick = () => {
        selectTemporalPair(Math.max(0, Number(slider.value) - 1), true);
    };
    document.getElementById("btnNextInSARPair").onclick = () => {
        selectTemporalPair(Math.min(temporalPairs.length - 1, Number(slider.value) + 1), true);
    };

    const requestedPairId = new URLSearchParams(window.location.search).get("pair_id");
    let selectedIndex = temporalPairs.findIndex((pair) => pair.pair_id === requestedPairId);
    if (selectedIndex < 0) {
        selectedIndex = temporalPairs.length - 1;
        if (requestedPairId) {
            console.warn(`Unknown InSAR pair "${requestedPairId}"; selecting the latest available pair.`);
        }
    }

    // Populate epoch quick-select pills
    const pillsContainer = document.getElementById("pairPillsContainer");
    if (pillsContainer) {
        pillsContainer.innerHTML = "";
        temporalPairs.forEach((pair, idx) => {
            const pill = document.createElement("button");
            pill.type = "button";
            pill.className = `btn-pair-pill ${idx === selectedIndex ? "active" : ""}`;
            pill.id = `pill_pair_${idx}`;
            pill.innerText = pair.label;
            pill.title = `${pair.reference_date} → ${pair.secondary_date}`;
            pill.addEventListener("click", () => {
                selectTemporalPair(idx, true);
            });
            pillsContainer.appendChild(pill);
        });
    }

    slider.value = String(selectedIndex);
    panel.hidden = false;
    selectTemporalPair(selectedIndex, false);
}

function selectTemporalPair(index, updateUrl) {
    const pair = temporalPairs[index];
    if (!pair) {
        throw new Error(`No temporal InSAR pair exists at timeline index ${index}.`);
    }
    activeInsarPair = pair;

    // Highlight active pill
    document.querySelectorAll(".btn-pair-pill").forEach((pill, idx) => {
        pill.classList.toggle("active", idx === index);
    });

    const losCheckbox = document.getElementById("chk_los");
    if (losCheckbox && !losCheckbox.checked) {
        losCheckbox.checked = true;
    }
    const layerVisible = losCheckbox ? losCheckbox.checked : true;
    for (const [pairId, model] of Object.entries(temporalLosModels)) {
        model.show = layerVisible && pairId === pair.pair_id;
    }

    document.getElementById("insarPairLabel").innerText = pair.label;
    document.getElementById("insarPairDates").innerText =
        `${pair.reference_date} → ${pair.secondary_date}`;
    document.getElementById("insarReferenceNote").innerText =
        [
            layerManifest.temporal.scope_note,
            layerManifest.temporal.comparison_note || pair.reference_note
        ].filter(Boolean).join(" ");
    document.getElementById("cardLosLabel").innerText =
        `InSAR LOS Disp (${pair.label})`;
    document.getElementById("legendTitle").innerText =
        `InSAR LOS Disp (${pair.label})`;

    if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set("pair_id", pair.pair_id);
        window.history.replaceState(null, "", url);
    }

    const slider = document.getElementById("insarPairSlider");
    if (slider) slider.value = String(index);
}

// Update Legend from Layer Manifest
function updateLegendFromLayer(layer) {
    if (!layer || !layer.legend) return;
    const leg = layer.legend;
    document.getElementById("legendTitle").innerText = leg.title || layer.name;
    document.getElementById("legendBar").style.background = leg.gradient || "#38bdf8";
    document.getElementById("legendMin").innerText = leg.min || "Low";
    document.getElementById("legendMax").innerText = leg.max || "High";
}

function nearestTerrainCell(longitude, latitude) {
    if (spatialGridData.length === 0) {
        throw new Error("DEM elevation samples are not loaded.");
    }

    const latitudeScale = Math.cos(Cesium.Math.toRadians(latitude));
    let nearest = null;
    let minimumDistanceSquared = Infinity;
    for (const cell of spatialGridData) {
        const eastDistance = (cell.lon - longitude) * latitudeScale * 111320;
        const northDistance = (cell.lat - latitude) * 111320;
        const distanceSquared = eastDistance * eastDistance + northDistance * northDistance;
        if (distanceSquared < minimumDistanceSquared) {
            minimumDistanceSquared = distanceSquared;
            nearest = cell;
        }
    }
    if (!nearest || !Number.isFinite(nearest.elev)) {
        throw new Error(`No valid DEM elevation is available near ${longitude}, ${latitude}.`);
    }
    return {
        longitude,
        latitude,
        elevation: nearest.elev,
        sampleDistanceMeters: Math.sqrt(minimumDistanceSquared)
    };
}

function terrainPosition(sample) {
    const height = TIRUMALA_CENTER.baseElev
        + (sample.elevation - terrainBaseElevation) * currentExaggeration;
    return Cesium.Cartesian3.fromDegrees(sample.longitude, sample.latitude, height);
}

function updateTerrainVectorHeights() {
    for (const vector of terrainVectorSamples) {
        if (vector.type === "point") {
            vector.entity.position = terrainPosition(vector.sample);
        } else {
            vector.entity.polygon.hierarchy = new Cesium.PolygonHierarchy(
                vector.samples.map(terrainPosition)
            );
        }
    }
}

// Place vector layers on the DEM-derived terrain surface.
async function loadVectorLayers() {
    // 1. AOI Boundary
    try {
        aoiDataSource = await Cesium.GeoJsonDataSource.load("./data/tirumala_aoi.geojson", {
            stroke: Cesium.Color.fromCssColorString("#38bdf8"),
            fill: Cesium.Color.fromCssColorString("#38bdf8").withAlpha(0.10),
            strokeWidth: 3,
            clampToGround: false
        });
        for (const entity of aoiDataSource.entities.values) {
            if (!entity.polygon) continue;
            const hierarchy = entity.polygon.hierarchy.getValue(viewer.clock.currentTime);
            if (!hierarchy) continue;
            const samples = hierarchy.positions.map((position) => {
                const cartographic = Cesium.Cartographic.fromCartesian(position);
                return nearestTerrainCell(
                    Cesium.Math.toDegrees(cartographic.longitude),
                    Cesium.Math.toDegrees(cartographic.latitude)
                );
            });
            entity.polygon.perPositionHeight = true;
            entity.polygon.height = undefined;
            terrainVectorSamples.push({ type: "polygon", entity, samples });
        }
        updateTerrainVectorHeights();
        viewer.dataSources.add(aoiDataSource);
    } catch (e) {
        console.error("Could not position AOI boundary on DEM terrain:", e);
    }

    // 2. GSI Historical Points
    try {
        gsiPointsDataSource = await Cesium.GeoJsonDataSource.load("./data/tirumala_gsi_points.geojson", {
            markerColor: Cesium.Color.fromCssColorString("#ef4444"),
            markerSize: 24,
            clampToGround: false
        });

        const entities = gsiPointsDataSource.entities.values;
        for (let i = 0; i < entities.length; i++) {
            const entity = entities[i];
            const cartesian = entity.position.getValue(viewer.clock.currentTime);
            if (!cartesian) continue;
            const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
            const sample = nearestTerrainCell(
                Cesium.Math.toDegrees(cartographic.longitude),
                Cesium.Math.toDegrees(cartographic.latitude)
            );
            terrainVectorSamples.push({ type: "point", entity, sample });
            const props = entity.properties;
            entity.point = new Cesium.PointGraphics({
                color: Cesium.Color.fromCssColorString("#ef4444"),
                pixelSize: 12,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2,
                heightReference: Cesium.HeightReference.NONE
            });
            entity.description = `
                <div style="font-size: 12px; color: #1e293b; padding: 6px;">
                    <b style="color: #ef4444;">Historical Landslide Hazard Point</b><br>
                    <b>ID:</b> ${props.id ? props.id.getValue() : "GSI"}<br>
                    <b>Source:</b> ${props.source ? props.source.getValue() : "GSI Figure 3.2"}<br>
                    <b>Coordinate Quality:</b> ${props.quality ? props.quality.getValue() : "Approximate"}<br>
                    <b>Nearest valid DEM sample:</b> ${Math.round(sample.sampleDistanceMeters)} m away
                </div>
            `;
        }
        updateTerrainVectorHeights();
        viewer.dataSources.add(gsiPointsDataSource);
    } catch (e) {
        console.error("Could not position GSI points on DEM terrain:", e);
    }
}

// Load client-side spatial grid for instant on-click queries
async function loadSpatialGridData() {
    const response = await fetch(cacheBustedUrl("./data/spatial_grid_lookup.json"));
    if (!response.ok) {
        throw new Error(`Could not load DEM elevation samples (${response.status}).`);
    }
    spatialGridData = await response.json();
    if (!Array.isArray(spatialGridData) || spatialGridData.length === 0) {
        throw new Error("DEM elevation sample data is empty or invalid.");
    }
    console.log(`Loaded ${spatialGridData.length} spatial grid cells for terrain sampling.`);
}

// Raycasting click inspector
function setupClickInspector() {
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);

    handler.setInputAction(function (movement) {
        const pickedPosition = viewer.scene.pickPosition(movement.position);
        if (!Cesium.defined(pickedPosition)) return;

        const cartographic = Cesium.Cartographic.fromCartesian(pickedPosition);
        const lon = Cesium.Math.toDegrees(cartographic.longitude);
        const lat = Cesium.Math.toDegrees(cartographic.latitude);
        const elev = cartographic.height;

        let nearest = null;
        let minDist = Infinity;

        for (let i = 0; i < spatialGridData.length; i++) {
            const cell = spatialGridData[i];
            const dLat = cell.lat - lat;
            const dLon = cell.lon - lon;
            const d2 = dLat * dLat + dLon * dLon;
            if (d2 < minDist) {
                minDist = d2;
                nearest = cell;
            }
        }

        updateInspectorHUD(lat, lon, elev, nearest);
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
}

// Update On-Click HUD Card
function updateInspectorHUD(lat, lon, elev, cellData) {
    const inspectorData = document.getElementById("inspectorData");
    if (inspectorData && inspectorData.hidden) {
        inspectorData.hidden = false;
        const toggleBtn = document.getElementById("btnToggleInspector");
        if (toggleBtn) toggleBtn.setAttribute("aria-expanded", "true");
    }

    document.getElementById("cardCoord").innerText = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;
    document.getElementById("cardElevation").innerText = `${elev.toFixed(1)} m`;

    const meterElevation = document.getElementById("meterElevation");
    if (meterElevation) {
        const elevPct = Math.min(100, Math.max(0, ((elev - 180.0) / 720.0) * 100));
        meterElevation.style.width = `${elevPct.toFixed(0)}%`;
    }

    const evidenceEl = document.getElementById("cardEvidence");

    if (cellData) {
        document.getElementById("cardSlope").innerText = `${cellData.slope.toFixed(1)}°`;
        const meterSlope = document.getElementById("meterSlope");
        if (meterSlope) {
            const slopePct = Math.min(100, Math.max(0, (cellData.slope / 45.0) * 100));
            meterSlope.style.width = `${slopePct.toFixed(0)}%`;
        }

        const losField = activeInsarPair ? activeInsarPair.lookup_los_field : null;
        const coherenceField = activeInsarPair ? activeInsarPair.lookup_coherence_field : null;
        let losMeters = losField ? cellData[losField] : null;
        let coherence = coherenceField ? cellData[coherenceField] : null;
        if (activeInsarPair && activeInsarPair.pair_id === "PAIR_20260817_20260829") {
            if (losMeters === null || losMeters === undefined) losMeters = cellData.los;
            if (coherence === null || coherence === undefined) coherence = cellData.corr;
        }
        const losDispMm = losMeters !== null && losMeters !== undefined
            ? `${(Number(losMeters) * 1000).toFixed(1)} mm`
            : "N/A";
        const cohStr = coherence !== null && coherence !== undefined
            ? Number(coherence).toFixed(2)
            : "N/A";

        document.getElementById("cardLos").innerText = losDispMm;
        document.getElementById("cardCorr").innerText = cohStr;
        document.getElementById("cardRain").innerText = cellData.rain_3d !== null ? `${cellData.rain_3d} mm` : "N/A";

        const riskPill = document.getElementById("cardRisk");
        const category = cellData.category || "Low";
        riskPill.innerText = category;
        riskPill.className = `risk-pill risk-${category.includes("Multiple") || category.includes("High") ? "High" : category.includes("Moderate") ? "Medium" : "Low"}`;

        if (evidenceEl) {
            const slopeVal = Number(cellData.slope) || 0;
            const slopeHazard = slopeVal >= 25 ? "Steep Escarpment (>25°)" : slopeVal >= 15 ? "Moderate Slope" : "Gentle Plateau";
            const rainVal = cellData.rain_3d !== null && cellData.rain_3d !== undefined ? `${cellData.rain_3d} mm` : "0 mm";
            evidenceEl.innerHTML = `• <b>Morphology:</b> ${slopeHazard} (${slopeVal.toFixed(1)}°)<br>` +
                `• <b>InSAR LOS Look:</b> ${losDispMm} (Quality Coherence γ=${cohStr})<br>` +
                `• <b>NASA GPM Precipitation:</b> 3-day cum. ${rainVal}<br>` +
                `• <b>Multi-Factor Vulnerability:</b> ${category}`;
        }
    } else {
        document.getElementById("cardSlope").innerText = "N/A";
        document.getElementById("cardLos").innerText = "N/A";
        document.getElementById("cardCorr").innerText = "N/A";
        document.getElementById("cardRain").innerText = "N/A";
        const meterSlope = document.getElementById("meterSlope");
        if (meterSlope) meterSlope.style.width = "0%";
        const riskPill = document.getElementById("cardRisk");
        riskPill.innerText = "Study Area";
        riskPill.className = "risk-pill risk-Low";

        if (evidenceEl) {
            evidenceEl.innerText = "Point outside dense grid cell boundaries. Click within the Tirumala catchment.";
        }
    }
}

// Cinematic 360° Drone Tour
let isDroneTourActive = false;
let droneAngle = 0;
const DRONE_RADIUS = 0.042;
const DRONE_ALTITUDE = 3800.0;

function toggleDroneOrbit() {
    isDroneTourActive = !isDroneTourActive;
    const btn = document.getElementById("btnDroneTour");
    if (btn) btn.classList.toggle("active", isDroneTourActive);
    if (isDroneTourActive) {
        viewer.clock.onTick.addEventListener(updateDroneOrbit);
    } else {
        viewer.clock.onTick.removeEventListener(updateDroneOrbit);
    }
}

function updateDroneOrbit() {
    if (!isDroneTourActive || !viewer) return;
    droneAngle += 0.0035;
    viewer.camera.lookAt(
        Cesium.Cartesian3.fromDegrees(TIRUMALA_CENTER.lon, TIRUMALA_CENTER.lat, TIRUMALA_CENTER.baseElev + 320.0),
        new Cesium.HeadingPitchRange(droneAngle, Cesium.Math.toRadians(-28.0), 4600.0)
    );
}

// Lighting Presets (Daylight / Sunset / Cyber Night)
let currentLightingMode = "day";
function cycleLightingMode() {
    if (!viewer) return;
    const icon = document.getElementById("lightingIcon");
    const text = document.getElementById("lightingModeText");

    if (currentLightingMode === "day") {
        currentLightingMode = "sunset";
        if (icon) icon.innerText = "🌅";
        if (text) text.innerText = "Sunset";
        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.atmosphereBrightnessShift = -0.05;
        viewer.scene.globe.atmosphereHueShift = -0.08;
        viewer.scene.globe.atmosphereSaturationShift = 0.35;
        viewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2026-08-20T12:45:00Z");
    } else if (currentLightingMode === "sunset") {
        currentLightingMode = "night";
        if (icon) icon.innerText = "🌌";
        if (text) text.innerText = "Night";
        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.atmosphereBrightnessShift = -0.3;
        viewer.scene.globe.atmosphereSaturationShift = 0.1;
        viewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2026-08-20T15:30:00Z");
    } else {
        currentLightingMode = "day";
        if (icon) icon.innerText = "☀️";
        if (text) text.innerText = "Daylight";
        viewer.scene.globe.enableLighting = true;
        viewer.scene.globe.atmosphereBrightnessShift = 0.10;
        viewer.scene.globe.atmosphereHueShift = -0.02;
        viewer.scene.globe.atmosphereSaturationShift = 0.15;
        viewer.clock.currentTime = Cesium.JulianDate.fromIso8601("2026-08-20T06:30:00Z");
    }
}

// 3D Landmark Beacons
let landmarkEntities = [];
let landmarksVisible = false;

function toggleLandmarks() {
    if (landmarkEntities.length === 0) {
        createLandmarkBeacons();
    } else {
        landmarksVisible = !landmarksVisible;
        landmarkEntities.forEach(e => e.show = landmarksVisible);
    }
    const btn = document.getElementById("btnLandmarks");
    if (btn) btn.classList.toggle("active", landmarksVisible);
}

function createLandmarkBeacons() {
    if (!viewer) return;
    const landmarks = [
        { name: "🚗 1st Ghat Road (Ascending)", lon: 79.388, lat: 13.655, height: 420.0, color: "#38bdf8" },
        { name: "🛣️ 2nd Ghat Road (Descending)", lon: 79.355, lat: 13.658, height: 480.0, color: "#818cf8" },
        { name: "🏛️ Tirumala Temple Township", lon: 79.348, lat: 13.678, height: 860.0, color: "#f59e0b" },
        { name: "⚠️ Critical Slope Hazard Flank", lon: 79.373, lat: 13.668, height: 680.0, color: "#ef4444" }
    ];
    landmarks.forEach(lm => {
        const entity = viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(lm.lon, lm.lat, lm.height),
            point: {
                pixelSize: 12,
                color: Cesium.Color.fromCssColorString(lm.color),
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2
            },
            label: {
                text: lm.name,
                font: "12px -apple-system, sans-serif",
                style: Cesium.LabelStyle.FILL_AND_OUTLINE,
                fillColor: Cesium.Color.WHITE,
                outlineColor: Cesium.Color.BLACK,
                outlineWidth: 2,
                verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                pixelOffset: new Cesium.Cartesian2(0, -12),
                distanceDisplayCondition: new Cesium.DistanceDisplayCondition(100.0, 18000.0)
            }
        });
        landmarkEntities.push(entity);
    });
    landmarksVisible = true;
    const btn = document.getElementById("btnLandmarks");
    if (btn) btn.classList.add("active");
}

// Setup Camera Presets and Sliders
function setupControls() {
    // Floating Quick Tools
    const btnDrone = document.getElementById("btnDroneTour");
    if (btnDrone) btnDrone.addEventListener("click", toggleDroneOrbit);

    const btnLight = document.getElementById("btnLightingToggle");
    if (btnLight) btnLight.addEventListener("click", cycleLightingMode);

    const btnLandmarks = document.getElementById("btnLandmarks");
    if (btnLandmarks) btnLandmarks.addEventListener("click", toggleLandmarks);

    const btnReset = document.getElementById("btnResetView");
    if (btnReset) {
        btnReset.addEventListener("click", () => {
            if (isDroneTourActive) toggleDroneOrbit();
            flyToViewpoint("overview");
        });
    }

    const btnFullscreen = document.getElementById("btnFullscreen3D");
    if (btnFullscreen) {
        btnFullscreen.addEventListener("click", () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => console.warn(err));
            } else {
                document.exitFullscreen().catch(err => console.warn(err));
            }
        });
    }

    // Panel toggle and close
    const btnTogglePanel = document.getElementById("btnTogglePanel");
    if (btnTogglePanel) {
        btnTogglePanel.addEventListener("click", () => {
            document.body.classList.toggle("panel-collapsed");
            const isCollapsed = document.body.classList.contains("panel-collapsed");
            btnTogglePanel.setAttribute("aria-expanded", String(!isCollapsed));
        });
    }

    const btnClosePanel = document.getElementById("btnClosePanel");
    if (btnClosePanel) {
        btnClosePanel.addEventListener("click", () => {
            document.body.classList.add("panel-collapsed");
            if (btnTogglePanel) btnTogglePanel.setAttribute("aria-expanded", "false");
        });
    }

    // Inspector collapse/expand toggle
    const btnToggleInspector = document.getElementById("btnToggleInspector");
    if (btnToggleInspector) {
        btnToggleInspector.addEventListener("click", () => {
            const inspectorData = document.getElementById("inspectorData");
            if (inspectorData) {
                inspectorData.hidden = !inspectorData.hidden;
                btnToggleInspector.setAttribute("aria-expanded", String(!inspectorData.hidden));
                btnToggleInspector.innerText = inspectorData.hidden ? "⌄" : "⌃";
            }
        });
    }

    // Close alert summary banner
    const btnCloseAlert = document.getElementById("btnCloseAlert");
    if (btnCloseAlert) {
        btnCloseAlert.addEventListener("click", () => {
            const banner = document.getElementById("hudAlertBanner");
            if (banner) banner.style.display = "none";
        });
    }

    // Vector layer checkboxes
    document.getElementById("chkGsi").addEventListener("change", (e) => {
        if (gsiPointsDataSource) gsiPointsDataSource.show = e.target.checked;
    });

    document.getElementById("chkAoi").addEventListener("change", (e) => {
        if (aoiDataSource) aoiDataSource.show = e.target.checked;
    });

    // Basemap satellite visibility
    document.getElementById("chkSatelliteBase").addEventListener("change", (e) => {
        if (viewer.imageryLayers.length > 0) {
            viewer.imageryLayers.get(0).show = e.target.checked;
        }
    });

    // Vertical Exaggeration slider
    const exagSlider = document.getElementById("exagSlider");
    const exagValue = document.getElementById("exagValue");
    exagSlider.addEventListener("input", (e) => {
        currentExaggeration = parseFloat(e.target.value);
        exagValue.innerText = `${currentExaggeration.toFixed(1)}x`;
        const newMatrix = getModelMatrix(currentExaggeration);
        const models = new Set([
            ...Object.values(terrainPrimitives),
            ...Object.values(temporalLosModels)
        ]);
        for (const model of models) {
            if (model) model.modelMatrix = newMatrix;
        }
        updateTerrainVectorHeights();
    });

    // Viewpoint buttons
    document.querySelectorAll(".btn-view").forEach(btn => {
        btn.addEventListener("click", () => {
            if (isDroneTourActive) toggleDroneOrbit();
            flyToViewpoint(btn.dataset.view);
        });
    });
}

// Camera Fly-To Viewpoint Presets
function flyToViewpoint(viewKey) {
    if (!viewer) return;

    const viewpoints = {
        overview: {
            destination: Cesium.Cartesian3.fromDegrees(TIRUMALA_CENTER.lon, TIRUMALA_CENTER.lat - 0.055, 4800.0),
            orientation: { heading: Cesium.Math.toRadians(0.0), pitch: Cesium.Math.toRadians(-35.0), roll: 0.0 }
        },
        ghat1: {
            destination: Cesium.Cartesian3.fromDegrees(79.388, 13.655, 1800.0),
            orientation: { heading: Cesium.Math.toRadians(310.0), pitch: Cesium.Math.toRadians(-22.0), roll: 0.0 }
        },
        ghat2: {
            destination: Cesium.Cartesian3.fromDegrees(79.355, 13.658, 2100.0),
            orientation: { heading: Cesium.Math.toRadians(30.0), pitch: Cesium.Math.toRadians(-25.0), roll: 0.0 }
        },
        township: {
            destination: Cesium.Cartesian3.fromDegrees(79.348, 13.678, 1600.0),
            orientation: { heading: Cesium.Math.toRadians(140.0), pitch: Cesium.Math.toRadians(-30.0), roll: 0.0 }
        },
        nadir: {
            destination: Cesium.Cartesian3.fromDegrees(TIRUMALA_CENTER.lon, TIRUMALA_CENTER.lat, 8500.0),
            orientation: { heading: Cesium.Math.toRadians(0.0), pitch: Cesium.Math.toRadians(-89.0), roll: 0.0 }
        }
    };

    const vp = viewpoints[viewKey] || viewpoints.overview;
    viewer.camera.flyTo({
        destination: vp.destination,
        orientation: vp.orientation,
        duration: 1.8
    });
}

// Load and Display Active Warning Alerts in the HUD Banner and on Globe
async function loadActiveAlerts() {
    try {
        const resp = await fetch(cacheBustedUrl("./data/active_alerts.geojson"));
        if (!resp.ok) return;
        activeAlertsData = await resp.json();
        if (alertDataSource) {
            viewer.dataSources.remove(alertDataSource, true);
            alertDataSource = null;
        }

        const banner = document.getElementById("hudAlertBanner");
        if (!activeAlertsData || !activeAlertsData.features || activeAlertsData.features.length === 0) {
            if (banner) banner.style.display = "none";
            return;
        }

        // Add alert pin markers on 3D globe
        try {
            alertDataSource = await Cesium.GeoJsonDataSource.load(
                cacheBustedUrl("./data/active_alerts.geojson"), {
                clampToGround: true
            });
            for (const entity of alertDataSource.entities.values) {
                const props = entity.properties;
                const level = props && props.warning_level ? props.warning_level.getValue() : "Watch";
                const color = level === "High concern" ? Cesium.Color.RED :
                    level === "Elevated concern" ? Cesium.Color.ORANGE : Cesium.Color.YELLOW;
                entity.point = new Cesium.PointGraphics({
                    color: color,
                    pixelSize: 14,
                    outlineColor: Cesium.Color.WHITE,
                    outlineWidth: 2
                });
            }
            viewer.dataSources.add(alertDataSource);
        } catch (err) {
            console.warn("Could not load alerts DataSource:", err);
        }

        // Surface highest severity alert to HUD banner
        const topFeature = activeAlertsData.features[0];
        const props = topFeature.properties || {};
        const coords = topFeature.geometry ? topFeature.geometry.coordinates : [TIRUMALA_CENTER.lon, TIRUMALA_CENTER.lat];

        if (banner) {
            banner.style.display = "flex";
            const titleEl = document.getElementById("alertBannerTitle");
            const descEl = document.getElementById("alertBannerDesc");
            if (titleEl) titleEl.innerText = `${props.warning_level || "Alert"}: ${props.trigger_rule || "Zone Alert"}`;
            if (descEl) descEl.innerText = props.recommended_action || `Risk score: ${props.max_risk_score || "N/A"}`;

            const zoomBtn = document.getElementById("btnZoomAlert");
            if (zoomBtn) {
                zoomBtn.onclick = () => {
                    const alertLon = Array.isArray(coords[0]) ? coords[0][0] : coords[0];
                    const alertLat = Array.isArray(coords[0]) ? coords[0][1] : coords[1];
                    viewer.camera.flyTo({
                        destination: Cesium.Cartesian3.fromDegrees(alertLon, alertLat - 0.015, 2500.0),
                        orientation: {
                            heading: Cesium.Math.toRadians(0.0),
                            pitch: Cesium.Math.toRadians(-35.0),
                            roll: 0.0
                        },
                        duration: 1.5
                    });
                };
            }
        }
    } catch (e) {
        console.warn("loadActiveAlerts notice:", e);
    }
}

// Load Temporal Observation Registry & Initialize Time Scrubber
async function loadTemporalRegistry() {
    try {
        const resp = await fetch(cacheBustedUrl("./data/temporal_registry.json"));
        if (!resp.ok) return;
        const payload = await resp.json();
        temporalRegistryData = Array.isArray(payload.epochs) ? payload.epochs : [];
        if (!Array.isArray(temporalRegistryData) || temporalRegistryData.length === 0) return;

        const slider = document.getElementById("timelineSlider");
        const select = document.getElementById("epochSelect");
        const prevBtn = document.getElementById("btnPrevEpoch");
        const nextBtn = document.getElementById("btnNextEpoch");
        const playBtn = document.getElementById("btnPlayEpoch");

        if (select) {
            select.innerHTML = "";
            temporalRegistryData.forEach((epoch, idx) => {
                const opt = document.createElement("option");
                opt.value = String(idx);
                opt.innerText = `${epoch.date} (${epoch.type})`;
                select.appendChild(opt);
            });
        }

        if (slider) {
            slider.min = "0";
            slider.max = String(temporalRegistryData.length - 1);
            slider.value = String(temporalRegistryData.length - 1);
        }

        currentEpochIndex = temporalRegistryData.length - 1;
        applyEpoch(currentEpochIndex);

        if (slider) {
                slider.oninput = (e) => {
                    applyEpoch(parseInt(e.target.value, 10));
                };
        }

        if (select) {
            select.onchange = (e) => {
                    applyEpoch(parseInt(e.target.value, 10));
            };
        }

        if (prevBtn) {
            prevBtn.onclick = () => {
                if (currentEpochIndex > 0) applyEpoch(currentEpochIndex - 1);
            };
        }

        if (nextBtn) {
            nextBtn.onclick = () => {
                if (currentEpochIndex < temporalRegistryData.length - 1) applyEpoch(currentEpochIndex + 1);
            };
        }

        if (playBtn) {
            playBtn.onclick = () => {
                if (isTimelinePlaying) {
                    clearInterval(timelinePlayTimer);
                    isTimelinePlaying = false;
                    playBtn.innerText = "▶";
                } else {
                    isTimelinePlaying = true;
                    playBtn.innerText = "⏸";
                    timelinePlayTimer = setInterval(() => {
                        let next = currentEpochIndex + 1;
                        if (next >= temporalRegistryData.length) next = 0;
                        applyEpoch(next);
                    }, 1200);
                }
            };
        }
    } catch (e) {
        console.warn("loadTemporalRegistry notice:", e);
    }
}

// Apply selected temporal epoch to HUD and 3D layers
function applyEpoch(idx) {
    if (!temporalRegistryData || !temporalRegistryData[idx]) return;
    currentEpochIndex = idx;
    const epoch = temporalRegistryData[idx];

    const slider = document.getElementById("timelineSlider");
    const select = document.getElementById("epochSelect");
    const dateBadge = document.getElementById("currentEpochDate");
    const sourceBadge = document.getElementById("currentEpochSource");

    if (slider) slider.value = String(idx);
    if (select) select.value = String(idx);
    if (dateBadge) dateBadge.innerText = epoch.date;
    if (sourceBadge) {
        const productId = epoch.metadata && epoch.metadata.product_id;
        const meta = productId ? ` (${productId.substring(0, 16)}...)` : "";
        sourceBadge.innerText = `${epoch.source || epoch.type}${meta}`;
    }

    // Switch InSAR model if epoch matches a Sentinel-1 pair
    if (epoch.type === "insar" && temporalPairs.length > 0) {
        const pIdx = temporalPairs.findIndex(
            p => p.secondary_date === epoch.date
                || p.pair_id.includes(epoch.date.replace(/-/g, ""))
        );
        if (pIdx >= 0) {
            selectTemporalPair(pIdx, true);
        }
    }
}

window.addEventListener("DOMContentLoaded", initCesiumTwin);
