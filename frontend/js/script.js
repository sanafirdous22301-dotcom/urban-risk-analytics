
// =============================================
// 1. GET HTML ELEMENTS
// =============================================

const assessmentForm = document.getElementById("assessmentForm");
const assessmentMessage = document.getElementById("assessmentMessage");

const latitudeInput = document.getElementById("latitude");
const longitudeInput = document.getElementById("longitude");

const adminBtn = document.getElementById("adminBtn");
const dataManagementBtn = document.getElementById("dataManagementBtn");


// =============================================
// 2. INITIALIZE LEAFLET MAP
// =============================================

const map = L.map("map").setView([17.385, 78.4867], 12);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);


// Layer for markers retrieved from database
const savedMarkers = L.layerGroup().addTo(map);

// Marker for the currently selected location
let selectedMarker = null;


// =============================================
// 3. LOAD SAVED PLOT LOCATIONS FROM FASTAPI
// =============================================

async function loadPlotLocations() {

    try {

        const response = await fetch("/api/locations/plots");

        if (!response.ok) {
            throw new Error("Failed to load saved plot locations.");
        }

        const data = await response.json();

        data.locations.forEach(function (location) {

            const marker = L.marker([
                location.latitude,
                location.longitude
            ]);

            marker.bindPopup(
                "<b>Saved Plot</b><br>" +
                "Latitude: " + location.latitude + "<br>" +
                "Longitude: " + location.longitude
            );

            savedMarkers.addLayer(marker);

        });

        console.log("Total saved plots:", data.total);

    } catch (error) {

        console.error("Location loading error:", error);

        assessmentMessage.textContent =
            "Unable to retrieve saved plot locations.";

    }

}


// Load markers when the dashboard opens
loadPlotLocations();


// =============================================
// 4. SELECT LOCATION BY CLICKING THE MAP
// =============================================

map.on("click", function (event) {

    const latitude = event.latlng.lat;
    const longitude = event.latlng.lng;

    // Fill coordinate input fields
    latitudeInput.value = latitude.toFixed(6);
    longitudeInput.value = longitude.toFixed(6);

    // Remove previous temporary marker
    if (selectedMarker !== null) {
        map.removeLayer(selectedMarker);
    }

    // Create marker for newly selected location
    selectedMarker = L.marker([
        latitude,
        longitude
    ]).addTo(map);

    selectedMarker.bindPopup(
        "<b>Selected Location</b><br>" +
        "Latitude: " + latitude.toFixed(6) + "<br>" +
        "Longitude: " + longitude.toFixed(6)
    ).openPopup();

    assessmentMessage.textContent =
        "Location selected. Click Run Location Assessment to save it.";

    console.log("Selected latitude:", latitude);
    console.log("Selected longitude:", longitude);

});


// =============================================
// 5. SAVE PLOT LOCATION THROUGH FASTAPI
// =============================================

assessmentForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const latitude = Number(latitudeInput.value);
    const longitude = Number(longitudeInput.value);

    // Validate geographical coordinates
    if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude) ||
        latitude < -90 ||
        latitude > 90 ||
        longitude < -180 ||
        longitude > 180
    ) {

        assessmentMessage.textContent =
            "Please enter valid geographical coordinates.";

        return;

    }

    assessmentMessage.textContent = "Saving plot location...";

    try {

        // Send coordinates to FastAPI
        const response = await fetch("/api/locations/plots", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                latitude: latitude,
                longitude: longitude
            })

        });

        const result = await response.json();

        if (!response.ok) {

            throw new Error(
                result.detail || "Unable to save plot location."
            );

        }

        // Display successful response
        assessmentMessage.textContent =
            "Plot location saved successfully. Location ID: " +
            result.location_id;

        // Remove temporary marker
        if (selectedMarker !== null) {

            map.removeLayer(selectedMarker);
            selectedMarker = null;

        }

        // Add permanent saved marker
        const marker = L.marker([
            latitude,
            longitude
        ]);

        marker.bindPopup(
            "<b>Saved Plot</b><br>" +
            "Latitude: " + latitude + "<br>" +
            "Longitude: " + longitude
        );

        savedMarkers.addLayer(marker);

        marker.openPopup();

        console.log("Plot saved successfully:", result);

    } catch (error) {

        assessmentMessage.textContent =
            "Error: " + error.message;

        console.error("Plot saving error:", error);

    }

});


// =============================================
// 6. ADMIN NAVIGATION
// =============================================

adminBtn.addEventListener("click", function () {

    document.getElementById("data-management").scrollIntoView({
        behavior: "smooth"
    });

});


// =============================================
// 7. DATA MANAGEMENT NAVIGATION
// =============================================

dataManagementBtn.addEventListener("click", function () {

    alert(
        "Dataset upload and validation functionality will be implemented in the next stage."
    );

});


// =============================================
// 8. SIDEBAR NAVIGATION
// =============================================

const navItems = document.querySelectorAll(".nav-item");

navItems.forEach(function (item) {

    item.addEventListener("click", function () {

        navItems.forEach(function (nav) {

            nav.classList.remove("active");

        });

        item.classList.add("active");

    });

});
