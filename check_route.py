"""Checks that an A -> B route is valid and really the lowest-cost one, without the frontend.

    uv run python check_route.py                                   # Rynek Główny -> Kazimierz
    uv run python check_route.py 50.0614 19.9383 50.0515 19.9445   # start_lat start_lon end_lat end_lon

Ratings come from the DB (fill them with generate_ratings.py). Writes route_check.geojson and
route_check.html - open it in a browser: blue = lowest cost, pink = shortest, and every way
around the route coloured by its rating (red 1 -> green 10, thin grey = unrated).
"""
import json
import math
import sqlite3
import sys

from routing import RoutingEngine, haversine_m, segment_cost

DB_PATH = "hackathon_map.db"
DEFAULT_POINTS = (50.0614, 19.9383, 50.0515, 19.9445)  # Rynek Główny -> Kazimierz
TOLERANCE = 1e-6


def db_ratings(db_path):
    conn = sqlite3.connect(db_path)
    ratings = dict(conn.execute("SELECT way_id, way_rating FROM ways"))
    conn.close()
    return ratings


def rated_ways_around(db_path, coords, margin_deg=0.004):
    """[[[lon, lat], ...], rating, ratings_count] for every way in the route's bounding box."""
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    west, east = min(lons) - margin_deg, max(lons) + margin_deg
    south, north = min(lats) - margin_deg, max(lats) + margin_deg
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT coordinates, way_rating, ratings_count FROM ways").fetchall()
    conn.close()
    ways = []
    for coords_json, rating, count in rows:
        line = [[round(p["lon"], 6), round(p["lat"], 6)] for p in json.loads(coords_json)]
        if any(west <= lon <= east and south <= lat <= north for lon, lat in line):
            ways.append([line, rating, count])
    return ways


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


def write_html(path, route, shortest_coords, start, end, rated_ways):
    data = json.dumps({
        "ways": rated_ways,
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
background:#fff;color:#222;padding:8px 12px;border-radius:6px;font:13px sans-serif;box-shadow:0 1px 4px #0004}}
.scale{{height:8px;margin-top:6px;background:linear-gradient(90deg,hsl(0,75%,45%),hsl(60,75%,45%),hsl(120,75%,35%))}}</style>
</head><body><div id="map"></div><div id="info"></div><script>
const d = {data};
const map = L.map('map', {{preferCanvas: true}});
// tile.openstreetmap.org ("usage policy") and CARTO ("API key required") both block pages opened
// from file:// (no Referer) -> Esri light grey canvas, which serves tiles without a key
const esri = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/';
L.tileLayer(esri + 'World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
  maxZoom: 16, maxNativeZoom: 16,
  attribution: 'Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors | routing data &copy; OpenStreetMap contributors (ODbL)'
}}).addTo(map);
L.tileLayer(esri + 'World_Light_Gray_Reference/MapServer/tile/{{z}}/{{y}}/{{x}}', {{maxZoom: 16, maxNativeZoom: 16}}).addTo(map);
const ll = c => c.map(([lon, lat]) => [lat, lon]);
// Every way around the route, red (1) -> green (10); unrated = thin grey
const ratings = L.layerGroup().addTo(map);
for (const [line, rating, count] of d.ways) {{
  const style = count > 0
    ? {{color: `hsl(${{(rating - 1) / 9 * 120}}, 75%, ${{rating > 7 ? 35 : 45}}%)`, weight: 3, opacity: 0.85}}
    : {{color: '#999', weight: 1.5, opacity: 0.6}};
  L.polyline(ll(line), style).addTo(ratings)
    .bindTooltip(count > 0 ? `rating ${{rating}} (${{count}} ratings)` : 'unrated (5.0)');
}}
// Both routes on their own panes above the ratings, each with a white casing so they never blend in.
// The shortest is drawn wider underneath, so where the two share a street both colours stay visible.
map.createPane('routes').style.zIndex = 450;
const route = (coords, color, width, tip) => L.layerGroup([
  L.polyline(ll(coords), {{pane: 'routes', color: '#fff', weight: width + 4, opacity: 1}}),
  L.polyline(ll(coords), {{pane: 'routes', color: color, weight: width, opacity: 1}}).bindTooltip(tip, {{sticky: true}}),
]).addTo(map);
const shortest = route(d.shortest, '#d81b60', 9, 'shortest: ' + d.props.shortest_length_m + ' m');
const comfy = route(d.route, '#1565c0', 4, 'lowest cost: ' + d.props.length_m + ' m');
L.control.layers(null, {{
  '<span style="color:#1565c0">■</span> lowest cost': comfy,
  '<span style="color:#d81b60">■</span> shortest': shortest,
  'ratings': ratings,
}}, {{collapsed: false, position: 'bottomleft'}}).addTo(map);
const r = L.featureGroup([L.polyline(ll(d.route)), L.polyline(ll(d.shortest))]);
L.marker(d.start).addTo(map).bindTooltip('A');
L.marker(d.end).addTo(map).bindTooltip('B');
map.fitBounds(r.getBounds(), {{padding: [30, 30]}});
document.getElementById('info').innerHTML =
  '<b style="color:#1565c0">lowest cost</b>: ' + d.props.length_m + ' m, cost ' + d.props.cost +
  '<br><b style="color:#d81b60">shortest</b>: ' + d.props.shortest_length_m + ' m<br>ways: ' + d.props.way_ids.length +
  '<div class="scale"></div><div style="display:flex;justify-content:space-between"><span>rating 1</span><span>10</span></div>';
</script></body></html>"""
    with open(path, "w") as f:
        f.write(html)


def main():
    args = sys.argv[1:]
    points = tuple(map(float, args)) if args else DEFAULT_POINTS
    if len(points) != 4:
        sys.exit(__doc__)
    start, end = points[:2], points[2:]

    engine = RoutingEngine(DB_PATH)
    engine.load_graph_from_db()
    result = check(engine, db_ratings(DB_PATH), start, end)

    route, shortest_coords, checks = result[:3]
    print(f"\nA = {start}, B = {end}")
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
    write_html("route_check.html", route, shortest_coords, start, end,
               rated_ways_around(DB_PATH, route["geometry"]["coordinates"] + shortest_coords))
    print("💾 route_check.geojson, route_check.html")

    if all(passed for _, passed in checks):
        print("\n✅ PASS")
    else:
        sys.exit("\n❌ FAIL")


if __name__ == "__main__":
    main()
