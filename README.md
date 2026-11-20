# Integrated Urban Risk Analytics and Resource Prioritization System (IUPS)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.162.0-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-8.0-47A248.svg?style=flat&logo=mongodb)](https://www.mongodb.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.9.1-F7931E.svg?style=flat&logo=scikit-learn)](https://scikit-learn.org/)
[![Python](https://img.shields.io/badge/Python-3.15-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Complete%20%26%20Verified-brightgreen.svg)]()

> **B.Tech Capstone Project — 2026**  
> **Study Region:** Hyderabad Metropolitan Area, Telangana, India  
> **Core Objective:** Provide an evidence-based multi-hazard spatial analytics and resource prioritization engine combining satellite thermal infrared data, historical flood inventories, OpenStreetMap infrastructure, and machine learning inference.

---

## 1. Project Overview & Multi-Hazard Framework

Urban centers face compounding climate hazards. The **Integrated Urban Risk Analytics and Resource Prioritization System (IUPS)** provides urban local bodies and municipal planners with an empirical decision-support platform. 

Rather than relying on ungrounded disaster probabilities, the system synthesizes four distinct evidence streams across a **1.0 km Hyderabad master grid (791 study cells)**:
1. **Flood Evidence (35%):** Observed rainfall depths and 40 documented historical Hyderabad flood events.
2. **Heat Evidence (35%):** MODIS satellite land surface temperature (LST) and Yale Urban Heat Island (UHI) anomalies.
3. **Infrastructure Gap (15%):** Mapped distance and availability of 2,000+ critical facilities (hospitals, fire stations, schools, clinics).
4. **Road Connectivity Gap (15%):** Representative-point density across 93,000+ OpenStreetMap road segments.

---

## 2. System Architecture

```
+-------------------------------------------------------------------------------+
|                            CLIENT PRESENTATION TIER                           |
|  - GIS Dashboard with Leaflet.js Interactive Web Map & Spatial Slicing        |
|  - Plot Assessment Drawer (IUPS Score, Multi-Hazard Evidence Cards)           |
|  - Live ML Surface Heat Inference Widget                                       |
|  - Dataset Registry & Provenance Management                                   |
|  - Real-Time System Status & Database Document Count Grid                     |
+-------------------------------------------------------------------------------+
                                      |
                                      v (REST JSON / GeoJSON)
+-------------------------------------------------------------------------------+
|                             FASTAPI APPLICATION                               |
|  - backend/main.py: Lifespan Manager (Priming Counters), Static Mounts, CORS  |
|  - backend/routers/ml.py: Deployed Random Forest Regressor Service            |
|  - backend/routers/assessments.py: Plot Evidence Engine & Citywide Summary    |
|  - backend/routers/map_layers.py: Geospatial 2dsphere $geoWithin Queries       |
|  - backend/routers/locations.py: Plot Location CRUD                           |
|  - backend/routers/datasets.py: Dataset Metadata Registration & File Upload  |
|  - backend/services/iups_service.py: Haversine Nearest-Grid Spatial Match     |
+-------------------------------------------------------------------------------+
                                      |
                                      v (PyMongo 4.20.0)
+-------------------------------------------------------------------------------+
|                            MONGODB STORAGE (8.0)                              |
|  Database: urban_risk_db (117,498 total documents)                            |
|  * spatial_locations (7,316 docs)      * hazard_observations (14,614 docs)    |
|  * infrastructure_assets (2,083 docs)  * flood_events (40 docs)               |
|  * road_segments (93,437 docs)         * dataset_versions (6 docs)            |
|  * counters (2 docs)                   * model_runs, risk_assessments (schema) |
+-------------------------------------------------------------------------------+
```

For complete architectural details, see [docs/PROJECT_ARCHITECTURE.md](docs/PROJECT_ARCHITECTURE.md).

---

## 3. Technology Stack

- **Backend:** FastAPI, Uvicorn, Starlette, Pydantic v2
- **Database:** MongoDB 8.0, PyMongo 4.20.0
- **Machine Learning & Analytics:** Scikit-Learn 1.9.1, Joblib 1.6.0, Pandas 3.1.1, NumPy 2.5.4
- **Frontend:** Semantic HTML5, Vanilla JavaScript (ES6+), CSS Custom Properties (Dark GIS Theme), Leaflet.js 1.9.4
- **Public Tunneling:** ngrok

---

## 4. Key Features

- **Interactive GIS Web Map:** Viewport-based bounding-box querying of 2,000+ infrastructure points and 93,000+ road segments using MongoDB 2dsphere geospatial indexing (`$geoWithin`).
- **Individual Plot-Level Assessment:** Click any point on the map or select saved plots to generate spatial evidence:
  - Nearest 1-km IUPS cell matching via spherical Haversine distance ($\le 0.75\text{ km}$ tolerance).
  - Infrastructure proximity within 1 km and nearest facility catalog.
  - Road network density within 250 m, 500 m, and 1 km.
  - Multi-hazard observations (MODIS heat, Yale UHI, CHIRPS rainfall).
  - Historical flood event occurrences (1981–2023).
- **Deployed Machine Learning Inference Service:**
  - Real-time land surface temperature estimation via trained Random Forest Regressor.
  - Input validation through Pydantic (`latitude`, `longitude`, `nighttime_temp_c`).
  - Diurnal anomaly calculation and heat risk categorization (Severe, High, Moderate, Low).
- **Dataset Registry & Ingestion:**
  - View metadata provenance for registered datasets.
  - Upload new CSV files with automatic header and row-structure validation.
- **Real-Time Operational Monitor:**
  - Live database health (`/health/db`).
  - Real-time document counts for all 9 collections (`/api/system-status`).

---

## 5. Machine Learning Model Information

| Parameter | Specification |
|---|---|
| **Model Type** | Random Forest Regressor Pipeline (`StandardScaler` + `RandomForestRegressor`) |
| **Model File** | `models/heat/modis/modis_daytime_temperature_regression_candidate.joblib` |
| **Input Features** | `latitude`, `longitude`, `nighttime_temp_c` |
| **Target Output** | `daytime_temp_c` (land surface temperature in °C) |
| **Spatial CV MAE** | **0.506 °C** |
| **Held-out Test MAE** | **0.949 °C** |
| **Held-out Test RMSE** | **1.360 °C** |
| **Held-out Test $R^2$** | **0.357** |
| **Baseline Test MAE** | 1.205 °C |

> **Note on Model Interpretation:** This model performs **cross-variable spatial estimation of measured surface heat**, not an autoregressive time-series weather forecast.

For full ML documentation, see [docs/ML_DEPLOYMENT.md](docs/ML_DEPLOYMENT.md).

---

## 6. Installation & Environment Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.15.0)
- MongoDB Community Server 8.0 running locally on port 27017

### 1. Clone or Open Workspace
```powershell
cd C:\Users\sanaf\OneDrive\Desktop\urban-risk-analytics
```

### 2. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Verify `.env` in the project root:
```env
MONGODB_URI=mongodb://127.0.0.1:27017/
MONGODB_DATABASE=urban_risk_db
```

---

## 7. Execution & Running the Platform

### Local Development Server
Start the FastAPI application and GIS web dashboard with one command:
```powershell
& "C:\Users\sanaf\AppData\Local\Python\bin\python.exe" scripts/serve_ml.py
```
Or with Uvicorn directly:
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Accessing the Interfaces
- **Interactive GIS Dashboard:** [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)
- **Interactive Swagger API Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Database Connection Health:** [http://127.0.0.1:8000/health/db](http://127.0.0.1:8000/health/db)
- **System Status & Collection Counts:** [http://127.0.0.1:8000/api/system-status](http://127.0.0.1:8000/api/system-status)

---

## 8. API Endpoints & Usage

### 1. Machine Learning Prediction (`POST /api/ml/predict`)
```powershell
curl.exe -X POST http://127.0.0.1:8000/api/ml/predict `
  -H "Content-Type: application/json" `
  -d '{\"latitude\": 17.3850, \"longitude\": 78.4867, \"nighttime_temp_c\": 24.5}'
```
**Sample Response:**
```json
{
  "status": "success",
  "task": "cross-variable estimation of measured daytime temperature; not forecasting",
  "model_name": "Random Forest Regressor",
  "input": { "latitude": 17.385, "longitude": 78.4867, "nighttime_temp_c": 24.5 },
  "prediction": {
    "predicted_daytime_temp_c": 34.1,
    "diurnal_temperature_difference_c": 9.6,
    "heat_risk_level": "High",
    "unit": "Celsius (°C)"
  },
  "evaluation_metrics": {
    "spatial_cv_mae_c": 0.506,
    "heldout_test_mae_c": 0.949,
    "heldout_test_rmse_c": 1.36,
    "heldout_test_r2": 0.357
  }
}
```

### 2. Plot Risk Assessment (`GET /api/assessments/plots/{location_id}`)
```powershell
curl.exe http://127.0.0.1:8000/api/assessments/plots/1
```

### 3. Citywide IUPS Priority Summary (`GET /api/assessments/summary`)
```powershell
curl.exe http://127.0.0.1:8000/api/assessments/summary
```

### 4. Postman Collection
An exportable, structured Postman test collection is provided at:  
[`docs/Urban_Risk_Analytics_ML_Postman_Collection.json`](docs/Urban_Risk_Analytics_ML_Postman_Collection.json)

---

## 9. Public Deployment with ngrok

For external evaluation and faculty grading:
1. In Terminal 1, keep the FastAPI server running:
   ```powershell
   & "C:\Users\sanaf\AppData\Local\Python\bin\python.exe" scripts/serve_ml.py
   ```
2. In Terminal 2, configure your private authtoken:
   ```powershell
   ngrok config add-authtoken <YOUR_PRIVATE_TOKEN>
   ```
3. Expose the port:
   ```powershell
   ngrok http 8000
   ```
4. Copy the public URL (e.g., `https://xxxx-xx-xx-xx.ngrok-free.dev`) and test:
   ```powershell
   curl.exe -X POST https://YOUR_NGROK_URL.ngrok-free.dev/api/ml/predict `
     -H "Content-Type: application/json" `
     -d '{\"latitude\": 17.3850, \"longitude\": 78.4867, \"nighttime_temp_c\": 24.5}'
   ```

> **Submission Notice:** Free ngrok URLs are session-based. The public link remains active only while both local terminal processes are running.

---

## 10. Verification Suite

Run the automated 19-test verification harness:
```powershell
& "C:\Users\sanaf\AppData\Local\Python\bin\python.exe" scripts/test_deployment.py
```
**Result:** **19/19 Tests Passed (100.0%)** across Database, ML Inference, Spatial Analytics, and Health APIs.  
See detailed execution log in [docs/TEST_REPORT.md](docs/TEST_REPORT.md).

---

## 11. Project Deliverables Index

- [docs/PROJECT_ARCHITECTURE.md](docs/PROJECT_ARCHITECTURE.md) — Tiered design, GIS data flows, and analytical models
- [docs/DATABASE_MIGRATION.md](docs/DATABASE_MIGRATION.md) — MySQL to MongoDB migration report, 9 collections, indexes, and document counts
- [docs/ML_DEPLOYMENT.md](docs/ML_DEPLOYMENT.md) — Supervised ML inference deployment, validation metrics, and ngrok guide
- [docs/TEST_REPORT.md](docs/TEST_REPORT.md) — Comprehensive 19-test execution log and system limitations
- [docs/Urban_Risk_Analytics_ML_Postman_Collection.json](docs/Urban_Risk_Analytics_ML_Postman_Collection.json) — Ready-to-import Postman collection
