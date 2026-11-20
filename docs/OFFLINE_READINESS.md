# URBANRISK — Offline Readiness Audit Report

**Assessment Date:** 20 November 2026  
**Project:** URBANRISK — Integrated Urban Risk Analytics & Resource Prioritization System  
**Target Environment:** Offline Windows Workstation / Laptop (Disconnected from Internet)  
**Local Access URL:** `http://127.0.0.1:8000/app`  
**Automated Verification:** **26/26 Tests Passed (100%)**

---

## 1. Executive Summary

The URBANRISK application has been audited and verified for **complete offline execution**. All runtime software components — including frontend presentation, UI styling, geospatial map rendering, backend API endpoints, machine learning inference, and database querying — operate from local project files and a local MongoDB instance.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        OFFLINE EXECUTION STACK                         │
├────────────────────────────────────────────────────────────────────────┤
│ • Presentation: Local HTML5/CSS3/JavaScript (No external CDNs)         │
│ • Map Engine:   Local Leaflet 1.9.4 (/static/vendor/leaflet/)          │
│ • Typography:   Local Variable DM Sans (/static/vendor/fonts/)         │
│ • Study Tiles:  Local Pre-cached Tiles (/static/vendor/tiles/ 10–12)   │
│ • Application:  FastAPI via local Python (127.0.0.1:8000)              │
│ • Database:     MongoDB Community Server (mongodb://127.0.0.1:27017/) │
│ • Intelligence: Local Joblib Models (MODIS 16.2 MB & Yale UHI 38.4 MB) │
│ • Spatial Grid: Precomputed 1-km IUPS Grid (791 cells in Hyderabad)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. External Dependency Audit

Every URL across the frontend and backend was categorized to separate legitimate documentation/attribution links from runtime dependencies:

| Asset / Resource | Original Dependency | Offline Status | Implementation Details |
| :--- | :--- | :--- | :--- |
| **Leaflet Stylesheet** | `unpkg.com/leaflet@1.9.4/dist/leaflet.css` | **100% Offline** | Served locally from `/static/vendor/leaflet/leaflet.css`. |
| **Leaflet Library** | `unpkg.com/leaflet@1.9.4/dist/leaflet.js` | **100% Offline** | Served locally from `/static/vendor/leaflet/leaflet.js`. |
| **Marker & Layer Icons** | `unpkg.com/leaflet@1.9.4/dist/images/*` | **100% Offline** | Stored locally in `/static/vendor/leaflet/images/` (`marker-icon.png`, `marker-icon-2x.png`, `marker-shadow.png`, `layers.png`, `layers-2x.png`). Configured via `L.Icon.Default.mergeOptions`. |
| **Typography (Fonts)** | `fonts.googleapis.com` / `fonts.gstatic.com` | **100% Offline** | Downloaded `dm-sans-variable.woff2` into `/static/vendor/fonts/` with `@font-face` declaration. Preserves modern system font stack fallback (`-apple-system`, `Segoe UI`, `Roboto`). All Google Fonts CDN tags removed from HTML. |
| **Hyderabad Study Map** | `tile.openstreetmap.org` | **100% Offline (Zooms 10–12)** | Stored 33 local raster tiles covering the Hyderabad study area (`17.26° N – 17.55° N, 78.24° E – 78.63° E`) in `/static/vendor/tiles/{z}/{x}/{y}.png`. Initial view (zoom 12) renders completely from disk. |
| **Deeper Map Zooms (13+)** | Dynamic online OSM request | **Graceful Offline Degradation** | If disconnected from internet and zooming beyond local tiles, the map displays a styled Cartesian coordinate grid canvas (`linear-gradient`) and activates the `#offlineTileNotice` banner. Location selection, pin placement, vector layers, and risk assessment continue working. |
| **Backend APIs** | External APIs / cloud endpoints | **100% Offline** | All 26 API endpoints query the local MongoDB, local ML models, and local CSV files. Zero outbound HTTP requests exist in backend code. |
| **Attribution Link** | `openstreetmap.org/copyright` | **Documentation Only** | Standard legal copyright hyperlink displayed inside Leaflet attribution bar. Not loaded as a resource. |

---

## 3. What Works Offline

The following core functionalities operate with zero internet connectivity:

1. **Local Web Dashboard (`/app`):** Complete municipal user interface loads with zero network calls.
2. **Interactive Map & Landmarks:** Renders Hyderabad street map at city overview zooms (10, 11, 12). Clicking coordinates or selecting landmarks (Charminar, Hitec City, Musi River Corridor, Begumpet, Banjara Hills, Malkajgiri) places the assessment pin and updates coordinates.
3. **Multi-Hazard Risk Evaluation (`/api/assessments/evaluate`):** Evaluates selected coordinates on-the-fly and populates all 3 municipal risk cards:
   * **Flood Risk:** Categorized against historical disaster records (40 events).
   * **Heat Risk:** Percentile-ranked exposure score (0–100) and live ML daytime temperature prediction.
   * **Infrastructure Deficit:** Proximity calculation to hospitals, fire stations, and local road density.
4. **Machine Learning Inference (`/api/ml/predict`):** Executes Random Forest regressors in real time using local Joblib binaries (`models/heat/modis/...` and `models/heat/yale/...`).
5. **Area-Level Prioritisation (IUPS):** Calculates combined 0–100 screening priority score with 35/35/15/15 weights and municipal action recommendations for GHMC and TSDMA.
6. **Detailed Evidence & Telemetry:** Secondary tabs display nearest infrastructure tables, historical flood inventory, dataset registries, and database telemetry.

---

## 4. How the Offline Version is Started

On any target Windows laptop:

1. **Ensure MongoDB is running:**
   ```cmd
   net start MongoDB
   ```
2. **Double-click the launch script:**
   ```cmd
   start_urbanrisk.bat
   ```
3. The script verifies MongoDB, launches the default browser to `http://127.0.0.1:8000/app`, and starts the FastAPI backend server.

---

## 5. Required Windows Components

To run URBANRISK offline on another machine, the destination PC must have:

1. **Windows 10 or 11 (64-bit)**
2. **Python 3.10, 3.11, or 3.12** (with Python in system `PATH`)
3. **MongoDB Community Server 6.0, 7.0, or 8.0** (running locally on port 27017)
4. **Python packages** installed via `pip install -r requirements.txt`

---

## 6. Known Offline Limitations

1. **Street-Level Map Zooms (13+):**
   * Detailed street-level tiles (zoom 13–18) are not packaged locally to avoid bloating the project size with gigabytes of image files.
   * At zoom 13+, the map renders a clean Cartesian coordinate grid canvas with all vector infrastructure points, road networks, and pins fully interactive.
2. **Live Weather Radar / Satellite Passes:**
   * The platform relies on historical satellite thermal observations (MODIS/Yale) and documented disaster event catalogues. No real-time predictive meteorological radar is connected.
