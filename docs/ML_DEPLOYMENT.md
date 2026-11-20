# Machine Learning Model Deployment Report
## Supervised Surface Heat & Urban Heat Island Inference Service
**Project:** Integrated Urban Risk Analytics and Resource Prioritization System  
**Framework:** FastAPI 0.162.0 / Scikit-Learn 1.9.1 / Joblib 1.6.0  
**Trained Artifacts:**  
- `models/heat/modis/modis_daytime_temperature_regression_candidate.joblib`
- `models/heat/yale/yale_daytime_uhi_regression_candidate.joblib`  
**Evaluation Status:** Verified against held-out spatial test splits  

---

## 1. Machine Learning Problem Formulation & Model Selection

Urban heat risk is a critical hazard dimension in Hyderabad. Rapid urbanization, high built-up surface fractions, and loss of vegetative cooling create severe thermal stress during pre-monsoon and dry periods.

### Primary Deployed Model:
- **Task:** Cross-variable spatial estimation of measured daytime land surface temperature from nighttime surface temperature and geographic coordinates.
- **Important Distinction:** This is a **cross-variable spatial estimation model**, not an autoregressive time-series weather forecast. It enables urban planners to estimate unmonitored daytime surface heat from nighttime thermal infrared passes.
- **Algorithm:** Scikit-Learn `Pipeline(StandardScaler, RandomForestRegressor)`
  - Number of estimators: 300
  - Random state: 42
  - Criterion: Squared error
- **Input Features:**
  1. `latitude`: Geographic latitude in decimal degrees ($17.0^\circ\text{N} \le \text{lat} \le 17.6^\circ\text{N}$)
  2. `longitude`: Geographic longitude in decimal degrees ($78.2^\circ\text{E} \le \text{lon} \le 78.7^\circ\text{E}$)
  3. `nighttime_temp_c`: Measured nighttime surface temperature in °C
- **Prediction Target:**
  - `daytime_temp_c`: Measured land surface temperature in °C
- **Derived Heat Risk Classification:**
  - Daytime Temp $\ge 38.0^\circ\text{C}$: **Severe Heat Risk**
  - Daytime Temp $\ge 34.0^\circ\text{C}$: **High Heat Risk**
  - Daytime Temp $\ge 28.0^\circ\text{C}$: **Moderate Heat Risk**
  - Daytime Temp $< 28.0^\circ\text{C}$: **Low Heat Risk**

### Secondary Deployed Model:
- **Model:** Hyderabad Yale Daytime Urban Heat Island Regressor (`models/heat/yale/`)
- **Target:** `daytime_uhi` (°C urban temperature anomaly above rural baseline)
- **Features:** `latitude`, `longitude`, `nighttime_uhi`

---

## 2. Empirical Model Evaluation Metrics (Non-Fabricated)

The models were evaluated during research notebook experimentation using spatial block cross-validation to prevent geographic data leakage:

| Evaluation Metric | Hyderabad MODIS Surface Heat Model | Hyderabad Yale UHI Model |
|---|---|---|
| **Spatial Block Size** | $0.04^\circ$ ($~4.4\text{ km}$) | $0.04^\circ$ ($~4.4\text{ km}$) |
| **Spatial CV MAE** | **0.506 °C** | **0.393 °C** |
| **Held-out Spatial Test MAE** | **0.949 °C** | **0.240 °C** |
| **Held-out Spatial Test RMSE** | **1.360 °C** | **0.323 °C** |
| **Held-out Spatial Test $R^2$** | **0.357** | **0.509** |
| **Baseline Test MAE** | 1.205 °C | 0.343 °C |

---

## 3. FastAPI Endpoint Contracts

### 1. `POST /api/ml/predict` (and alias `POST /predict`)
Estimates daytime surface temperature and evaluates heat risk.

**Request Body (`application/json`):**
```json
{
  "latitude": 17.3850,
  "longitude": 78.4867,
  "nighttime_temp_c": 24.5
}
```

**Response Body (`HTTP 200 OK`):**
```json
{
  "status": "success",
  "task": "cross-variable estimation of measured daytime temperature; not forecasting",
  "model_name": "Random Forest Regressor",
  "input": {
    "latitude": 17.385,
    "longitude": 78.4867,
    "nighttime_temp_c": 24.5
  },
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

### 2. `POST /api/ml/predict/uhi`
Estimates daytime Urban Heat Island anomaly.

**Request Body (`application/json`):**
```json
{
  "latitude": 17.3850,
  "longitude": 78.4867,
  "nighttime_uhi": 1.5
}
```

### 3. `GET /api/ml/info`
Returns full catalog metadata, features, datasets, and verified test metrics for all active models.

---

## 4. Local Verification & Postman Collection

- **Automated Verification Script:** [`scripts/test_deployment.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/scripts/test_deployment.py)
  - Tests model loading, standard prediction, root alias prediction, UHI prediction, and negative validation tests (latitude out of bounds, missing fields).
  - Test result: **19/19 passing (100%)**.
- **Postman Collection File:** [`docs/Urban_Risk_Analytics_ML_Postman_Collection.json`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/docs/Urban_Risk_Analytics_ML_Postman_Collection.json)
  - Ready for one-click import into Postman.
  - Contains preconfigured requests with JSON bodies and test assertions for both positive and negative cases.

---

## 5. Public ngrok Deployment Guide & Submission Instructions

Faculty Requirement: Expose the local FastAPI server to a public URL and test the endpoint through Postman.

### Step 1: Start the Local FastAPI Server
In PowerShell:
```powershell
cd c:\Users\sanaf\OneDrive\Desktop\urban-risk-analytics
& "C:\Users\sanaf\AppData\Local\Python\bin\python.exe" scripts/serve_ml.py
```
*Verify that the server starts on `http://127.0.0.1:8000`.*

### Step 2: Configure ngrok Authtoken
In a second PowerShell terminal (do not paste token into chat):
```powershell
ngrok config add-authtoken <YOUR_PRIVATE_NGROK_AUTHTOKEN>
```

### Step 3: Launch the ngrok Tunnel
```powershell
ngrok http 8000
```
ngrok will print the active forwarding address, for example:
```text
Forwarding   https://sulfate-universal-nearest.ngrok-free.dev -> http://localhost:8000
```

### Step 4: Test the Live Public Prediction Endpoint
In Postman or terminal curl:
```powershell
curl.exe -X POST https://YOUR_NGROK_URL.ngrok-free.dev/api/ml/predict `
  -H "Content-Type: application/json" `
  -d '{\"latitude\": 17.3850, \"longitude\": 78.4867, \"nighttime_temp_c\": 24.5}'
```

### Important Public URL Notice:
- Free ngrok public URLs are **session-based and temporary**.
- The public URL is active **only as long as both the local FastAPI server (`serve_ml.py`) and the `ngrok http 8000` process remain running**.
- For your 21 November 2026 project submission and faculty evaluation, keep both terminal windows open and active.
