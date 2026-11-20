/**
 * Tirumala Hills 3D Digital Twin: CesiumJS Interactive Controller
 */

// Study Area Constants
const TIRUMALA_CENTER = {
    lon: 79.373845,
    lat: 13.668008,
    baseElev: 180.0
};

let viewer = null;
let currentTerrainModel = null;
let terrainPrimitives = {};
let spatialGridData = [];
let gsiPointsDataSource = null;
let aoiDataSource = null;
let currentExaggeration = 2.0;

// Initialize Cesium Application
async function initCesiumTwin() {
    try {
        // Disable Cesium Ion default access token requirement
        Cesium.Ion.defaultAccessToken = "";

        // Configure local/open imagery provider (Esri World Imagery)
        const imageryProvider = new Cesium.ArcGisMapServerImageryProvider({
            url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer"
        });

        viewer = new Cesium.Viewer("cesiumContainer", {
            imageryProvider: imageryProvider,
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

        // Set initial camera view
        flyToViewpoint("overview");

        // Load 3D Terrain Models
        await loadTerrainModels();

        // Load GIS Vectors
        await loadVectorLayers();

        // Load Spatial Evidence Lookup Grid
        await loadSpatialGridData();

        // Setup User Interactions
        setupClickInspector();
        setupControls();

        console.log("Tirumala 3D Digital Twin initialized successfully.");
    } catch (error) {
        console.error("Cesium initialization error:", error);
        document.getElementById("statusText").innerText = "Viewer Error (Check Console)";
    }
}

// Build model matrix in East-North-Up metric frame
function getModelMatrix(verticalScale = 1.0) {
    const position = Cesium.Cartesian3.fromDegrees(
        TIRUMALA_CENTER.lon,
        TIRUMALA_CENTER.lat,
        TIRUMALA_CENTER.baseElev
    );
    // East-North-Up frame with optional Z scale
    const transform = Cesium.Transforms.eastNorthUpToFixedFrame(position);
    if (verticalScale !== 1.0) {
        const scaleMatrix = Cesium.Matrix4.fromScale(new Cesium.Cartesian3(1.0, 1.0, verticalScale));
        return Cesium.Matrix4.multiply(transform, scaleMatrix, new Cesium.Matrix4());
    }
    return transform;
}

// Load and manage 3D GLB models
async function loadTerrainModels() {
    const modelUrls = {
        relief: "./models/tirumala_terrain_relief.glb",
        slope: "./models/tirumala_terrain_slope.glb",
        los: "./models/tirumala_terrain_los.glb",
        corr: "./models/tirumala_terrain_corr.glb"
    };

    const modelMatrix = getModelMatrix(currentExaggeration);

    for (const [key, url] of Object.entries(modelUrls)) {
        try {
            const model = await Cesium.Model.fromGltfAsync({
                url: url,
                modelMatrix: modelMatrix,
                scale: 1.0,
                id: `terrain_${key}`
            });
            model.show = (key === "relief"); // Default to relief
            viewer.scene.primitives.add(model);
            terrainPrimitives[key] = model;
        } catch (err) {
            console.warn(`Could not load GLB for ${key}:`, err);
        }
    }
    currentTerrainModel = terrainPrimitives["relief"];
}

// Switch active terrain colormap overlay
function switchOverlay(overlayKey) {
    for (const [key, model] of Object.entries(terrainPrimitives)) {
        if (model) {
            model.show = (key === overlayKey);
            if (model.show) {
                currentTerrainModel = model;
            }
        }
    }
    updateLegend(overlayKey);
}

// Update Legend display
function updateLegend(overlayKey) {
    const legendTitle = document.getElementById("legendTitle");
    const legendBar = document.getElementById("legendBar");
    const legendMin = document.getElementById("legendMin");
    const legendMax = document.getElementById("legendMax");

    if (overlayKey === "relief") {
        legendTitle.innerText = "Elevation (GLO-30 DEM)";
        legendBar.style.background = "linear-gradient(to right, #2b83ba, #abdda4, #ffffbf, #fdae61, #d7191c)";
        legendMin.innerText = "192 m";
        legendMax.innerText = "884 m";
    } else if (overlayKey === "slope") {
        legendTitle.innerText = "Topographic Slope (deg)";
        legendBar.style.background = "linear-gradient(to right, #30123b, #4686fb, #1ae4b6, #a2fc3c, #fbb31e, #d82b04)";
        legendMin.innerText = "0° (Flat)";
        legendMax.innerText = "50° (Steep)";
    } else if (overlayKey === "los") {
        legendTitle.innerText = "InSAR LOS Disp (mm)";
        legendBar.style.background = "linear-gradient(to right, #b2182b, #ef8a62, #f7f7f7, #67a9cf, #2166ac)";
        legendMin.innerText = "-48 mm";
        legendMax.innerText = "+12 mm";
    } else if (overlayKey === "corr") {
        legendTitle.innerText = "Coherence (γ)";
        legendBar.style.background = "linear-gradient(to right, #440154, #3b528b, #21918c, #5ec962, #fde725)";
        legendMin.innerText = "0.50";
        legendMax.innerText = "1.00";
    }
}

// Load vector layers (GSI historical points and AOI boundary)
async function loadVectorLayers() {
    // 1. AOI Boundary
    try {
        aoiDataSource = await Cesium.GeoJsonDataSource.load("./data/tirumala_aoi.geojson", {
            stroke: Cesium.Color.fromCssColorString("#38bdf8"),
            fill: Cesium.Color.fromCssColorString("#38bdf8").withAlpha(0.12),
            strokeWidth: 3,
            clampToGround: true
        });
        viewer.dataSources.add(aoiDataSource);
    } catch (e) {
        console.warn("Could not load AOI GeoJSON:", e);
    }

    // 2. GSI Historical Points
    try {
        gsiPointsDataSource = await Cesium.GeoJsonDataSource.load("./data/tirumala_gsi_points.geojson", {
            markerColor: Cesium.Color.fromCssColorString("#ef4444"),
            markerSize: 24,
            clampToGround: true
        });

        // Add popups and labels
        const entities = gsiPointsDataSource.entities.values;
        for (let i = 0; i < entities.length; i++) {
            const entity = entities[i];
            const props = entity.properties;
            entity.point = new Cesium.PointGraphics({
                color: Cesium.Color.RED,
                pixelSize: 10,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND
            });
            entity.description = `
                <div style="font-size: 12px; color: #333;">
                    <b>Historical Landslide Hazard Point</b><br>
                    <b>ID:</b> ${props.id ? props.id.getValue() : "GSI"}<br>
                    <b>Source:</b> ${props.source ? props.source.getValue() : "GSI Figure 3.2"}<br>
                    <b>Quality:</b> ${props.quality ? props.quality.getValue() : "Approximate"}
                </div>
            `;
        }
        viewer.dataSources.add(gsiPointsDataSource);
    } catch (e) {
        console.warn("Could not load GSI GeoJSON:", e);
    }
}

// Load client-side spatial grid for instant on-click queries
async function loadSpatialGridData() {
    try {
        const resp = await fetch("./data/spatial_grid_lookup.json");
        spatialGridData = await resp.json();
        console.log(`Loaded ${spatialGridData.length} spatial grid cells for raycasting.`);
    } catch (err) {
        console.warn("Could not load spatial grid lookup:", err);
    }
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

        // Find nearest cell in spatial grid
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

        // Update HUD Card
        updateInspectorHUD(lat, lon, elev, nearest);
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
}

// Update On-Click HUD Card
function updateInspectorHUD(lat, lon, elev, cellData) {
    document.getElementById("cardCoord").innerText = `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;
    document.getElementById("cardElevation").innerText = `${elev.toFixed(1)} m`;

    if (cellData) {
        document.getElementById("cardSlope").innerText = `${cellData.slope.toFixed(1)}°`;
        document.getElementById("cardLos").innerText = cellData.los !== null ? `${cellData.los.toFixed(1)} mm` : "N/A";
        document.getElementById("cardCorr").innerText = cellData.corr !== null ? cellData.corr.toFixed(2) : "N/A";
        document.getElementById("cardRain").innerText = cellData.rain_3d !== null ? `${cellData.rain_3d} mm` : "N/A";

        const riskPill = document.getElementById("cardRisk");
        const category = cellData.category || "Low";
        riskPill.innerText = category;
        riskPill.className = `risk-pill risk-${category.includes("Multiple") || category.includes("High") ? "High" : category.includes("Moderate") ? "Medium" : "Low"}`;
    } else {
        document.getElementById("cardSlope").innerText = "N/A";
        document.getElementById("cardLos").innerText = "N/A";
        document.getElementById("cardCorr").innerText = "N/A";
        document.getElementById("cardRain").innerText = "N/A";
        const riskPill = document.getElementById("cardRisk");
        riskPill.innerText = "Study Area";
        riskPill.className = "risk-pill risk-Low";
    }
}

// Setup Camera Presets and Sliders
function setupControls() {
    // Overlay radio buttons
    document.querySelectorAll('input[name="overlay"]').forEach(radio => {
        radio.addEventListener("change", (e) => {
            switchOverlay(e.target.value);
        });
    });

    // Vector layer checkboxes
    document.getElementById("chkGsi").addEventListener("change", (e) => {
        if (gsiPointsDataSource) gsiPointsDataSource.show = e.target.checked;
    });

    document.getElementById("chkAoi").addEventListener("change", (e) => {
        if (aoiDataSource) aoiDataSource.show = e.target.checked;
    });

    // Vertical Exaggeration slider
    const exagSlider = document.getElementById("exagSlider");
    const exagValue = document.getElementById("exagValue");
    exagSlider.addEventListener("input", (e) => {
        currentExaggeration = parseFloat(e.target.value);
        exagValue.innerText = `${currentExaggeration.toFixed(1)}x`;
        const newMatrix = getModelMatrix(currentExaggeration);
        for (const model of Object.values(terrainPrimitives)) {
            if (model) model.modelMatrix = newMatrix;
        }
    });

    // Viewpoint buttons
    document.querySelectorAll(".btn-view").forEach(btn => {
        btn.addEventListener("click", () => {
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

window.addEventListener("DOMContentLoaded", initCesiumTwin);
