import networkx as nx
import numpy as np
import sqlite3
import random
import math
import json
import os

EARTH_RADIUS_M = 6378137.0

# Ratings are on a 1-10 scale; cost of a segment = length * (MAX_GRADE - grade),
# so a 10-rated street costs 1 per meter and a 1-rated one costs 10 per meter.
MIN_GRADE = 1
MAX_RATED_GRADE = 10
MAX_GRADE = 11
DEFAULT_GRADE = 5.0  # unrated ways (ratings_count = 0)

# point_distance turning points must lie within this fraction of the radius from the circle's edge
CIRCLE_EDGE_BAND = 0.1
# point_distance round trips: number of turning points on the edge per loop, the fraction of its
# sector they spread over, and how much more an already walked edge costs in later legs
LOOP_TURNS = 3
LOOP_ARC = 0.6
LOOP_REUSE_PENALTY = 5.0
# two_points alternatives: an edge used by an earlier suggestion costs this much more for the next
# one, and a suggestion longer than ALT_MAX_STRETCH times the first is dropped as a pointless detour
ALT_REUSE_PENALTY = 2.0
ALT_MAX_STRETCH = 1.5

# OSM tags of the ways, downloaded by generate_ratings.py - the only place street names live
WAY_TAGS_PATH = os.path.join("cache", "ratings_way_tags.json")


def node_id(lon, lat):
    """Node key from exact coordinates - OSM ways that share a vertex share identical coords."""
    return f"{lat:.7f}_{lon:.7f}"


def haversine_m(lon1, lat1, lon2, lat2):
    """Great-circle distance in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def grade_of(rating):
    """Average rating from the DB clamped to the 1-10 scale (DEFAULT_GRADE when unrated)."""
    if rating is None:
        return DEFAULT_GRADE
    return min(max(float(rating), MIN_GRADE), MAX_RATED_GRADE)


def segment_cost(length, rating):
    return length * (MAX_GRADE - grade_of(rating))


class RoutingEngine:
    def __init__(self, db_path='hackathon_map.db'):
        self.db_path = db_path
        self.G = nx.Graph()  # creating undirected graph for pedestrians
        self.nodes_coords = {} # dictionary for quickly finding the nearest node
        self._node_ids = []
        self._node_lons = np.empty(0)
        self._node_lats = np.empty(0)
        self.way_names = {}  # way_id -> street name, only for named ways
        self.way_grades = {}  # way_id -> rating on the 1-10 scale (DEFAULT_GRADE when unrated)

    def load_way_names(self, tags_path=WAY_TAGS_PATH):
        """Reads street names from the OSM tags cache; without the cache every way stays unnamed."""
        if not os.path.exists(tags_path):
            print(f"No {tags_path} - run generate_ratings.py to get street names")
            return
        with open(tags_path) as f:
            tags = json.load(f)
        self.way_names = {int(way_id): t["name"] for way_id, t in tags.items() if t.get("name")}
        print(f"Street names loaded for {len(self.way_names)} ways")

    def route_names(self, way_ids):
        """Street names along the ways in walking order, each once; unnamed ways are skipped."""
        names = []
        for way_id in way_ids:
            name = self.way_names.get(way_id)
            if name and name not in names:
                names.append(name)
        return names

    def load_graph_from_db(self):
        """Loads data from the table into the NetworkX engine."""
        print("Loading graph from database...")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT way_id, way_rating, coordinates FROM ways")
        rows = cursor.fetchall()
        conn.close()

        edges = {}  # (u, v) -> edge attributes; bulk-inserted into the graph afterwards
        nodes_coords = {}
        self.way_grades = {way_id: grade_of(rating) for way_id, rating, _ in rows}

        for way_id, rating, geometry_str in rows:
            try:
                coords_list = json.loads(geometry_str) if isinstance(geometry_str, str) else geometry_str
                # {"lat": Y, "lon": X} -> [lon, lat]
                coords = [[round(p["lon"], 7), round(p["lat"], 7)] for p in coords_list]
            except Exception:
                continue

            if not coords or len(coords) < 2:
                continue

            # One noise draw per way, so a whole street is consistently "better" or "worse" in loops
            noise = random.uniform(0.9, 1.1)

            # Every vertex becomes a node. OSM ways cross and join each other at interior
            # vertices, so connecting only the first and last point leaves the graph in islands.
            for a, b in zip(coords, coords[1:]):
                u, v = node_id(*a), node_id(*b)
                if u == v:
                    continue

                length = haversine_m(a[0], a[1], b[0], b[1])
                cost = segment_cost(length, rating)
                key = (u, v) if u < v else (v, u)

                # Two ways can share a segment - keep the cheaper one
                if key in edges and edges[key]['cost'] <= cost:
                    continue

                edges[key] = {
                    'length': length,
                    'cost': cost,            # exact length * (MAX_GRADE - grade), used for A -> B
                    'weight': cost * noise,  # randomised, used for loops
                    'way_id': way_id,
                    'geometry': json.dumps([a, b]),
                }
                nodes_coords[u] = a
                nodes_coords[v] = b

        G = nx.Graph()
        G.add_edges_from((u, v, attrs) for (u, v), attrs in edges.items())

        # Keep only the largest connected component, so every snapped point is reachable
        if G.number_of_nodes() > 0:
            largest = max(nx.connected_components(G), key=len)
            G.remove_nodes_from([n for n in list(G.nodes) if n not in largest])
            nodes_coords = {n: nodes_coords[n] for n in G.nodes}

        self.G = G
        self.nodes_coords = nodes_coords
        self._node_ids = list(nodes_coords.keys())
        self._node_lons = np.array([c[0] for c in nodes_coords.values()])
        self._node_lats = np.array([c[1] for c in nodes_coords.values()])

        print(f"Graph loaded! Number of nodes: {self.G.number_of_nodes()}, edges: {self.G.number_of_edges()}")

    def find_nearest_node(self, lon, lat):
        """Finds the nearest node, taking into account the curvature of the Earth."""
        if not self._node_ids:
            return None

        # Correction factor for latitude (Kraków ~50 degrees)
        cos_lat = math.cos(math.radians(lat))

        # Corrected Pythagoras (local approximation), vectorised over all nodes
        dx = (self._node_lons - lon) * cos_lat
        dy = self._node_lats - lat
        return self._node_ids[int(np.argmin(dx * dx + dy * dy))]

    def _straight_line_m(self, u, v):
        (lon1, lat1), (lon2, lat2) = self.nodes_coords[u], self.nodes_coords[v]
        return haversine_m(lon1, lat1, lon2, lat2)

    def path_length(self, path):
        """Real walking length of a node path in meters."""
        return sum(self.G[u][v]['length'] for u, v in zip(path, path[1:]))

    def path_cost(self, path):
        """Sum of length * (MAX_GRADE - grade) over a node path."""
        return sum(self.G[u][v]['cost'] for u, v in zip(path, path[1:]))

    def path_way_ids(self, path):
        """Ordered OSM way ids the path walks along, without consecutive repeats."""
        way_ids = []
        for u, v in zip(path, path[1:]):
            way_id = self.G[u][v]['way_id']
            if not way_ids or way_ids[-1] != way_id:
                way_ids.append(way_id)
        return way_ids

    def path_coordinates(self, path):
        """[lon, lat] list for a node path (every node is a vertex, so no extra geometry needed)."""
        return [self.nodes_coords[n] for n in path]

    def best_road(self, path):
        """Highest-rated named street along a node path, or None if it has no named street.

        A street is all of its ways on the path, rated by their length-weighted average;
        ties go to the longer one. Its geometry is a MultiLineString - one line per
        stretch the path walks along it.
        """
        roads = {}  # name -> {"length", "graded" (sum of length * grade), "lines"}
        prev_name = None
        for u, v in zip(path, path[1:]):
            edge = self.G[u][v]
            name = self.way_names.get(edge['way_id'])
            if name is None:
                prev_name = None
                continue
            road = roads.setdefault(name, {"length": 0.0, "graded": 0.0, "lines": []})
            road["length"] += edge['length']
            road["graded"] += edge['length'] * self.way_grades.get(edge['way_id'], DEFAULT_GRADE)
            if name == prev_name:
                road["lines"][-1].append(self.nodes_coords[v])
            else:
                road["lines"].append([self.nodes_coords[u], self.nodes_coords[v]])
            prev_name = name

        if not roads:
            return None
        # Rounded, so float noise in the averages doesn't decide ties that should go to length
        name, road = max(roads.items(),
                         key=lambda r: (round(r[1]["graded"] / r[1]["length"], 6), r[1]["length"]))
        return {
            "name": name,
            "rating": round(road["graded"] / road["length"], 2),
            "length_m": round(road["length"], 1),
            "geometry": {"type": "MultiLineString", "coordinates": road["lines"]},
        }

    def lowest_cost_path(self, source, target, graph=None):
        """Node path minimising sum of length * (MAX_GRADE - grade).

        A* with straight-line distance as the heuristic: the cheapest possible segment
        costs length * (MAX_GRADE - MAX_RATED_GRADE) = length * 1 >= straight-line distance,
        so the heuristic never overestimates and the result is optimal.
        `graph` restricts the search to part of the network (default: all of it).
        """
        graph = self.G if graph is None else graph
        return nx.astar_path(graph, source, target, heuristic=self._straight_line_m, weight='cost')

    def shortest_path(self, source, target, graph=None):
        """Node path minimising pure walking length (for comparison)."""
        graph = self.G if graph is None else graph
        return nx.astar_path(graph, source, target, heuristic=self._straight_line_m, weight='length')

    def route_feature(self, path, shortest):
        """GeoJSON Feature of a lowest-cost node path, with the shortest one for comparison."""
        way_ids = self.path_way_ids(path)
        return {
            "type": "Feature",
            "properties": {
                "length_m": round(self.path_length(path), 1),
                "cost": round(self.path_cost(path), 1),
                "shortest_length_m": round(self.path_length(shortest), 1),
                "way_ids": way_ids,
                "names": self.route_names(way_ids),
                "best_road": self.best_road(path),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": self.path_coordinates(path),
            },
        }

    def find_routes(self, start_lon, start_lat, end_lon, end_lat, count=3):
        """Up to `count` different low-cost walks from A to B as GeoJSON Features, best first.

        The first is the lowest-cost path. Every later one is searched with the edges of the
        earlier suggestions ALT_REUSE_PENALTY times more expensive (compounding), so it
        prefers other streets where they are not much worse. Repeats and detours longer than
        ALT_MAX_STRETCH times the first route are dropped.
        """
        if self.G.number_of_nodes() == 0:
            self.load_graph_from_db()

        start_node = self.find_nearest_node(start_lon, start_lat)
        end_node = self.find_nearest_node(end_lon, end_lat)
        if start_node is None or end_node is None or start_node == end_node:
            return []

        try:
            shortest = self.shortest_path(start_node, end_node)
        except nx.NetworkXNoPath:
            return []

        penalty = {}  # edge (u, v) with u < v -> cost multiplier from earlier suggestions

        def weight(u, v, d):
            return d['cost'] * penalty.get((u, v) if u < v else (v, u), 1.0)

        paths = []
        max_length = None
        # A few extra attempts, since some come back as repeats or detours
        for _ in range(count * 2):
            if len(paths) == count:
                break
            # The penalty only raises costs, so the straight-line heuristic stays admissible
            path = nx.astar_path(self.G, start_node, end_node, heuristic=self._straight_line_m, weight=weight)
            for u, v in zip(path, path[1:]):
                key = (u, v) if u < v else (v, u)
                penalty[key] = penalty.get(key, 1.0) * ALT_REUSE_PENALTY
            if path in paths:
                continue
            length = self.path_length(path)
            if max_length is None:
                max_length = length * ALT_MAX_STRETCH
            elif length > max_length:
                continue
            paths.append(path)

        return [self.route_feature(path, shortest) for path in paths]

    def find_route(self, start_lon, start_lat, end_lon, end_lat):
        """Lowest-cost walk from A to B as a GeoJSON Feature, or None if there is none."""
        routes = self.find_routes(start_lon, start_lat, end_lon, end_lat, count=1)
        return routes[0] if routes else None

    def calculate_midpoint(self, lon, lat, distance_m, bearing_deg):
        """Calculates the midpoint of the path."""
        R = 6378137.0 
        lat_rad, lon_rad = math.radians(lat), math.radians(lon)
        bearing_rad = math.radians(bearing_deg)
        
        new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(distance_m/R) + 
                                math.cos(lat_rad) * math.sin(distance_m/R) * math.cos(bearing_rad))
        new_lon_rad = lon_rad + math.atan2(math.sin(bearing_rad) * math.sin(distance_m/R) * math.cos(lat_rad), 
                                           math.cos(distance_m/R) - math.sin(lat_rad) * math.sin(new_lat_rad))
        return math.degrees(new_lon_rad), math.degrees(new_lat_rad)

    def loop_feature(self, path, turning_points, center, radius_m):
        """GeoJSON Feature of a round trip, with its turning points and how close they get to the edge."""
        way_ids = self.path_way_ids(path)
        return {
            "type": "Feature",
            "properties": {
                "length_m": round(self.path_length(path), 1),
                "cost": round(self.path_cost(path), 1),
                "radius_m": radius_m,
                "turning_points": [self.nodes_coords[n] for n in turning_points],
                "turning_point_distances_m": [round(haversine_m(*center, *self.nodes_coords[n]), 1)
                                              for n in turning_points],
                "way_ids": way_ids,
                "names": self.route_names(way_ids),
                "best_road": self.best_road(path),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": self.path_coordinates(path),
            },
        }

    def loop_through(self, stops, graph=None):
        """Lowest-cost legs joining consecutive stops into one node path. Edges walked by an
        earlier leg cost LOOP_REUSE_PENALTY times more, so later legs avoid retracing them
        wherever there is another way. None if some leg has no path."""
        graph = self.G if graph is None else graph
        used = set()

        def weight(u, v, d):
            return d['cost'] * (LOOP_REUSE_PENALTY if (u, v) in used else 1)

        path = [stops[0]]
        for a, b in zip(stops, stops[1:]):
            try:
                # The penalty only raises costs, so the straight-line heuristic stays admissible
                leg = nx.astar_path(graph, a, b, heuristic=self._straight_line_m, weight=weight)
            except nx.NetworkXNoPath:
                return None
            for u, v in zip(leg, leg[1:]):
                used.add((u, v))
                used.add((v, u))
            path.extend(leg[1:])
        return path

    def find_loops_on_circle(self, lon, lat, radius_m, count=3):
        """Up to `count` round trips from a point that turn at the edge of a circle of radius_m
        around it, using only roads inside the circle.

        The circle is cut into `count` equal sectors from a random starting bearing (so every
        request suggests different directions). In each sector LOOP_TURNS turning points are
        picked on the circle's edge (no more than CIRCLE_EDGE_BAND of the radius short of it),
        spread evenly over the middle LOOP_ARC of the sector, and joined by loop_through:
        start -> T1 -> T2 -> T3 -> start - out to the edge, along it and back by another way.
        A sector whose reachable roads never get near the edge (a river, railway, ...) gives
        no loop.
        """
        if self.G.number_of_nodes() == 0:
            self.load_graph_from_db()

        start_node = self.find_nearest_node(lon, lat)
        if start_node is None:
            return []

        # Local metric projection around the centre: distance and bearing of every node
        cos_lat = math.cos(math.radians(lat))
        dx = np.radians(self._node_lons - lon) * cos_lat * EARTH_RADIUS_M
        dy = np.radians(self._node_lats - lat) * EARTH_RADIUS_M
        dist = np.hypot(dx, dy)
        bearing = np.degrees(np.arctan2(dx, dy)) % 360

        inside = np.flatnonzero(dist <= radius_m)
        circle = self.G.subgraph(self._node_ids[i] for i in inside)
        if start_node not in circle:
            return []
        reachable = nx.node_connected_component(circle, start_node)

        min_dist = radius_m * (1 - CIRCLE_EDGE_BAND)
        edge = np.array([i for i in inside if dist[i] >= min_dist 
                 and self._node_ids[i] in reachable 
                 and self.G.degree(self._node_ids[i]) >= 2],
                dtype=int)
        if edge.size == 0:
            return []

        step = 360.0 / count
        first = random.uniform(0, 360)
        arc = step * LOOP_ARC
        spacing = arc / max(LOOP_TURNS - 1, 1)

        loops = []
        for sector in range(count):
            # Sector `sector` covers [first + sector*step, first + (sector+1)*step)
            middle = first + (sector + 0.5) * step
            targets = [middle] if LOOP_TURNS == 1 else \
                [middle - arc / 2 + k * spacing for k in range(LOOP_TURNS)]
            turns = []
            for target in targets:
                # Each turning point within half the spacing of its target bearing, so they stay in order
                off = np.abs((bearing[edge] - target + 180) % 360 - 180)
                near = np.flatnonzero(off <= spacing / 2)
                if near.size == 0:
                    continue
                # Metres along the edge from the target bearing plus metres short of the edge
                score = np.radians(off[near]) * radius_m + (radius_m - dist[edge[near]])
                node = self._node_ids[edge[near[np.argmin(score)]]]
                if node not in turns:
                    turns.append(node)
            if not turns:
                continue
            path = self.loop_through([start_node, *turns, start_node])
            if path is not None:
                loops.append(self.loop_feature(path, turns, (lon, lat), radius_m))
        return loops

    def generate_loop(self, start_lon, start_lat, total_distance_m=3000):
        """Main algorithm for generating a loop."""
        if self.G.number_of_nodes() == 0:
            self.load_graph_from_db()

        # Changing the city network lengthens the path (so-called Detour Index in cities is ~1.3-1.4)
        # Thanks to this, the user will get a path actually close to e.g. 3000m walk.
        straight_line_dist = total_distance_m / 1.3 
        half_dist = straight_line_dist / 2.0
        
        random_bearing = random.uniform(0, 360) 
        mid_lon, mid_lat = self.calculate_midpoint(start_lon, start_lat, half_dist, random_bearing)

        start_node = self.find_nearest_node(start_lon, start_lat)
        mid_node = self.find_nearest_node(mid_lon, mid_lat)

        if not start_node or not mid_node:
            return None

        # 3. Path to the midpoint
        try:
            path_there = nx.shortest_path(self.G, source=start_node, target=mid_node, weight='weight')
        except nx.NetworkXNoPath:
            return None

        # 4. Penalties! 
        edges_to_restore = []
        for i in range(len(path_there) - 1):
            u, v = path_there[i], path_there[i+1]
            old_weight = self.G[u][v]['weight']
            self.G[u][v]['weight'] = old_weight * 100
            edges_to_restore.append((u, v, old_weight))

        # 5. Path back
        try:
            path_back = nx.shortest_path(self.G, source=mid_node, target=start_node, weight='weight')
        except nx.NetworkXNoPath:
            path_back = [mid_node, start_node]

        # 6. Cleaning (reversing the penalties)
        for u, v, old_weight in edges_to_restore:
            self.G[u][v]['weight'] = old_weight

        # 7. Correct building GeoJSON - avoiding zigzags!
        full_path_nodes = path_there + path_back[1:]
        geojson_coordinates = []
        
        for i in range(len(full_path_nodes) - 1):
            u, v = full_path_nodes[i], full_path_nodes[i+1]
            edge_geom = json.loads(self.G[u][v]['geometry'])
            
            # In the undirected graph, the path u->v could be saved as v->u.
            # If the first point of the geometry is not the node "u", we need to reverse it.
            if self.nodes_coords[u] != edge_geom[0]:
                edge_geom = edge_geom[::-1]
            
            # avoiding duplicate points at intersections
            if i > 0:
                edge_geom = edge_geom[1:] 
            geojson_coordinates.extend(edge_geom)

        return {
            "type": "LineString",
            "coordinates": geojson_coordinates
        }