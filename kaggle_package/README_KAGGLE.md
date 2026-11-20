# URBANRISK — Integrated Urban Risk Analytics & Resource Prioritization System
## Kaggle Demonstration & Research Package

**Author:** Sana Firdous  
**Project:** B.Tech CSE Final Year Project  
**Location Focus:** Hyderabad Metropolitan Area, Telangana, India  
**Technologies:** Python, FastAPI, scikit-learn, Leaflet.js, MongoDB, Geospatial Analytics

---

## 1. Project Title & Problem Statement

### Project Title
**URBANRISK: Integrated Urban Risk Analytics and Resource Prioritization System (IUPS)**

### Problem Statement
Rapid urbanization in metropolitan Hyderabad has exacerbated multi-hazard vulnerabilities — particularly flash flooding from intense monsoonal storms, extreme land surface temperatures driven by the Urban Heat Island (UHI) effect, and uneven spatial access to critical emergency infrastructure (hospitals, fire stations, arterial roads). 

Traditional urban risk analyses assess hazards in isolated silos, leaving municipal administrators (GHMC, HMDA, TSDMA) without a unified framework to prioritize infrastructure interventions, resource allocations, and disaster mitigation strategies.

---

## 2. Project Objectives

1. **Multi-Hazard Integration:** Synthesize disparate empirical data sources — historical disaster records, satellite thermal observations, and OpenStreetMap spatial infrastructure — into a coherent analytical platform.
2. **Machine Learning Deployment:** Deploy trained Random Forest regression models to estimate daytime land surface temperatures and Urban Heat Island anomalies at granular spatial coordinates.
3. **Screening & Prioritization Engine (IUPS):** Implement an Integrated Urban Priority Screening framework across 791 one-square-kilometer grid cells to identify priority intervention zones.
4. **Transparent Decision Support:** Provide an accessible, stakeholder-oriented dashboard with verified data provenance, freshness tagging, and contextual municipal recommendations.

---

## 3. Technologies Used

* **Programming Language:** Python 3.10+
* **Backend Framework:** FastAPI (Asynchronous REST API)
* **Web Server:** Uvicorn (ASGI)
* **Machine Learning:** scikit-learn, Joblib, NumPy, Pandas
* **Database:** MongoDB (with 2dsphere geospatial indexing)
* **Frontend:** HTML5, CSS3, Vanilla JavaScript, Leaflet.js
* **Data Sources:** NASA MODIS, Yale Center for Earth Observation, IMD Flood Inventory, OpenStreetMap

---

## 4. Dataset Sources

| Hazard / Module | Source Dataset | Coverage / Timeframe | Records |
| :--- | :--- | :--- | :--- |
| **Heat Exposure** | NASA MODIS Land Surface Temp (LST) | 2003–2018 Summer Baseline | 14,530 grid samples |
| **Urban Heat Island** | Yale Center for Earth Observation UHI | Multi-Year Anomaly Data | 791 cells |
| **Flood Hazard** | IMD Historical Flood Inventory & NASA POWER | 1969–2022 Disasters & 2020–2021 Rainfall | 40 events / 84 rain stations |
| **Civic Amenities** | OpenStreetMap (OSM) Civic Amenities | Hospitals, clinics, fire stations, schools | 2,083 mapped assets |
| **Road Network** | OpenStreetMap (OSM) Road Network | Arterials, primaries, secondaries, residentials | 93,437 road segments |
| **Precomputed Grid**| Integrated Urban Priority Screening Grid | 791 1-km cells across Hyderabad | 741 scored cells |

---

## 5. Machine Learning Models

Two primary scikit-learn regression pipelines are packaged:

1. **MODIS Daytime Surface Temperature Regressor:**
   * **Algorithm:** `RandomForestRegressor(n_estimators=100, max_depth=12)`
   * **Input Features:** `latitude`, `longitude`, `nighttime_temp_c`
   * **Target:** `daytime_temp_c`
   * **Performance:** Held-out Test MAE = 0.506 °C, R² = 0.357
   * **Artifact:** `models/heat/modis/modis_daytime_temperature_regression_candidate.joblib` (16.2 MB)

2. **Yale Daytime Urban Heat Island Regressor:**
   * **Algorithm:** `RandomForestRegressor(n_estimators=100, max_depth=12)`
   * **Input Features:** `latitude`, `longitude`, `nighttime_uhi`
   * **Target:** `daytime_uhi_anomaly_c`
   * **Performance:** Spatial Cross-Validation MAE = 0.702 °C
   * **Artifact:** `models/heat/yale/yale_daytime_uhi_regression_candidate.joblib` (38.4 MB)

---

## 6. System Architecture & IUPS Concept

```
┌────────────────────────────────────────────────────────────────────────┐
│              INTEGRATED URBAN PRIORITY SCREENING (IUPS)                │
│                                                                        │
│   IUPS Priority Score = 0.35 × (Flood Evidence Score)                  │
│                       + 0.35 × (Heat Evidence Score)                   │
│                       + 0.15 × (Infrastructure Gap Score)              │
│                       + 0.15 × (Road Representation Gap Score)         │
└────────────────────────────────────────────────────────────────────────┘
```

* **Flood Evidence Score (35%):** Normalized depth and drainage hazard context.
* **Heat Evidence Score (35%):** Percentile-ranked daytime surface temperature and UHI anomaly across Hyderabad.
* **Infrastructure Gap Score (15%):** Accessibility deficit based on travel distance to nearest hospitals and fire stations.
* **Road Network Gap Score (15%):** Local transit density deficit and evacuation accessibility.

### Priority Bands
* **< 25 / 100:** Lower screening priority (adequate civic coverage, lower hazard exposure).
* **25 – 50 / 100:** Moderate screening priority (periodic monitoring and drainage maintenance).
* **>= 50 / 100:** Higher / Very High screening priority (urgent target for cool roofs, green canopy, drainage desilting, or mobile health posts).

---

## 7. How to Run Locally

```bash
# 1. Clone or extract package
cd urban-risk-analytics

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ensure MongoDB is running on port 27017
# 4. Start the server
python scripts/serve_ml.py

# 5. Access the web dashboard
http://127.0.0.1:8000/app
```

---

## 8. Offline & Render Cloud Deployments

* **Offline Portability:** The platform is configured with local Leaflet 1.9.4 vendor files, local DM Sans variable fonts, and pre-cached Hyderabad study area map tiles. Double-clicking `start_urbanrisk.bat` on any offline Windows machine launches the full application.
* **Render Cloud Deployment:** Fully compatible with Render Web Services using standard `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` connected to a MongoDB Atlas cluster. See `render.yaml` and `docs/ATLAS_SETUP_GUIDE.md`.

---

## 9. Limitations & Ethical Considerations

1. **Screening vs. Micro-Simulation:** IUPS is designed for relative spatial prioritization across 1-km cells; it does not replace engineering hydrodynamic flood modeling or building-level thermal simulations.
2. **Data Recency:** Thermal baseline reflects multi-year satellite climatology (2003–2018); flood records reflect documented historical disaster inventories (1969–2022).
3. **No Live Radar:** The platform does not forecast live rainfall; historical and monitored gauge depth data are utilized.
