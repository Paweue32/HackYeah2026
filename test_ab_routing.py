"""Checks of the A -> B lowest-cost routing on a tiny hand-made map (no OSM data needed).

    uv run python test_ab_routing.py
"""
import json
import os
import sqlite3
import tempfile

from init_db import ensure_ways_rating_columns
from routing import RoutingEngine, MAX_GRADE

# A ---------- short way ---------- B
#  \                               /
#   ------ M (long way) ----------
#          |
#          C   (spur that touches the long way only at its interior vertex M)
A = (19.90, 50.000)
B = (19.92, 50.000)
M = (19.91, 50.004)
C = (19.91, 50.008)

SHORT_WAY, LONG_WAY, SPUR_WAY = 1, 2, 3


def coords(*points):
    return json.dumps([{"lat": lat, "lon": lon} for lon, lat in points])


def make_db(path, short_rating, long_rating):
    conn = sqlite3.connect(path)
    # Table as created by database_setup.py - without ratings_count, so the migration has work to do
    conn.execute("CREATE TABLE ways (way_id INTEGER NOT NULL, nodes JSON, coordinates JSON, "
                 "distance INTEGER, way_rating FLOAT, PRIMARY KEY (way_id))")
    conn.executemany("INSERT INTO ways (way_id, coordinates, way_rating) VALUES (?, ?, ?)", [
        (SHORT_WAY, coords(A, B), short_rating),
        (LONG_WAY, coords(A, M, B), long_rating),
        (SPUR_WAY, coords(M, C), None),
    ])
    conn.commit()
    conn.close()


def route(db_path, start, end):
    engine = RoutingEngine(db_path)
    engine.load_graph_from_db()
    return engine, engine.find_route(*start, *end)


with tempfile.TemporaryDirectory() as tmp:
    print("--- Migration adds ratings_count and is idempotent ---")
    db = os.path.join(tmp, "migrate.db")
    make_db(db, 1, 10)
    ensure_ways_rating_columns(db)
    ensure_ways_rating_columns(db)
    conn = sqlite3.connect(db)
    columns = [r[1] for r in conn.execute("PRAGMA table_info(ways)")]
    rows = conn.execute("SELECT way_id, way_rating, ratings_count FROM ways ORDER BY way_id").fetchall()
    conn.close()
    assert "ratings_count" in columns and "way_rating" in columns, columns
    assert rows == [(1, 1.0, 0), (2, 10.0, 0), (3, None, 0)], rows
    print("✅ ok")

    print("--- Well-rated detour beats a badly rated short way ---")
    engine, r = route(db, A, B)
    assert r is not None
    assert r["properties"]["way_ids"] == [LONG_WAY], r["properties"]
    assert r["properties"]["length_m"] > r["properties"]["shortest_length_m"], r["properties"]
    # Long way rated 10 -> cost = length * (11 - 10)
    assert abs(r["properties"]["cost"] - r["properties"]["length_m"] * (MAX_GRADE - 10)) < 1, r["properties"]
    assert r["geometry"]["coordinates"][0] == list(A) and r["geometry"]["coordinates"][-1] == list(B)
    print(f"✅ ok: {r['properties']}")

    print("--- Swapped ratings -> the short way wins ---")
    db2 = os.path.join(tmp, "swapped.db")
    make_db(db2, 10, 1)
    _, r = route(db2, A, B)
    assert r["properties"]["way_ids"] == [SHORT_WAY], r["properties"]
    assert r["properties"]["length_m"] == r["properties"]["shortest_length_m"], r["properties"]
    print(f"✅ ok: {r['properties']}")

    print("--- Ways joined at an interior vertex are connected (no islands) ---")
    _, r = route(db, A, C)
    assert r is not None, "spur M-C is not connected to the long way at M"
    assert r["properties"]["way_ids"][-1] == SPUR_WAY, r["properties"]
    assert list(M) in r["geometry"]["coordinates"]
    print(f"✅ ok: {r['properties']}")

    print("--- Same start and end -> no route ---")
    assert engine.find_route(*A, *A) is None
    print("✅ ok")

print("\nAll A -> B routing checks passed.")
