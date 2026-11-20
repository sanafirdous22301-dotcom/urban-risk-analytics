# Project Architecture
## Integrated Urban Risk Analytics and Resource Prioritization System (IUPS)
**Academic Project — B.Tech 2026**  
**Study Region:** Hyderabad Metropolitan Area, Telangana, India  
**Primary Database:** MongoDB 8.0 (`urban_risk_db`)  
**Backend Framework:** FastAPI / Uvicorn (Python 3.15)  
**Frontend Stack:** Semantic HTML5, CSS Custom Properties (Dark Theme GIS), Vanilla JavaScript (ES6+), Leaflet.js  

---

## 1. System Overview & Multi-Tier Architecture

The Integrated Urban Risk Analytics and Resource Prioritization System is an end-to-end GIS and decision-support platform. It integrates multi-hazard empirical evidence (extreme rainfall, historical floods, satellite surface heat, urban heat island anomalies) with urban physical exposure (OpenStreetMap infrastructure facilities and road networks) to drive localized risk assessments and citywide resource prioritization.

```
+-----------------------------------------------------------------------------------+
|                                 CLIENT TIER                                       |
|  - GIS Dashboard Interface (Leaflet.js Web Map + Assessment Drawer)               |
|  - Interactive Multi-Hazard Analysis & Live ML Prediction Form                    |
|  - Dataset Registry & Upload Portal (Multipart CSV file ingestion)                |
|  - Platform Operations & MongoDB Document Count Monitors                          |
+-----------------------------------------------------------------------------------+
                                       |
                                       | HTTP / REST API (JSON & GeoJSON)
                                       v
+-----------------------------------------------------------------------------------+
|                                FASTAPI BACKEND                                    |
|  - backend/main.py: Lifespan Manager (Priming Counters), Static Mounts, CORS      |
|  - backend/routers/ml.py: Real-Time Random Forest Inference & Metadata Catalog    |
|  - backend/routers/assessments.py: Plot Evidence Engine & Citywide Summary API    |
|  - backend/routers/map_layers.py: 2dsphere Bounding Box Geospatial Slicing        |
|  - backend/routers/locations.py: Plot GeoJSON Ingestion & Retrieval               |
|  - backend/routers/datasets.py: Dataset Metadata Registration & File Ingestion   |
|  - backend/services/iups_service.py: Haversine Nearest-Grid Spatial Assignment    |
+-----------------------------------------------------------------------------------+
                  |                                           |
                  | BSON / GeoJSON                            | CSV Stream / In-Memory
                  v                                           v
+------------------------------------+   +------------------------------------------+
|          MONGODB STORAGE           |   |       PRECOMPUTED SPATIAL BACKBONE       |
|  Database: urban_risk_db (117k docs)   |   |  - 1.0 km Hyderabad Master Grid (791)   |
|  9 Primary Collections:            |   |  - Integrated Urban Risk Priority Grid   |
|    * spatial_locations (7,316)     |   |    (integrated_urban_risk_priority_grid) |
|    * infrastructure_assets (2,083) |   |  - Random Forest Trained Model Bundles:  |
|    * road_segments (93,437)        |   |    * MODIS Heat Regressor (.joblib)      |
|    * hazard_observations (14,614)  |   |    * Yale UHI Regressor (.joblib)        |
|    * flood_events (40)             |   +------------------------------------------+
|    * dataset_versions (6)          |
|    * counters (2 sequence tracks)  |
|    * model_runs, risk_assessments, |
|      resource_priorities           |
+------------------------------------+
```

---

## 2. Frontend Architecture

The frontend is served directly by FastAPI via static file mounts at `/app`, `/css`, and `/js`. It does not rely on heavy build tools or external frontend runtime dependencies.

### Key Components:
1. **Interactive GIS Map (`Leaflet.js`):**
   - Configured with CartoDB Dark Matter tiles matching the project's UI design system.
   - Dynamic viewport-based geospatial querying: when the user pans or zooms, `moveend` triggers bounding-box requests to `/api/map-layers/infrastructure` and `/api/map-layers/roads`.
   - Spatial Selection: clicking on any point in Hyderabad captures coordinates into the assessment drawer and live ML predictor.
2. **Individual Plot Assessment Drawer:**
   - Populated from `/api/locations/plots` (saved plots) and evaluated via `/api/assessments/plots/{location_id}`.
   - Renders 5 distinct analytical cards: IUPS Priority Screening, Infrastructure Proximity within 1 km, Road Connectivity within 250m/500m/1km, Hazard Observations (historical rainfall and surface temperatures), and Historical Flood Context.
3. **Live ML Prediction Module:**
   - Direct frontend hook to `POST /api/ml/predict`.
   - Allows users to test land surface temperature estimation and heat risk categorization in real time.
4. **Platform Operations & Live Database Monitor:**
   - Communicates with `/api/system-status` and `/health/db` to report real-time MongoDB connectivity and document counts across all collections.

---

## 3. Backend Architecture & API Flow

The backend is built with FastAPI, using asynchronous route definitions, Pydantic data validation, and PyMongo client management.

### Endpoint Mapping:
- **Core Operations:**
  - `GET /`: Health status and platform information.
  - `GET /health/db`: MongoDB ping, server version, and database name.
  - `GET /api/system-status`: Live collection document counts.
- **Machine Learning Inference (`backend/routers/ml.py`):**
  - `POST /api/ml/predict`: Primary prediction endpoint (validates latitude, longitude, and nighttime temperature).
  - `POST /predict`: Root compatibility alias.
  - `POST /api/ml/predict/uhi`: Daytime Urban Heat Island anomaly prediction.
  - `GET /api/ml/info`: Model metadata, algorithm details, and evaluation metrics.
- **Plot Assessment & Prioritization (`backend/routers/assessments.py`):**
  - `GET /api/assessments/plots/{location_id}`: Comprehensive multi-evidence plot assessment.
  - `GET /api/assessments/summary`: Citywide 1-km priority grid summary, coverage statistics, and analytical weights.
- **Map Layers (`backend/routers/map_layers.py`):**
  - `GET /api/map-layers/infrastructure`: Bounding-box spatial query using MongoDB `$geoWithin`.
  - `GET /api/map-layers/roads`: Bounding-box query on road representative points.
- **Locations & Datasets:**
  - `GET /api/locations/plots`, `POST /api/locations/plots`
  - `GET /api/datasets/`, `POST /api/datasets/`, `POST /api/datasets/upload`

---

## 4. IUPS Calculation & Spatial Flow

The Integrated Urban Priority Screening (IUPS) system uses a 1.0 km resolution grid spanning 791 cells across Hyderabad:
1. **Assignment Tolerance:** A plot is matched to the nearest grid cell if within $0.75\text{ km}$ ($750\text{ m}$).
2. **Normalized Multi-Hazard Analytical Weights:**
   $$\text{IUPS Score} = (0.35 \times \text{Flood Evidence}) + (0.35 \times \text{Heat Evidence}) + (0.15 \times \text{Infrastructure Gap}) + (0.15 \times \text{Road Gap})$$
3. **Screening Priority Bands:**
   - **Higher screening priority:** Score $\ge 60$ or high compound hazard with limited local infrastructure.
   - **Moderate screening priority:** Intermediate hazard or moderate service availability.
   - **Lower screening priority:** Low relative hazard observations and established infrastructure.
   - **Not scored:** Cells where hazard observations are missing (missing data is never assumed to be zero risk).
4. **Important Interpretation:** The IUPS score is a relative screening indicator designed for urban planners to prioritize investigation and municipal resource allocation; it is not a statistical probability of disaster occurrence.

---

## 5. Machine Learning Pipeline

```
Raw Spatial Dataset
(hyderabad_modis_heat.csv)
          |
          v
Feature Extraction
(Latitude, Longitude, Nighttime Temperature)
          |
          v
Spatial Train-Test Split (Block: 0.04 deg)
          |
          v
Scikit-Learn Pipeline
[StandardScaler -> RandomForestRegressor(n_estimators=300)]
          |
          v
Validation & Evaluation Metrics
(Spatial CV MAE: 0.506 °C | Held-out RMSE: 1.360 °C | R²: 0.357)
          |
          v
Joblib Serialization (.joblib + .json metadata)
          |
          v
FastAPI Deployment (backend/routers/ml.py)
[Pydantic Validation -> Model Inference -> Heat Risk Categorization]
```
