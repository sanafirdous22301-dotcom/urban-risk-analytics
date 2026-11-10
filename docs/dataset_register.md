# Dataset Register

## Integrated Urban Risk Analytics and Resource Prioritization System-II

**Project category:** Web Development  
**Geographical scope:** Global  
**Development pilot:** Hyderabad, Telangana, India  
**Dataset preference:** Public datasets  
**Data formats:** Tabular and geospatial

---

# 1. FLOOD DATASET

## Dataset Information

- **Dataset name:** VIIRS/JPSS1+JPSS2 Global Flood Product L3 NRT 250m 2-day GeoTIFF
- **Short name:** VCDWD_L3_F2_NRT
- **Provider:** NASA/GSFC/EOS/ESDIS/LANCE MODIS
- **Product version:** 002
- **Dataset DOI:** 10.5067/VIIRS/VCDWD_L3_F2_NRT.002
- **Catalogue:** https://catalog.data.gov/dataset/viirs-jpss1jpss2-global-flood-product-l3-nrt-250m-2-day-geotiff
- **Data archive:** https://nrt3.modaps.eosdis.nasa.gov/archive/allData/5200/VCDWD_L3_F2_NRT
- **User guide:** https://www.earthdata.nasa.gov/s3fs-public/2025-12/MCDWD_VCDWD_UserGuide_RevF.pdf

## Geographic Information

- **Geographic coverage:** Global
- **Development area:** Hyderabad, India
- **Selected tile:** h25v07
- **Approximate tile boundaries:** 70°E–80°E longitude and 10°N–20°N latitude
- **File format:** GeoTIFF (.tif)
- **Nominal spatial resolution:** Approximately 250 metres
- **Temporal type:** Near Real-Time (NRT)
- **Composite period:** 2 days

## Selected File

- **Filename:** VCDWD_L3_F2_NRT.A2026307.h25v07.002.tif
- **Observation date:** 2026-11-03
- **Tile identifier:** h25v07
- **Storage directory:** data/raw/flood/
- **Download status:** Selected; download not yet confirmed.

## Important Data Information

The product provides satellite-derived flood and surface-water observations.

Documented pixel classifications:

- 0 = No water
- 1 = Surface water
- 2 = Recurring flood (not populated in the documented Beta 1 product)
- 3 = Unusual flood
- 255 = Insufficient data

Exact raster metadata and classifications will be verified against the downloaded file and product documentation.

## Intended Use

- Identify observed flood-affected areas.
- Visualize flood extent geographically.
- Analyse unusual flood-water observations.
- Support flood susceptibility and exposure analysis.

## Limitations

- Near-real-time observations are not a complete historical flood database.
- Does not independently provide rainfall measurements or ground-based water levels.
- Requires additional datasets for comprehensive flood susceptibility modelling.
- Historical validation is necessary before claiming predictive performance.

## Licence and Attribution

- Publicly accessible NASA dataset.
- Check the provider's use and attribution guidance.
- Citation: NASA/GSFC/EOS/ESDIS/LANCE MODIS.

---

# 2. HEAT DATASET

## Dataset Information

- **Dataset name:** Yale Center for Earth Observation (YCEO) Surface Urban Heat Islands, Version 4
- **Short name:** YCEO Surface Urban Heat Islands V4
- **Creators:** T. Chakraborty and X. Lee
- **Provider:** Yale Center for Earth Observation
- **Publisher:** NASA Socioeconomic Data and Applications Center (SEDAC)
- **DOI:** 10.7927/S5M5-ZK14
- **Download page:** https://sedac.ciesin.columbia.edu/data/set/sdei-yceo-sfc-uhi-v4/data-download
- **Documentation:** https://sedac.ciesin.columbia.edu/data/set/sdei-yceo-sfc-uhi-v4/docs
- **Google Earth Engine catalogue:** https://developers.google.com/earth-engine/datasets/catalog/YALE_YCEO_UHI_UHI_all_averaged_v4

## Geographic Information

- **Geographic coverage:** Global urban extents
- **Development area:** Hyderabad, India
- **Temporal coverage:** 2003–2018
- **Spatial resolution:** 300 metres for pixel-level products
- **Data format:** Geospatial raster and derived tabular data
- **Measurement unit:** Degrees Celsius (°C)

## Important Variables

The main annual, seasonal and day/night bands include:

- all_daytime_UHI
- all_nighttime_UHI
- summer_daytime_UHI
- summer_nighttime_UHI
- winter_daytime_UHI
- winter_nighttime_UHI

These bands represent surface urban heat-island intensity.

## Intended Use

- Identify urban heat hotspots.
- Compare daytime and nighttime heat patterns.
- Analyse seasonal variations in urban heat.
- Support heat-risk assessment.
- Combine heat observations with vegetation and infrastructure information.

## Limitations

- Surface urban heat-island intensity is not the same as air temperature.
- It does not directly measure human heat-health risk.
- Additional population, vegetation and land-cover information may be required.
- The dataset covers 2003–2018 and does not represent current-year measurements.

## Licence and Attribution

- **Terms of use:** CC BY 4.0 (as listed in the Google Earth Engine catalogue).
- **Citation:** Chakraborty, T., & Lee, X. (2023). Yale Center for Earth Observation (YCEO) Surface Urban Heat Islands, Version 4, 2003–2018.
- **Download status:** Candidate selected; not downloaded.

---

# 3. INFRASTRUCTURE DATASET

## Dataset Information

- **Dataset name:** OpenStreetMap (OSM)
- **Provider:** OpenStreetMap contributors
- **Regional download source:** https://download.geofabrik.de/asia/india.html
- **Global/regional download source:** https://download.geofabrik.de/
- **Data formats:** OSM PBF, Shapefile and other available formats
- **Geographic coverage:** Global
- **Development area:** Hyderabad, India

## Important Features and Tags

### Buildings
- building

### Roads
- highway

### Hospitals
- amenity=hospital

### Fire Stations
- amenity=fire_station

### Schools
- amenity=school

### Waterways
- waterway

Actual attributes and tags depend on the selected OSM extract.

## Derived Indicators

- Building count
- Building density
- Road length
- Road density
- Number of hospitals
- Number of fire stations
- Distance to nearest hospital
- Distance to nearest emergency facility
- Infrastructure exposure to flood and heat zones

## Intended Use

- Analyse the geographical distribution of infrastructure.
- Assess infrastructure exposure to environmental hazards.
- Estimate emergency-service accessibility.
- Identify areas requiring infrastructure improvements.

## Limitations

- Infrastructure coverage and completeness vary geographically.
- Building age and structural condition are not consistently available.
- OSM data does not directly provide verified infrastructure vulnerability labels.
- Derived vulnerability indicators must be documented and independently validated.

## Licence and Attribution

- **Licence:** Open Database License (ODbL 1.0).
- **Attribution:** © OpenStreetMap contributors.
- **Copyright information:** https://www.openstreetmap.org/copyright
- **Download status:** Candidate selected; not downloaded.

---

# 4. DATASET INTEGRATION PLAN

## Common Geographical Unit

To be finalized after inspecting the spatial coverage and resolution of all three datasets.

Possible geographical units:

- Regular grid cells
- Administrative wards
- Other suitable geographical zones

## Common Identifier

Every geographical analysis zone will receive a unique identifier:

`zone_id`

## Integration Requirements

1. Inspect all original datasets.
2. Verify coordinate reference systems (CRS).
3. Check spatial resolution and geographical extent.
4. Handle missing and invalid observations.
5. Align datasets geographically.
6. Extract raster and vector information into common zones.
7. Create a combined dataset using zone_id.
8. Validate geographical relationships.
9. Avoid spatial data leakage during model evaluation.

---

# 5. PROPOSED FINAL OUTPUT

For each geographical zone, the integrated system should produce:

| Output | Description |
|---|---|
| Flood risk | Flood exposure or susceptibility |
| Heat risk | Urban heat exposure |
| Infrastructure vulnerability | Infrastructure exposure and accessibility indicators |
| Integrated risk score | Combined risk assessment |
| Priority ranking | Areas requiring attention first |
| Suggested intervention | Recommended resource allocation |

---

# 6. PROJECT DATA STORAGE

| Dataset | Storage directory |
|---|---|
| Raw flood data | data/raw/flood/ |
| Raw heat data | data/raw/heat/ |
| Raw infrastructure data | data/raw/infrastructure/ |
| Processed flood data | data/processed/flood/ |
| Processed heat data | data/processed/heat/ |
| Processed infrastructure data | data/processed/infrastructure/ |

Large raw datasets and generated ML models should remain outside the GitHub repository unless specifically needed. Maintain source links, licences and processing documentation.

---

# 7. DATASET VERIFICATION CHECKLIST

## Flood
- [ ] Download NASA GeoTIFF.
- [ ] Verify file size and raster dimensions.
- [ ] Inspect pixel values and metadata.
- [ ] Verify coordinate reference system.
- [ ] Identify additional historical flood data.

## Heat
- [ ] Inspect Yale download resources.
- [ ] Select suitable pixel-level or cluster-level product.
- [ ] Download the Hyderabad-relevant data.
- [ ] Verify bands, units and metadata.

## Infrastructure
- [ ] Select Hyderabad regional extract.
- [ ] Download suitable OSM data.
- [ ] Inspect building, road and facility attributes.
- [ ] Calculate infrastructure indicators.

## Integration
- [ ] Choose common geographical zones.
- [ ] Align all datasets.
- [ ] Create common zone_id.
- [ ] Prepare clean processed datasets.
- [ ] Verify suitability for ML and geospatial analysis.