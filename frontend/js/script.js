
"use strict";

// =============================================
// 1. GET HTML ELEMENTS
// =============================================

// Plot assessment elements
const assessmentForm = document.getElementById("assessmentForm");
const assessmentMessage = document.getElementById("assessmentMessage");

const latitudeInput = document.getElementById("latitude");
const longitudeInput = document.getElementById("longitude");
// Plot assessment result elements
const savedPlotSelect = document.getElementById("savedPlotSelect");
const assessPlotBtn = document.getElementById("assessPlotBtn");

const assessmentResults = document.getElementById("assessmentResults");
const assessmentPlotLabel = document.getElementById("assessmentPlotLabel");
const assessmentSummary = document.getElementById("assessmentSummary");

// Road-network assessment elements
const roadSummary = document.getElementById("roadSummary");
const roadTypeResults = document.getElementById("roadTypeResults");
const nearestRoadsResults = document.getElementById("nearestRoadsResults");
const roadGeometryNote = document.getElementById("roadGeometryNote");

const infrastructureResults = document.getElementById("infrastructureResults");
const hazardResults = document.getElementById("hazardResults");
const floodContextSummary = document.getElementById("floodContextSummary");
const floodEventsResults = document.getElementById("floodEventsResults");

const assessmentSources = document.getElementById("assessmentSources");
const assessmentLimitations = document.getElementById("assessmentLimitations");
// Navigation elements
const adminBtn = document.getElementById("adminBtn");
const dataManagementBtn = document.getElementById("dataManagementBtn");

// Dataset management elements
const datasetForm = document.getElementById("datasetForm");
const datasetMessage = document.getElementById("datasetMessage");
const datasetTableBody = document.getElementById("datasetTableBody");
const datasetTotal = document.getElementById("datasetTotal");
const refreshDatasetsBtn = document.getElementById("refreshDatasetsBtn");


// =============================================
// 2. MESSAGE HELPERS
// =============================================

function showAssessmentMessage(message, type = "info") {

    const icon = document.createElement("span");

    icon.className = "message-icon";

    if (type === "success") {
        icon.textContent = "✓";
    } else if (type === "error") {
        icon.textContent = "!";
    } else {
        icon.textContent = "i";
    }

    assessmentMessage.replaceChildren(
        icon,
        document.createTextNode(" " + message)
    );

    assessmentMessage.classList.remove("success", "error");

    if (type === "success" || type === "error") {
        assessmentMessage.classList.add(type);
    }
}


function showDatasetMessage(message, type = "info") {

    datasetMessage.textContent = message;

    datasetMessage.classList.remove("success", "error");

    if (type === "success" || type === "error") {
        datasetMessage.classList.add(type);
    }

}


function updateMapStatus(message) {

    const mapStatus = document.querySelector(".map-status");

    if (mapStatus) {
        mapStatus.textContent = message;
    }

}


// =============================================
// 3. INITIALIZE LEAFLET MAP
// =============================================

const map = L.map("map").setView(
    [17.385, 78.4867],
    12
);


L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }
).addTo(map);


// Layer containing markers retrieved from MySQL
const savedMarkers = L.layerGroup().addTo(map);
// Separate layers for infrastructure and roads
const infrastructureLayer = L.layerGroup().addTo(map);
const roadsLayer = L.layerGroup();

// Layer switcher
L.control.layers(
    null,
    {
        "Infrastructure Assets": infrastructureLayer,
        "Road Network": roadsLayer
    },
    {
        collapsed: false
    }
).addTo(map);


// Colours for infrastructure categories
function getInfrastructureColor(category) {

    const colors = {
        hospital: "#ef4444",
        clinic: "#f97316",
        school: "#3b82f6",
        college: "#6366f1",
        pharmacy: "#14b8a6",
        police: "#8b5cf6",
        fire_station: "#dc2626"
    };

    return colors[String(category || "").toLowerCase()] || "#0d9488";

}


// Colours for road types
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


// Create safe popup content for map features
function createFeaturePopup(title, properties) {

    const container = document.createElement("div");

    const heading = document.createElement("strong");
    heading.textContent = title || "Unnamed feature";

    container.appendChild(heading);

    Object.entries(properties).forEach(function ([key, value]) {

        if (value === null || value === undefined || value === "") {
            return;
        }

        const line = document.createElement("div");
        line.textContent = key + ": " + value;

        container.appendChild(line);

    });

    return container;

}


// Keep track of active requests
let infrastructureRequest = null;
let roadsRequest = null;


// Load infrastructure inside the visible map area
async function loadInfrastructure() {

    if (infrastructureRequest) {
        infrastructureRequest.abort();
    }

    infrastructureRequest = new AbortController();

    const bounds = map.getBounds();

    const params = new URLSearchParams({
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
        limit: 3000
    });

    try {

        const response = await fetch(
            "/api/map-layers/infrastructure?" + params.toString(),
            {
                signal: infrastructureRequest.signal
            }
        );

        if (!response.ok) {
            throw new Error("Infrastructure API returned " + response.status);
        }

        const data = await response.json();

        infrastructureLayer.clearLayers();

        L.geoJSON(data, {

            pointToLayer: function (feature, latlng) {

                const properties = feature.properties || {};

                return L.circleMarker(latlng, {
                    radius: 6,
                    color: "#ffffff",
                    weight: 1,
                    fillColor: getInfrastructureColor(properties.category),
                    fillOpacity: 0.9
                });

            },

            onEachFeature: function (feature, layer) {

                const properties = feature.properties || {};

                layer.bindPopup(
                    createFeaturePopup(
                        properties.asset_name || properties.category,
                        {
                            Category: properties.category,
                            Subtype: properties.subtype
                        }
                    )
                );

            }

        }).addTo(infrastructureLayer);

        if (data.truncated) {
            console.warn("Infrastructure results reached the 3000-record limit.");
        }

        console.log("Infrastructure loaded:", data.total);

    } catch (error) {

        if (error.name !== "AbortError") {
            console.error("Infrastructure loading failed:", error);
        }

    }

}


// Load roads only when the user enables the road layer
async function loadRoads() {

    // Avoid loading thousands of road points when zoomed out
    if (map.getZoom() < 14) {
        roadsLayer.clearLayers();
        console.info("Zoom in to level 14 or higher to view road points.");
        return;
    }

    if (roadsRequest) {
        roadsRequest.abort();
    }

    roadsRequest = new AbortController();

    const bounds = map.getBounds();

    const params = new URLSearchParams({
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
        limit: 3000
    });

    try {

        const response = await fetch(
            "/api/map-layers/roads?" + params.toString(),
            {
                signal: roadsRequest.signal
            }
        );

        if (!response.ok) {
            throw new Error("Road API returned " + response.status);
        }

        const data = await response.json();

        roadsLayer.clearLayers();

        L.geoJSON(data, {

            pointToLayer: function (feature, latlng) {

                const properties = feature.properties || {};

                return L.circleMarker(latlng, {
                    radius: 3,
                    color: getRoadColor(properties.road_type),
                    weight: 1,
                    fillColor: getRoadColor(properties.road_type),
                    fillOpacity: 0.75
                });

            },

            onEachFeature: function (feature, layer) {

                const properties = feature.properties || {};

                layer.bindPopup(
                    createFeaturePopup(
                        properties.road_name || "Road segment",
                        {
                            RoadType: properties.road_type,
                            MaxSpeed: properties.maxspeed,
                            OneWay: properties.oneway,
                            LengthKm: properties.length_km
                        }
                    )
                );

            }

        }).addTo(roadsLayer);

        if (data.truncated) {
            console.warn("Road results reached the 3000-record limit. Zoom in further for more detail.");
        }

        console.log("Road points loaded:", data.total);

    } catch (error) {

        if (error.name !== "AbortError") {
            console.error("Road loading failed:", error);
        }

    }

}


// Reload visible layers when the map moves
let layerReloadTimer = null;

function reloadVisibleMapLayers() {

    clearTimeout(layerReloadTimer);

    layerReloadTimer = setTimeout(function () {

        if (map.hasLayer(infrastructureLayer)) {
            loadInfrastructure();
        }

        if (map.hasLayer(roadsLayer)) {
            loadRoads();
        }

    }, 400);

}


// Listen for map movement and layer selection
map.on("moveend", reloadVisibleMapLayers);

map.on("overlayadd", function (event) {

    if (event.layer === infrastructureLayer) {
        loadInfrastructure();
    }

    if (event.layer === roadsLayer) {
        loadRoads();
    }

});


// Initial infrastructure load
map.whenReady(function () {
    loadInfrastructure();
});

// Temporary selected marker
let selectedMarker = null;


// Create safe popup content
function createLocationPopup(title, latitude, longitude) {

    const container = document.createElement("div");

    const heading = document.createElement("strong");
    heading.textContent = title;

    const latitudeText = document.createElement("div");
    latitudeText.textContent = "Latitude: " + latitude.toFixed(6);

    const longitudeText = document.createElement("div");
    longitudeText.textContent = "Longitude: " + longitude.toFixed(6);

    container.append(
        heading,
        latitudeText,
        longitudeText
    );

    return container;

}


// Refresh Leaflet map dimensions
requestAnimationFrame(function () {
    map.invalidateSize();
});

window.addEventListener("resize", function () {
    map.invalidateSize();
});


// =============================================
// 4. LOAD SAVED PLOT LOCATIONS
// =============================================
// Add a saved plot to the assessment dropdown
function addSavedPlotOption(location, selectOption = false) {

    const locationId = String(location.location_id);

    const existingOption = Array.from(
        savedPlotSelect.options
    ).find(option => option.value === locationId);

    if (!existingOption) {

        const option = document.createElement("option");

        option.value = locationId;

        option.textContent =
            "Plot #" + locationId +
            " - " +
            Number(location.latitude).toFixed(5) +
            ", " +
            Number(location.longitude).toFixed(5);

        savedPlotSelect.appendChild(option);

    }

    if (selectOption) {
        savedPlotSelect.value = locationId;
    }

    savedPlotSelect.disabled = false;
    assessPlotBtn.disabled = !savedPlotSelect.value;

}
async function loadPlotLocations() {

    try {

        const response = await fetch("/api/locations/plots");

        if (!response.ok) {
            throw new Error("Failed to retrieve saved plot locations.");
        }

        const data = await response.json();

        if (!Array.isArray(data.locations)) {
            throw new Error("Unexpected plot-location response.");
        }

        // Reset the assessment dropdown
        savedPlotSelect.replaceChildren();

        const placeholder = document.createElement("option");

        placeholder.value = "";
        placeholder.textContent = data.locations.length
            ? "Choose a saved plot"
            : "No saved plots available";

        placeholder.selected = true;

        savedPlotSelect.appendChild(placeholder);

        savedPlotSelect.disabled = true;
        assessPlotBtn.disabled = true;

        let loadedCount = 0;

        data.locations.forEach(function (location) {

            const latitude = Number(location.latitude);
            const longitude = Number(location.longitude);

            if (
                !Number.isFinite(latitude) ||
                !Number.isFinite(longitude) ||
                latitude < -90 ||
                latitude > 90 ||
                longitude < -180 ||
                longitude > 180
            ) {
                console.warn("Invalid saved location skipped:", location);
                return;
            }

            const marker = L.marker([
                latitude,
                longitude
            ]);

            marker.bindPopup(
                createLocationPopup(
                    "Saved Plot #" + location.location_id,
                    latitude,
                    longitude
                )
            );

            savedMarkers.addLayer(marker);

            // Add this plot to the assessment dropdown
            addSavedPlotOption(location);

            loadedCount++;

        });

        console.log("Total saved plots loaded:", loadedCount);

        updateMapStatus(
            loadedCount + " saved plot location(s) loaded"
        );

    } catch (error) {

        console.error("Location loading error:", error);

        showAssessmentMessage(
            "Unable to retrieve saved plot locations.",
            "error"
        );

        updateMapStatus("Unable to load saved locations");

    }

}

// Load saved locations when dashboard opens
loadPlotLocations();
// =============================================
// 6A. ASSESSMENT DISPLAY HELPERS
// =============================================

// Format numeric values safely
function formatAssessmentNumber(value, decimals = 1) {

    if (value === null || value === undefined || value === "") {
        return "Not recorded";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
        return "Not recorded";
    }

    return number.toLocaleString("en-IN", {
        maximumFractionDigits: decimals
    });

}


// Create an assessment summary card
function createEvidenceCard(label, value, detail) {

    const card = document.createElement("div");
    card.className = "evidence-card";

    const heading = document.createElement("div");
    heading.className = "evidence-card-label";
    heading.textContent = label;

    const result = document.createElement("div");
    result.className = "evidence-card-value";
    result.textContent = value;

    const description = document.createElement("div");
    description.className = "evidence-card-detail";
    description.textContent = detail;

    card.append(heading, result, description);

    return card;

}


// Create a table using safe text insertion
function createEvidenceTable(headers, rows) {

    const wrapper = document.createElement("div");
    wrapper.className = "evidence-table-wrap";

    if (!rows.length) {

        wrapper.className = "assessment-empty-state";
        wrapper.textContent = "No matching records available.";

        return wrapper;

    }

    const table = document.createElement("table");
    table.className = "evidence-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    headers.forEach(function (headingText) {

        const th = document.createElement("th");
        th.textContent = headingText;

        headerRow.appendChild(th);

    });

    thead.appendChild(headerRow);

    const tbody = document.createElement("tbody");

    rows.forEach(function (row) {

        const tr = document.createElement("tr");

        row.forEach(function (cellValue) {

            const td = document.createElement("td");

            td.textContent =
                cellValue === null || cellValue === undefined
                    ? "Not recorded"
                    : String(cellValue);

            tr.appendChild(td);

        });

        tbody.appendChild(tr);

    });

    table.append(thead, tbody);
    wrapper.appendChild(table);

    return wrapper;

}


// Add a section heading or explanation
function createEvidenceText(message) {

    const paragraph = document.createElement("p");
    paragraph.className = "evidence-muted";
    paragraph.textContent = message;

    return paragraph;

}


// =============================================
// 6B. RENDER ASSESSMENT RESULTS
// =============================================

function renderAssessmentResults(data) {

    const infrastructure = data.infrastructure || {};

    const summary = infrastructure.summary_within_1km || [];

    const assets = infrastructure.nearest_assets || [];

    const hospitals = summary.find(
        item => item.category === "hospital"
    );

    const fireStations = summary.find(
        item => item.category === "fire_station"
    );

    const nearestHospital = assets.find(
        item => item.category === "hospital"
    );

    const nearestFireStation = assets.find(
        item => item.category === "fire_station"
    );


    // 1. Plot information

    assessmentPlotLabel.textContent =
        "PLOT #" + data.plot.location_id;


    // 2. Summary cards

    assessmentSummary.replaceChildren(

        createEvidenceCard(
            "Hospitals within 1 km",
            hospitals ? hospitals.assets_within_1km : "0",
            "Nearest: " +
            (
                nearestHospital
                    ? formatAssessmentNumber(
                        nearestHospital.distance_m
                    ) + " m"
                    : "No facility recorded"
            )
        ),

        createEvidenceCard(
            "Fire stations within 1 km",
            fireStations ? fireStations.assets_within_1km : "0",
            "Nearest: " +
            (
                nearestFireStation
                    ? formatAssessmentNumber(
                        nearestFireStation.distance_m
                    ) + " m"
                    : "No facility recorded"
            )
        ),

        createEvidenceCard(
            "Heat observations",
            (
                data.hazard_observations || []
            ).filter(item => item.hazard_type === "heat").length,
            "Measurement groups returned"
        ),

        createEvidenceCard(
            "Historical flood records",
            data.historical_flood_context.matching_event_count,
            "Regional records mentioning Hyderabad"
        )

    );


    // 3. Infrastructure results

    infrastructureResults.replaceChildren();

    const infrastructureHeading =
        document.createElement("h4");

    infrastructureHeading.textContent =
        "Infrastructure coverage within 1 km";

    infrastructureResults.appendChild(infrastructureHeading);

    infrastructureResults.appendChild(
        createEvidenceTable(
            ["Category", "Assets", "Nearest distance"],
            summary.map(item => [
                item.category,
                item.assets_within_1km,
                formatAssessmentNumber(item.nearest_distance_m) + " m"
            ])
        )
    );


    const nearestHeading = document.createElement("h4");

    nearestHeading.style.marginTop = "15px";
    nearestHeading.textContent = "Ten nearest infrastructure assets";

    infrastructureResults.appendChild(nearestHeading);

    infrastructureResults.appendChild(
        createEvidenceTable(
            ["Asset", "Category", "Subtype", "Distance"],
            assets.map(item => [
                item.asset_name || "Unnamed facility",
                item.category,
                item.subtype,
                formatAssessmentNumber(item.distance_m) + " m"
            ])
        )
    );
// =============================================
// ROAD NETWORK RESULTS
// =============================================

const roadNetwork = data.road_network || {};


// 1. Road proximity summary cards

roadSummary.replaceChildren(

    createEvidenceCard(
        "Road points within 250 m",
        formatAssessmentNumber(
            roadNetwork.road_points_within_250m,
            0
        ),
        "Representative road points"
    ),

    createEvidenceCard(
        "Road points within 500 m",
        formatAssessmentNumber(
            roadNetwork.road_points_within_500m,
            0
        ),
        "Representative road points"
    ),

    createEvidenceCard(
        "Road points within 1 km",
        formatAssessmentNumber(
            roadNetwork.road_points_within_1km,
            0
        ),
        "Representative road points"
    ),

    createEvidenceCard(
        "Nearest road point",
        roadNetwork.nearest_road_point_m === null ||
        roadNetwork.nearest_road_point_m === undefined
            ? "Unavailable"
            : formatAssessmentNumber(
                roadNetwork.nearest_road_point_m
            ) + " m",
        "Distance from selected plot"
    )

);


// 2. Road-type distribution

const roadTypes = roadNetwork.road_type_distribution || [];

roadTypeResults.replaceChildren(
    createEvidenceTable(
        ["Road type", "Representative points within 1 km"],
        roadTypes.map(item => [
            item.road_type,
            item.road_points_within_1km
        ])
    )
);


// 3. Five nearest road records

const nearestRoads = roadNetwork.nearest_roads || [];

nearestRoadsResults.replaceChildren(
    createEvidenceTable(
        [
            "Road ID",
            "Road name",
            "Road type",
            "Length",
            "Max speed",
            "Distance"
        ],

        nearestRoads.map(item => [

            item.road_id,

            item.road_name || "Unnamed road",

            item.road_type || "Not recorded",

            item.length_km === null ||
            item.length_km === undefined
                ? "Not recorded"
                : formatAssessmentNumber(
                    item.length_km,
                    4
                ) + " km",

            item.maxspeed || "Not recorded",

            formatAssessmentNumber(
                item.distance_m
            ) + " m"

        ])
    )
);


// 4. Explain the geometry limitation

roadGeometryNote.textContent =
    roadNetwork.geometry_note ||
    "Road locations represent individual points, not complete road geometries.";

    // 4. Heat and rainfall results

    hazardResults.replaceChildren();

    const hazards = data.hazard_observations || [];

    hazardResults.appendChild(
        createEvidenceTable(
            [
                "Dataset",
                "Measurement",
                "Observation date",
                "Average within 5 km",
                "Sample points",
                "Nearest point"
            ],

            hazards.map(item => [

                item.dataset_name,

                item.metric_name.replace(/_/g, " "),

                item.observed_at || "Date unavailable",

                item.average_value_within_5km === null
                    ? "Not available"
                    : formatAssessmentNumber(
                        item.average_value_within_5km,
                        2
                    ) + " " + item.unit,

                item.sample_locations_within_5km,

                formatAssessmentNumber(
                    item.nearest_observation_m
                ) + " m"

            ])
        )
    );


    // 5. Historical flood context

    const floodContext = data.historical_flood_context;

    floodContextSummary.textContent =
        floodContext.matching_event_count +
        " historical source records contain Hyderabad in their district field. " +
        floodContext.geographic_precision;

    const floodEvents = floodContext.events || [];

    floodEventsResults.replaceChildren();

    floodEventsResults.appendChild(
        createEvidenceText(
            "Showing the 10 most recent records out of " +
            floodEvents.length + "."
        )
    );

    floodEventsResults.appendChild(
        createEvidenceTable(
            [
                "Start date",
                "End date",
                "Cause",
                "Duration",
                "Fatalities"
            ],

            floodEvents.slice(0, 10).map(item => [

                item.start_date || "Not recorded",

                item.end_date || "Not recorded",

                item.main_cause || "Not recorded",

                item.duration_days === null
                    ? "Not recorded"
                    : item.duration_days + " days",

                item.human_fatality === null
                    ? "Not recorded"
                    : item.human_fatality

            ])
        )
    );


    // 6. Dataset sources

    const sources = data.data_sources || [];

    assessmentSources.replaceChildren();

    assessmentSources.appendChild(
        createEvidenceTable(
            [
                "Dataset",
                "Source",
                "Version",
                "Date range",
                "Records"
            ],

            sources.map(item => [

                item.dataset_name,

                item.source_name,

                item.version_label,

                (item.date_range_start || "Unknown") +
                " to " +
                (item.date_range_end || "Unknown"),

                item.record_count

            ])
        )
    );


    // 7. Data limitations

    assessmentLimitations.replaceChildren();

    (data.limitations || []).forEach(function (limitation) {

        const li = document.createElement("li");
        li.textContent = limitation;

        assessmentLimitations.appendChild(li);

    });


    // Display completed results

    assessmentResults.hidden = false;

    assessmentResults.scrollIntoView({
        behavior: "smooth",
        block: "nearest"
    });

}
// =============================================
// 6C. ASSESS SELECTED PLOT
// =============================================

assessPlotBtn.addEventListener("click", async function () {

    const locationId = savedPlotSelect.value;

    if (!locationId) {

        showAssessmentMessage(
            "Please select a saved plot first.",
            "error"
        );

        return;

    }

    const buttonLabel = assessPlotBtn.querySelector("span");

    const originalButtonText = buttonLabel.textContent;

    assessPlotBtn.disabled = true;

    buttonLabel.textContent = "Analysing plot...";

    assessmentResults.hidden = true;

    showAssessmentMessage(
        "Retrieving spatial evidence for Plot #" + locationId + "...",
        "info"
    );


    try {

        const response = await fetch(
            "/api/assessments/plots/" + encodeURIComponent(locationId)
        );

        const result = await response.json().catch(function () {
            return {};
        });


        if (!response.ok) {

            throw new Error(
                typeof result.detail === "string"
                    ? result.detail
                    : "Unable to assess the selected plot."
            );

        }


        renderAssessmentResults(result);

        showAssessmentMessage(
            "Spatial evidence successfully retrieved for Plot #" +
            result.plot.location_id,
            "success"
        );

        updateMapStatus(
            "Assessment completed for Plot #" + result.plot.location_id
        );

        console.log("Plot assessment:", result);


    } catch (error) {

        showAssessmentMessage(
            "Assessment failed: " + error.message,
            "error"
        );

        console.error("Assessment error:", error);

    } finally {

        assessPlotBtn.disabled = !savedPlotSelect.value;

        buttonLabel.textContent = originalButtonText;

    }

});
savedPlotSelect.addEventListener("change", function () {

    assessPlotBtn.disabled = !savedPlotSelect.value;

});

// =============================================
// 5. SELECT LOCATION ON MAP
// =============================================

map.on("click", function (event) {

    const latitude = event.latlng.lat;
    const longitude = event.latlng.lng;

    latitudeInput.value = latitude.toFixed(6);
    longitudeInput.value = longitude.toFixed(6);

    if (selectedMarker !== null) {
        map.removeLayer(selectedMarker);
    }

    selectedMarker = L.marker([
        latitude,
        longitude
    ]).addTo(map);

    selectedMarker.bindPopup(
        createLocationPopup(
            "Selected Location",
            latitude,
            longitude
        )
    ).openPopup();

    showAssessmentMessage(
        "Location selected. Register this location to save it.",
        "info"
    );

    updateMapStatus(
        "Selected: " +
        latitude.toFixed(5) +
        ", " +
        longitude.toFixed(5)
    );

    console.log("Selected latitude:", latitude);
    console.log("Selected longitude:", longitude);

});


// =============================================
// 6. SAVE PLOT LOCATION
// =============================================

assessmentForm.addEventListener(
    "submit",
    async function (event) {

        event.preventDefault();

        const latitudeValue = latitudeInput.value.trim();
        const longitudeValue = longitudeInput.value.trim();

        if (!latitudeValue || !longitudeValue) {

            showAssessmentMessage(
                "Please enter both latitude and longitude.",
                "error"
            );

            return;

        }

        const latitude = Number(latitudeValue);
        const longitude = Number(longitudeValue);

        if (
            !Number.isFinite(latitude) ||
            !Number.isFinite(longitude) ||
            latitude < -90 ||
            latitude > 90 ||
            longitude < -180 ||
            longitude > 180
        ) {

            showAssessmentMessage(
                "Please enter valid geographical coordinates.",
                "error"
            );

            return;

        }


        const submitButton = assessmentForm.querySelector(
            'button[type="submit"]'
        );

        const buttonText = submitButton.querySelector("span");
        const originalButtonText = buttonText.textContent;

        submitButton.disabled = true;
        buttonText.textContent = "Saving location...";

        showAssessmentMessage(
            "Saving plot location to the database...",
            "info"
        );


        try {

            const response = await fetch(
                "/api/locations/plots",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({
                        latitude: latitude,
                        longitude: longitude
                    })
                }
            );


            const result = await response.json().catch(function () {
                return {};
            });


            if (!response.ok) {

                throw new Error(
                    typeof result.detail === "string"
                        ? result.detail
                        : "Unable to save plot location."
                );

            }


            if (selectedMarker !== null) {
                map.removeLayer(selectedMarker);
                selectedMarker = null;
            }


            const marker = L.marker([
                latitude,
                longitude
            ]);

            marker.bindPopup(
                createLocationPopup(
                    "Saved Plot",
                    latitude,
                    longitude
                )
            );
addSavedPlotOption(
    {
        location_id: result.location_id,
        latitude: latitude,
        longitude: longitude
    },
    true
);
            savedMarkers.addLayer(marker);
            marker.openPopup();


            showAssessmentMessage(
                "Plot location saved successfully. Location ID: " +
                result.location_id,
                "success"
            );

            updateMapStatus(
                "Plot saved successfully · ID " + result.location_id
            );

            console.log("Plot saved successfully:", result);

        } catch (error) {

            showAssessmentMessage(
                "Error: " + error.message,
                "error"
            );

            console.error("Plot saving error:", error);

        } finally {

            submitButton.disabled = false;
            buttonText.textContent = originalButtonText;

        }

    }
);


// =============================================
// 7. DATASET DISPLAY HELPERS
// =============================================

// Format a database date such as 2026-11-15
function formatDatasetDate(value) {

    if (!value) {
        return "—";
    }

    const parts = String(value).slice(0, 10).split("-");

    if (parts.length !== 3 || parts.some(part => !/^\d+$/.test(part))) {
        return String(value);
    }

    const [year, month, day] = parts;

    return day + "/" + month + "/" + year;

}


// Format date coverage
function formatDateRange(start, end) {

    if (start && end) {
        return formatDatasetDate(start) + " – " + formatDatasetDate(end);
    }

    if (start) {
        return "From " + formatDatasetDate(start);
    }

    if (end) {
        return "Until " + formatDatasetDate(end);
    }

    return "Not specified";

}


// Format registered timestamp
function formatRegisteredAt(value) {

    if (!value) {
        return "—";
    }

    return String(value)
        .replace("T", " ")
        .slice(0, 16);

}


// Create a table cell safely
function createDatasetCell(value) {

    const cell = document.createElement("td");

    cell.textContent = value === null || value === undefined
        ? "—"
        : String(value);

    return cell;

}


// Display one dataset record
function addDatasetRow(dataset) {

    const row = document.createElement("tr");

    row.append(
        createDatasetCell(dataset.dataset_id),
        createDatasetCell(dataset.dataset_name),
        createDatasetCell(dataset.source_name),
        createDatasetCell(dataset.version_label || "—"),
        createDatasetCell(
            formatDateRange(
                dataset.date_range_start,
                dataset.date_range_end
            )
        ),
        createDatasetCell(
            dataset.record_count === null ||
            dataset.record_count === undefined
                ? "—"
                : Number(dataset.record_count).toLocaleString("en-IN")
        ),
        createDatasetCell(
            formatRegisteredAt(dataset.retrieved_at)
        )
    );

    datasetTableBody.appendChild(row);

}


// Display empty or loading table message
function showDatasetTableMessage(message) {

    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 7;
    cell.className = "dataset-table-empty";
    cell.textContent = message;

    row.appendChild(cell);
    datasetTableBody.replaceChildren(row);

}


// =============================================
// 8. GET REGISTERED DATASETS FROM FASTAPI
// =============================================

async function loadDatasets() {

    if (!datasetTableBody) {
        return;
    }

    showDatasetTableMessage("Loading registered datasets...");

    try {

        const response = await fetch("/api/datasets/");

        const data = await response.json().catch(function () {
            return {};
        });


        if (!response.ok) {

            throw new Error(
                typeof data.detail === "string"
                    ? data.detail
                    : "Unable to retrieve datasets."
            );

        }


        if (!Array.isArray(data.datasets)) {
            throw new Error("Unexpected dataset API response.");
        }


        // Display total dataset count
        datasetTotal.textContent =
            data.total + (data.total === 1 ? " dataset" : " datasets");


        // Show empty state when no records exist
        if (data.datasets.length === 0) {

            showDatasetTableMessage(
                "No datasets registered yet."
            );

            return;

        }


        // Clear old rows
        datasetTableBody.replaceChildren();


        // Create a table row for every database record
        data.datasets.forEach(function (dataset) {

            addDatasetRow(dataset);

        });


        console.log("Datasets retrieved:", data.total);

    } catch (error) {

        console.error("Dataset loading error:", error);

        datasetTotal.textContent = "Unavailable";

        showDatasetTableMessage(
            "Unable to load registered datasets."
        );

        showDatasetMessage(
            "Dataset retrieval failed: " + error.message,
            "error"
        );

    }

}

// =============================================
// 9. UPLOAD AND REGISTER DATASET
// =============================================

datasetForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const datasetName = document.getElementById("datasetName").value.trim();
    const sourceName = document.getElementById("sourceName").value.trim();
    const versionLabel = document.getElementById("versionLabel").value.trim();

    const dateRangeStart = document.getElementById("dateRangeStart").value;
    const dateRangeEnd = document.getElementById("dateRangeEnd").value;

    const fileInput = document.getElementById("datasetFile");
    const selectedFile = fileInput.files[0];

    // Validate required fields
    if (!datasetName || !sourceName || !selectedFile) {
        showDatasetMessage(
            "Dataset name, source name and CSV file are required.",
            "error"
        );
        return;
    }

    // Validate file extension
    if (!selectedFile.name.toLowerCase().endsWith(".csv")) {
        showDatasetMessage("Please select a CSV file.", "error");
        return;
    }

    // Maximum file size: 50 MB
    const MAX_FILE_SIZE = 50 * 1024 * 1024;

    if (selectedFile.size > MAX_FILE_SIZE) {
        showDatasetMessage("File size exceeds the 50 MB limit.", "error");
        return;
    }

    // Validate date range
    if (
        dateRangeStart &&
        dateRangeEnd &&
        dateRangeStart > dateRangeEnd
    ) {
        showDatasetMessage(
            "Start date cannot be after end date.",
            "error"
        );
        return;
    }

    // Build multipart form data
    const formData = new FormData();

    formData.append("file", selectedFile);
    formData.append("dataset_name", datasetName);
    formData.append("source_name", sourceName);

    if (versionLabel) {
        formData.append("version_label", versionLabel);
    }

    if (dateRangeStart) {
        formData.append("date_range_start", dateRangeStart);
    }

    if (dateRangeEnd) {
        formData.append("date_range_end", dateRangeEnd);
    }

    const registerButton = document.getElementById("registerDatasetBtn");
    const buttonText = registerButton.querySelector("span");
    const originalButtonText = buttonText.textContent;

    registerButton.disabled = true;
    buttonText.textContent = "Uploading...";

    showDatasetMessage(
        "Uploading and validating CSV file...",
        "info"
    );

    try {

        // Send actual file to FastAPI
        const response = await fetch("/api/datasets/upload", {
            method: "POST",
            body: formData
        });

        const result = await response.json().catch(function () {
            return {};
        });

        if (!response.ok) {

            let errorMessage = "CSV upload failed.";

            if (typeof result.detail === "string") {
                errorMessage = result.detail;
            } else if (Array.isArray(result.detail)) {
                errorMessage = result.detail
                    .map(function (item) {
                        return item.msg || "Invalid field";
                    })
                    .join("; ");
            }

            throw new Error(errorMessage);
        }

        // Reset form after successful upload
        datasetForm.reset();

        showDatasetMessage(
            "CSV uploaded and registered successfully. Dataset ID: " +
            result.dataset_id +
            " | Records: " +
            result.record_count,
            "success"
        );

        console.log("CSV upload successful:", result);

        // Refresh registry from MySQL
        await loadDatasets();

    } catch (error) {

        showDatasetMessage(
            "Upload error: " + error.message,
            "error"
        );

        console.error("CSV upload error:", error);

    } finally {

        registerButton.disabled = false;
        buttonText.textContent = originalButtonText;

    }

});
// =============================================
// 10. REFRESH DATASET TABLE
// =============================================

refreshDatasetsBtn.addEventListener(
    "click",
    async function () {

        refreshDatasetsBtn.disabled = true;

        try {

            await loadDatasets();

        } finally {

            refreshDatasetsBtn.disabled = false;

        }

    }
);


// Load dataset records when dashboard opens
loadDatasets();


// =============================================
// 11. ADMINISTRATION NAVIGATION
// =============================================

adminBtn.addEventListener("click", function () {

    document.getElementById("data-management").scrollIntoView({
        behavior: "smooth"
    });

});


// =============================================
// 12. DATA MANAGEMENT NAVIGATION
// =============================================

dataManagementBtn.addEventListener("click", function () {

    document.getElementById("data-management").scrollIntoView({
        behavior: "smooth"
    });

});


// =============================================
// 13. SIDEBAR NAVIGATION
// =============================================

const navItems = document.querySelectorAll(".nav-item");


function setActiveNavigation(activeItem) {

    navItems.forEach(function (item) {
        item.classList.remove("active");
    });

    if (activeItem) {
        activeItem.classList.add("active");
    }

}


navItems.forEach(function (item) {

    item.addEventListener("click", function () {

        setActiveNavigation(item);

    });

});


// =============================================
// 14. UPDATE NAVIGATION WHILE SCROLLING
// =============================================

if ("IntersectionObserver" in window) {

    const sectionObserver = new IntersectionObserver(
        function (entries) {

            const visibleSections = entries
                .filter(function (entry) {
                    return entry.isIntersecting;
                })
                .sort(function (a, b) {
                    return b.intersectionRatio - a.intersectionRatio;
                });

            if (visibleSections.length === 0) {
                return;
            }

            const currentSectionId = visibleSections[0].target.id;

            const activeItem = Array.from(navItems).find(
                function (item) {
                    return item.getAttribute("href") ===
                        "#" + currentSectionId;
                }
            );

            setActiveNavigation(activeItem);

        },
        {
            root: null,
            rootMargin: "-15% 0px -65% 0px",
            threshold: [0, 0.1, 0.25, 0.5]
        }
    );


    navItems.forEach(function (item) {

        const sectionId = item.getAttribute("href");

        const section = document.querySelector(sectionId);

        if (section) {
            sectionObserver.observe(section);
        }

    });

}


// =============================================
// 15. INITIALIZATION
// =============================================

console.log("Urban Risk Intelligence dashboard initialized.");
console.log("Plot assessment service initialized.");
console.log("Dataset registry service initialized.");
