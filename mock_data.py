import argparse
import random
import sqlite3

import httpx
import osmnx as ox

from init_db import DB_PATH, upsert_ways

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_ways(place):
    print(f"Geocoding '{place}'...")
    west, south, east, north = ox.geocode_to_gdf(place).total_bounds

    query = f"""
    [out:json][timeout:120];
    way["highway"]({south},{west},{north},{east});
    out geom tags;
    """
    print("Downloading ways from Overpass (This may take a while)...")
    response = httpx.post(
        OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": "HackYeah2026"},
        timeout=180,
    )
    response.raise_for_status()

    ways = []
    for element in response.json()["elements"]:
        if element["type"] != "way":
            continue
        tags = element.get("tags", {})
        ways.append({
            "id": element["id"],
            "name": tags.get("name"),
            "highway_type": tags.get("highway"),
            "surface": tags.get("surface"),
            "maxspeed": tags.get("maxspeed"),
            "nodes": element["nodes"],
            "geometry": element["geometry"],
            "tags": tags,
        })
    return ways


def add_random_ratings(conn):
    # generating random rating from 1 to 5 for ways that have no ratings yet
    ids = [row[0] for row in conn.execute("SELECT id FROM ways WHERE ratings_count = 0")]
    ratings = [(r, r, way_id) for way_id in ids for r in [random.randint(1, 5)]]
    conn.executemany('''
        UPDATE ways SET sum_ratings = ?, ratings_count = 1, avg_rating = ?
        WHERE id = ?
    ''', ratings)
    conn.commit()
    print(f"Added random ratings to {len(ratings)} ways.")


def main():
    parser = argparse.ArgumentParser(description="Download all OSM ways of a place into the database")
    parser.add_argument("place", nargs="?", default="Stare Miasto, Kraków, Poland")
    parser.add_argument("--random-ratings", action="store_true", help="give unrated ways a random 1-5 rating")
    args = parser.parse_args()

    try:
        ways = fetch_ways(args.place)
    except Exception as e:
        print(f"Error downloading OSM data: {e}")
        return

    print(f"Extracted {len(ways)} ways. Saving to SQLite database...")
    conn = sqlite3.connect(DB_PATH)
    upsert_ways(conn, ways)
    if args.random_ratings:
        add_random_ratings(conn)
    conn.close()
    print("Done! Ways are ready.")


if __name__ == "__main__":
    main()
