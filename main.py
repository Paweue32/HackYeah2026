from contextlib import asynccontextmanager
import httpx
import pathlib
from fastapi import FastAPI
from sqlalchemy import insert
from database import database, models
from typing import Dict, Any, List
from geopy.distance import geodesic
from database.models import Ways
from database.database import SessionLocal
import json

# Table creation in SQLite upon app startup
models.Base.metadata.create_all(bind=database.engine)

db = SessionLocal()

OVERPASS_URLS = [
    "https://overpass.openstreetmap.fr/api/interpreter", 
    "https://overpass.osm.ch/api/interpreter",         
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",         
    "https://overpass.kumi.systems/api/interpreter",    
    "https://overpass.private.coffee/api/interpreter",  
    "https://overpass.nchc.org.tw/api/interpreter"
    
]

CACHE_FILE = pathlib.Path("krakow_roads_formatted.json")

async def fetch_krakow_roads(client: httpx.AsyncClient, highway: str = "primary|secondary|tertiary|footway|pedestrian") -> List[Dict[str, Any]]:
    """Helper function - downloads data from Overpass API."""
    
    query = f"""
    [out:json][timeout:200];
    area["boundary"="administrative"]["name"="Kraków"]["admin_level"="7"]->.searchArea;
    way["highway"~"^({highway})$"](area.searchArea);
    (._; >;);
    out body;
    """

    for url in OVERPASS_URLS:
        try:
            print(f"⏳ Downloading data from {url}...")
            response = await client.post(url, data={"data": query})
            response.raise_for_status()

            raw_data = response.json()
            elements = raw_data.get("elements", [])

            # Indexing all nodes (node_id -> coords)
            nodes_coords = {}
            for item in elements:
                if item.get("type") == "node":
                    nodes_coords[item["id"]] = {
                        "lat": item["lat"],
                        "lon": item["lon"]
                    }
            
            ways = []
            for item in elements:
                if item.get("type") == "way":
                    # Odtwarzamy listę geometrii na podstawie ID z pola "nodes"
                    geometry = [
                        nodes_coords[node_id]
                        for node_id in item.get("nodes", [])
                        if node_id in nodes_coords
                    ]

                    # count way distance based on geometry
                    points = [(p["lat"], p["lon"]) for p in geometry]

                    distance = sum(geodesic(a, b).meters for a, b in zip(points, points[1:]))

                    ways.append({
                        "way_id": item["id"],
                        "nodes": item.get("nodes", []),
                        "coordinates": geometry,
                        "distance": distance,
                        "way_rating": 5,
                    })

            # TMP save data to json
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(ways, f, ensure_ascii=False, indent=2)
            print("✅ Loaded data to krakow_roads.json")

            return ways

            # Save downloaded and parsed data to database
            try:
                db.execute(insert(Ways), ways)
                db.commit()
            finally:
                db.close()
            return ways

        except Exception as e:
            print(f"⚠️ Data download Error from url: {url} , Error: {e}")
            continue

    print("❌ The data was not downloaded.")
    return []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- CODE THAT RUNS UPON APP START ---

    headers = {"User-Agent": "HackYeah2026_KrakowApp/1.0"}

    print("⏳ Downloading Krakow roads from Overpass API...")
    
    async with httpx.AsyncClient(headers=headers, timeout=200.0) as client:
        
        # pass the data to the db
        await fetch_krakow_roads(client)

        
    
    yield  # Here the app starts and accepts requests

    # --- CODE THAT RUNS UPON APP HALT ---
    print("🛑 Closing app...")
    app.state.krakow_roads.clear()

app = FastAPI(lifespan=lifespan)

@app.get("/map/")
async def testing_call(start: str, dest: str) -> list:
    res : list[str] = []
    res.append(start)
    res.append(dest)
    return res

