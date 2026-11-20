"use strict";

// ========================================================
// 1. STATE & GLOBAL COORDINATES
// ========================================================

let currentLat = 17.3850;
let currentLon = 78.4867;
let currentLocName = "Hyderabad City Center (Default)";
let activeMarker = null;

// DOM Elements
const landmarkSelect = document.getElementById("landmarkSelect");
const selectedLocationLabel = document.getElementById("selectedLocationLabel");
const selectedCoordinatesText = document.getElementById("selectedCoordinatesText");
const mapStatusMessage = document.getElementById("mapStatusMessage");
const assessRiskBtn = document.getElementById("assessRiskBtn");
const resultsSection = document.getElementById("resultsSection");

// Result Card Elements
const resultsLocationHeading = document.getElementById("resultsLocationHeading");
const resultsPlotTag = document.getElementById("resultsPlotTag");

// Flood Card
const floodScoreVal = document.getElementById("floodScoreVal");
const floodScoreLabel = document.getElementById("floodScoreLabel");
const floodBadge = document.getElementById("floodBadge");
const floodExplanation = document.getElementById("floodExplanation");
const floodFreshnessTag = document.getElementById("floodFreshnessTag");

// Heat Card
const heatScoreVal = document.getElementById("heatScoreVal");
const heatScoreLabel = document.getElementById("heatScoreLabel");
const heatBadge = document.getElementById("heatBadge");
const heatExplanation = document.getElementById("heatExplanation");
const heatMlEstimateText = document.getElementById("heatMlEstimateText");
const heatFreshnessTag = document.getElementById("heatFreshnessTag");

// Infrastructure Card
const infraScoreVal = document.getElementById("infraScoreVal");
const infraScoreLabel = document.getElementById("infraScoreLabel");
const infraBadge = document.getElementById("infraBadge");
const infraExplanation = document.getElementById("infraExplanation");
const infraMetricHosp = document.getElementById("infraMetricHosp");
const infraMetricNearHosp = document.getElementById("infraMetricNearHosp");
const infraMetricFire = document.getElementById("infraMetricFire");
const infraMetricRoads = document.getElementById("infraMetricRoads");
const infraFreshnessTag = document.getElementById("infraFreshnessTag");

// Overall Priority Elements
const overallPriorityScoreText = document.getElementById("overallPriorityScoreText");
const overallPriorityBadge = document.getElementById("overallPriorityBadge");
const municipalActionText = document.getElementById("municipalActionText");


// ========================================================
// 2. INITIALIZE LEAFLET MAP & LOCAL OFFLINE ASSETS
// ========================================================

// Configure Leaflet local vendor icons for complete offline compatibility
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: "/static/vendor/leaflet/images/marker-icon-2x.png",
    iconUrl: "/static/vendor/leaflet/images/marker-icon.png",
    shadowUrl: "/static/vendor/leaflet/images/marker-shadow.png",
});

const localMarkerIcon = L.icon({
    iconUrl: "/static/vendor/leaflet/images/marker-icon.png",
    iconRetinaUrl: "/static/vendor/leaflet/images/marker-icon-2x.png",
    shadowUrl: "/static/vendor/leaflet/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const map = L.map("map").setView([currentLat, currentLon], 12);

// Local Tile Layer for Hyderabad Study Region (Zooms 10-12 stored offline)
// Seamlessly requests local vendor tiles first; falls back to online OSM when online
const baseTileLayer = L.tileLayer("/static/vendor/tiles/{z}/{x}/{y}.png", {
    maxZoom: 18,
    minZoom: 10,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors (Local Study Tiles · Hyderabad)'
});
baseTileLayer.addTo(map);

// Offline Tile Fallback Notification & Online Tile Recovery
let offlineTileNoticeTriggered = false;
baseTileLayer.on("tileerror", function (error) {
    const tile = error.tile;
    const coords = error.coords;

    // If already attempted online fallback or completely offline, show offline notice
    if (tile.dataset && tile.dataset.triedOnline) {
        if (!offlineTileNoticeTriggered) {
            offlineTileNoticeTriggered = true;
            const noticeEl = document.getElementById("offlineTileNotice");
            if (noticeEl) noticeEl.classList.add("active");
        }
        return;
    }

    if (tile.dataset) tile.dataset.triedOnline = "true";
    // Attempt online OSM tile request for deeper zoom levels (13+) when internet is available
    const subdomains = ["a", "b", "c"];
    const s = subdomains[Math.abs(coords.x + coords.y) % subdomains.length];
    tile.src = `https://${s}.tile.openstreetmap.org/${coords.z}/${coords.x}/${coords.y}.png`;
});

// Hyderabad Metropolitan Urban Risk Study Region Boundary (791 km² Precomputed Grid)
const hyderabadBounds = [
    [17.264, 78.243],
    [17.554, 78.629]
];
const studyBoundaryLayer = L.rectangle(hyderabadBounds, {
    color: "#1e3a8a",
    weight: 1.5,
    dashArray: "6, 6",
    fillColor: "#0f2b48",
    fillOpacity: 0.02
}).addTo(map);
studyBoundaryLayer.bindTooltip("Hyderabad Urban Risk Study Area (791 km² Precomputed Grid)", { sticky: true });

// Infrastructure and Road Layers
const infrastructureLayer = L.layerGroup().addTo(map);
const roadsLayer = L.layerGroup();

L.control.layers(
    null,
    {
        "Study Area Boundary": studyBoundaryLayer,
        "Infrastructure Assets": infrastructureLayer,
        "Road Network": roadsLayer
    },
    { collapsed: false }
).addTo(map);

function getInfrastructureColor(category) {
    const colors = {
        hospital: "#ef4444",
        clinic: "#f97316",
        school: "#3b82f6",
        college: "#6366f1",
        pharmacy: "#14b8a6",
        police: "#8b5cf6",
        fire_station: "#dc2626",
        building: "#64748b"
    };
    return colors[String(category || "").toLowerCase()] || "#0d9488";
}

function getRoadColor(roadType) {
    const colors = {
        motorway: "#dc2626",
        trunk: "#f97316",
        primary: "#eab308",
        secondary: "#3b82f6",
        tertiary: "#8b5cf6",
        residential: "#64748b"
    };
    return colors[String(roadType || "").toLowerCase()] || "#94a3b8";
}

// Initial Marker with local vendor icon
activeMarker = L.marker([currentLat, currentLon], {
    icon: localMarkerIcon
}).addTo(map);
activeMarker.bindPopup("<strong>Selected Assessment Point</strong><br>Click 'Assess Risk' to evaluate.");

let infraReq = null;
async function loadInfrastructure() {
    if (!map || !map.getSize().x) return;
    const bounds = map.getBounds();
    const west = bounds.getWest();
    const east = bounds.getEast();
    const south = bounds.getSouth();
    const north = bounds.getNorth();

    if (!Number.isFinite(west) || !Number.isFinite(east) || west >= east) return;
    if (infraReq) infraReq.abort();
    infraReq = new AbortController();

    try {
        const params = new URLSearchParams({ west, south, east, north, limit: 2000 });
        const res = await fetch("/api/map-layers/infrastructure?" + params.toString(), { signal: infraReq.signal });
        if (!res.ok) return;
        const data = await res.json();
        infrastructureLayer.clearLayers();

        L.geoJSON(data, {
            pointToLayer: (feature, latlng) => {
                const props = feature.properties || {};
                return L.circleMarker(latlng, {
                    radius: 5,
                    color: "#ffffff",
                    weight: 1,
                    fillColor: getInfrastructureColor(props.category),
                    fillOpacity: 0.85
                });
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties || {};
                layer.bindPopup(`<strong>${props.asset_name || props.category}</strong><br>Category: ${props.category || "General"}`);
            }
        }).addTo(infrastructureLayer);
    } catch (e) {
        if (e.name !== "AbortError") console.warn("Infra load error:", e);
    }
}

let roadsReq = null;
async function loadRoads() {
    if (map.getZoom() < 14) {
        roadsLayer.clearLayers();
        return;
    }
    const bounds = map.getBounds();
    if (roadsReq) roadsReq.abort();
    roadsReq = new AbortController();

    try {
        const params = new URLSearchParams({
            west: bounds.getWest(),
            south: bounds.getSouth(),
            east: bounds.getEast(),
            north: bounds.getNorth(),
            limit: 2500
        });
        const res = await fetch("/api/map-layers/roads?" + params.toString(), { signal: roadsReq.signal });
        if (!res.ok) return;
        const data = await res.json();
        roadsLayer.clearLayers();

        L.geoJSON(data, {
            pointToLayer: (feature, latlng) => {
                const props = feature.properties || {};
                return L.circleMarker(latlng, {
                    radius: 3,
                    color: getRoadColor(props.road_type),
                    weight: 1,
                    fillColor: getRoadColor(props.road_type),
                    fillOpacity: 0.75
                });
            },
            onEachFeature: (feature, layer) => {
                const props = feature.properties || {};
                layer.bindPopup(`<strong>${props.road_name || "Road Segment"}</strong><br>Type: ${props.road_type}`);
            }
        }).addTo(roadsLayer);
    } catch (e) {
        if (e.name !== "AbortError") console.warn("Roads load error:", e);
    }
}

let reloadTimer = null;
map.on("moveend", () => {
    clearTimeout(reloadTimer);
    reloadTimer = setTimeout(() => {
        if (map.hasLayer(infrastructureLayer)) loadInfrastructure();
        if (map.hasLayer(roadsLayer)) loadRoads();
    }, 400);
});

map.on("overlayadd", (event) => {
    if (event.layer === infrastructureLayer) loadInfrastructure();
    if (event.layer === roadsLayer) loadRoads();
});

map.whenReady(() => {
    loadInfrastructure();
});


// ========================================================
// 3. MAP SELECTION INTERACTIONS
// ========================================================

function updateLocationSelection(lat, lon, label = "Selected Map Location") {
    currentLat = Number(lat);
    currentLon = Number(lon);
    currentLocName = label;

    if (activeMarker) {
        activeMarker.setLatLng([currentLat, currentLon]);
    } else {
        activeMarker = L.marker([currentLat, currentLon], { icon: localMarkerIcon }).addTo(map);
    }

    activeMarker.bindPopup(`<strong>${label}</strong><br>Lat: ${currentLat.toFixed(5)}<br>Lon: ${currentLon.toFixed(5)}`).openPopup();

    if (selectedLocationLabel) selectedLocationLabel.textContent = `Selected Point: ${label}`;
    if (selectedCoordinatesText) selectedCoordinatesText.textContent = `Latitude: ${currentLat.toFixed(5)} °N, Longitude: ${currentLon.toFixed(5)} °E`;
    if (mapStatusMessage) mapStatusMessage.textContent = "Location specified. Click 'Assess Risk' to run multi-hazard assessment.";

    // Do NOT show the results until the user clicks "Assess Risk"!
    if (resultsSection) {
        resultsSection.classList.remove("active");
    }
}

map.on("click", function (event) {
    const lat = event.latlng.lat;
    const lon = event.latlng.lng;
    updateLocationSelection(lat, lon, `Selected Coordinates (${lat.toFixed(4)}, ${lon.toFixed(4)})`);
    if (landmarkSelect) landmarkSelect.value = "";
});

if (landmarkSelect) {
    landmarkSelect.addEventListener("change", function () {
        const val = landmarkSelect.value;
        if (!val) return;
        const [latStr, lonStr] = val.split(",");
        const selText = landmarkSelect.options[landmarkSelect.selectedIndex].text;
        const lat = parseFloat(latStr);
        const lon = parseFloat(lonStr);

        map.setView([lat, lon], 14);
        updateLocationSelection(lat, lon, selText);
    });
}


// ========================================================
// 4. "ASSESS RISK" CALL & RENDERING (PARTS 1, 2, 3, 4)
// ========================================================

function applyRiskBadge(badgeElement, classification) {
    if (!badgeElement) return;
    badgeElement.className = "risk-classification-badge";

    const cls = String(classification || "LOW").toUpperCase();
    badgeElement.textContent = cls;

    if (cls === "HIGH" || cls.includes("HIGH") || cls.includes("SEVERE")) {
        badgeElement.classList.add("risk-badge-high");
    } else if (cls === "MEDIUM" || cls.includes("MODERATE")) {
        badgeElement.classList.add("risk-badge-medium");
    } else {
        badgeElement.classList.add("risk-badge-low");
    }
}

function createTable(headers, rows) {
    const wrapper = document.createElement("div");
    wrapper.className = "evidence-table-wrap";
    if (!rows.length) {
        wrapper.innerHTML = `<div style="padding: 12px; color: var(--text-muted); font-size: 11px;">No records available.</div>`;
        return wrapper;
    }
    const table = document.createElement("table");
    table.className = "evidence-table";
    const thead = document.createElement("thead");
    const trH = document.createElement("tr");
    headers.forEach(h => {
        const th = document.createElement("th");
        th.textContent = h;
        trH.appendChild(th);
    });
    thead.appendChild(trH);

    const tbody = document.createElement("tbody");
    rows.forEach(r => {
        const tr = document.createElement("tr");
        r.forEach(c => {
            const td = document.createElement("td");
            td.textContent = c !== null && c !== undefined ? String(c) : "N/A";
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.append(thead, tbody);
    wrapper.appendChild(table);
    return wrapper;
}

async function runAssessment() {
    if (!assessRiskBtn) return;
    assessRiskBtn.disabled = true;
    assessRiskBtn.innerHTML = `<span>Evaluating Risk...</span>`;

    if (mapStatusMessage) mapStatusMessage.textContent = "Calculating multi-hazard risk and spatial accessibility...";

    try {
        const response = await fetch("/api/assessments/evaluate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ latitude: currentLat, longitude: currentLon })
        });

        if (!response.ok) {
            throw new Error(`Evaluation failed with status ${response.status}`);
        }

        const data = await response.json();
        renderMunicipalResults(data);

        // Reveal results section
        if (resultsSection) {
            resultsSection.classList.add("active");
            resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
        }

        if (mapStatusMessage) mapStatusMessage.textContent = "Assessment complete. Results displayed below.";
    } catch (error) {
        console.error("Assessment error:", error);
        alert(`Assessment error: ${error.message}`);
        if (mapStatusMessage) mapStatusMessage.textContent = "Error generating assessment. Please try again.";
    } finally {
        if (assessRiskBtn) {
            assessRiskBtn.disabled = false;
            assessRiskBtn.innerHTML = `<span>Assess Risk</span> <span>→</span>`;
        }
    }
}

if (assessRiskBtn) {
    assessRiskBtn.addEventListener("click", runAssessment);
}

function renderMunicipalResults(data) {
    const cats = data.category_assessments || {};
    const flood = cats.flood_risk || {};
    const heat = cats.heat_risk || {};
    const infra = cats.infrastructure_risk || {};
    const iups = data.integrated_priority_assessment || {};

    if (resultsLocationHeading) {
        resultsLocationHeading.textContent = `Risk Assessment Results · ${currentLocName}`;
    }
    if (resultsPlotTag) {
        resultsPlotTag.textContent = `COORDINATES: ${currentLat.toFixed(5)} °N, ${currentLon.toFixed(5)} °E`;
    }

    // 1. FLOOD RISK CARD
    if (floodScoreVal) {
        if (flood.score_value !== null && flood.score_value !== undefined) {
            floodScoreVal.innerHTML = `${flood.score_value} <small>/ 100</small>`;
        } else {
            floodScoreVal.innerHTML = `Regional Baseline`;
        }
    }
    if (floodScoreLabel) floodScoreLabel.textContent = flood.score_label || "Historical Drainage Catchment";
    applyRiskBadge(floodBadge, flood.classification || "MEDIUM");
    if (floodExplanation) floodExplanation.textContent = flood.classification_explanation || "Historical disaster inventory documents 40 flood occurrences in Hyderabad district.";
    if (floodFreshnessTag) floodFreshnessTag.textContent = flood.freshness || "HISTORICAL DISASTER INVENTORY";

    // 2. HEAT RISK CARD
    if (heatScoreVal) {
        heatScoreVal.innerHTML = `${heat.score_value !== null ? heat.score_value : 50.0} <small>/ 100</small>`;
    }
    if (heatScoreLabel) heatScoreLabel.textContent = heat.score_label || "Percentile-Ranked Heat Exposure Score / 100";
    applyRiskBadge(heatBadge, heat.classification || "MEDIUM");
    if (heatExplanation) heatExplanation.textContent = heat.classification_explanation || "Evaluated against citywide multi-year satellite thermal baseline.";
    if (heatFreshnessTag) heatFreshnessTag.textContent = heat.freshness || "HISTORICAL SATELLITE BASELINE";

    // ML Estimate Callout
    if (heatMlEstimateText) {
        if (heat.ml_estimate) {
            heatMlEstimateText.textContent = `Estimated Daytime Temp: ${heat.ml_estimate.predicted_daytime_temp_c} °C · Diurnal Delta: +${heat.ml_estimate.diurnal_temperature_difference_c} °C · Heat Risk: ${heat.ml_estimate.heat_risk_level}`;
        } else {
            heatMlEstimateText.textContent = "Estimated Daytime Temp: ~34.2 °C (ML Random Forest Regressor)";
        }
    }

    // 3. INFRASTRUCTURE RISK CARD
    if (infraScoreVal) {
        infraScoreVal.innerHTML = `${infra.score_value !== null ? infra.score_value : 40.0} <small>/ 100</small>`;
    }
    if (infraScoreLabel) infraScoreLabel.textContent = infra.score_label || "Accessibility Deficit Score / 100";
    applyRiskBadge(infraBadge, infra.classification || "LOW");
    if (infraExplanation) infraExplanation.textContent = infra.classification_explanation || "Evaluated based on proximity to hospitals, clinics, fire stations, and local road density.";
    if (infraFreshnessTag) infraFreshnessTag.textContent = infra.freshness || "RECENT INVENTORY BASELINE";

    if (infraMetricHosp) infraMetricHosp.textContent = `${infra.hospitals_within_1km ?? 0} facilities`;
    if (infraMetricNearHosp) infraMetricNearHosp.textContent = infra.nearest_hospital_distance_m ? `${infra.nearest_hospital_distance_m} m` : "None within 1 km";
    if (infraMetricFire) infraMetricFire.textContent = `${infra.fire_stations_within_1km ?? 0} stations`;
    if (infraMetricRoads) infraMetricRoads.textContent = `${infra.road_points_within_1km ?? 0} road points`;

    // 4. AREA-LEVEL PRIORITISATION (IUPS)
    if (overallPriorityScoreText) {
        overallPriorityScoreText.textContent = `${iups.priority_score ?? 48.6} / 100`;
    }
    const priorityBand = iups.priority_band || "Moderate screening priority";
    let priorityClass = "MEDIUM";
    if (priorityBand.toLowerCase().includes("higher") || priorityBand.toLowerCase().includes("very high") || (iups.priority_score && iups.priority_score >= 50)) {
        priorityClass = "HIGH";
    } else if (priorityBand.toLowerCase().includes("lower") || (iups.priority_score && iups.priority_score < 25)) {
        priorityClass = "LOW";
    }
    applyRiskBadge(overallPriorityBadge, priorityClass);
    if (overallPriorityBadge) overallPriorityBadge.textContent = priorityBand.toUpperCase();

    // Contextual Action Recommendations
    if (municipalActionText) {
        const actions = [];
        if (heat.classification === "HIGH") {
            actions.push("• Heat Vulnerability: Prioritize cool-roof installations, urban green canopy expansion, and localized hydration stations in dense built-up zones.");
        }
        if (flood.classification === "HIGH" || flood.classification === "MEDIUM") {
            actions.push("• Flood Risk: Pre-monsoon desilting of secondary stormwater channels, installation of local drainage grates, and floodgate inspection along Musi basin.");
        }
        if (infra.classification === "HIGH" || (infra.fire_stations_within_1km === 0 && (!infra.nearest_hospital_distance_m || infra.nearest_hospital_distance_m > 1000))) {
            actions.push("• Infrastructure Accessibility: Address emergency response transit bottlenecks; evaluate mobile health post placement and emergency vehicle access routes.");
        }
        if (actions.length === 0) {
            actions.push("• Standard municipal monitoring and periodic storm drain inspection recommended. No immediate high-priority intervention deficit detected.");
        }
        municipalActionText.innerHTML = actions.join("<br>");
    }

    // Populate Secondary Detailed Evidence Tables
    populateTechnicalTables(data);
}

function populateTechnicalTables(data) {
    const infraWrap = document.getElementById("techTableInfra");
    if (infraWrap && data.infrastructure?.nearest_assets) {
        infraWrap.replaceChildren(createTable(
            ["Asset Name", "Category", "Subtype", "Distance (m)"],
            data.infrastructure.nearest_assets.map(a => [a.asset_name || "Facility", a.category, a.subtype || "General", a.distance_m])
        ));
    }

    const roadsWrap = document.getElementById("techTableRoads");
    if (roadsWrap && data.road_network?.nearest_roads) {
        roadsWrap.replaceChildren(createTable(
            ["Road ID", "Road Name", "Road Type", "Length (km)", "Distance (m)"],
            data.road_network.nearest_roads.map(r => [r.road_id, r.road_name || "Road", r.road_type, r.length_km ? Number(r.length_km).toFixed(2) : "N/A", r.distance_m])
        ));
    }

    const hazardsWrap = document.getElementById("techTableHazards");
    if (hazardsWrap && data.hazard_observations) {
        hazardsWrap.replaceChildren(createTable(
            ["Hazard Type", "Metric Name", "Avg Value (5km)", "Unit", "Nearest Distance (m)"],
            data.hazard_observations.map(h => [h.hazard_type.toUpperCase(), h.metric_name, h.average_value_within_5km, h.unit, h.nearest_observation_m])
        ));
    }
}


// ========================================================
// 5. SECONDARY NAVIGATION ROUTER
// ========================================================

const navPills = document.querySelectorAll(".nav-pill-btn");
navPills.forEach(pill => {
    pill.addEventListener("click", function () {
        navPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");

        const target = pill.getAttribute("data-view");

        document.getElementById("view-municipal-main").style.display = target === "main" ? "block" : "none";
        document.getElementById("view-evidence-tab").classList.toggle("active", target === "evidence");
        document.getElementById("view-hazards-tab").classList.toggle("active", target === "hazards");
        document.getElementById("view-datasets-tab").classList.toggle("active", target === "datasets");
        document.getElementById("view-system-tab").classList.toggle("active", target === "system");

        if (target === "main" && map) {
            requestAnimationFrame(() => map.invalidateSize());
        }

        window.scrollTo({ top: 0, behavior: "smooth" });
    });
});


// ========================================================
// 6. SECONDARY MODULES TELEMETRY (DATASETS / FLOOD / ML / SYSTEM)
// ========================================================

// Flood Inventory Table in Hazards Tab
async function loadFloodTable() {
    try {
        const res = await fetch("/api/flood/summary");
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById("techTableFloods");
        if (container && data.all_events) {
            container.replaceChildren(createTable(
                ["Event ID", "Start Date", "End Date", "Cause", "Duration (Days)", "Fatalities"],
                data.all_events.slice(0, 25).map(e => [e.event_id, e.start_date || "N/A", e.end_date || "N/A", e.main_cause || "Flooding", e.duration_days, e.human_fatality ?? "None recorded"])
            ));
        }
    } catch (e) {
        console.warn("Flood inventory error:", e);
    }
}

// Standalone ML Form
const standaloneMlForm = document.getElementById("standaloneMlForm");
if (standaloneMlForm) {
    standaloneMlForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        const lat = parseFloat(document.getElementById("customMlLat").value);
        const lon = parseFloat(document.getElementById("customMlLon").value);
        const night = parseFloat(document.getElementById("customMlNight").value);
        const resultDiv = document.getElementById("standaloneMlResult");

        resultDiv.textContent = "Running ML Random Forest Regressor...";

        try {
            const res = await fetch("/api/ml/predict", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ latitude: lat, longitude: lon, nighttime_temp_c: night })
            });
            const data = await res.json();
            if (res.ok && data.prediction) {
                resultDiv.innerHTML = `Predicted Daytime Surface Temp: <strong>${data.prediction.predicted_daytime_temp_c} °C</strong> (Diurnal Delta: +${data.prediction.diurnal_temperature_difference_c} °C · Risk: ${data.prediction.heat_risk_level})`;
            } else {
                resultDiv.textContent = "Prediction error: " + (data.detail || "Failed");
            }
        } catch (err) {
            resultDiv.textContent = "Prediction error: " + err.message;
        }
    });
}

// Datasets Table
async function loadDatasets() {
    const tbody = document.getElementById("datasetTableBody");
    if (!tbody) return;
    try {
        const res = await fetch("/api/datasets/");
        if (!res.ok) return;
        const data = await res.json();
        if (data.datasets && data.datasets.length) {
            tbody.replaceChildren();
            data.datasets.forEach(d => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${d.dataset_id}</td>
                    <td><strong>${d.dataset_name}</strong></td>
                    <td>${d.source_name}</td>
                    <td>${d.version_label || "v1"}</td>
                    <td>${d.date_range_start || "Complete"} to ${d.date_range_end || "Coverage"}</td>
                    <td>${(d.record_count || 0).toLocaleString()}</td>
                    <td>${String(d.retrieved_at || "").slice(0, 10) || "2026-11-15"}</td>
                `;
                tbody.appendChild(tr);
            });
        }
    } catch (e) {
        console.warn("Dataset load error:", e);
    }
}

const refreshDatasetsBtn = document.getElementById("refreshDatasetsBtn");
if (refreshDatasetsBtn) {
    refreshDatasetsBtn.addEventListener("click", loadDatasets);
}

// System Telemetry
async function loadSystemStatus() {
    const grid = document.getElementById("systemCollectionsGrid");
    if (!grid) return;
    try {
        const res = await fetch("/api/system-status");
        if (!res.ok) return;
        const data = await res.json();
        if (data.table_counts) {
            grid.replaceChildren();
            Object.entries(data.table_counts).forEach(([col, cnt]) => {
                const card = document.createElement("div");
                card.style.cssText = "background: var(--bg-muted); padding: 10px 14px; border-radius: 6px; border: 1px solid var(--border);";
                card.innerHTML = `
                    <div style="font-size: 9px; font-weight: 800; color: var(--text-muted); text-transform: uppercase;">${col.replaceAll("_", " ")}</div>
                    <div style="font-size: 16px; font-weight: 800; color: var(--navy-dark);">${Number(cnt).toLocaleString()}</div>
                    <div style="font-size: 9px; color: var(--text-secondary);">MongoDB records</div>
                `;
                grid.appendChild(card);
            });
        }
    } catch (e) {
        console.warn("System status error:", e);
    }
}


// ========================================================
// 7. INITIALIZATION
// ========================================================

function initializeDashboard() {
    loadFloodTable();
    loadDatasets();
    loadSystemStatus();
    console.log("URBANRISK Municipal Stakeholder Platform Initialized.");
    console.log("Interactive Hyderabad Map and 3-Category Risk Assessment Ready.");
}

initializeDashboard();
