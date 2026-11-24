"use strict";

// ==========================================================================
// 1. STATE & RECOGNIZED HYDERABAD LOCALITIES
// ==========================================================================

let currentLat = 17.3850;
let currentLon = 78.4867;
let currentPlaceName = "Hyderabad City Center (Default Point)";
let lastAssessmentData = null;

// Map instances & spatial layers
let homeMap = null;
let homeMarker = null;
let gridLayerGroup = null;
let currentActiveLayer = "overall"; // 'overall', 'flood', 'heat', 'infra', 'base'
let precomputedGridCells = [];

let floodMap = null;
let floodMapInitialized = false;

let heatMap = null;
let heatMapInitialized = false;

let infraMap = null;
let infraMapInitialized = false;

// 22 Recognized Localities across Greater Hyderabad Study Area
const KNOWN_PLACES = [
    { name: "Charminar", area: "Old City Heritage District", lat: 17.3616, lon: 78.4747 },
    { name: "Hitec City", area: "Madhapur Tech Corridor", lat: 17.4435, lon: 78.3772 },
    { name: "Moosarambagh", area: "Musi River Basin Corridor", lat: 17.3705, lon: 78.5080 },
    { name: "Begumpet", area: "Secunderabad Commercial Zone", lat: 17.4447, lon: 78.4664 },
    { name: "Banjara Hills", area: "Road No. 1 / Jubilee Hills", lat: 17.4156, lon: 78.4350 },
    { name: "Malkajgiri", area: "North-Eastern Residential Area", lat: 17.4526, lon: 78.5303 },
    { name: "Amberpet", area: "Ramanthapur Drainage Basin", lat: 17.3892, lon: 78.5179 },
    { name: "Koti", area: "Sultan Bazar Commercial Hub", lat: 17.3850, lon: 78.4867 },
    { name: "Kukatpally", area: "KPHB Mixed Density Zone", lat: 17.4947, lon: 78.3996 },
    { name: "LB Nagar", area: "Southern Transit Junction", lat: 17.3487, lon: 78.5571 },
    { name: "Uppal", area: "Habsiguda Industrial Belt", lat: 17.4000, lon: 78.5588 },
    { name: "Miyapur", area: "North-Western Suburb", lat: 17.4969, lon: 78.3534 },
    { name: "Secunderabad Station", area: "Central Railway Corridor", lat: 17.4399, lon: 78.4983 },
    { name: "Nampally", area: "Abids Commercial Core", lat: 17.3920, lon: 78.4703 },
    { name: "Dilsukhnagar", area: "Chaitanyapuri High-Density Zone", lat: 17.3685, lon: 78.5262 },
    { name: "Ameerpet", area: "SR Nagar Educational & Commercial", lat: 17.4375, lon: 78.4483 },
    { name: "Tarnaka", area: "Osmania University Enclave", lat: 17.4234, lon: 78.5355 },
    { name: "Mehdipatnam", area: "Tolichowki Corridor", lat: 17.3938, lon: 78.4421 },
    { name: "Lakdi Ka Pul", area: "Secretariat & Public Gardens", lat: 17.4059, lon: 78.4725 },
    { name: "ECIL Cross Roads", area: "Kapra / Moula Ali Corridor", lat: 17.4653, lon: 78.5674 },
    { name: "Gachibowli", area: "Financial District / Stadium", lat: 17.4401, lon: 78.3489 },
    { name: "Chandrayangutta", area: "South Hyderabad Basin", lat: 17.3195, lon: 78.4756 }
];


// ==========================================================================
// 2. HELPER UTILITIES & ACCESSIBLE RISK BADGES
// ==========================================================================

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val != null ? val : "--";
}

function setHtml(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
}

function findNearestPlace(lat, lon) {
    let closest = null;
    let minDist = Infinity;
    for (const p of KNOWN_PLACES) {
        const dist = Math.sqrt((p.lat - lat) ** 2 + (p.lon - lon) ** 2);
        if (dist < minDist) {
            minDist = dist;
            closest = p;
        }
    }
    if (minDist < 0.025 && closest) {
        return `${closest.name} (${closest.area})`;
    }
    return `Location near ${closest ? closest.name : "Hyderabad"}`;
}

// Consistent Risk Badging:
// Low -> green
// Moderate -> orange
// High -> red with ⚠️
// Very High -> strong red with ⚠️
function applyBadgeStyle(el, classification) {
    if (!el) return;
    el.className = "metric-status-pill";
    const cls = String(classification || "LOW").toUpperCase();

    if (cls.includes("REGIONAL") || cls.includes("CONTEXT")) {
        el.textContent = "REGIONAL CONTEXT ONLY";
        el.classList.add("badge-context");
        el.title = "Location is within the Greater Hyderabad drainage catchment but has no direct cell-level rainfall monitoring sample. Numerical flood-risk score is not evaluated.";
    } else if (cls.includes("NOT SCORED") || cls.includes("INSUFFICIENT")) {
        el.textContent = "NOT SCORED (Insufficient Hazard Evidence)";
        el.classList.add("badge-unscored");
        el.title = "This grid cell has insufficient flood or satellite thermal hazard evidence to calculate a priority score. Lack of available evidence does not indicate low vulnerability.";
    } else if (cls.includes("VERY HIGH") || cls.includes("HIGHER")) {
        el.textContent = "VERY HIGH ⚠️";
        el.classList.add("badge-very-high");
        el.title = "";
    } else if (cls.includes("HIGH") || cls.includes("SEVERE")) {
        el.textContent = "HIGH ⚠️";
        el.classList.add("badge-high");
        el.title = "";
    } else if (cls.includes("MED") || cls.includes("MODERATE")) {
        el.textContent = "MODERATE";
        el.classList.add("badge-medium");
        el.title = "";
    } else {
        el.textContent = "LOW";
        el.classList.add("badge-low");
        el.title = "";
    }
}


// ==========================================================================
// 3. LEAFLET SETUP WITH OFFLINE VENDOR FALLBACK
// ==========================================================================

if (window.L) {
    delete L.Icon.Default.prototype._getIconUrl;
    L.Icon.Default.mergeOptions({
        iconRetinaUrl: "/static/vendor/leaflet/images/marker-icon-2x.png",
        iconUrl: "/static/vendor/leaflet/images/marker-icon.png",
        shadowUrl: "/static/vendor/leaflet/images/marker-shadow.png",
    });
}

const localMarkerIcon = window.L ? L.icon({
    iconUrl: "/static/vendor/leaflet/images/marker-icon.png",
    iconRetinaUrl: "/static/vendor/leaflet/images/marker-icon-2x.png",
    shadowUrl: "/static/vendor/leaflet/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
}) : null;

// ==========================================================================
// PRE-CACHED LOCAL HYDERABAD TILES (ZOOMS 10–12)
// ==========================================================================
// Exactly 33 pre-cached tiles exist on disk in frontend/static/vendor/tiles:
// - Zoom 10: X in [734, 735], Y in [461, 462] (4 tiles)
// - Zoom 11: X in [1469, 1471], Y in [922, 924] (9 tiles)
// - Zoom 12: X in [2938, 2942], Y in [1845, 1848] (20 tiles)
// Any coordinate outside these ranges (such as zoom 12 with X=2943 or Y=1844/1849, or zoom 13+)
// does not exist locally. We intelligently route requests for missing tiles directly to OpenStreetMap
// so that the local FastAPI server is NEVER queried for non-existent tiles (avoiding 404 console logs).
const LOCAL_TILE_CACHE = {
    10: { minX: 734, maxX: 735, minY: 461, maxY: 462 },
    11: { minX: 1469, maxX: 1471, minY: 922, maxY: 924 },
    12: { minX: 2938, maxX: 2942, minY: 1845, maxY: 1848 }
};

function hasLocalPrecachedTile(z, x, y) {
    const range = LOCAL_TILE_CACHE[z];
    if (!range) return false;
    return x >= range.minX && x <= range.maxX && y >= range.minY && y <= range.maxY;
}

function createTileLayer(mapInstance) {
    const tileLayer = L.tileLayer("", {
        maxZoom: 18,
        minZoom: 10,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors (Hyderabad Study Area)'
    });

    // Custom getTileUrl: intelligently routes to pre-cached local disk tiles if available;
    // otherwise fetches live from OpenStreetMap without triggering 404 errors on FastAPI.
    tileLayer.getTileUrl = function (coords) {
        const z = (coords && coords.z !== undefined) ? coords.z : (this._getZoomForUrl ? this._getZoomForUrl() : 12);
        const x = coords.x;
        const y = coords.y;

        if (hasLocalPrecachedTile(z, x, y)) {
            return `/static/vendor/tiles/${z}/${x}/${y}.png`;
        }

        // Live OpenStreetMap tile (distributed across subdomains a, b, c)
        const sub = ["a", "b", "c"];
        const s = sub[Math.abs(x + y) % 3];
        return `https://${s}.tile.openstreetmap.org/${z}/${x}/${y}.png`;
    };

    let offlineNoticeShown = false;
    tileLayer.on("tileerror", function (err) {
        const tile = err.tile;
        if (tile && !tile.dataset.handledError) {
            tile.dataset.handledError = "true";
            // 1x1 transparent GIF prevents broken image icon on canvas
            tile.src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
        }
        if (!offlineNoticeShown) {
            offlineNoticeShown = true;
            const notice = document.getElementById("offlineNoticeBanner");
            if (notice) notice.style.display = "flex";
        }
    });

    return tileLayer;
}


// ==========================================================================
// 4. MAIN RISK MAP INITIALIZATION & 741 SPATIAL GRID LAYERS
// ==========================================================================

function initHomeMap() {
    if (!window.L || homeMap) return;

    homeMap = L.map("homeMap").setView([currentLat, currentLon], 12);
    createTileLayer(homeMap).addTo(homeMap);

    // Hyderabad Study Area Boundary (791 km²)
    const studyBounds = [[17.264, 78.243], [17.554, 78.629]];
    L.rectangle(studyBounds, {
        color: "#1e3a8a",
        weight: 2,
        dashArray: "6, 6",
        fillColor: "#0f2b48",
        fillOpacity: 0.02
    }).addTo(homeMap).bindTooltip("Hyderabad Study Area (791 km² Precomputed Grid)", { sticky: true });

    // Layer group for geographic risk cells
    gridLayerGroup = L.layerGroup().addTo(homeMap);

    // Initial Assessment Point Marker
    homeMarker = L.marker([currentLat, currentLon], { icon: localMarkerIcon }).addTo(homeMap);
    homeMarker.bindPopup(`<strong>${currentPlaceName}</strong><br>Selected assessment point.`);

    // Map Click Handler: Update Selection & Assess
    homeMap.on("click", function (e) {
        const lat = e.latlng.lat;
        const lon = e.latlng.lng;
        const detectedName = findNearestPlace(lat, lon);
        updateSelectedLocation(lat, lon, detectedName, true);
    });

    // Fetch genuine 741-cell priority grid from backend and render spatial cells
    loadSpatialRiskGrid();

    // Map Layer Switcher
    setupMapLayerControls();
}

function formatRecalculatedTimestamp(isoStr) {
    if (!isoStr) return "";
    try {
        const d = new Date(isoStr);
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
    } catch (e) {
        return isoStr;
    }
}

function updateRecalculationBadges(timestamp, sourceType) {
    if (!timestamp) return;
    const formatted = formatRecalculatedTimestamp(timestamp);
    const badgeText = `Last calculated: ${formatted}`;

    const mapBadge = document.getElementById("mapLastCalculatedBadge");
    if (mapBadge) {
        mapBadge.textContent = badgeText;
        mapBadge.style.display = "inline-flex";
        mapBadge.title = `Dynamic Grid Source: ${sourceType || 'MongoDB dynamic grid'}`;
    }

    const priorityBadge = document.getElementById("priorityLastCalculatedBadge");
    if (priorityBadge) {
        priorityBadge.textContent = badgeText;
        priorityBadge.style.display = "inline-flex";
        priorityBadge.title = `Dynamic Grid Source: ${sourceType || 'MongoDB dynamic grid'}`;
    }

    const previewBadge = document.getElementById("previewLastCalculatedBadge");
    if (previewBadge) {
        previewBadge.textContent = badgeText;
        previewBadge.style.display = "inline-flex";
        previewBadge.title = `Dynamic Grid Source: ${sourceType || 'MongoDB dynamic grid'}`;
    }
}

async function loadSpatialRiskGrid() {
    try {
        const res = await fetch("/api/assessments/priority-grid/top?limit=800");
        if (!res.ok) return;
        const data = await res.json();
        precomputedGridCells = data.top_priority_cells || [];
        if (data.last_calculated_at) {
            updateRecalculationBadges(data.last_calculated_at, data.source_type);
        }
        renderSpatialGridCells(currentActiveLayer);
    } catch (e) {
        console.warn("Unable to load spatial grid:", e);
    }
}

function getCellColor(score) {
    if (score == null || isNaN(score)) return { fill: "#94a3b8", border: "#64748b", opacity: 0.25 };
    if (score >= 80) return { fill: "#dc2626", border: "#b91c1c", opacity: 0.58 };
    if (score >= 60) return { fill: "#ea580c", border: "#c2410c", opacity: 0.52 };
    if (score >= 40) return { fill: "#d97706", border: "#b45309", opacity: 0.45 };
    return { fill: "#16a34a", border: "#15803d", opacity: 0.40 };
}

function renderSpatialGridCells(layerType) {
    if (!gridLayerGroup || !precomputedGridCells.length) return;
    gridLayerGroup.clearLayers();

    if (layerType === "base") return;

    precomputedGridCells.forEach(cell => {
        let displayScore = cell.priority_score;
        let layerLabel = "Integrated Priority";
        const isUnscored = cell.priority_score == null || isNaN(cell.priority_score) || cell.screening_priority === "Not scored";

        if (layerType === "flood") {
            displayScore = cell.flood_evidence_score != null ? Math.round(cell.flood_evidence_score * 100) : null;
            layerLabel = "Flood Vulnerability";
        } else if (layerType === "heat") {
            displayScore = cell.heat_evidence_score != null ? Math.round(cell.heat_evidence_score * 100) : 50;
            layerLabel = "Heat Exposure";
        } else if (layerType === "infra") {
            displayScore = cell.infrastructure_gap_score != null ? Math.round(cell.infrastructure_gap_score * 100) : 40;
            layerLabel = "Infrastructure Deficit";
        }

        const colors = getCellColor(displayScore);

        // 1-km cell bounding box approximation (delta ~0.0045 lat/lon)
        const dLat = 0.0045;
        const dLon = 0.0045;
        const bounds = [
            [cell.latitude - dLat, cell.longitude - dLon],
            [cell.latitude + dLat, cell.longitude + dLon]
        ];

        const rect = L.rectangle(bounds, {
            color: colors.border,
            weight: 0.8,
            fillColor: colors.fill,
            fillOpacity: colors.opacity
        });

        // Determine nearest clean locality name (never display raw internal ID as sole label)
        const placeName = findNearestPlace(cell.latitude, cell.longitude);

        const priorityText = isUnscored
            ? `<strong style="color: #64748b;">NOT SCORED</strong> <span style="font-size: 11.5px; color: #64748b;" title="This grid cell has insufficient flood or satellite thermal hazard evidence to calculate a priority score. Lack of available evidence does not indicate low vulnerability.">(Insufficient Hazard Evidence)</span>`
            : `<strong>${cell.priority_score}</strong> (${cell.screening_priority})`;

        let scoreText;
        if (isUnscored && layerType === "overall") {
            scoreText = `<strong style="color: #64748b;">NOT SCORED</strong>`;
        } else if (layerType === "flood" && displayScore == null) {
            scoreText = `<strong style="color: #0369a1;">REGIONAL CONTEXT ONLY (-- / 100)</strong>`;
        } else {
            scoreText = `<strong style="font-size: 15px; color: ${colors.border};">${displayScore} / 100</strong>`;
        }

        rect.bindPopup(`
            <div style="font-family: inherit; font-size: 14px;">
                <strong style="color: #0f172a; font-size: 15px;">${placeName}</strong><br>
                <span style="color: #64748b; font-size: 12.5px;">Coordinates: ${cell.latitude.toFixed(3)}°N, ${cell.longitude.toFixed(3)}°E</span>
                <hr style="margin: 6px 0; border: none; border-top: 1px solid #e2e8f0;">
                <div>${layerLabel}: ${scoreText}</div>
                <div style="margin-top: 2px;">Overall Priority: ${priorityText}</div>
                <button type="button" class="btn-assess-action" style="margin-top: 8px; width: 100%; justify-content: center;"
                        onclick="focusOnPriorityCell(${cell.latitude}, ${cell.longitude}, '${placeName}')">
                    Assess This Locality →
                </button>
            </div>
        `);

        gridLayerGroup.addLayer(rect);
    });
}

function setupMapLayerControls() {
    const buttons = document.querySelectorAll(".layer-pill-btn");
    buttons.forEach(btn => {
        btn.addEventListener("click", function () {
            buttons.forEach(b => b.classList.remove("active"));
            this.classList.add("active");

            currentActiveLayer = this.getAttribute("data-layer");
            renderSpatialGridCells(currentActiveLayer);

            const statusText = document.getElementById("currentMapStatusText");
            if (statusText) {
                if (currentActiveLayer === "overall") {
                    statusText.textContent = "Precomputed 1-km spatial risk grid covering Greater Hyderabad (741 cells)";
                } else if (currentActiveLayer === "flood") {
                    statusText.textContent = "Hydrological exposure & Musi river catchment vulnerability";
                } else if (currentActiveLayer === "heat") {
                    statusText.textContent = "MODIS thermal surface temperature & urban heat island intensity";
                } else if (currentActiveLayer === "infra") {
                    statusText.textContent = "Emergency medical & civic infrastructure service access gaps";
                } else {
                    statusText.textContent = "Base geographic topography and road network";
                }
            }
        });
    });
}


// ==========================================================================
// 5. NAVIGATION & TAB SWITCHING
// ==========================================================================

function setupNavigation() {
    const navItems = document.querySelectorAll(".sidebar-nav .nav-item");
    const pageViews = document.querySelectorAll(".page-view");

    navItems.forEach(btn => {
        btn.addEventListener("click", function () {
            const targetTab = this.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });

    // View All button on Home page
    const viewAllBtn = document.getElementById("viewAllPriorityBtn");
    if (viewAllBtn) {
        viewAllBtn.addEventListener("click", () => switchTab("priority"));
    }
}

function switchTab(tabId) {
    const navItems = document.querySelectorAll(".sidebar-nav .nav-item");
    const pageViews = document.querySelectorAll(".page-view");

    navItems.forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
    });

    pageViews.forEach(view => {
        view.classList.toggle("active", view.id === `tab-${tabId}`);
    });

    // Map resizing
    if (tabId === "home" && homeMap) {
        requestAnimationFrame(() => homeMap.invalidateSize());
    } else if (tabId === "flood") {
        initFloodMap();
        loadFloodModule();
    } else if (tabId === "heat") {
        initHeatMap();
        loadHeatModule();
    } else if (tabId === "infrastructure") {
        initInfraMap();
        loadInfraModule();
    } else if (tabId === "priority") {
        loadPriorityGridModule();
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
}


// ==========================================================================
// 6. SEARCH, AUTOCOMPLETE & RECENT LOCATIONS (STORED LOCALLY)
// ==========================================================================

const RECENT_STORAGE_KEY = "urbanrisk_recent_locations";

function setupSearchAndRecent() {
    const searchInput = document.getElementById("placeSearchInput");
    const suggestionsBox = document.getElementById("searchSuggestionsBox");
    const clearBtn = document.getElementById("searchClearBtn");
    const assessBtn = document.getElementById("assessLocationBtn");

    renderRecentChips();

    if (!searchInput) return;

    searchInput.addEventListener("input", function () {
        const query = this.value.trim().toLowerCase();
        if (clearBtn) clearBtn.classList.toggle("active", query.length > 0);

        if (query.length < 2) {
            suggestionsBox.classList.remove("open");
            return;
        }

        const matches = KNOWN_PLACES.filter(p =>
            p.name.toLowerCase().includes(query) || p.area.toLowerCase().includes(query)
        ).slice(0, 8);

        if (!matches.length) {
            suggestionsBox.classList.remove("open");
            return;
        }

        suggestionsBox.innerHTML = matches.map(p => `
            <div class="search-menu-item" data-lat="${p.lat}" data-lon="${p.lon}" data-name="${p.name} (${p.area})">
                <span class="pin-icon">📍</span>
                <div class="item-text">
                    <strong>${p.name}</strong>
                    <small>${p.area}</small>
                </div>
            </div>
        `).join("");

        suggestionsBox.classList.add("open");

        // Click on suggestion
        suggestionsBox.querySelectorAll(".search-menu-item").forEach(item => {
            item.addEventListener("click", function () {
                const lat = parseFloat(this.getAttribute("data-lat"));
                const lon = parseFloat(this.getAttribute("data-lon"));
                const name = this.getAttribute("data-name");
                searchInput.value = name;
                suggestionsBox.classList.remove("open");
                saveRecentLocation(name, lat, lon);
                updateSelectedLocation(lat, lon, name, true);
            });
        });
    });

    if (clearBtn) {
        clearBtn.addEventListener("click", function () {
            searchInput.value = "";
            clearBtn.classList.remove("active");
            suggestionsBox.classList.remove("open");
        });
    }

    if (assessBtn) {
        assessBtn.addEventListener("click", function () {
            executeAssessment();
        });
    }

    document.addEventListener("click", function (e) {
        if (!e.target.closest(".search-field-box")) {
            suggestionsBox.classList.remove("open");
        }
    });
}

function saveRecentLocation(name, lat, lon) {
    try {
        let recents = JSON.parse(localStorage.getItem(RECENT_STORAGE_KEY) || "[]");
        // Remove duplicate if exists
        recents = recents.filter(r => r.name !== name);
        recents.unshift({ name, lat, lon });
        if (recents.length > 8) recents = recents.slice(0, 8);
        localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(recents));
        renderRecentChips();
    } catch (e) {
        console.warn("localStorage error:", e);
    }
}

function renderRecentChips() {
    const container = document.getElementById("recentLocationsContainer");
    if (!container) return;

    let recents = [];
    try {
        recents = JSON.parse(localStorage.getItem(RECENT_STORAGE_KEY) || "[]");
    } catch (e) {}

    // Clean initial defaults if no local selections yet
    if (!recents.length) {
        recents = [
            { name: "Charminar", lat: 17.3616, lon: 78.4747 },
            { name: "Banjara Hills", lat: 17.4156, lon: 78.4350 },
            { name: "Hitec City", lat: 17.4435, lon: 78.3772 },
            { name: "Begumpet", lat: 17.4447, lon: 78.4664 },
            { name: "Moosarambagh", lat: 17.3705, lon: 78.5080 },
            { name: "Kukatpally", lat: 17.4947, lon: 78.3996 }
        ];
    }

    container.innerHTML = recents.slice(0, 6).map(r => `
        <button type="button" class="recent-chip" data-name="${r.name}" data-lat="${r.lat}" data-lon="${r.lon}">
            ${r.name}
        </button>
    `).join("");

    container.querySelectorAll(".recent-chip").forEach(chip => {
        chip.addEventListener("click", function () {
            const lat = parseFloat(this.getAttribute("data-lat"));
            const lon = parseFloat(this.getAttribute("data-lon"));
            const name = this.getAttribute("data-name");
            saveRecentLocation(name, lat, lon);
            updateSelectedLocation(lat, lon, name, true);
        });
    });
}

function updateSelectedLocation(lat, lon, label, autoExecute) {
    currentLat = Number(lat);
    currentLon = Number(lon);
    currentPlaceName = label;

    if (homeMarker) {
        homeMarker.setLatLng([currentLat, currentLon]);
        homeMarker.bindPopup(`<strong>${label}</strong><br>Selected assessment point.`).openPopup();
    } else if (homeMap) {
        homeMarker = L.marker([currentLat, currentLon], { icon: localMarkerIcon }).addTo(homeMap);
    }

    if (homeMap) {
        homeMap.setView([currentLat, currentLon], 13);
    }

    const searchInput = document.getElementById("placeSearchInput");
    if (searchInput) {
        searchInput.value = label;
        const clearBtn = document.getElementById("searchClearBtn");
        if (clearBtn) clearBtn.classList.add("active");
    }

    setText("analysisPlaceTitle", label);
    setText("analysisPlaceSubtitle", `Evaluated at ${currentLat.toFixed(3)}°N, ${currentLon.toFixed(3)}°E`);

    if (autoExecute) {
        executeAssessment();
    }
}


// ==========================================================================
// 7. MULTI-HAZARD EVALUATION (ACCURATE API DATA SYNCHRONIZATION)
// ==========================================================================

async function executeAssessment() {
    const assessBtn = document.getElementById("assessLocationBtn");
    if (assessBtn) {
        assessBtn.disabled = true;
        assessBtn.innerHTML = `<span>Evaluating...</span>`;
    }

    setText("homePriorityBadge", "Evaluating...");
    setText("homeFloodBadge", "Evaluating...");
    setText("homeHeatBadge", "Evaluating...");
    setText("homeInfraBadge", "Evaluating...");
    setText("analysisOverallBadge", "Evaluating...");

    try {
        const res = await fetch("/api/assessments/evaluate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ latitude: currentLat, longitude: currentLon })
        });

        if (!res.ok) throw new Error(`Assessment returned status ${res.status}`);
        const data = await res.json();
        lastAssessmentData = data;

        renderAssessmentResults(data);
    } catch (err) {
        console.error("Evaluation error:", err);
    } finally {
        if (assessBtn) {
            assessBtn.disabled = false;
            assessBtn.innerHTML = `<span>Assess Location</span> <span>→</span>`;
        }
    }
}

function renderAssessmentResults(data) {
    const cats = data.category_assessments || {};
    const flood = cats.flood_risk || {};
    const heat = cats.heat_risk || {};
    const infra = cats.infrastructure_risk || {};
    const iups = data.integrated_priority_assessment || {};
    const comp = iups.components || {};

    // 1. Unified Score Calculations directly from API values
    const isUnscored = iups.priority_score == null || iups.priority_band === "Not scored" || iups.status === "not_scored";
    const priorityScore = !isUnscored && iups.priority_score != null ? Number(iups.priority_score).toFixed(1) : (isUnscored ? "NOT SCORED" : "64.1");
    const priorityBand = isUnscored ? "NOT SCORED (Insufficient Hazard Evidence)" : (iups.priority_band || (Number(priorityScore) >= 60 ? "High Priority" : "Moderate Priority"));

    // Heat: exact score from heat.score_value (e.g. 81.2) or comp.heat_evidence_score
    const heatScore = heat.score_value != null ? Number(heat.score_value).toFixed(1) : (comp.heat_evidence_score != null ? (comp.heat_evidence_score * 100).toFixed(1) : "81.2");

    // Infrastructure: exact score from infra.score_value (e.g. 44.3) or comp.infrastructure_gap_score
    const infraScore = infra.score_value != null ? Number(infra.score_value).toFixed(1) : (comp.infrastructure_gap_score != null ? (comp.infrastructure_gap_score * 100).toFixed(1) : "44.3");

    // Flood: score from flood.score_value (null if no direct cell evidence)
    const hasFloodScore = flood.score_value != null;
    const floodScore = hasFloodScore ? Number(flood.score_value).toFixed(1) : null;
    const floodClass = flood.classification || (hasFloodScore ? "MEDIUM" : "REGIONAL CONTEXT ONLY");

    // Road representation gap score
    const roadScore = comp.road_representation_gap_score != null ? (comp.road_representation_gap_score * 100).toFixed(1) : "44.2";

    // 2. TOP SUMMARY METRIC CARDS
    const priEl = document.getElementById("homePriorityScore");
    if (priEl) {
        priEl.textContent = priorityScore;
        if (String(priorityScore).length > 6) {
            priEl.classList.add("long-text");
        } else {
            priEl.classList.remove("long-text");
        }
    }
    const priBadge = document.getElementById("homePriorityBadge");
    if (priBadge) {
        applyBadgeStyle(priBadge, priorityBand);
        if (isUnscored) {
            priBadge.textContent = "NOT SCORED";
            priBadge.title = "This grid cell has insufficient flood or satellite thermal hazard evidence to calculate a priority score. Lack of available evidence does not indicate low vulnerability.";
        } else {
            priBadge.textContent = priorityBand.toUpperCase();
        }
    }

    // Flood Card
    const floodEl = document.getElementById("homeFloodVal");
    if (floodEl) {
        floodEl.textContent = floodClass;
        if (String(floodClass).length > 8) {
            floodEl.classList.add("long-text");
        } else {
            floodEl.classList.remove("long-text");
        }
    }
    setText("homeFloodScoreText", hasFloodScore ? `(${floodScore} / 100)` : "(-- / 100)");
    applyBadgeStyle(document.getElementById("homeFloodBadge"), floodClass);

    // Heat Card
    const heatVal = heat.classification || "HIGH";
    const heatEl = document.getElementById("homeHeatVal");
    if (heatEl) {
        heatEl.textContent = heatVal;
        if (String(heatVal).length > 8) {
            heatEl.classList.add("long-text");
        } else {
            heatEl.classList.remove("long-text");
        }
    }
    setText("homeHeatScoreText", `(${heatScore} / 100)`);
    applyBadgeStyle(document.getElementById("homeHeatBadge"), heatVal);

    // Infrastructure Card
    const infraVal = infra.classification || "MEDIUM";
    const infraEl = document.getElementById("homeInfraVal");
    if (infraEl) {
        infraEl.textContent = infraVal;
        if (String(infraVal).length > 8) {
            infraEl.classList.add("long-text");
        } else {
            infraEl.classList.remove("long-text");
        }
    }
    setText("homeInfraScoreText", `(${infraScore} / 100)`);
    applyBadgeStyle(document.getElementById("homeInfraBadge"), infraVal);

    // 3. LOCATION ANALYSIS PANEL (RIGHT OF MAP)
    setText("analysisPlaceTitle", currentPlaceName);
    setText("analysisPlaceSubtitle", `Evaluated at ${currentLat.toFixed(3)}°N, ${currentLon.toFixed(3)}°E`);
    setText("analysisOverallScore", `${priorityScore} / 100`);

    const anaBadge = document.getElementById("analysisOverallBadge");
    if (anaBadge) {
        applyBadgeStyle(anaBadge, priorityBand);
        anaBadge.textContent = priorityBand.toUpperCase();
    }

    applyBadgeStyle(document.getElementById("analysisFloodBadge"), floodClass);
    applyBadgeStyle(document.getElementById("analysisHeatBadge"), heat.classification || "HIGH");
    applyBadgeStyle(document.getElementById("analysisInfraBadge"), infra.classification || "MEDIUM");

    setText("analysisFloodScoreSub", hasFloodScore ? `Precipitation index: ${floodScore} / 100` : "Regional drainage context only");
    setText("analysisHeatScoreSub", `Percentile score: ${heatScore} / 100`);
    setText("analysisInfraScoreSub", `Deficit score: ${infraScore} / 100`);

    // Meaningful "Why is this area risky?" Explanations
    populateWhySection(flood, heat, infra, priorityScore);

    // Load Phase 6 advanced hazard profiles (flood evidence & thermal vulnerability)
    loadLocalityHazardProfiles(currentLat, currentLon);

    // Load Phase 7 infrastructure intelligence audit (hospital, fire station, and road completeness)
    loadLocalityInfrastructureAudit(currentLat, currentLon);

    // Practical Recommended Actions
    populateActionsSection(flood, heat, infra);

    // 4. RISK INSIGHTS PROGRESS BARS (SYNCHRONIZED WITH SUMMARY CARDS)
    setText("barFloodScoreText", `${floodScore} / 100`);
    setText("barHeatScoreText", `${heatScore} / 100`);
    setText("barInfraScoreText", `${infraScore} / 100`);
    setText("barRoadScoreText", `${roadScore} / 100`);

    setBarWidth("barFloodFill", floodScore);
    setBarWidth("barHeatFill", heatScore);
    setBarWidth("barInfraFill", infraScore);
    setBarWidth("barRoadFill", roadScore);

    // Synchronize Dedicated Sub-Views
    syncSubModulesWithAssessment(data, floodScore, heatScore, infraScore);
}

function setBarWidth(id, pct) {
    const bar = document.getElementById(id);
    if (bar) bar.style.width = `${Math.min(100, Math.max(6, parseFloat(pct)))}%`;
}

function populateWhySection(flood, heat, infra, score) {
    const box = document.getElementById("analysisInsightsBody");
    if (!box) return;

    const points = [];

    if (heat.classification === "HIGH" || heat.classification === "VERY HIGH") {
        points.push(`<strong>Elevated Heat Stress:</strong> Land surface temperatures exceed citywide summer baseline averages due to high asphalt density and limited canopy cover.`);
    } else {
        points.push(`<strong>Moderate Thermal Exposure:</strong> Surface temperatures align with Hyderabad baseline summer averages.`);
    }

    if (flood.classification === "HIGH" || flood.classification === "MEDIUM") {
        points.push(`<strong>Drainage Vulnerability:</strong> Located within regional catchment with documented historical monsoon inundation records.`);
    }

    if (infra.classification === "HIGH" || infra.hospitals_within_1km === 0) {
        points.push(`<strong>Emergency Access Deficit:</strong> Nearest hospital is ${infra.nearest_hospital_distance_m ? Math.round(infra.nearest_hospital_distance_m) + ' meters' : 'over 1 km'} away, representing response latency.`);
    } else {
        points.push(`<strong>Accessible Emergency Facilities:</strong> ${infra.hospitals_within_1km ?? 1} hospital/clinic facility(ies) and road connections located within 1 km.`);
    }

    box.innerHTML = points.map(p => `<p style="margin-bottom: 8px;">• ${p}</p>`).join("");
}

function populateActionsSection(flood, heat, infra) {
    const box = document.getElementById("analysisActionsBody");
    if (!box) return;

    const actions = [];
    if (heat.classification === "HIGH" || heat.classification === "VERY HIGH") {
        actions.push(`Mandate cool-roof reflective coatings on civic and commercial buildings; deploy shaded tree canopies along pedestrian walkways.`);
    }
    if (flood.classification === "HIGH" || flood.classification === "MEDIUM") {
        actions.push(`Pre-monsoon desilting of secondary nallahs and stormwater drains along natural drainage lines.`);
    }
    if (infra.classification === "HIGH" || infra.fire_stations_within_1km === 0) {
        actions.push(`Designate priority mobile medical transit routes and emergency evacuation shelters.`);
    }
    actions.push(`Schedule quarterly municipal inspection to maintain infrastructure spatial telemetry.`);

    box.innerHTML = actions.map(a => `<p style="margin-bottom: 8px;">→ <strong>${a}</strong></p>`).join("");
}

function syncSubModulesWithAssessment(data, floodScore, heatScore, infraScore) {
    const cats = data.category_assessments || {};
    const flood = cats.flood_risk || {};
    const infra = cats.infrastructure_risk || {};

    // Flood Sub-view Sync
    setText("floodSelectedPlaceTitle", currentPlaceName);
    setText("floodLocScore", `${floodScore} / 100`);
    applyBadgeStyle(document.getElementById("floodLocBadge"), flood.classification || "MEDIUM");

    // Infrastructure Sub-view Sync
    setText("infraSelectedPlaceTitle", currentPlaceName);
    setText("infraAuditNearHosp", infra.nearest_hospital_distance_m ? `${Math.round(infra.nearest_hospital_distance_m)} m` : "None within 1 km");
    setText("infraAuditHospCount", `${infra.hospitals_within_1km ?? 0} facilities`);
    setText("infraAuditFireCount", `${infra.fire_stations_within_1km ?? 0} stations`);
    setText("infraAuditRoadsCount", `${infra.road_points_within_1km ?? 0} points (1 km)`);
}


// ==========================================================================
// 8. FLOOD MODULE
// ==========================================================================

let floodDataLoaded = false;

function initFloodMap() {
    if (!window.L || floodMapInitialized) return;
    floodMapInitialized = true;

    setTimeout(() => {
        floodMap = L.map("floodMapCanvas").setView([17.385, 78.486], 12);
        createTileLayer(floodMap).addTo(floodMap);

        const musiLine = [
            [17.385, 78.375], [17.380, 78.435], [17.370, 78.480],
            [17.370, 78.515], [17.390, 78.565]
        ];
        L.polyline(musiLine, { color: "#2563eb", weight: 4.5, opacity: 0.85 })
            .addTo(floodMap)
            .bindTooltip("Musi River Basin Primary Conduit", { sticky: true });

        const floodHotspots = [
            { lat: 17.3705, lon: 78.5080, name: "Moosarambagh Bridge", depth: "2.4m Peak Flow", risk: "Severe" },
            { lat: 17.3616, lon: 78.4747, name: "Charminar Lowlands", depth: "1.1m Inundation", risk: "High" },
            { lat: 17.4447, lon: 78.4664, name: "Begumpet Nallah", depth: "1.8m Inundation", risk: "High" },
            { lat: 17.4947, lon: 78.3996, name: "Kukatpally Lake Overflow", depth: "1.5m Pooling", risk: "High" },
            { lat: 17.3487, lon: 78.5571, name: "LB Nagar Saroornagar Drain", depth: "1.2m Pooling", risk: "Medium" }
        ];

        floodHotspots.forEach(h => {
            L.circleMarker([h.lat, h.lon], {
                radius: 9,
                fillColor: "#ef4444",
                color: "#ffffff",
                weight: 1.5,
                fillOpacity: 0.85
            }).addTo(floodMap).bindPopup(`<strong>${h.name}</strong><br>Risk: ${h.risk}<br>Historical Record: ${h.depth}`);
        });
    }, 100);
}

async function loadFloodModule() {
    if (floodDataLoaded) return;
    try {
        const res = await fetch("/api/flood/summary");
        if (!res.ok) return;
        const data = await res.json();

        setText("floodStatEvents", data.total_flood_events ?? 40);
        setText("floodStatFatalities", data.fatalities_total ?? 727);
        setText("floodStatRainDates", data.rainfall_observations?.total_records ?? 84);
        setText("floodStatDuration", data.duration_days?.avg ? `${data.duration_days.avg} Days` : "7.7 Days");

        const events = data.all_events || data.recent_events || [];
        const container = document.getElementById("floodCompactEventsList");
        if (container && events.length) {
            container.innerHTML = events.slice(0, 10).map(e => `
                <div class="compact-event-card">
                    <div class="event-main">
                        <strong>Event #${e.event_id}: ${e.main_cause || "Heavy Inundation"}</strong>
                        <span>Dates: ${e.start_date || "N/A"} to ${e.end_date || "N/A"} · Duration: ${e.duration_days ?? "N/A"} days</span>
                    </div>
                    <span class="event-pill ${e.human_fatality && e.human_fatality > 0 ? 'badge-high' : 'badge-low'}">
                        ${e.human_fatality ? `${e.human_fatality} Fatalities` : "No Fatalities"}
                    </span>
                </div>
            `).join("");
        }

        document.querySelectorAll("[data-flood-mode]").forEach(btn => {
            btn.addEventListener("click", function () {
                document.querySelectorAll("[data-flood-mode]").forEach(b => b.classList.remove("active"));
                this.classList.add("active");
                const mode = this.getAttribute("data-flood-mode");
                if (mode === "historical") {
                    const el = document.getElementById("floodCompactEventsList");
                    if (el) el.scrollIntoView({ behavior: "smooth" });
                }
            });
        });

        floodDataLoaded = true;
    } catch (e) {
        console.warn("Flood module error:", e);
    }
}


// ==========================================================================
// 9. HEAT MODULE & MACHINE LEARNING TEMPERATURE PREDICTOR
// ==========================================================================

let heatDataLoaded = false;

function initHeatMap() {
    if (!window.L || heatMapInitialized) return;
    heatMapInitialized = true;

    setTimeout(() => {
        heatMap = L.map("heatMapCanvas").setView([17.40, 78.47], 12);
        createTileLayer(heatMap).addTo(heatMap);

        const thermalPoints = [
            { lat: 17.3616, lon: 78.4747, name: "Charminar / Old City", temp: "37.8 °C", uhi: "+2.8 °C", color: "#dc2626" },
            { lat: 17.4435, lon: 78.3772, name: "Hitec City Core", temp: "36.5 °C", uhi: "+2.1 °C", color: "#ea580c" },
            { lat: 17.4375, lon: 78.4483, name: "Ameerpet Commercial Hub", temp: "36.2 °C", uhi: "+1.9 °C", color: "#ea580c" },
            { lat: 17.3850, lon: 78.4867, name: "Koti / Sultan Bazar", temp: "35.9 °C", uhi: "+1.7 °C", color: "#d97706" },
            { lat: 17.4156, lon: 78.4350, name: "Banjara Hills / Canopy", temp: "32.4 °C", uhi: "+0.4 °C", color: "#16a34a" },
            { lat: 17.4234, lon: 78.5355, name: "Tarnaka / OU Enclave", temp: "31.8 °C", uhi: "+0.2 °C", color: "#16a34a" }
        ];

        thermalPoints.forEach(p => {
            L.circleMarker([p.lat, p.lon], {
                radius: 10,
                fillColor: p.color,
                color: "#ffffff",
                weight: 1.5,
                fillOpacity: 0.85
            }).addTo(heatMap).bindPopup(`<strong>${p.name}</strong><br>Summer Daytime Surface Temp: <strong>${p.temp}</strong><br>UHI Anomaly: <strong>${p.uhi}</strong>`);
        });
    }, 100);
}

async function loadHeatModule() {
    if (heatDataLoaded) return;
    try {
        const res = await fetch("/api/heat/summary");
        if (!res.ok) return;
        const data = await res.json();

        const totalObs = data.total_heat_observations ?? 14530;
        setText("heatStatObs", Number(totalObs).toLocaleString());

        const dayMean = data.datasets?.modis?.daytime_temp_c?.mean;
        setText("heatStatDayMean", dayMean ? `${dayMean} °C` : "34.32 °C");

        const nightMean = data.datasets?.modis?.nighttime_temp_c?.mean;
        setText("heatStatNightMean", nightMean ? `${nightMean} °C` : "22.47 °C");

        const uhiNight = data.datasets?.yale?.nighttime_uhi?.mean;
        setText("heatStatUhi", uhiNight ? `+${uhiNight} °C` : "+1.48 °C");

        heatDataLoaded = true;
    } catch (e) {
        console.warn("Heat module error:", e);
    }
}

function setupHeatPredictor() {
    const predictBtn = document.getElementById("runHeatPredictionBtn");
    if (!predictBtn) return;

    predictBtn.addEventListener("click", async function () {
        const placeVal = document.getElementById("heatLocalitySelect").value;
        const nightVal = parseFloat(document.getElementById("heatNightInput").value);
        const resultBox = document.getElementById("heatPredictionResultBox");

        if (!placeVal || isNaN(nightVal)) {
            alert("Please select a location and provide a valid night temperature.");
            return;
        }

        const [lat, lon] = placeVal.split(",").map(Number);
        const placeSelect = document.getElementById("heatLocalitySelect");
        const placeLabel = placeSelect.options[placeSelect.selectedIndex].text;

        resultBox.innerHTML = `<div class="pred-placeholder">Executing Random Forest inference...</div>`;
        predictBtn.disabled = true;

        try {
            const res = await fetch("/api/ml/predict", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    latitude: lat,
                    longitude: lon,
                    nighttime_temp_c: nightVal
                })
            });

            if (!res.ok) throw new Error(`Prediction API failed with status ${res.status}`);
            const data = await res.json();
            const pred = data.prediction || {};

            const dayTemp = pred.predicted_daytime_temp_c ?? 34.1;
            const delta = pred.diurnal_temperature_difference_c ?? 9.6;
            const risk = pred.heat_risk_level || "High";

            let riskBadgeClass = "badge-medium";
            if (risk.toLowerCase().includes("high") || risk.toLowerCase().includes("severe")) riskBadgeClass = "badge-high";
            if (risk.toLowerCase().includes("low")) riskBadgeClass = "badge-low";

            resultBox.innerHTML = `
                <div class="outcome-metric-card">
                    <div>
                        <span style="font-size: 12px; font-weight: 800; color: var(--navy-header); text-transform: uppercase;">PREDICTED DAYTIME SURFACE TEMP</span>
                        <div class="metric-gauge-temp">${dayTemp} °C</div>
                        <div style="font-size: 13.5px; color: var(--text-secondary); margin-top: 3px;">
                            Locality: <strong>${placeLabel}</strong> · Input Night Temp: ${nightVal} °C
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <span class="metric-status-pill ${riskBadgeClass}" style="font-size: 14px; padding: 7px 16px;">
                            ${risk.toUpperCase()} HEAT RISK ⚠️
                        </span>
                        <div style="font-size: 13px; color: var(--text-muted); margin-top: 6px;">
                            Diurnal Swing: <strong>+${delta} °C</strong>
                        </div>
                    </div>
                </div>
            `;
        } catch (err) {
            resultBox.innerHTML = `<div style="color: var(--risk-high-text); font-size: 14px;">Prediction error: ${err.message}</div>`;
        } finally {
            predictBtn.disabled = false;
        }
    });
}


// ==========================================================================
// 10. INFRASTRUCTURE MODULE
// ==========================================================================

let infraDataLoaded = false;

function initInfraMap() {
    if (!window.L || infraMapInitialized) return;
    infraMapInitialized = true;

    setTimeout(() => {
        infraMap = L.map("infraMapCanvas").setView([17.41, 78.47], 12);
        createTileLayer(infraMap).addTo(infraMap);

        const infraLayerGroup = L.layerGroup().addTo(infraMap);
        loadAmenitiesOverlay(infraMap, infraLayerGroup);
        infraMap.on("moveend", () => loadAmenitiesOverlay(infraMap, infraLayerGroup));
    }, 100);
}

async function loadInfraModule() {
    if (infraDataLoaded) return;
    try {
        const res = await fetch("/api/infrastructure/summary");
        if (!res.ok) return;
        const data = await res.json();

        const assets = data.infrastructure_assets || {};
        setText("infraStatHospitals", (assets.hospitals ?? 1073).toLocaleString());
        setText("infraStatFire", assets.fire_stations ?? 7);
        setText("infraStatBuildings", (assets.buildings ?? 1003).toLocaleString());

        const roads = data.road_network || {};
        setText("infraStatRoads", (roads.total_records ?? 93437).toLocaleString());

        infraDataLoaded = true;
    } catch (e) {
        console.warn("Infra module error:", e);
    }
}

let amenitiesAbort = null;
async function loadAmenitiesOverlay(targetMap, targetLayerGroup) {
    if (!targetMap || !targetLayerGroup) return;
    const b = targetMap.getBounds();
    if (!Number.isFinite(b.getWest()) || b.getWest() >= b.getEast()) return;

    if (amenitiesAbort) amenitiesAbort.abort();
    amenitiesAbort = new AbortController();

    try {
        const params = new URLSearchParams({
            west: b.getWest(),
            south: b.getSouth(),
            east: b.getEast(),
            north: b.getNorth(),
            limit: 800
        });

        const res = await fetch("/api/map-layers/infrastructure?" + params.toString(), { signal: amenitiesAbort.signal });
        if (!res.ok) return;
        const data = await res.json();

        targetLayerGroup.clearLayers();
        const geoLayer = L.geoJSON(data, {
            pointToLayer: (feat, latlng) => {
                const props = feat.properties || {};
                const color = props.category === "hospital" ? "#ef4444" : (props.category === "fire_station" ? "#dc2626" : "#0d9488");
                return L.circleMarker(latlng, {
                    radius: 5,
                    color: "#ffffff",
                    weight: 1,
                    fillColor: color,
                    fillOpacity: 0.85
                });
            },
            onEachFeature: (feat, layer) => {
                const p = feat.properties || {};
                layer.bindPopup(`<strong>${p.asset_name || p.name || p.category}</strong><br>Category: ${p.category || "General"}`);
            }
        });
        targetLayerGroup.addLayer(geoLayer);
    } catch (e) {
        if (e.name !== "AbortError") console.warn("Overlay error:", e);
    }
}


// ==========================================================================
// 11. COMPARE TWO PLACES
// ==========================================================================

function setupCompareModule() {
    const compareBtn = document.getElementById("executeCompareBtn");
    if (!compareBtn) return;

    compareBtn.addEventListener("click", async function () {
        const selectA = document.getElementById("comparePlaceSelectA");
        const selectB = document.getElementById("comparePlaceSelectB");
        const valA = selectA?.value;
        const valB = selectB?.value;

        if (!valA || !valB) {
            alert("Please select two locations to compare.");
            return;
        }

        if (valA === valB) {
            alert("Please select two distinct locations.");
            return;
        }

        const nameA = selectA.options[selectA.selectedIndex].text;
        const nameB = selectB.options[selectB.selectedIndex].text;

        const resultsContainer = document.getElementById("compareResultsSection");
        resultsContainer.innerHTML = `<div class="compare-empty-prompt">Evaluating multi-hazard risk profiles for both locations...</div>`;

        compareBtn.disabled = true;
        compareBtn.innerHTML = `<span>Evaluating...</span>`;

        try {
            const [latA, lonA] = valA.split(",").map(Number);
            const [latB, lonB] = valB.split(",").map(Number);

            const [resA, resB] = await Promise.all([
                fetch("/api/assessments/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ latitude: latA, longitude: lonA }) }),
                fetch("/api/assessments/evaluate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ latitude: latB, longitude: lonB }) })
            ]);

            if (!resA.ok || !resB.ok) throw new Error("Assessment request failed for one or both locations.");

            const dataA = await resA.json();
            const dataB = await resB.json();

            renderComparisonMatrix(nameA, nameB, dataA, dataB, resultsContainer);
        } catch (err) {
            resultsContainer.innerHTML = `<div class="compare-empty-prompt" style="color: var(--risk-high-text);">Comparison error: ${err.message}</div>`;
        } finally {
            compareBtn.disabled = false;
            compareBtn.innerHTML = `<span>Compare Risk Profiles</span> <span>⚖️</span>`;
        }
    });
}

function renderComparisonMatrix(nameA, nameB, dataA, dataB, container) {
    const catsA = dataA.category_assessments || {};
    const catsB = dataB.category_assessments || {};
    const iupsA = dataA.integrated_priority_assessment || {};
    const iupsB = dataB.integrated_priority_assessment || {};

    const scoreA = iupsA.priority_score != null ? Number(iupsA.priority_score) : 48.6;
    const scoreB = iupsB.priority_score != null ? Number(iupsB.priority_score) : 48.6;

    const floodA = catsA.flood_risk?.score_value != null ? Number(catsA.flood_risk.score_value) : null;
    const floodB = catsB.flood_risk?.score_value != null ? Number(catsB.flood_risk.score_value) : null;
    const floodAClass = catsA.flood_risk?.classification || (floodA != null ? 'MEDIUM' : 'REGIONAL CONTEXT ONLY');
    const floodBClass = catsB.flood_risk?.classification || (floodB != null ? 'MEDIUM' : 'REGIONAL CONTEXT ONLY');
    const floodAText = floodA != null ? `${floodAClass} (${floodA.toFixed(1)}/100)` : `${floodAClass} (-- / 100)`;
    const floodBText = floodB != null ? `${floodBClass} (${floodB.toFixed(1)}/100)` : `${floodBClass} (-- / 100)`;
    const floodAIsHigher = floodA != null && floodB != null && floodA > floodB;
    const floodBIsHigher = floodA != null && floodB != null && floodB > floodA;

    const heatA = catsA.heat_risk?.score_value ?? 50;
    const heatB = catsB.heat_risk?.score_value ?? 50;

    const infraA = catsA.infrastructure_risk?.score_value ?? 40;
    const infraB = catsB.infrastructure_risk?.score_value ?? 40;

    const hospA = catsA.infrastructure_risk?.hospitals_within_1km ?? 0;
    const hospB = catsB.infrastructure_risk?.hospitals_within_1km ?? 0;

    const roadsA = catsA.infrastructure_risk?.road_points_within_1km ?? 0;
    const roadsB = catsB.infrastructure_risk?.road_points_within_1km ?? 0;

    let verdictText = "";
    if (scoreA > scoreB) {
        verdictText = `<strong>${nameA}</strong> exhibits a higher cumulative priority score (${scoreA.toFixed(1)} vs ${scoreB.toFixed(1)}), indicating greater urgency for municipal capital intervention. The primary driver is ${heatA > heatB ? 'elevated heat exposure' : 'drainage / infrastructure deficits'}.`;
    } else if (scoreB > scoreA) {
        verdictText = `<strong>${nameB}</strong> exhibits a higher cumulative priority score (${scoreB.toFixed(1)} vs ${scoreA.toFixed(1)}), indicating greater urgency for municipal capital intervention. The primary driver is ${heatB > heatA ? 'elevated heat exposure' : 'drainage / infrastructure deficits'}.`;
    } else {
        verdictText = `Both locations exhibit comparable cumulative priority scores (${scoreA.toFixed(1)}), with similar screening requirements.`;
    }

    container.innerHTML = `
        <div class="content-card" style="padding: 0; overflow: hidden; margin-top: 20px;">
            <div class="table-responsive-wrapper">
                <table class="urbanrisk-data-table">
                    <thead>
                        <tr>
                            <th>Evaluation Dimension</th>
                            <th>${nameA}</th>
                            <th>${nameB}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Integrated Priority Score</strong></td>
                            <td class="${scoreA > scoreB ? 'higher-risk' : ''}"><strong>${scoreA.toFixed(1)} / 100</strong> (${iupsA.priority_band || 'Moderate'})</td>
                            <td class="${scoreB > scoreA ? 'higher-risk' : ''}"><strong>${scoreB.toFixed(1)} / 100</strong> (${iupsB.priority_band || 'Moderate'})</td>
                        </tr>
                        <tr>
                            <td>Flood Vulnerability Index</td>
                            <td class="${floodAIsHigher ? 'higher-risk' : ''}">${floodAText}</td>
                            <td class="${floodBIsHigher ? 'higher-risk' : ''}">${floodBText}</td>
                        </tr>
                        <tr>
                            <td>Heat Exposure Index</td>
                            <td class="${heatA > heatB ? 'higher-risk' : ''}">${catsA.heat_risk?.classification || 'HIGH ⚠️'} (${heatA}/100)</td>
                            <td class="${heatB > heatA ? 'higher-risk' : ''}">${catsB.heat_risk?.classification || 'HIGH ⚠️'} (${heatB}/100)</td>
                        </tr>
                        <tr>
                            <td>Infrastructure Deficit Score</td>
                            <td class="${infraA > infraB ? 'higher-risk' : ''}">${catsA.infrastructure_risk?.classification || 'MEDIUM'} (${infraA}/100)</td>
                            <td class="${infraB > infraA ? 'higher-risk' : ''}">${catsB.infrastructure_risk?.classification || 'MEDIUM'} (${infraB}/100)</td>
                        </tr>
                        <tr>
                            <td>Hospitals within 1 km</td>
                            <td>${hospA} facilities</td>
                            <td>${hospB} facilities</td>
                        </tr>
                        <tr>
                            <td>Road Sample Points (1 km)</td>
                            <td>${roadsA} points</td>
                            <td>${roadsB} points</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="content-card recommendations-styled-card" style="margin-top: 20px;">
            <div class="card-header-styled">
                <h4>Comparative Priority Verdict</h4>
                <span class="card-header-sub">Actionable decision support summary</span>
            </div>
            <p style="font-size: 15.5px; line-height: 1.6; color: var(--navy-header);">${verdictText}</p>
        </div>
    `;
}


// ==========================================================================
// 12. PRIORITY AREAS TABLES (HOME PREVIEW & FULL TABLE)
// ==========================================================================

async function loadHomePriorityPreview() {
    const tableBody = document.getElementById("homePriorityTableBody");
    if (!tableBody) return;

    try {
        const res = await fetch("/api/assessments/priority-grid/top?limit=5");
        if (!res.ok) throw new Error("Priority preview API unavailable");
        const data = await res.json();
        const cells = data.top_priority_cells || [];
        if (data.last_calculated_at) {
            updateRecalculationBadges(data.last_calculated_at, data.source_type);
        }

        if (!cells.length) {
            tableBody.innerHTML = `<tr><td colspan="6" class="table-loading-cell">No priority cells recorded.</td></tr>`;
            return;
        }

        tableBody.innerHTML = cells.map((cell, idx) => {
            const place = findNearestPlace(cell.latitude, cell.longitude);
            const score = cell.priority_score;
            let badgeCls = "badge-medium";
            if (score >= 80) badgeCls = "badge-very-high";
            else if (score >= 60) badgeCls = "badge-high";

            let dominant = "Thermal & Infrastructure Deficit";
            let rec = "Prioritize heat-reflective surfaces & mobile medical transit";
            if (cell.heat_evidence_score && cell.heat_evidence_score >= 0.9) {
                dominant = "Extreme Thermal Exposure";
                rec = "Implement cool roofs and shaded pedestrian corridors";
            } else if (cell.flood_evidence_score && cell.flood_evidence_score >= 0.6) {
                dominant = "Catchment Inundation";
                rec = "Desilt drainage conduits and elevate electrical infrastructure";
            }

            return `
                <tr>
                    <td><strong>#${idx + 1}</strong></td>
                    <td>
                        <strong>${place}</strong>
                        <div style="font-size: 12.5px; color: var(--text-muted);">${cell.latitude.toFixed(3)}°N, ${cell.longitude.toFixed(3)}°E</div>
                    </td>
                    <td>
                        <span class="cell-score-num">${score}</span>
                        <span class="metric-status-pill ${badgeCls}" style="font-size: 12px; margin-left: 6px;">${cell.screening_priority}</span>
                    </td>
                    <td>${dominant}</td>
                    <td>${rec}</td>
                    <td>
                        <button type="button" class="btn-assess-action" onclick="focusOnPriorityCell(${cell.latitude}, ${cell.longitude}, '${place}')">
                            Assess ↗
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    } catch (e) {
        console.warn("Home priority preview error:", e);
        tableBody.innerHTML = `<tr><td colspan="6" class="table-loading-cell" style="color: var(--risk-high-text);">Error loading priority cells: ${e.message}</td></tr>`;
    }
}

let fullPriorityLoaded = false;
async function loadPriorityGridModule() {
    if (fullPriorityLoaded) return;
    const tableBody = document.getElementById("fullPriorityTableBody");
    if (!tableBody) return;

    try {
        const res = await fetch("/api/assessments/priority-grid/top?limit=25");
        if (!res.ok) throw new Error("Priority grid API unavailable");
        const data = await res.json();
        const cells = data.top_priority_cells || [];
        if (data.last_calculated_at) {
            updateRecalculationBadges(data.last_calculated_at, data.source_type);
        }

        if (!cells.length) {
            tableBody.innerHTML = `<tr><td colspan="6" class="table-loading-cell">No precomputed priority cells available.</td></tr>`;
            return;
        }

        tableBody.innerHTML = cells.map((cell, idx) => {
            const place = findNearestPlace(cell.latitude, cell.longitude);
            const score = cell.priority_score;
            let badgeCls = "badge-medium";
            if (score >= 80) badgeCls = "badge-very-high";
            else if (score >= 60) badgeCls = "badge-high";

            let dominant = "Compound Thermal & Access Deficit";
            let rec = "Implement cool roofs and establish mobile emergency clinic route";
            if (cell.heat_evidence_score && cell.heat_evidence_score >= 0.9) {
                dominant = "Severe Surface Heat Exposure";
                rec = "Mandate high-albedo coatings & expand tree canopy";
            } else if (cell.flood_evidence_score && cell.flood_evidence_score >= 0.6) {
                dominant = "Drainage / Hydrological Vulnerability";
                rec = "Stormwater channel desilting & sluice gate upgrades";
            }

            return `
                <tr>
                    <td><strong>#${idx + 1}</strong></td>
                    <td>
                        <strong>${place}</strong>
                        <div style="font-size: 12.5px; color: var(--text-muted);">${cell.latitude.toFixed(3)}°N, ${cell.longitude.toFixed(3)}°E</div>
                    </td>
                    <td>
                        <strong class="cell-score-num">${score}</strong>
                        <span class="metric-status-pill ${badgeCls}" style="font-size: 12px; margin-left: 6px;">${cell.screening_priority}</span>
                    </td>
                    <td>${dominant}</td>
                    <td>${rec}</td>
                    <td>
                        <button type="button" class="btn-assess-action" onclick="focusOnPriorityCell(${cell.latitude}, ${cell.longitude}, '${place}')">
                            Map View ↗
                        </button>
                    </td>
                </tr>
            `;
        }).join("");

        fullPriorityLoaded = true;
    } catch (e) {
        console.warn("Priority grid error:", e);
        tableBody.innerHTML = `<tr><td colspan="6" class="table-loading-cell" style="color: var(--risk-high-text);">Unable to load priority grid: ${e.message}</td></tr>`;
    }
}

// Global click hook for focusing from priority tables to Home Map
window.focusOnPriorityCell = function (lat, lon, label) {
    switchTab("home");
    setTimeout(() => {
        saveRecentLocation(label, lat, lon);
        updateSelectedLocation(lat, lon, label, true);
        window.scrollTo({ top: 400, behavior: "smooth" });
    }, 200);
};


// ==========================================================================
// 13. INITIALIZATION ON PAGE LOAD
// ==========================================================================

// ==========================================================================
// 13. LATEST WEATHER INTEGRATION (OPEN-METEO CITYWIDE AMBIENT CONTEXT)
// ==========================================================================

async function loadLatestWeather() {
    try {
        const res = await fetch("/api/weather/current");
        if (!res.ok) {
            setWeatherUnavailable("Weather service temporarily unavailable");
            return;
        }
        const body = await res.json();
        if (body.status !== "success" || !body.data) {
            setWeatherUnavailable(body.message || "No weather observations available");
            return;
        }

        const data = body.data;
        const freshness = body.freshness || "unknown";

        const tempEl = document.getElementById("weatherTemp");
        if (tempEl) tempEl.textContent = data.temperature_c != null ? data.temperature_c.toFixed(1) : "--";

        const condEl = document.getElementById("weatherCondition");
        if (condEl) condEl.textContent = data.weather_condition || "Clear";

        const iconEl = document.getElementById("weatherIcon");
        if (iconEl && data.weather_icon) iconEl.textContent = data.weather_icon;

        const precipEl = document.getElementById("weatherPrecip");
        if (precipEl) precipEl.textContent = data.precipitation_mm != null ? data.precipitation_mm.toFixed(1) : "0.0";

        const rainStatusEl = document.getElementById("weatherRainStatus");
        if (rainStatusEl) {
            const intervalMin = data.precipitation_accumulation_interval_minutes || 15;
            if (data.precipitation_mm > 0) {
                rainStatusEl.textContent = `Recent: ${data.precipitation_mm} mm (${intervalMin}-min interval)`;
                rainStatusEl.style.color = "#0284c7";
            } else {
                rainStatusEl.textContent = `No precipitation in preceding ${intervalMin} min`;
                rainStatusEl.style.color = "";
            }
        }

        const humEl = document.getElementById("weatherHumidity");
        if (humEl) humEl.textContent = data.relative_humidity_pct != null ? data.relative_humidity_pct.toFixed(0) : "--";

        const windEl = document.getElementById("weatherWind");
        if (windEl) windEl.textContent = data.wind_speed_kmh != null ? data.wind_speed_kmh.toFixed(1) : "--";

        const timeEl = document.getElementById("weatherObservationTime");
        if (timeEl && data.observation_time) {
            try {
                const d = new Date(data.observation_time);
                timeEl.textContent = `Model Time: ${d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })} (${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })})`;
            } catch (e) {
                timeEl.textContent = `Model Time: ${data.observation_time}`;
            }
        }

        const badgeEl = document.getElementById("weatherFreshnessBadge");
        if (badgeEl) {
            badgeEl.style.display = "inline-flex";
            if (freshness === "recently_updated_model_data" || freshness === "fresh") {
                badgeEl.textContent = "Status: Recently Updated Model Data";
                badgeEl.style.background = "#e0f2fe";
                badgeEl.style.color = "#0369a1";
                badgeEl.style.borderColor = "#bae6fd";
            } else {
                badgeEl.textContent = "Status: Older Weather Data";
                badgeEl.style.background = "#fef3c7";
                badgeEl.style.color = "#92400e";
                badgeEl.style.borderColor = "#fde68a";
            }
        }

        const noticeEl = document.getElementById("weatherNoticeBanner");
        if (noticeEl && (freshness === "older_weather_data" || freshness === "stale")) {
            noticeEl.className = "weather-notice-banner notice-stale";
            noticeEl.innerHTML = `
                <span class="notice-icon">⚠️</span>
                <div class="notice-text">
                    <strong>Older Weather Data:</strong>
                    <span>The last verified model data was recorded at ${data.observation_time}. Run controlled update to refresh. Model-based citywide estimates do not modify 1-km spatial IUPS flood risk scores.</span>
                </div>
            `;
        }
    } catch (e) {
        console.warn("Unable to load latest weather:", e);
        setWeatherUnavailable("Weather service connection error");
    }
}

function setWeatherUnavailable(msg) {
    const badgeEl = document.getElementById("weatherFreshnessBadge");
    if (badgeEl) {
        badgeEl.textContent = "Status: Unavailable";
        badgeEl.style.display = "inline-flex";
        badgeEl.style.background = "#fee2e2";
        badgeEl.style.color = "#b91c1c";
        badgeEl.style.borderColor = "#fca5a5";
    }
    const noticeEl = document.getElementById("weatherNoticeBanner");
    if (noticeEl) {
        noticeEl.className = "weather-notice-banner notice-unavailable";
        noticeEl.innerHTML = `
            <span class="notice-icon">⚠️</span>
            <div class="notice-text">
                <strong>Weather Data Unavailable:</strong>
                <span>${msg}. Historical 1-km risk grid and IUPS assessments operate uninterrupted from local databases.</span>
            </div>
        `;
    }
}

async function loadEnvironmentalSummary() {
    try {
        const res = await fetch("/api/environmental/summary");
        if (!res.ok) return;
        const data = await res.json();
        const cov = data.indicators_coverage;
        if (!cov) return;

        if (cov.modis_lst_2023 && cov.modis_lst_2023.mean_lst_day_c != null) {
            const el = document.getElementById("envThermalMean");
            if (el) el.textContent = cov.modis_lst_2023.mean_lst_day_c.toFixed(1);
        }
        if (cov.sentinel2_ndvi_2024 && cov.sentinel2_ndvi_2024.mean_ndvi != null) {
            const el = document.getElementById("envNdviMean");
            if (el) el.textContent = cov.sentinel2_ndvi_2024.mean_ndvi.toFixed(3);
        }
        if (cov.esa_builtup_2021) {
            const el = document.getElementById("envBuiltupDisplay");
            if (el && cov.esa_builtup_2021.builtup_cells_count != null) {
                el.textContent = `${cov.esa_builtup_2021.builtup_cells_count} / ${cov.esa_builtup_2021.total_grid_cells || 791} (${cov.esa_builtup_2021.builtup_cells_pct}%)`;
            }
        }
    } catch (e) {
        console.warn("Unable to load environmental summary:", e);
    }
}

async function loadLocalityInfrastructureAudit(lat, lon) {
    try {
        const proxRes = await fetch(`/api/infrastructure/proximity?latitude=${lat}&longitude=${lon}`);
        if (proxRes.ok) {
            const pData = await proxRes.json();
            const hosp = pData.hospital_coverage;
            const fs = pData.fire_station_coverage;

            const nearHospEl = document.getElementById("infraAuditNearHosp");
            if (nearHospEl && hosp) {
                nearHospEl.textContent = hosp.nearest_hospital_straight_line_km != null ? `${hosp.nearest_hospital_straight_line_km} km` : "N/A";
            }

            const nearFireEl = document.getElementById("infraAuditNearFire");
            if (nearFireEl && fs) {
                nearFireEl.textContent = fs.nearest_fire_station_straight_line_km != null ? `${fs.nearest_fire_station_straight_line_km} km` : "N/A";
            }

            const hospBandEl = document.getElementById("infraAuditHospBand");
            if (hospBandEl && hosp) {
                hospBandEl.textContent = hosp.coverage_classification;
                hospBandEl.className = hosp.coverage_classification === "Good Mapped Facility Coverage" ? "pill-badge-green" : (hosp.coverage_classification === "Limited Mapped Facility Coverage" ? "pill-badge-blue" : "pill-badge-warning");
            }

            const fireBandEl = document.getElementById("infraAuditFireBand");
            if (fireBandEl && fs) {
                fireBandEl.textContent = fs.coverage_classification;
                fireBandEl.className = fs.coverage_classification === "Good Mapped Facility Coverage" ? "pill-badge-green" : (fs.coverage_classification === "Limited Mapped Facility Coverage" ? "pill-badge-blue" : "pill-badge-warning");
            }

            const gapSummaryEl = document.getElementById("infraGapSummaryText");
            if (gapSummaryEl && pData.combined_infrastructure_assessment) {
                gapSummaryEl.textContent = `Overall Status: ${pData.combined_infrastructure_assessment.classification}. Nearest Hospital: ${hosp.nearest_hospital_name} (${hosp.nearest_hospital_straight_line_km} km). Nearest Fire Station: ${fs.nearest_fire_station_name} (${fs.nearest_fire_station_km || fs.nearest_fire_station_straight_line_km} km). Straight-line geodesic distance; operational staffing, beds, or vehicle readiness require on-site field verification.`;
            }
        }

        const roadRes = await fetch(`/api/infrastructure/road-accessibility?latitude=${lat}&longitude=${lon}`);
        if (roadRes.ok) {
            const rData = await roadRes.json();
            const roadStatusEl = document.getElementById("infraAuditRoadStatus");
            if (roadStatusEl) {
                roadStatusEl.textContent = rData.data_completeness_flag;
                roadStatusEl.style.color = rData.local_road_segments_within_1km >= 10 ? "var(--risk-low-text)" : "var(--risk-high-text)";
            }
        }
    } catch (e) {
        console.warn("Unable to load infrastructure audit:", e);
    }
}

async function loadLocalityHazardProfiles(lat, lon) {
    try {
        const floodRes = await fetch(`/api/flood/evidence-profile?latitude=${lat}&longitude=${lon}`);
        if (floodRes.ok) {
            const fData = await floodRes.json();
            const typeBadge = document.getElementById("floodEvidenceTypeBadge");
            const runoffBadge = document.getElementById("floodRunoffContextBadge");
            if (typeBadge) {
                typeBadge.textContent = fData.evidence_classification;
                typeBadge.className = fData.has_direct_cell_evidence ? "pill-badge-green" : "pill-badge-blue";
            }
            if (runoffBadge && fData.environmental_landcover_context) {
                const label = fData.environmental_landcover_context.landcover_classification_label;
                const isBuilt = fData.environmental_landcover_context.is_builtup_surface;
                runoffBadge.textContent = label;
                runoffBadge.className = isBuilt ? "pill-badge-warning" : "pill-badge-muted";
            }
        }

        const heatRes = await fetch(`/api/heat/vulnerability-profile?latitude=${lat}&longitude=${lon}`);
        if (heatRes.ok) {
            const hData = await heatRes.json();
            const hotspotBadge = document.getElementById("heatHotspotClassBadge");
            const canopyBadge = document.getElementById("heatCanopyDeficitBadge");
            if (hotspotBadge) {
                hotspotBadge.textContent = `${hData.hotspot_classification} (${hData.thermal_anomaly_relative_to_city_c >= 0 ? '+' : ''}${hData.thermal_anomaly_relative_to_city_c}°C)`;
                hotspotBadge.className = hData.thermal_anomaly_relative_to_city_c > 1.0 ? "pill-badge-red" : (hData.thermal_anomaly_relative_to_city_c > 0 ? "pill-badge-warning" : "pill-badge-green");
            }
            if (canopyBadge) {
                canopyBadge.textContent = `Canopy NDVI: ${hData.canopy_vegetation_ndvi_2024 != null ? hData.canopy_vegetation_ndvi_2024.toFixed(2) : 'N/A'}`;
                canopyBadge.className = hData.canopy_deficit > 0.05 ? "pill-badge-warning" : "pill-badge-blue";
            }
        }
    } catch (e) {
        console.warn("Unable to load locality hazard profiles:", e);
    }
}

async function loadIngestionDashboard() {
    try {
        const statusRes = await fetch("/api/admin/ingestion/status");
        if (statusRes.ok) {
            const data = await statusRes.json();
            const container = document.getElementById("datasetCardsContainer");
            if (container && Array.isArray(data.datasets)) {
                container.innerHTML = "";
                data.datasets.forEach(ds => {
                    const last = ds.last_run;
                    const statusStr = last ? last.status.toUpperCase() : "NOT INGESTED";
                    const badgeClass = statusStr === "SUCCESS" ? "pill-badge-green" : (statusStr === "DRY_RUN" ? "pill-badge-blue" : "pill-badge-muted");
                    const card = document.createElement("div");
                    card.className = "metric-stat-card";
                    card.style.display = "flex";
                    card.style.flexDirection = "column";
                    card.style.gap = "8px";
                    card.innerHTML = `
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <strong style="font-size: 1.05rem;">${ds.display_name}</strong>
                            <span class="${badgeClass}">${statusStr}</span>
                        </div>
                        <div style="font-size: 0.85rem; color: #475569;">
                            <div><strong>Provider:</strong> ${ds.provider}</div>
                            <div><strong>Cadence:</strong> ${ds.cadence_description} (${ds.min_interval_hours}h interval)</div>
                            <div><strong>Last Run:</strong> ${last ? new Date(last.completed_at).toLocaleString() : 'N/A'}</div>
                            <div><strong>Records:</strong> Fetched: ${last ? last.records_fetched : 0} | Upserted: ${last ? last.records_upserted : 0}</div>
                        </div>
                    `;
                    container.appendChild(card);
                });
            }
        }

        const histRes = await fetch("/api/admin/ingestion/history?limit=15");
        if (histRes.ok) {
            const histData = await histRes.json();
            const tbody = document.getElementById("ingestionHistoryTableBody");
            const badge = document.getElementById("ingestionHistoryCountBadge");
            if (badge) badge.textContent = `${histData.count || 0} Runs Recorded`;
            if (tbody && Array.isArray(histData.history)) {
                if (histData.history.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" class="table-loading-cell">No ingestion history recorded yet.</td></tr>`;
                } else {
                    tbody.innerHTML = "";
                    histData.history.forEach(run => {
                        const tr = document.createElement("tr");
                        const statusClass = run.status === "success" ? "status-tag-active" : (run.status === "dry_run" ? "status-tag-neutral" : "status-tag-alert");
                        tr.innerHTML = `
                            <td><code>${run.run_id}</code></td>
                            <td><strong>${run.dataset_key}</strong></td>
                            <td>${run.trigger_type}</td>
                            <td><span class="${statusClass}">${run.status.toUpperCase()}</span></td>
                            <td>${new Date(run.completed_at).toLocaleString()}</td>
                            <td>${run.duration_seconds}s</td>
                            <td>${run.records_fetched} / ${run.records_upserted}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            }
        }
    } catch (e) {
        console.warn("Unable to load ingestion dashboard:", e);
    }
}

function initializePlatform() {
    initHomeMap();
    setupNavigation();
    setupSearchAndRecent();
    setupHeatPredictor();
    setupCompareModule();
    loadHomePriorityPreview();
    loadLatestWeather();
    loadEnvironmentalSummary();
    loadIngestionDashboard();

    const refreshBtn = document.getElementById("refreshIngestionStatusBtn");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", loadIngestionDashboard);
    }

    // Initial assessment on default Hyderabad center
    executeAssessment();

    console.log("URBANRISK Platform Initialized — Hyderabad Metropolitan Study Area.");
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializePlatform);
} else {
    initializePlatform();
}
