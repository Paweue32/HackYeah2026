"""Fills ways.way_rating / ways.ratings_count with ratings that could have come from real walkers.

Every way gets a hidden "true" quality (1-10) from its OSM surroundings:
    + parks, gardens, forests, meadows around it       (up to +3.5)
    + river / water nearby (e.g. the Vistula boulevards) (up to +1.5)
    - running next to a busy primary/secondary road     (up to -2.0)
    - the busy road itself, fast or wide roads, tunnels
Then a number of walkers (more on popular, green, pedestrian ways; some ways nobody rated)
each give a noisy integer rating around that quality, and their average + count is stored.

    uv run python generate_ratings.py            # downloads OSM data once (cached in cache/), then rates
    uv run python generate_ratings.py --seed 7   # different simulated walkers, same OSM data

Needs network on the first run (Overpass API); later runs work offline from cache/.
Tag download is resumable: Ctrl+C and run again, finished tiles are kept.
"""
import argparse
import json
import os
import socket
import sqlite3
import time

import geopandas as gpd
import httpx
import numpy as np
import osmnx as ox
import pandas as pd
import shapely
import urllib3.util.connection

from routing import DEFAULT_GRADE, MAX_RATED_GRADE, MIN_GRADE

DB_PATH = "hackathon_map.db"
TAGS_CACHE = os.path.join("cache", "ratings_way_tags.json")
AREAS_CACHE = os.path.join("cache", "ratings_areas.gpkg")
METRIC_CRS = "EPSG:2180"  # Poland CS92, meters

OVERPASS_URLS = [
    "https://overpass.kumi.systems/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
    "https://overpass.private.coffee/api",
    "https://overpass-api.de/api",  # last: often unreachable over IPv4 (shows up as "[Errno -9]")
]
# Tag download tiles per side. Mirror proxies give up after ~60s (504), so a tile must be
# small enough for a busy server to answer well within that; the densest of 144 has ~3k ways
TAGS_GRID = 12
TAGS_ROUNDS = 4      # passes over all mirrors before giving up on a tile ...
TAGS_ROUND_PAUSE = 30  # ... with this many seconds of rest between them
# Fail fast on a dead mirror (connect), but give Overpass time to answer a big query (read)
TAGS_TIMEOUT = httpx.Timeout(180, connect=10)

GREEN_TAGS = {
    "leisure": ["park", "garden", "nature_reserve", "recreation_ground"],
    "landuse": ["forest", "grass", "meadow", "recreation_ground", "village_green"],
    "natural": ["wood", "scrub", "heath", "grassland"],
}
WATER_TAGS = {
    "natural": ["water"],
    "waterway": ["river", "riverbank", "canal"],
}

SAMPLE_STEP_M = 10   # each way is sampled every 10 m
GREEN_DIST_M = 15    # a sample "is in the park" when within 15 m of a green area
WATER_DIST_M = 60    # ... "is by the water" within 60 m of water
BUSY_DIST_M = 20     # ... "is next to traffic" within 20 m of a busy road

BUSY_HIGHWAYS = {"motorway", "trunk", "primary", "secondary",
                 "motorway_link", "trunk_link", "primary_link", "secondary_link"}
BASE_QUALITY = {
    "pedestrian": 7.0, "living_street": 6.5, "path": 6.5, "footway": 6.0, "steps": 5.0,
    "residential": 5.0, "tertiary": 4.5, "tertiary_link": 4.0,
    "secondary": 3.5, "secondary_link": 3.0, "primary": 2.5, "primary_link": 2.0,
    "trunk": 1.5, "trunk_link": 1.5, "motorway": 1.0, "motorway_link": 1.0,
}
FOOTWAY_KIND_QUALITY = {"sidewalk": 4.5, "crossing": 4.5}  # footway=sidewalk is the edge of a road
RATING_NOISE = 1.3   # how much individual walkers disagree (std dev, in grade points)


# ---------- OSM data (downloaded once, cached) ----------

def force_ipv4():
    """Use IPv4 only. Without an IPv6 route, overpass-api.de (which resolves to IPv6 first)
    fails with "[Errno 101] Network is unreachable" instead of falling back to IPv4."""
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET  # requests / osmnx


def save_json(path, data):
    """Write via a temp file, so Ctrl+C mid-write never leaves a broken cache behind."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def fetch_way_tags(ways):
    """OSM tags of the given ways, from Overpass (cached in TAGS_CACHE, resumable).

    Asks for all highway tags in TAGS_GRID x TAGS_GRID bbox tiles instead of listing way ids:
    a handful of small, cheap queries that busy public mirrors answer in seconds. A tile is
    skipped when none of its ways is missing from the cache, which is what makes it resumable."""
    tags = {}
    if os.path.exists(TAGS_CACHE):
        with open(TAGS_CACHE) as f:
            tags = {int(k): v for k, v in json.load(f).items()}
    missing = ~ways.way_id.isin(list(tags)).to_numpy()
    if not missing.any():
        return tags

    # Each way belongs to the tile of its first point; the tile bbox query returns every way
    # that crosses it, so it covers its own ways (and some of the neighbours' as a bonus)
    west, south, east, north = ways.total_bounds
    first = shapely.get_point(ways.geometry.values, 0)
    col = np.minimum(((shapely.get_x(first) - west) / (east - west) * TAGS_GRID).astype(int), TAGS_GRID - 1)
    row = np.minimum(((shapely.get_y(first) - south) / (north - south) * TAGS_GRID).astype(int), TAGS_GRID - 1)
    tiles = sorted({(r, c) for r, c in zip(row[missing], col[missing])})
    step_x, step_y = (east - west) / TAGS_GRID, (north - south) / TAGS_GRID

    print(f"Downloading tags of {missing.sum()} ways in {len(tiles)} tiles from Overpass "
          f"({len(tags)} already cached)...")
    mirrors = list(OVERPASS_URLS)
    transport = httpx.HTTPTransport(local_address="0.0.0.0", retries=1)  # IPv4, see force_ipv4
    with httpx.Client(timeout=TAGS_TIMEOUT, transport=transport) as client:
        for done, (r, c) in enumerate(tiles, 1):
            s, w = south + r * step_y, west + c * step_x
            started = None
            query = f'[out:json][timeout:170];way["highway"]({s},{w},{s + step_y},{w + step_x});out tags;'
            for url in [m for _ in range(TAGS_ROUNDS) for m in mirrors]:
                if url == mirrors[0] and started is not None:
                    print(f"  all mirrors failed, retrying in {TAGS_ROUND_PAUSE}s")
                    time.sleep(TAGS_ROUND_PAUSE)
                started = time.monotonic()
                try:
                    response = client.post(f"{url}/interpreter", data={"data": query})
                    response.raise_for_status()
                    for el in response.json().get("elements", []):
                        tags[el["id"]] = el.get("tags", {})
                    # Next tile starts with the mirror that just worked
                    mirrors.remove(url)
                    mirrors.insert(0, url)
                    break
                except Exception as e:
                    print(f"  {url} failed after {time.monotonic() - started:.0f}s ({str(e).splitlines()[0]}), "
                          f"trying next mirror")
            else:
                raise RuntimeError("All Overpass mirrors failed - rerun later, finished tiles are kept")
            for way_id in ways.way_id[(row == r) & (col == c)]:
                tags.setdefault(int(way_id), {})  # deleted from OSM since the DB was built
            save_json(TAGS_CACHE, tags)  # after every tile, so Ctrl+C / a failure loses nothing
            print(f"  tile {done}/{len(tiles)} ({url.split('/')[2]}, {time.monotonic() - started:.0f}s)")
    return tags


def fetch_areas(bbox):
    """Green areas and water around Kraków as one GeoDataFrame with a `kind` column (cached)."""
    if os.path.exists(AREAS_CACHE):
        return gpd.read_file(AREAS_CACHE)

    frames = []
    for kind, tags in (("green", GREEN_TAGS), ("water", WATER_TAGS)):
        print(f"Downloading {kind} areas from Overpass...")
        for url in OVERPASS_URLS:
            print(f"  trying {url}")
            ox.settings.overpass_url = url
            ox.settings.requests_timeout = 300
            try:
                gdf = ox.features_from_bbox(bbox, tags=tags)
                break
            except Exception as e:
                print(f"  {url} failed ({e}), trying next mirror")
        else:
            raise RuntimeError("All Overpass mirrors failed")
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon", "LineString", "MultiLineString"])]
        frames.append(gpd.GeoDataFrame({"kind": kind}, geometry=gdf.geometry.values, crs=gdf.crs))

    areas = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    areas.to_file(AREAS_CACHE, driver="GPKG")
    return areas


# ---------- scoring ----------

def load_ways(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT way_id, coordinates FROM ways").fetchall()
    conn.close()
    ids, lines = [], []
    for way_id, coords_json in rows:
        coords = [(p["lon"], p["lat"]) for p in json.loads(coords_json)]
        if len(coords) >= 2:
            ids.append(way_id)
            lines.append(shapely.LineString(coords))
    return gpd.GeoDataFrame({"way_id": ids}, geometry=lines, crs="EPSG:4326")


def sample_points(lines):
    """Points every SAMPLE_STEP_M along each line; returns (points, index of their line)."""
    lengths = shapely.length(lines)
    counts = np.maximum(np.ceil(lengths / SAMPLE_STEP_M).astype(int), 1)
    owner = np.repeat(np.arange(len(lines)), counts)
    # Midpoint of each step: (k + 0.5) / count of the line length
    k = np.arange(len(owner)) - np.repeat(np.cumsum(counts) - counts, counts)
    fractions = (k + 0.5) / counts[owner]
    points = shapely.line_interpolate_point(lines[owner], fractions, normalized=True)
    return points, owner


def share_near(points, owner, n_lines, targets, distance_m):
    """For each line: fraction of its sample points within distance_m of any target geometry."""
    if len(targets) == 0:
        return np.zeros(n_lines)
    tree = shapely.STRtree(targets)
    point_idx, _ = tree.query(points, predicate="dwithin", distance=distance_m)
    near = np.zeros(len(points), dtype=bool)
    near[point_idx] = True
    return np.bincount(owner, weights=near, minlength=n_lines) / np.bincount(owner, minlength=n_lines)


def to_number(value):
    """'50', '50 mph', '2;3' -> first number as float, else None."""
    try:
        return float(str(value).split(";")[0].split()[0])
    except (ValueError, IndexError):
        return None


def base_quality(tags):
    highway = tags.get("highway", "")
    if highway == "footway" and tags.get("footway") in FOOTWAY_KIND_QUALITY:
        return FOOTWAY_KIND_QUALITY[tags["footway"]]
    return BASE_QUALITY.get(highway, 5.0)


def true_quality(tags, green, water, busy_near):
    """Hidden 1-10 quality of a way that the simulated walkers rate around."""
    q = base_quality(tags)
    q += 3.5 * green + 1.5 * water
    if tags.get("highway") not in BUSY_HIGHWAYS:
        q -= 2.0 * busy_near
    if (to_number(tags.get("maxspeed")) or 0) >= 60 or (to_number(tags.get("lanes")) or 0) >= 4:
        q -= 1.0
    if tags.get("tunnel") in ("yes", "building_passage"):
        q -= 1.0
    if tags.get("lit") == "yes":
        q += 0.3
    return float(np.clip(q, MIN_GRADE, MAX_RATED_GRADE))


def simulate_ratings(quality, popularity, rng):
    """(average, count) from a Poisson number of walkers, each rating quality + noise."""
    n = int(rng.poisson(popularity))
    if n == 0:
        return DEFAULT_GRADE, 0
    ratings = np.clip(np.rint(rng.normal(quality, RATING_NOISE, n)), MIN_GRADE, MAX_RATED_GRADE)
    return round(float(ratings.mean()), 2), n


def popularity(tags, length_m, green, water):
    """Expected number of ratings: pleasant, pedestrian and long ways get rated more often."""
    lam = 2.5 + 6.0 * green + 3.0 * water
    if tags.get("highway") in ("pedestrian", "living_street"):
        lam += 4.0
    return lam * min(1.0, 0.5 + length_m / 300)


def score_ways(ways, tags, areas):
    """Adds green / water / busy_near / quality columns to the ways GeoDataFrame (metric CRS)."""
    ways = ways.to_crs(METRIC_CRS)
    areas = areas.to_crs(METRIC_CRS)
    lines = ways.geometry.values
    points, owner = sample_points(lines)

    highway = np.array([tags.get(w, {}).get("highway", "") for w in ways.way_id])
    busy_lines = lines[np.isin(highway, list(BUSY_HIGHWAYS))]

    ways["green"] = share_near(points, owner, len(ways), areas[areas.kind == "green"].geometry.values, GREEN_DIST_M)
    ways["water"] = share_near(points, owner, len(ways), areas[areas.kind == "water"].geometry.values, WATER_DIST_M)
    ways["busy_near"] = share_near(points, owner, len(ways), busy_lines, BUSY_DIST_M)
    ways["length_m"] = shapely.length(lines)
    ways["quality"] = [true_quality(tags.get(w, {}), g, wa, b)
                       for w, g, wa, b in zip(ways.way_id, ways.green, ways.water, ways.busy_near)]
    return ways


def write_ratings(db_path, ways, tags, seed):
    rng = np.random.default_rng(seed)
    updates = []
    for w, q, length, g, wa in zip(ways.way_id, ways.quality, ways.length_m, ways.green, ways.water):
        avg, n = simulate_ratings(q, popularity(tags.get(w, {}), length, g, wa), rng)
        updates.append((avg, n, int(w)))

    conn = sqlite3.connect(db_path)
    conn.executemany("UPDATE ways SET way_rating = ?, ratings_count = ? WHERE way_id = ?", updates)
    conn.commit()
    conn.close()
    return updates


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from init_db import ensure_ways_rating_columns
    ensure_ways_rating_columns(args.db)
    force_ipv4()

    ways = load_ways(args.db)
    west, south, east, north = ways.total_bounds
    tags = fetch_way_tags(ways)
    areas = fetch_areas((west, south, east, north))
    print(f"{len(ways)} ways, {int((areas.kind == 'green').sum())} green areas, "
          f"{int((areas.kind == 'water').sum())} water features")

    ways = score_ways(ways, tags, areas)
    updates = write_ratings(args.db, ways, tags, args.seed)

    rated = [(avg, n) for avg, n, _ in updates if n > 0]
    avgs = np.array([a for a, _ in rated])
    print(f"Rated {len(rated)}/{len(updates)} ways with {sum(n for _, n in rated)} simulated ratings; "
          f"average grade {avgs.mean():.2f}, 10th-90th percentile {np.percentile(avgs, 10):.1f}-"
          f"{np.percentile(avgs, 90):.1f}")
    by_kind = {}
    for w, q in zip(ways.way_id, ways.quality):
        by_kind.setdefault(tags.get(w, {}).get("highway", "?"), []).append(q)
    for kind, qs in sorted(by_kind.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"  {kind:<14} {len(qs):>6} ways, mean quality {np.mean(qs):.2f}")


if __name__ == "__main__":
    main()
