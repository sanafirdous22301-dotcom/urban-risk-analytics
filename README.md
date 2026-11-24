# URBANRISK — Integrated Urban Risk Analytics and Resource Prioritization System

[![FastAPI](https://img.shields.io/badge/FastAPI-0.162.0-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-8.0-47A248.svg?style=flat&logo=mongodb)](https://www.mongodb.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-1.9.1-F7931E.svg?style=flat&logo=scikit-learn)](https://scikit-learn.org/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.15-3776AB.svg?style=flat&logo=python)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Production%20Ready%20%28Phases%201--8%20Complete%29-brightgreen.svg)]()

> **B.Tech CSE Capstone Project — 2026**  
> **Study Region:** Greater Hyderabad Metropolitan Area, Telangana, India  
> **Core Objective:** Provide a transparent, evidence-based spatial risk screening and municipal resource prioritization platform combining multi-source satellite thermal/vegetation observations, historical flood inventories, Open-Meteo weather models, OpenStreetMap infrastructure assets, and machine learning inference.

---

## 1. System Disclaimer & Intended Use
> **Important Distinction:**  
> URBANRISK is an **evidence-based spatial screening and resource prioritization platform** for municipal capital planning and hazard awareness. It is **NOT** an operational real-time disaster forecast or live emergency dispatch system.  
> - Land Surface Temperature (LST) measures radiometric ground skin temperature, not 2-metre air temperature.  
> - Facility proximities are straight-line geodesic screening distances, not driving response times.  
> - Missing spatial evidence is strictly preserved as null/None and never converted to zero or low risk.

---

## 2. Integrated Urban Priority Screening (IUPS) Framework

The system evaluates **791 one-square-kilometer grid cells** covering Greater Hyderabad (741 scored cells, 50 unscored cells preserved due to missing evidence boundaries).

The approved multi-hazard screening formula:
$$\text{IUPS} = 0.35 \times \text{Flood} + 0.35 \times \text{Heat} + 0.15 \times \text{InfraGap} + 0.15 \times \text{RoadGap}$$

### Component Invariants:
1. **Flood Evidence (35%):** Observed storm rainfall (CHIRPS v3.0 raster extracts) and 40 documented historical Hyderabad flood disaster records (1969–2022).
2. **Heat Evidence (35%):** NASA MODIS Aqua Land Surface Temperature (2018 & 2023) and Yale Urban Heat Island (UHI) climatology baseline.
3. **Infrastructure Deficit (15%):** Straight-line geodesic distance to 1,073 mapped hospitals and 7 mapped fire stations.
4. **Road Connectivity Gap (15%):** Representation point density across 93,437 OpenStreetMap road segments.

---

## 3. Technology Stack & Architecture

- **Backend API:** FastAPI (Python 3.11 / 3.15) with asynchronous lifespan state management.
- **Database:** MongoDB 8.0 with `2dsphere` geospatial indexing and unique sequence counters.
- **Machine Learning:** Scikit-Learn Random Forest Regressors evaluated with genuine **5-Fold Spatial-Block Cross-Validation** (zero geographic fold overlap).
- **Frontend Dashboard:** Vanilla JavaScript (ES6+), modern CSS3 layout, Leaflet.js interactive mapping with offline tile caching.
- **Security:** HTTP Security Headers (`nosniff`, `DENY`, `XSS`, `Referrer-Policy`, `Permissions-Policy`), restricted CORS middleware, and fail-closed administrative authentication via `X-Admin-Key`.

---

## 4. Multi-Phase Capabilities (Phases 1–8)

1. **Phase 1 — Transparency & Temporal Awareness:** Strict source-product attribution, explicit distinction between historical inventories vs real-time telemetry, unscored cell tooltip indicators.
2. **Phase 2 — Dynamic Recalculation:** On-demand recalculation service with mathematical determinism, audit run tracking (`grid_recalculation_runs`), and parameter sensitivity simulation.
3. **Phase 3 — Latest Weather Integration:** Seamless integration of Open-Meteo current model conditions without perturbing historical IUPS hazard scores.
4. **Phase 4 — Satellite Environmental Intelligence:** Planetary Computer & AWS Copernicus STAC integration for 2023 MODIS LST, Sentinel-2 10m NDVI canopy density (Tile `43QHV`), and ESA WorldCover 2021 built-up land cover.
5. **Phase 5 — Automated Dataset Ingestion:** Non-destructive unified ingestion pipeline with provider publishing cadence skip checks (`min_interval_hours`), dry-run preview, and immutable audit logging in `dataset_ingestion_runs`.
6. **Phase 6 — Advanced Hazard Modelling:** Long-term 42-year daily rainfall climatology (NASA POWER 1981–2022) with recurrence percentiles, and environmental thermal regression validated with spatial block cross-validation.
7. **Phase 7 — Infrastructure Intelligence:** Configurable screening distance bands (hospitals: 1/3/5 km; fire stations: 3/5/8 km), road network completeness assessment, and explainable planning recommendations.
8. **Phase 8 — Production Readiness & Hardening:** End-to-end security verification, fail-closed auth, CORS origin control, full database invariant audits, and 8 comprehensive regression suites.

---

## 5. Local Setup & Execution Guide

### Prerequisites
- Python 3.11 or 3.15 installed.
- MongoDB 7+ or 8+ running locally on port 27017 (or MongoDB Atlas connection string).

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/sanafirdous22301-dotcom/urban-risk-analytics.git
cd urban-risk-analytics

# Create .env file
cp .env.example .env
```

Ensure `.env` contains:
```ini
MONGODB_URI=mongodb://127.0.0.1:27017/
MONGODB_DATABASE=urban_risk_db
ADMIN_API_KEY=your-secure-admin-secret-key
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Start the Backend Server
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Access:
- **Web Dashboard:** `http://127.0.0.1:8000/app/`
- **Interactive API Docs (Swagger):** `http://127.0.0.1:8000/docs`
- **Database Health Check:** `http://127.0.0.1:8000/health/db`

---

## 6. Administrative Ingestion CLI

Administrators can inspect status, dry-run previews, or ingest datasets from the CLI:
```bash
# Check operational status and publishing cadences
python scripts/ingest_datasets.py --status

# Inspect recent ingestion runs
python scripts/ingest_datasets.py --history

# Dry-run validation (no database writes)
python scripts/ingest_datasets.py --dataset modis --dry-run

# Live ingestion with force bypass of cadence check
python scripts/ingest_datasets.py --dataset weather --force
```

---

## 7. Verification Test Suites

Execute all test suites to confirm complete project integrity across all phases:
```bash
# Phase 1: Transparency & Metadata
python scripts/test_phase1_transparency.py

# Phase 2: Dynamic Grid Recalculation
python scripts/test_phase2_recalculation.py

# Phase 3: Open-Meteo Weather Integration
python scripts/test_phase3_weather.py

# Phase 4: Environmental Satellites
python scripts/test_phase4_environmental.py

# Phase 5: Ingestion & Cadence Logic
python scripts/test_phase5_ingestion.py

# Phase 6: Advanced Hazard Models (Spatial CV)
python scripts/test_phase6_hazard_models.py

# Phase 7: Infrastructure Intelligence
python scripts/test_phase7_infrastructure.py

# Phase 8: Final Security, API, & Invariant Validation
python scripts/test_phase8_final_validation.py

# System Deployment Verification (26 Tests)
python scripts/test_deployment.py
```

---

## 8. Deployment Notes (Render Free Web Service)
- **Deployment File:** [`render.yaml`](render.yaml) specifies a Python Web Service with `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- **Environment Secrets:** `MONGODB_URI` and `ADMIN_API_KEY` are configured with `sync: false` and must be entered securely in the Render Dashboard Environment pane.
- **Free-Tier Inactivity:** Render free services spin down after 15 minutes of inactivity. Scheduled background cron execution is inactive; manual CLI and authenticated API ingestion (`POST /api/admin/ingestion/trigger` with `X-Admin-Key`) remain supported.
