import sys
import asyncio

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
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter", 
    "https://overpass-api.de/api/interpreter", 
    "https://overpass.openstreetmap.fr/api/interpreter", 
    "https://overpass.osm.ch/api/interpreter",         
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter"
    
]

CACHE_FILE = pathlib.Path("krakow_roads_formatted.json")

async def fetch_krakow_roads(client: httpx.AsyncClient, highway: str = "primary|secondary|tertiary|footway|pedestrian") -> List[Dict[str, Any]]:
    """Helper function - downloads data from Overpass API."""

    query = f"""
    [out:json][timeout:200];
    area["boundary"="administrative"]["name"="Kraków"]->.searchArea;
    way["highway"~"^({highway})$"](area.searchArea);
    out geom;
    """
    
    # query = f"""
    # [out:json][timeout:200];
    # area["boundary"="administrative"]["name"="Kraków"]->.searchArea;
    # way["highway"~"^({highway})$"](area.searchArea);
    # (._; >;);
    # out body;
    # """

    for url in OVERPASS_URLS:
        try:
            print(f"⏳ Downloading data from {url}...")
            response = await client.post(url, data={"data": query})
            response.raise_for_status()

            raw_data = response.json()
            elements = raw_data.get("elements", [])

            # # Indexing all nodes (node_id -> coords)
            # nodes_coords = {}
            # for item in elements:
            #     if item.get("type") == "node":
            #         nodes_coords[item["id"]] = {
            #             "lat": item["lat"],
            #             "lon": item["lon"]
            #         }

            # print(nodes_coords)

            # Jeśli użyjesz `out geom;`, pętla wygląda tak prosto:
            ways = []
            for item in elements:
                if item.get("type") == "way":
                    # Masz gotowe współrzędne podpięte pod drogę!
                    geometry = item.get("geometry", []) 
                    
                    points = [(p["lat"], p["lon"]) for p in geometry]
                    distance = sum(geodesic(a, b).meters for a, b in zip(points, points[1:]))

                    ways.append({
                        "way_id": item["id"],
                        "coordinates": geometry,
                        "distance": distance,
                        "way_rating": 5,
                    })
            
            # ways = []
            # for item in elements:
            #     if item.get("type") == "way":
            #         # Odtwarzamy listę geometrii na podstawie ID z pola "nodes"
            #         geometry = [
            #             nodes_coords[node_id]
            #             for node_id in item.get("nodes", [])
            #             if node_id in nodes_coords
            #         ]

            #         # count way distance based on geometry
            #         points = [(p["lat"], p["lon"]) for p in geometry]

            #         distance = sum(geodesic(a, b).meters for a, b in zip(points, points[1:]))

            #         ways.append({
            #             "way_id": item["id"],
            #             "nodes": item.get("nodes", []),
            #             "coordinates": geometry,
            #             "distance": distance,
            #             "way_rating": 5,
            #         })

            # Zapis do JSON
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(ways, f, ensure_ascii=False, indent=2)
            print("✅ Loaded data to krakow_roads_formatted.json")

            # Przerwij, jeśli brak wygenerowanych dróg
            if not ways:
                print("⚠️ No ways/roads to insert to db.")
                return []

            # Bezpieczny zapis do bazy danych (własny try-except)
            try:
                db.execute(insert(Ways), ways)
                db.commit()
                print("✅ Ways saved to db!")
                return ways # Zwracamy po udanym pełnym procesie
            except Exception as db_error:
                print(f"🛑 DB save error: {db_error}")
                db.rollback()
                return ways # Zwracamy mimo błędu DB (bo pobieranie się udało)

        except Exception as e:
            # Ten blok łapie tylko błędy komunikacji z Overpass API
            print(f"⚠️ Data download Error from url: {url} , Error: {e}")
            continue

    print("❌ The data was not downloaded.")
    return []

app = FastAPI()

async def run_dev_mode():
    """Funkcja pomocnicza inicjalizująca klienta HTTP i uruchamiająca pobieranie."""
    # Ustawiamy timeout większy niż [timeout:200] z zapytania Overpass, 
    # aby uniknąć błędów httpx.ReadTimeout
    async with httpx.AsyncClient(timeout=210.0) as client:
        await fetch_krakow_roads(client)

def main():
    """Główny punkt wejścia dla skryptu CLI."""
    # Sprawdzamy, czy przekazano argument 'dev'
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        print("🚀 Uruchamianie w trybie dev: rozpoczęto pobieranie dróg...")
        # Uruchamiamy asynchroniczną funkcję w synchronicznym punkcie wejścia
        asyncio.run(run_dev_mode())
    else:
        print("Uruchomiono bez argumentu 'dev'. Pobieranie dróg zostało pominięte.")

# Ten warunek sprawia, że kod wykona się tylko przy bezpośrednim uruchomieniu pliku
if __name__ == "__main__":
    main()