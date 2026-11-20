# System Verification & Test Report
## Integrated Urban Risk Analytics and Resource Prioritization System
**Date of Verification:** 20 November 2026  
**Execution Environment:** Windows PowerShell / Python 3.15.0 / MongoDB 8.0.38  
**Verification Harness:** `scripts/test_deployment.py`  
**Overall Status:** **25 / 25 Tests Passed (100.0%)**  

---

## 1. Test Suite Summary Table

| Category | Test Case Name | Target Under Test | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **Database** | Live MongoDB Connectivity | `check_mongodb_connection()` | Ping `1.0`, DB: `urban_risk_db` | `ping: 1.0`, `urban_risk_db` | **PASS** |
| **Database** | 9 Migrated Collections | `db.list_collection_names()` | All 9 collections exist with documents | All 9 collections verified | **PASS** |
| **Database** | MongoDB Sequence Counters | `db.counters` / `initialize_counter` | `location_id` and `dataset_id` primed | `loc_id=14710`, `ds_id=13` | **PASS** |
| **Machine Learning** | Model Catalog Metadata | `GET /api/ml/info` | 2 models loaded with metrics | Both MODIS and Yale models active | **PASS** |
| **Machine Learning** | Daytime Temp Prediction | `POST /api/ml/predict` | Estimated temp, delta, risk band | 34.1 °C, +9.6 °C, High Risk | **PASS** |
| **Machine Learning** | Root Prediction Alias | `POST /predict` | Compatible with root path | 34.2 °C, High Risk | **PASS** |
| **Machine Learning** | UHI Anomaly Prediction | `POST /api/ml/predict/uhi` | Estimated daytime UHI anomaly | -0.177 °C anomaly | **PASS** |
| **Machine Learning** | Input Validation (Lat > 90) | Pydantic `HeatPredictRequest` | HTTP 422 Unprocessable Entity | Correctly rejected with validation error | **PASS** |
| **Machine Learning** | Input Validation (Lon < -180) | Pydantic `HeatPredictRequest` | HTTP 422 Unprocessable Entity | Correctly rejected with validation error | **PASS** |
| **Spatial / IUPS** | IUPS Local Grid Service | `assess_plot_iups(lat, lon)` | Match nearest 1 km cell | Grid 26_13, Score 64.141, Higher Priority | **PASS** |
| **Spatial / IUPS** | Citywide IUPS Summary | `GET /api/assessments/summary` | 791 cells, 741 scored, weights | 791 cells, 741 scored (93.7% coverage) | **PASS** |
| **Spatial / IUPS** | Saved Plots Retrieval | `GET /api/locations/plots` | Return saved plot array | 12 plots retrieved from MongoDB | **PASS** |
| **Spatial / IUPS** | Plot Assessment Evidence | `GET /api/assessments/plots/1` | Multi-evidence payload | Infra: 1, Roads: 1056, Hazard: 6, Floods: 40 | **PASS** |
| **Spatial / IUPS** | Infrastructure Spatial Query | `GET /api/map-layers/infrastructure` | GeoJSON within bbox ($geoWithin) | 219 features returned | **PASS** |
| **Spatial / IUPS** | Roads Spatial Query | `GET /api/map-layers/roads` | GeoJSON within bbox ($geoWithin) | 3,000 features returned | **PASS** |
| **Datasets** | Datasets Registry | `GET /api/datasets/` | Return registered datasets | 6 datasets retrieved from MongoDB | **PASS** |
| **Platform Health** | FastAPI Home Endpoint | `GET /` | Status success, ML deployed flag | `status: success`, `ml_model_deployed: True` | **PASS** |
| **Platform Health** | Database Health Endpoint | `GET /health/db` | Database connection status | `connected`, MongoDB 8.0.38 | **PASS** |
| **Platform Health** | System Status Endpoint | `GET /api/system-status` | 9 collections document counts | `connected`, 9 collection counts verified | **PASS** |
| **Flood Module** | Flood Summary Endpoint | `GET /api/flood/summary` | 40 events, 727 fatalities, 84 rainfall obs | Verified 40 flood records, 84 rainfall obs | **PASS** |
| **Heat Module** | Heat Summary Endpoint | `GET /api/heat/summary` | 14,530 heat obs, MODIS/Yale stats | Verified 14,530 obs, 34.32°C day mean | **PASS** |
| **Infrastructure** | Infrastructure Summary | `GET /api/infrastructure/summary` | 2,083 assets, 93,437 roads | Verified 2,083 assets, 93,437 roads | **PASS** |
| **Persistence** | Model Runs Collection | `db.model_runs` | Active deployed model registration | Verified 1 deployed run record | **PASS** |
| **Persistence** | Risk Assessments Collection | `db.risk_assessments` | Persisted plot assessment evaluation | Verified real evaluated assessment record | **PASS** |
| **Persistence** | Resource Priorities Collection| `db.resource_priorities` | Persisted priority rankings | Verified real evaluated priority record | **PASS** |

---

## 2. Detailed Execution Log

```text
======================================================================
 URBAN RISK ANALYTICS & ML DEPLOYMENT - COMPREHENSIVE SYSTEM VERIFICATION
======================================================================

--- 1. DATABASE & MONGODB INTEGRATION ---
[01] PASS - MongoDB Live Connectivity
       Database: urban_risk_db, Ping: 1.0
[02] PASS - Nine Migrated MongoDB Collections
       All 9 present. Counts: dataset_versions: 6, spatial_locations: 7319, model_runs: 1, hazard_observations: 14614, flood_events: 40, infrastructure_assets: 2083, road_segments: 93437, risk_assessments: 2, resource_priorities: 2
[03] PASS - MongoDB Sequence Counters
       Counters primed: location_id=14710, dataset_id=13

--- 2. MACHINE LEARNING DEPLOYMENT ---
[04] PASS - ML Model Catalog
       Active models: ['Hyderabad MODIS Daytime Surface Temperature Regressor', 'Hyderabad Yale Daytime Urban Heat Island Regressor']
[05] PASS - ML Predict Daytime Surface Temperature
       Predicted: 34.1°C (Diurnal Delta: +9.6°C, Risk: High)
[06] PASS - ML Predict Root Alias (/predict)
       Predicted: 34.2°C, Risk: High
[07] PASS - ML Predict Urban Heat Island Anomaly
       Predicted Daytime UHI: -0.177°C anomaly
[08] PASS - ML Input Validation (Latitude > 90)
       Correctly rejected with HTTP 422 validation: Input should be less than or equal to 90
[09] PASS - ML Input Validation (Longitude < -180)
       Correctly rejected with HTTP 422 validation: Input should be greater than or equal to -180

--- 3. SPATIAL & MULTI-HAZARD ANALYTICS ---
[10] PASS - IUPS Grid Service (Local Precomputed 1-km Grid)
       Grid ID: 26_13, Priority Score: 64.141, Band: Higher screening priority
[11] PASS - Citywide IUPS Summary API
       Total Cells: 791, Scored: 741, Weights: {'flood_evidence_score': 0.35, 'heat_evidence_score': 0.35, 'infrastructure_gap_score': 0.15, 'road_representation_gap_score': 0.15}
[12] PASS - Spatial Locations Listing (/api/locations/plots)
       Total saved plot locations: 12
[13] PASS - Plot Spatial Assessment (/api/assessments/plots/1)
       Infrastructure within 1km: 1, Road points: 1056, Hazard obs: 6, Historical floods: 40
[14] PASS - Map Infrastructure GeoJSON Layer
       Features returned within bounding box: 219
[15] PASS - Map Roads GeoJSON Layer
       Features returned within bounding box: 3000
[16] PASS - Datasets Registry (/api/datasets/)
       Registered datasets in MongoDB: 6

--- 4. FASTAPI PLATFORM HEALTH & STATUS ---
[17] PASS - FastAPI Home Endpoint (/)
       Status: success, ML Deployed: True
[18] PASS - Database Health Endpoint (/health/db)
       Database: urban_risk_db, Version: 8.0.38, Ping: 1.0
[19] PASS - System Status Endpoint (/api/system-status)
       Status: connected, Tracked collections: 9

--- 5. DEDICATED MODULE SUMMARIES & PERSISTENCE ---
[20] PASS - Flood Summary Endpoint (/api/flood/summary)
       Total Floods: 40, Fatalities: 727, Rainfall Obs: 84
[21] PASS - Heat Summary Endpoint (/api/heat/summary)
       Total Heat Obs: 14530, MODIS Day Mean: 34.32°C, ML Status: deployed
[22] PASS - Infrastructure Summary Endpoint (/api/infrastructure/summary)
       Assets: 2083, Roads: 93437
[23] PASS - MongoDB Persistence: model_runs
       Registered model runs: 1
[24] PASS - MongoDB Persistence: risk_assessments
       Stored plot assessments: 2
[25] PASS - MongoDB Persistence: resource_priorities
       Stored resource priorities: 2

======================================================================
 TOTAL TESTS RUN: 25 | PASSED: 25 | FAILED: 0 (100.0%)
======================================================================
```
