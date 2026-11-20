# URBANRISK — Three-Deliverable Deployment Status Report

**Report Date:** 20 November 2026  
**Project:** URBANRISK — Integrated Urban Risk Analytics & Resource Prioritization System  
**Repository Path:** `C:\Users\sanaf\OneDrive\Desktop\urban-risk-analytics`  
**Automated Verification:** **26/26 Tests Passed (100.0%)**

---

## 1. ONLINE VERSION (Render Cloud Deployment)

### Current Render Readiness
* **Configuration Specification:** Created `render.yaml` defining a lightweight Python Web Service using Render's standard environment.
* **Dependencies:** Added `dnspython>=2.6.0` to `requirements.txt` to support MongoDB Atlas `mongodb+srv://` URIs.
* **Linux Compatibility:** All file paths use `pathlib.Path`. Zero hardcoded `C:\` or Windows backslashes exist in application code.
* **Relative API Calls:** Frontend `script.js` uses relative paths (`/api/...`), ensuring automatic routing on `https://urbanrisk.onrender.com`.
* **Deployment State:** **Prepared for deployment.** The configuration files are ready, but the service has **not yet been launched on Render** (awaiting your Render account connection).

### Remaining Render Setup Steps
1. Push the updated repository to your GitHub account (`urban-risk-analytics`).
2. Log in to [render.com](https://render.com/) and click **"New > Web Service"** (or use **"Blueprint"** with `render.yaml`).
3. Connect your GitHub repository.
4. Set the Build and Start commands (or let `render.yaml` populate them automatically):
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   * **Health Check Path:** `/`

### Required MongoDB Atlas Configuration
Render requires a cloud database because its free-tier instances are stateless:
1. Create a free M0 cluster on [mongodb.com/atlas](https://www.mongodb.com/cloud/atlas/register).
2. Allow network access from `0.0.0.0/0` in Atlas Security.
3. Migrate your local 9 collections using the provided utility:
   ```powershell
   python scripts/export_to_atlas.py --atlas-uri "mongodb+srv://<user>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority"
   ```
4. In Render Dashboard, add Environment Variables:
   * `MONGODB_URI` = `mongodb+srv://<user>:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority`
   * `MONGODB_DATABASE` = `urban_risk_db`

---

## 2. OFFLINE PORTABLE VERSION (Another Windows Laptop)

### Current Offline Readiness
* **Offline State:** **100% Fully Prepared and Verified.**
* **Local Assets:** Leaflet 1.9.4 CSS, JavaScript, marker icons, and layer control icons are served entirely from `/static/vendor/leaflet/`.
* **Local Typography:** Variable DM Sans font (`dm-sans-variable.woff2`) is stored in `/static/vendor/fonts/` with system font stack fallbacks. All Google Fonts CDN calls removed.
* **Local Hyderabad Study Area Map:** Stored 33 pre-cached raster tiles (`/static/vendor/tiles/`) covering the complete Hyderabad metropolitan study bounds (`17.26° N – 17.55° N, 78.24° E – 78.63° E`) at overview zooms (10, 11, 12).
* **Graceful Degradation:** Deeper zooms (13+) fall back to a styled Cartesian coordinate grid canvas with interactive vector infrastructure points, road networks, and an offline notification banner.
* **Zero External Calls:** Multi-hazard evaluation, spatial queries, and ML surface temperature inference execute 100% locally.

### Startup Command & Launcher
* **Double-click:** `start_urbanrisk.bat` in the project root.
* **Manual Command:**
  ```cmd
  python scripts\serve_ml.py
  ```
* **Local Application URL:** `http://127.0.0.1:8000/app`

### Remaining Offline Limitations
* High-zoom street-level tiles (zoom 13+) require an internet connection for live OpenStreetMap downloading; otherwise, the map displays the Cartesian coordinate grid with full vector overlay interactivity.
* Real-time weather radar precipitation forecasting is not included; the platform relies on historical disaster catalogues (1969–2022) and rain gauge depths.

---

## 3. KAGGLE SUBMISSION PACKAGE

### Current Kaggle Readiness
* **Package State:** **100% Prepared Locally.** (The package has been prepared on disk; you will perform the manual upload to your personal Kaggle account).
* **Package Directory:** `kaggle_package/`
* **Clean Zip Archive:** `URBANRISK_Kaggle_Submission.zip` (**14.70 MB**)
* **Contents Packaged:**
  1. `data/`: Curated CSVs (`hyderabad_modis_heat.csv`, `hyderabad_yale_heat.csv`, `integrated_urban_risk_priority_grid_1km.csv`, `hyderabad_historical_flood_events.csv`) and spatial GeoJSONs.
  2. `models/`: Trained MODIS (16.2 MB) and Yale UHI (38.4 MB) Joblib regression pipelines and metadata.
  3. `requirements.txt`: Python package requirements.
  4. `README_KAGGLE.md`: Comprehensive academic and technical documentation.
  5. `KAGGLE_UPLOAD_GUIDE.md`: Detailed 10-point upload instructions.
  6. `URBANRISK_Demonstration.ipynb`: 12-section educational Kaggle notebook covering problem statement, EDA, ML training, sample predictions, spatial analysis, and IUPS prioritization.
* **Security & Cleanliness Guarantee:**
  * Excluded `.env`, passwords, API keys, and credentials.
  * Excluded `.git`, `__pycache__`, and non-runtime 56 MB GeoJSON files.

### What You Still Need to Upload Manually to Kaggle
1. Go to [kaggle.com/datasets](https://www.kaggle.com/datasets) > **"+ New Dataset"** > Upload `URBANRISK_Kaggle_Submission.zip` (or the contents of `kaggle_package/data`).
2. Go to [kaggle.com/code](https://www.kaggle.com/code) > **"+ New Notebook"** > **File > Import Notebook** > Upload `kaggle_package/URBANRISK_Demonstration.ipynb`.
3. Attach your newly created Dataset to the notebook, click **"Run All"**, and click **"Save Version (Commit)"**.
