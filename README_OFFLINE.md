# URBANRISK — Offline Portable Edition Guide

## Running on Another Windows Laptop (No Internet Required)

This guide explains how to run the **URBANRISK** platform on any Windows laptop without an active internet connection.

---

### Prerequisites on the Destination Laptop

1. **Python 3.10, 3.11, or 3.12+**
   * Download and install Python from [python.org](https://www.python.org/) with the checkbox **"Add Python to PATH"** enabled.
2. **MongoDB Community Server (v6.0, 7.0, or 8.0)**
   * Install MongoDB Community Server with the **"Run MongoDB as a Service"** option checked.
   * Default connection URL: `mongodb://127.0.0.1:27017/`.

---

### Step 1: Copy the Project Folder

Copy the entire `urban-risk-analytics/` directory to the destination laptop (via USB drive, local network, or archive).

---

### Step 2: Install Required Python Packages

Open Command Prompt or PowerShell in the project directory and run:

```cmd
pip install -r requirements.txt
```

*(All required packages: `fastapi`, `uvicorn`, `pymongo`, `scikit-learn`, `joblib`, `pandas`, `numpy`, `dnspython`).*

---

### Step 3: Populate Local MongoDB Database

If MongoDB on the new laptop is fresh, restore the 9 collections from the included database dump:

```cmd
mongorestore --db=urban_risk_db ./backups/mongo_dump/urban_risk_db
```

*(Alternatively, if running the SQL baseline, the provided backup file `backups/urban_risk_db_backup.sql` is also preserved).*

---

### Step 4: Start URBANRISK (One-Click)

Double-click the startup script in the project root:

```cmd
start_urbanrisk.bat
```

This script will:
1. Check if MongoDB is active on port 27017 (or start the Windows MongoDB service).
2. Launch your default browser to **`http://127.0.0.1:8000/app`**.
3. Start the FastAPI backend and ML prediction servers.

---

### Verifying Offline Features

* **Hyderabad Map & Landmarks:** Renders offline using local Leaflet assets and pre-cached study area tiles (`/static/vendor/tiles/`).
* **Location Selection:** Click anywhere on the map or pick landmarks (Charminar, Hitec City, Begumpet, etc.) from the dropdown.
* **Risk Evaluation:** Click **"Assess Risk"** to run multi-hazard risk assessment on local MongoDB and local Random Forest ML models.
* **Area-Level Prioritisation:** Generates the 0–100 IUPS screening priority score and actionable municipal directives.
* **Interactive API Documentation:** Available offline at **`http://127.0.0.1:8000/docs`**.

---

### Stopping the Application

In the Command Prompt window opened by `start_urbanrisk.bat`, press **`Ctrl + C`**, then type **`Y`** to stop the server.
