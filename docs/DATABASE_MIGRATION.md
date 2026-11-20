# Database Migration Report
## MySQL 8.0 to MongoDB 8.0 Architecture Migration
**Project:** Integrated Urban Risk Analytics and Resource Prioritization System  
**Target Database:** MongoDB (`urban_risk_db`)  
**Active Client:** PyMongo 4.20.0  
**Migration Verification Status:** Complete & Verified  

---

## 1. Former MySQL Architecture

The project initially used MySQL 8.0 with SQLAlchemy 2.x and PyMySQL to manage tabular dataset records, flood events, spatial locations, and infrastructure assets.

### Former Relational Limitations:
1. **Rigid Table Schemas:** Multi-hazard observations (rainfall depths, surface temperatures, heat island anomalies) required complex multi-table joins across `hazard_observations`, `dataset_versions`, and `spatial_locations`.
2. **Spatial Indexing Constraints:** MySQL spatial support required manual WKT conversion and had performance constraints when querying 93,000+ road segment coordinates and 2,000+ infrastructure points concurrently with web map bounding-box pans.
3. **Primary Key Auto-Increment Dependency:** Relational tables relied on MySQL `AUTO_INCREMENT` IDs (`BIGINT`), which required database round-trips for document generation.

---

## 2. MongoDB Architecture & Migration Strategy

The migration was planned and executed using [`scripts/migrate_mysql_to_mongodb.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/scripts/migrate_mysql_to_mongodb.py) with the following design rules:
1. **Preserve Original Primary Keys:** MySQL primary keys (`location_id`, `dataset_id`, `asset_id`, etc.) were mapped directly to MongoDB `_id` and retained as top-level integer fields to maintain complete backward compatibility with frontend contracts and ML pipelines.
2. **Standardize GeoJSON Spatial Fields:** MySQL `POINT(longitude, latitude)` columns were converted to standard GeoJSON:
   ```json
   {
     "type": "Point",
     "coordinates": [78.4867, 17.3850]
   }
   ```
   Stored under `geom` for `spatial_locations` and `infrastructure_assets`, and `representative_point` for `road_segments`.
3. **Create Geospatial 2dsphere Indexes:** High-performance 2dsphere indexes were established to allow `$geoWithin` polygon bounding box queries directly from the Leaflet.js interactive map.
4. **Sequence Counter Collections (`db.counters`):** To preserve integer auto-increment semantics without relational locks, atomic MongoDB sequence tracking (`find_one_and_update` with `$inc`) was implemented in [`database/counters.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/database/counters.py).

---

## 3. The Nine Migrated Collections

Every collection from the relational schema was migrated into MongoDB. All collections exist in `urban_risk_db`:

| # | Collection Name | Document Count | Indexes Configured | Purpose & Data Stored |
|---|---|---|---|---|
| 1 | `dataset_versions` | **6** | `_id_`, `dataset_name_1`, `retrieved_at_1` | Metadata catalog for integrated datasets (dates, records, provenance). |
| 2 | `spatial_locations` | **7,316** | `_id_`, `location_type_1`, `geom_2dsphere` | Master geographic sample points and user-saved assessment plots. |
| 3 | `infrastructure_assets` | **2,083** | `_id_`, `dataset_id_1`, `category_1`, `geom_2dsphere` | Mapped facilities (hospitals, fire stations, schools, clinics). |
| 4 | `road_segments` | **93,437** | `_id_`, `dataset_id_1`, `road_type_1`, `representative_point_2dsphere` | OpenStreetMap road segment sample points with road types and speed limits. |
| 5 | `hazard_observations` | **14,614** | `_id_`, `dataset_id_1`, `location_id_1`, `hazard_type_1` | Empirical measurements of rainfall, surface temperature, and UHI index. |
| 6 | `flood_events` | **40** | `_id_`, `dataset_id_1`, `district_1` | Documented historical Hyderabad flood occurrences (1981–2023). |
| 7 | `model_runs` | **0** | `_id_`, `module_name_1` | Preserved for future automated ML batch run metadata logging. |
| 8 | `risk_assessments` | **0** | `_id_`, `location_id_1`, `model_run_id_1` | Preserved for future predictive risk score storage. |
| 9 | `resource_priorities` | **0** | `_id_`, `assessment_id_1` | Preserved for municipal resource prioritization records. |
| + | `counters` | **2** | `_id_` | Sequence generators for `location_id` (14,707) and `dataset_id` (13). |

**Total Documents in MongoDB:** **117,498 documents**

---

## 4. Retained Legacy Files & Backups

In strict accordance with project safety guidelines, no legacy files were deleted:
- [`backups/urban_risk_db_backup.sql`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/backups/urban_risk_db_backup.sql): Preserved complete 15.5 MB mysqldump export file.
- [`database/schema.sql`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/database/schema.sql): Preserved reference MySQL DDL table definition.
- [`database/connection.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/database/connection.py): Preserved legacy SQLAlchemy engine configuration.
- [`database/session.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/database/session.py): Preserved legacy session factory (confirmed unused by active FastAPI routers).
- [`scripts/migrate_mysql_to_mongodb.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/scripts/migrate_mysql_to_mongodb.py): Preserved one-time migration execution script.
- [`scripts/import_datasets.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/scripts/import_datasets.py): Preserved legacy CSV-to-MySQL ETL script.

---

## 5. Active Database Verification

- **Connection Management:** [`database/mongodb.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/database/mongodb.py) provides the single source of truth for the PyMongo client and database handle.
- **Connection Health:** Verified via `db.admin.command("ping")` on endpoint `/health/db` (returns `ping: 1.0`, MongoDB 8.0.38).
- **FastAPI Lifespan Priming:** [`backend/main.py`](file:///c:/Users/sanaf/OneDrive/Desktop/urban-risk-analytics/backend/main.py) primes `db.counters` during application startup to guarantee that new plot insertions or dataset registrations never generate colliding IDs.
