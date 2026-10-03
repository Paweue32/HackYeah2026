from contextlib import asynccontextmanager
import httpx
import json
import pathlib
from fastapi import FastAPI
from database import database, models
from typing import Dict, Any, List

# Table creation in SQLite upon app startup
models.Base.metadata.create_all(bind=database.engine)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

CACHE_FILE = pathlib.Path("krakow_roads.json")

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
            
            roads = []
            for item in elements:
                if item.get("type") == "way":
                    # Odtwarzamy listę geometrii na podstawie ID z pola "nodes"
                    geometry = [
                        nodes_coords[node_id]
                        for node_id in item.get("nodes", [])
                        if node_id in nodes_coords
                    ]

                    roads.append({
                        "id": item["id"],
                        "name": item.get("tags", {}).get("name", "No name"),
                        "highway_type": item.get("tags", {}).get("highway"),
                        "surface": item.get("tags", {}).get("surface"),
                        "maxspeed": item.get("tags", {}).get("maxspeed"),
                        "nodes": item.get("nodes", []),
                        "geometry": geometry,
                        "tags": item.get("tags", {})
                    })

            # Zapisz pobrane dane do pliku JSON
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(roads, f, ensure_ascii=False, indent=2)
            print("✅ Loaded data to krakow_roads.json")

            return roads

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
        
        # Downloaded data to krakow_roads.json
        await fetch_krakow_roads(client)

        # pass the data to the db
    
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

