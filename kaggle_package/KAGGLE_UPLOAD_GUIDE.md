# URBANRISK — Kaggle Upload & Publishing Guide

This step-by-step guide walks you through creating your **Kaggle Dataset** and publishing your **Kaggle Notebook**.

---

## Part A: Create the Kaggle Dataset

### 1. Log in to Kaggle
* Visit [kaggle.com](https://www.kaggle.com/) and sign in to your Kaggle account.

### 2. Create a New Dataset
* Click the **"+ Create"** button in the top left sidebar and select **"New Dataset"**.

### 3. Suggested Dataset Details
* **Dataset Title:** `URBANRISK — Integrated Urban Risk Analytics (Hyderabad)`
* **URL Slug / Identifier:** `urbanrisk-hyderabad-datasets`
* **Visibility:** Set to **Public** (or **Private** initially if you want to test first).

### 4. What Files to Upload
Upload the curated files from your `kaggle_package/data/` directory:
1. `hyderabad_modis_heat.csv` (Satellite daytime/nighttime surface temperatures)
2. `hyderabad_yale_heat.csv` (Urban Heat Island anomalies)
3. `integrated_urban_risk_priority_grid_1km.csv` (791 precomputed IUPS 1-km cells)
4. `hyderabad_floods_historical.geojson` (Historical flood disaster polygons)
5. `osm_amenities_hyderabad.geojson` (Civic emergency amenities)

*(Alternatively, you can drag and drop the `kaggle_package/data` folder or upload `URBANRISK_Kaggle_Submission.zip`).*

### 5. Suggested Description
Paste the following description in the dataset summary:
> **URBANRISK** compiles multi-hazard environmental observations, satellite thermal imagery (NASA MODIS & Yale UHI), historical flood disaster events (IMD 1969–2022), and civic emergency infrastructure (OpenStreetMap) across Greater Hyderabad, Telangana, India. The dataset supports spatial regression modeling and multi-criteria Integrated Urban Priority Screening (IUPS).

### 6. Click "Create"
Kaggle will process the files and generate your public Dataset URL:
* **Your Dataset URL format:** `https://www.kaggle.com/datasets/<your-username>/urbanrisk-hyderabad-datasets`

---

## Part B: Create & Run the Kaggle Notebook

### 1. Create a New Notebook
* On Kaggle, click **"+ Create" > "New Notebook"** (or click **"New Notebook"** directly from your newly created dataset page).

### 2. Import the Demonstration Notebook
* In the notebook editor, click **File > Import Notebook**.
* Upload the file: **`kaggle_package/URBANRISK_Demonstration.ipynb`**.

### 3. Attach Your Dataset
* In the right-hand panel under **Data**, click **"+ Add Data"**.
* Search for your dataset: `URBANRISK — Integrated Urban Risk Analytics (Hyderabad)` (or select from **"Your Work"**).
* Click **"Add"**.
* Kaggle will mount your dataset under: `/kaggle/input/urbanrisk-hyderabad-datasets/`.

### 4. Configure Session Settings
* **Language:** Python
* **Environment:** Default (Python 3.10+)
* **Accelerator:** CPU (Standard) is sufficient; no GPU required.
* **Internet:** Off or On (the notebook runs completely self-contained).

### 5. Run All Cells
* Click **Run > Run All** (or press `Shift + Enter` through each cell).
* Observe:
  1. Data summary statistics and histograms.
  2. Random Forest Regressor training and validation (MAE ~0.506 °C).
  3. Landmark predictions for Charminar, Hitec City, Begumpet, and Moosarambagh.
  4. IUPS Priority Score distribution and top 10 priority intervention cells.

### 6. Save & Publish Your Notebook
* Click the **"Save Version"** button in the top right.
* Select **"Save & Run All (Commit)"**.
* Once the run completes successfully, open the version.
* Click **"Sharing"** and switch from **Private** to **Public**.

### 7. Your Final Kaggle URLs
* **Dataset URL:** `https://www.kaggle.com/datasets/<your-username>/urbanrisk-hyderabad-datasets`
* **Notebook URL:** `https://www.kaggle.com/code/<your-username>/urbanrisk-demonstration`

Share these URLs with your project mentor, evaluators, or in your final project report!
