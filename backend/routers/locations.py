
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from database.mongodb import db
from database.counters import get_next_sequence
from backend.location_schemas import PlotLocationCreate


router = APIRouter(
    prefix="/api/locations",
    tags=["Spatial Locations"]
)

# Standard curated Hyderabad municipal localities across Greater Hyderabad
CURATED_HYDERABAD_LOCALITIES = [
    {"name": "Charminar", "area": "Old City Heritage District", "latitude": 17.3616, "longitude": 78.4747, "type": "locality"},
    {"name": "Hitec City", "area": "Madhapur Tech Corridor", "latitude": 17.4435, "longitude": 78.3772, "type": "locality"},
    {"name": "Madhapur", "area": "HITEC City / Cyberabad Corridor", "latitude": 17.4483, "longitude": 78.3915, "type": "locality"},
    {"name": "Gachibowli", "area": "Financial District / IT SEZ", "latitude": 17.4401, "longitude": 78.3489, "type": "locality"},
    {"name": "Kondapur", "area": "Botanical Garden / Cyberabad Hub", "latitude": 17.4658, "longitude": 78.3582, "type": "locality"},
    {"name": "Banjara Hills", "area": "Road No. 1 / Central Core", "latitude": 17.4156, "longitude": 78.4350, "type": "locality"},
    {"name": "Jubilee Hills", "area": "Road No. 36 / Film Nagar Corridor", "latitude": 17.4319, "longitude": 78.4073, "type": "locality"},
    {"name": "Secunderabad", "area": "Twin City Commercial Core", "latitude": 17.4399, "longitude": 78.4983, "type": "locality"},
    {"name": "Begumpet", "area": "Airport Road Commercial Corridor", "latitude": 17.4447, "longitude": 78.4664, "type": "locality"},
    {"name": "Ameerpet", "area": "SR Nagar Educational & Metro Hub", "latitude": 17.4375, "longitude": 78.4483, "type": "locality"},
    {"name": "Kukatpally", "area": "High-Density Urban Commercial Zone", "latitude": 17.4947, "longitude": 78.3996, "type": "locality"},
    {"name": "Kukatpally Housing Board", "area": "KPHB Colony / Mixed Density Sector", "latitude": 17.4962, "longitude": 78.3912, "type": "locality"},
    {"name": "Miyapur", "area": "North-Western Transit Terminal Hub", "latitude": 17.4969, "longitude": 78.3534, "type": "locality"},
    {"name": "Nizampet", "area": "Pragathi Nagar Lake Corridor", "latitude": 17.5180, "longitude": 78.3810, "type": "locality"},
    {"name": "Bachupally", "area": "Educational & Healthcare Zone", "latitude": 17.5380, "longitude": 78.3680, "type": "locality"},
    {"name": "Chandanagar", "area": "BHEL Township Adjacent Sector", "latitude": 17.4920, "longitude": 78.3260, "type": "locality"},
    {"name": "Hafeezpet", "area": "Miyapur / Kondapur Connecting Corridor", "latitude": 17.4840, "longitude": 78.3490, "type": "locality"},
    {"name": "Lingampally", "area": "BHEL Township / Outer Transit Terminal", "latitude": 17.4880, "longitude": 78.3180, "type": "locality"},
    {"name": "Patancheru", "area": "North-Western Industrial Zone", "latitude": 17.5300, "longitude": 78.2650, "type": "locality"},
    {"name": "Tellapur", "area": "Western Growth Corridor", "latitude": 17.4670, "longitude": 78.2980, "type": "locality"},
    {"name": "Nanakramguda", "area": "Financial District South", "latitude": 17.4200, "longitude": 78.3490, "type": "locality"},
    {"name": "Kokapet", "area": "Neopolis Commercial Growth Corridor", "latitude": 17.4120, "longitude": 78.3320, "type": "locality"},
    {"name": "Narsingi", "area": "Outer Ring Road Junction Sector", "latitude": 17.3910, "longitude": 78.3580, "type": "locality"},
    {"name": "Puppalguda", "area": "Manikonda / Gachibowli Link Zone", "latitude": 17.4080, "longitude": 78.3690, "type": "locality"},
    {"name": "Manikonda", "area": "Outer Ring Road IT Corridor Hub", "latitude": 17.4042, "longitude": 78.3789, "type": "locality"},
    {"name": "Shaikpet", "area": "Tolichowki / Gachibowli Link", "latitude": 17.4120, "longitude": 78.3970, "type": "locality"},
    {"name": "Tolichowki", "area": "Golconda Heritage Corridor", "latitude": 17.4018, "longitude": 78.4124, "type": "locality"},
    {"name": "Mehdipatnam", "area": "Tolichowki / PVNR Expressway Corridor", "latitude": 17.3938, "longitude": 78.4421, "type": "locality"},
    {"name": "Masab Tank", "area": "Banjara Hills Transit Approach", "latitude": 17.4040, "longitude": 78.4480, "type": "locality"},
    {"name": "Somajiguda", "area": "Raj Bhavan Road Corridor", "latitude": 17.4260, "longitude": 78.4570, "type": "locality"},
    {"name": "Panjagutta", "area": "Central Transit Intersection", "latitude": 17.4270, "longitude": 78.4500, "type": "locality"},
    {"name": "SR Nagar", "area": "Ameerpet Metro Commercial Belt", "latitude": 17.4420, "longitude": 78.4440, "type": "locality"},
    {"name": "Sanathnagar", "area": "Industrial & Residential Hub", "latitude": 17.4560, "longitude": 78.4430, "type": "locality"},
    {"name": "Moosapet", "area": "Kukatpally Industrial Transit Junction", "latitude": 17.4720, "longitude": 78.4230, "type": "locality"},
    {"name": "Balanagar", "area": "Industrial & Aerospace Corridor", "latitude": 17.4690, "longitude": 78.4410, "type": "locality"},
    {"name": "Jeedimetla", "area": "Industrial & Residential Sector", "latitude": 17.5180, "longitude": 78.4520, "type": "locality"},
    {"name": "Kompally", "area": "Medchal Highway Residential Hub", "latitude": 17.5400, "longitude": 78.4840, "type": "locality"},
    {"name": "Bowenpally", "area": "National Highway Transit Gate", "latitude": 17.4720, "longitude": 78.4860, "type": "locality"},
    {"name": "Alwal", "area": "Northern Secunderabad Cantonment Belt", "latitude": 17.5020, "longitude": 78.5140, "type": "locality"},
    {"name": "Sainikpuri", "area": "ECIL / Kapra Residential Belt", "latitude": 17.4890, "longitude": 78.5480, "type": "locality"},
    {"name": "ECIL Cross Roads", "area": "Kapra / Moula Ali Corridor", "latitude": 17.4653, "longitude": 78.5674, "type": "locality"},
    {"name": "Moula Ali", "area": "Industrial & Railway Enclave", "latitude": 17.4720, "longitude": 78.5610, "type": "locality"},
    {"name": "Malkajgiri", "area": "North-Eastern Residential Belt", "latitude": 17.4526, "longitude": 78.5303, "type": "locality"},
    {"name": "Marredpally", "area": "East & West Marredpally Enclave", "latitude": 17.4470, "longitude": 78.5110, "type": "locality"},
    {"name": "Tarnaka", "area": "Osmania University / Rail Nilayam", "latitude": 17.4234, "longitude": 78.5355, "type": "locality"},
    {"name": "Habsiguda", "area": "Metro Line 3 Transit Enclave", "latitude": 17.4140, "longitude": 78.5440, "type": "locality"},
    {"name": "Nacharam", "area": "Industrial Estate Corridor", "latitude": 17.4280, "longitude": 78.5680, "type": "locality"},
    {"name": "Uppal", "area": "Habsiguda Industrial & Sports Belt", "latitude": 17.4000, "longitude": 78.5588, "type": "locality"},
    {"name": "Nagole", "area": "Musi River South Bank", "latitude": 17.3760, "longitude": 78.5650, "type": "locality"},
    {"name": "LB Nagar", "area": "Southern Transit Corridor Junction", "latitude": 17.3487, "longitude": 78.5571, "type": "locality"},
    {"name": "Vanasthalipuram", "area": "Highway Residential Township", "latitude": 17.3320, "longitude": 78.5720, "type": "locality"},
    {"name": "Hayathnagar", "area": "East Highway Municipal Ward", "latitude": 17.3270, "longitude": 78.5990, "type": "locality"},
    {"name": "Saroornagar", "area": "Lake Catchment Residential Ward", "latitude": 17.3520, "longitude": 78.5380, "type": "locality"},
    {"name": "Dilsukhnagar", "area": "Chaitanyapuri High-Density Zone", "latitude": 17.3685, "longitude": 78.5262, "type": "locality"},
    {"name": "Kothapet", "area": "Fruit Market Commercial Belt", "latitude": 17.3650, "longitude": 78.5410, "type": "locality"},
    {"name": "Malakpet", "area": "Old City Eastern Corridor", "latitude": 17.3750, "longitude": 78.5020, "type": "locality"},
    {"name": "Moosarambagh", "area": "Musi River Basin Corridor", "latitude": 17.3705, "longitude": 78.5080, "type": "locality"},
    {"name": "Amberpet", "area": "Ramanthapur Drainage Basin", "latitude": 17.3892, "longitude": 78.5179, "type": "locality"},
    {"name": "Kachiguda", "area": "Railway Junction Commercial Sector", "latitude": 17.3910, "longitude": 78.4980, "type": "locality"},
    {"name": "Koti", "area": "Sultan Bazar Commercial Hub", "latitude": 17.3850, "longitude": 78.4867, "type": "locality"},
    {"name": "Abids", "area": "Central Commercial District", "latitude": 17.3910, "longitude": 78.4735, "type": "locality"},
    {"name": "Nampally", "area": "Station Road Core Sector", "latitude": 17.3920, "longitude": 78.4703, "type": "locality"},
    {"name": "Lakdi Ka Pul", "area": "Secretariat & Public Gardens", "latitude": 17.4059, "longitude": 78.4725, "type": "locality"},
    {"name": "Khairatabad", "area": "Hussain Sagar Western Shore", "latitude": 17.4120, "longitude": 78.4620, "type": "locality"},
    {"name": "Himayatnagar", "area": "Narayanaguda Commercial Sector", "latitude": 17.3990, "longitude": 78.4870, "type": "locality"},
    {"name": "Basheerbagh", "area": "Administrative & Commercial District", "latitude": 17.4020, "longitude": 78.4780, "type": "locality"},
    {"name": "Musheerabad", "area": "Central Mixed-Density Ward", "latitude": 17.4180, "longitude": 78.4990, "type": "locality"},
    {"name": "Secunderabad Station", "area": "Major Rail Transit Hub", "latitude": 17.4340, "longitude": 78.5010, "type": "locality"},
    {"name": "Paradise", "area": "Twin City Transit Intersection", "latitude": 17.4410, "longitude": 78.4880, "type": "locality"},
    {"name": "Santoshnagar", "area": "IS Sadan High-Density Ward", "latitude": 17.3480, "longitude": 78.5060, "type": "locality"},
    {"name": "Saidabad", "area": "South-East Drainage Catchment", "latitude": 17.3620, "longitude": 78.5120, "type": "locality"},
    {"name": "Chandrayangutta", "area": "South Hyderabad Drainage Basin", "latitude": 17.3195, "longitude": 78.4756, "type": "locality"},
    {"name": "Falaknuma", "area": "Palace Sector Heritage Core", "latitude": 17.3320, "longitude": 78.4680, "type": "locality"},
    {"name": "Bahadurpura", "area": "Nehru Zoological Park Basin", "latitude": 17.3550, "longitude": 78.4520, "type": "locality"},
    {"name": "Purana Pul", "area": "Musi River Historic Crossing", "latitude": 17.3680, "longitude": 78.4610, "type": "locality"},
    {"name": "Karwan", "area": "Heritage Residential Ward", "latitude": 17.3780, "longitude": 78.4410, "type": "locality"},
    {"name": "Golconda", "area": "Fort Heritage Enclave", "latitude": 17.3830, "longitude": 78.4010, "type": "locality"},
    {"name": "Attapur", "area": "Rajendranagar Urban Basin", "latitude": 17.3639, "longitude": 78.4326, "type": "locality"},
    {"name": "Rajendranagar", "area": "Agricultural University Corridor", "latitude": 17.3180, "longitude": 78.4080, "type": "locality"},
    {"name": "Shamshabad", "area": "RGIA Airport Environs Sector", "latitude": 17.2650, "longitude": 78.4280, "type": "locality"}
]


@router.get("/search")
def search_locations(
    q: str = Query(..., min_length=1, description="Locality or place search query"),
    limit: int = Query(10, ge=1, le=25)
):
    """
    Search Hyderabad localities, civic amenities (hospitals, clinics, civic buildings),
    and major roads using the project's authentic spatial database.
    """
    query = q.strip().lower()
    if not query:
        return {"query": q, "total": 0, "results": []}

    results = []
    seen = set()

    # 1. Match against Curated Localities (highest priority for primary urban localities)
    for loc in CURATED_HYDERABAD_LOCALITIES:
        name = loc["name"]
        area = loc["area"]
        if query in name.lower() or query in area.lower():
            seen.add(name.lower())
            results.append({
                "name": name,
                "label": f"{name}, Hyderabad",
                "subtext": f"{area} · Hyderabad, Telangana",
                "category": "Locality",
                "latitude": loc["latitude"],
                "longitude": loc["longitude"]
            })
            if len(results) >= limit:
                return {"query": q, "total": len(results), "results": results}

    # 2. Match against OpenStreetMap Named Infrastructure Assets (hospitals, clinics, civic centers)
    if db is not None:
        try:
            regex_pattern = re.compile(re.escape(query), re.IGNORECASE)
            # Find in infrastructure_assets
            for asset in db.infrastructure_assets.find({"asset_name": regex_pattern}).limit(15):
                name = (asset.get("asset_name") or "").strip()
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                cat = asset.get("category", "civic").capitalize()
                subtype = (asset.get("subtype") or cat).capitalize()
                results.append({
                    "name": name,
                    "label": f"{name}, Hyderabad",
                    "subtext": f"{subtype} · Hyderabad, Telangana",
                    "category": cat,
                    "latitude": round(asset["latitude"], 5),
                    "longitude": round(asset["longitude"], 5)
                })
                if len(results) >= limit:
                    break
        except Exception:
            pass

    # 3. Match against OpenStreetMap Major Named Road Corridors
    if len(results) < limit and db is not None:
        try:
            regex_pattern = re.compile(re.escape(query), re.IGNORECASE)
            for road in db.road_segments.find({"road_name": regex_pattern}).limit(10):
                name = (road.get("road_name") or "").strip()
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                road_type = (road.get("road_type") or "corridor").capitalize()
                results.append({
                    "name": name,
                    "label": f"{name}, Hyderabad",
                    "subtext": f"{road_type} Road · Hyderabad, Telangana",
                    "category": "Road",
                    "latitude": round(road["latitude"], 5),
                    "longitude": round(road["longitude"], 5)
                })
                if len(results) >= limit:
                    break
        except Exception:
            pass

    return {
        "query": q,
        "total": len(results),
        "results": results
    }


# POST: Save a new plot location
@router.post("/plots", status_code=201)
def create_plot_location(location: PlotLocationCreate):
    try:
        location_id = get_next_sequence("location_id")
        location_document = {
            "_id": location_id,
            "location_id": location_id,
            "location_type": "plot",
            "latitude": location.latitude,
            "longitude": location.longitude,
            "geom": {
                "type": "Point",
                "coordinates": [
                    location.longitude,
                    location.latitude
                ]
            },
            "created_at": datetime.now(timezone.utc)
        }
        db.spatial_locations.insert_one(location_document)
        return {
            "message": "Plot location saved successfully",
            "location_id": location_id,
            "location_type": "plot",
            "latitude": location.latitude,
            "longitude": location.longitude
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to save plot location"
        )


# GET: Retrieve all saved plot locations
@router.get("/plots")
def get_plot_locations():
    try:
        locations = list(
            db.spatial_locations.find(
                {"location_type": "plot"},
                {
                    "_id": 0,
                    "location_id": 1,
                    "location_type": 1,
                    "latitude": 1,
                    "longitude": 1,
                    "created_at": 1
                }
            ).sort("location_id", -1)
        )
        return {
            "total": len(locations),
            "locations": locations
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve plot locations"
        )

