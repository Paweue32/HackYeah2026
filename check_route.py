"""Checks that an A -> B route is valid and really the lowest-cost one, without the frontend.

    uv run python check_route.py                                   # Rynek Główny -> Kazimierz
    uv run python check_route.py 50.0614 19.9383 50.0515 19.9445   # start_lat start_lon end_lat end_lon
    uv run python check_route.py --demo-ratings                    # random 1-10 ratings on a temp copy of the DB

Writes route_check.geojson and route_check.html (open in a browser: blue = lowest cost, grey = shortest).
"""
import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile

from routing import RoutingEngine, haversine_m, segment_cost

DEFAULT_POINTS = (50.0614, 19.9383, 50.0515, 19.9445)  # Rynek Główny -> Kazimierz
TOLERANCE = 1e-6


def db_ratings(db_path):
    conn = sqlite3.connect(db_path)
    ratings = dict(conn.execute("SELECT way_id, way_rating FROM ways"))
    conn.close()
    return ratings


def demo_db(db_path, tmp_dir):
    """Copy of the DB with random 1-10 ratings, so lowest-cost and shortest routes differ."""
    path = os.path.join(tmp_dir, "demo.db")
    shutil.copy(db_path, path)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE ways SET way_rating = abs(random()) % 10 + 1")
    conn.commit()
    conn.close()
    return path


def check(engine, ratings, start, end):
    """Returns (route feature, shortest-path coordinates, list of (check name, passed))."""
    s_lat, s_lon = start
    e_lat, e_lon = end
    route = engine.find_route(s_lon, s_lat, e_lon, e_lat)
    if route is None:
        return None, None, [("route found", False)], None, None

    s_node = engine.find_nearest_node(s_lon, s_lat)
    e_node = engine.find_nearest_node(e_lon, e_lat)
    path = engine.lowest_cost_path(s_node, e_node)
    shortest = engine.shortest_path(s_node, e_node)
    props = route["properties"]

    # Cost recomputed from scratch: geometry + way_rating read straight from the DB
    recomputed_cost = 0.0
    recomputed_length = 0.0
    for u, v in zip(path, path[1:]):
        (lon1, lat1), (lon2, lat2) = engine.nodes_coords[u], engine.nodes_coords[v]
        length = haversine_m(lon1, lat1, lon2, lat2)
        recomputed_length += length
        recomputed_cost += segment_cost(length, ratings[engine.G[u][v]['way_id']])

    shortest_cost = engine.path_cost(shortest)
    coords = route["geometry"]["coordinates"]
    snap_m = haversine_m(s_lon, s_lat, *coords[0]), haversine_m(e_lon, e_lat, *coords[-1])

    checks = [
        ("route found", True),
        ("every step is an edge of the graph", all(engine.G.has_edge(u, v) for u, v in zip(path, path[1:]))),
        ("starts at snapped A and ends at snapped B", path[0] == s_node and path[-1] == e_node),
        ("geometry matches the node path", coords == engine.path_coordinates(path)),
        ("no node visited twice", len(set(path)) == len(path)),
        ("cost = Σ length*(11-grade) from DB ratings", math.isclose(recomputed_cost, props["cost"], abs_tol=0.1)),
        ("length = Σ segment lengths", math.isclose(recomputed_length, props["length_m"], abs_tol=0.1)),
        ("cost <= cost of the shortest path", engine.path_cost(path) <= shortest_cost + TOLERANCE),
        ("length >= shortest length", props["length_m"] >= props["shortest_length_m"] - 0.1),
        ("A and B snapped within 300 m", max(snap_m) < 300),
    ]
    return route, engine.path_coordinates(shortest), checks, shortest_cost, snap_m


def write_html(path, route, shortest_coords, start, end):
    data = json.dumps({
        "route": route["geometry"]["coordinates"],
        "shortest": shortest_coords,
        "start": [start[0], start[1]],
        "end": [end[0], end[1]],
        "props": route["properties"],
    })
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Route check</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>html,body,#map{{height:100%;margin:0}}#info{{position:absolute;z-index:1000;top:10px;right:10px;
background:#fff;padding:8px 12px;border-radius:6px;font:13px sans-serif;box-shadow:0 1px 4px #0004}}</style>
</head><body><div id="map"></div><div id="info"></div><script>
const d = {data};
const map = L.map('map');
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{attribution: '&copy; OpenStreetMap contributors'}}).addTo(map);
const ll = c => c.map(([lon, lat]) => [lat, lon]);
L.polyline(ll(d.shortest), {{color: '#888', weight: 7, opacity: 0.6}}).addTo(map).bindTooltip('shortest');
const r = L.polyline(ll(d.route), {{color: '#1565c0', weight: 4}}).addTo(map).bindTooltip('lowest cost');
L.marker(d.start).addTo(map).bindTooltip('A');
L.marker(d.end).addTo(map).bindTooltip('B');
map.fitBounds(r.getBounds(), {{padding: [30, 30]}});
document.getElementById('info').innerHTML =
  '<b style="color:#1565c0">lowest cost</b>: ' + d.props.length_m + ' m, cost ' + d.props.cost +
  '<br><b style="color:#888">shortest</b>: ' + d.props.shortest_length_m + ' m<br>ways: ' + d.props.way_ids.length;
</script></body></html>"""
    with open(path, "w") as f:
        f.write(html)


def main():
    args = [a for a in sys.argv[1:] if a != "--demo-ratings"]
    demo = "--demo-ratings" in sys.argv
    points = tuple(map(float, args)) if args else DEFAULT_POINTS
    if len(points) != 4:
        sys.exit(__doc__)
    start, end = points[:2], points[2:]

    with tempfile.TemporaryDirectory() as tmp:
        db_path = demo_db("hackathon_map.db", tmp) if demo else "hackathon_map.db"
        engine = RoutingEngine(db_path)
        engine.load_graph_from_db()
        ratings = db_ratings(db_path)
        result = check(engine, ratings, start, end)

    route, shortest_coords, checks = result[:3]
    print(f"\nA = {start}, B = {end}{'  (demo ratings)' if demo else ''}")
    for name, passed in checks:
        print(f"  {'✅' if passed else '❌'} {name}")
    if route is None:
        sys.exit("\n❌ FAIL: no route")

    shortest_cost, snap_m = result[3:]
    p = route["properties"]
    print(f"\nlowest cost: {p['length_m']} m, cost {p['cost']}, {len(p['way_ids'])} ways")
    print(f"shortest:    {p['shortest_length_m']} m, cost {round(shortest_cost, 1)}")
    print(f"snap distance: A {snap_m[0]:.0f} m, B {snap_m[1]:.0f} m")

    with open("route_check.geojson", "w") as f:
        json.dump(route, f)
    write_html("route_check.html", route, shortest_coords, start, end)
    print("💾 route_check.geojson, route_check.html")

    if all(passed for _, passed in checks):
        print("\n✅ PASS")
    else:
        sys.exit("\n❌ FAIL")


if __name__ == "__main__":
    main()
