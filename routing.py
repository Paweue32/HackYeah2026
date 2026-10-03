import networkx as nx
import sqlite3
import random
import math
import json

class RoutingEngine:
    def __init__(self, db_path='hackathon_map.db'):
        self.db_path = db_path
        self.G = nx.Graph()  # creating undirected graph for pedestrians
        self.nodes_coords = {} # dictionary for quickly finding the nearest node

    def load_graph_from_db(self):
        """Loads data from the table into the NetworkX engine."""
        print("Loading graph from database...")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Zaktualizowane zapytanie - dostosowane do tabeli kolegi (tabela nazywa się "ways", a nie "edges")
        cursor.execute("SELECT way_id, distance, way_rating, coordinates FROM ways")
        
        for row in cursor.fetchall():
            way_id, length, rating, geometry_str = row
            
            try:
                # Parsujemy JSON z tabeli
                coords_list = json.loads(geometry_str) if isinstance(geometry_str, str) else geometry_str
                
                # Konwertujemy format kolegi {"lat": Y, "lon": X} na naszą listę [lon, lat]
                coords = [[p["lon"], p["lat"]] for p in coords_list]
                
            except Exception as e:
                continue

            if not coords or len(coords) < 2:
                continue

            # Ustawiamy punkty początkowe i końcowe jako unikalne ID węzłów
            start_point = coords[0]
            end_point = coords[-1]

            u = f"{start_point[1]:.4f}_{start_point[0]:.4f}"
            v = f"{end_point[1]:.4f}_{end_point[0]:.4f}"

            if u == v:
                continue

            safe_rating = rating if rating is not None else 5 
            noise = random.uniform(0.9, 1.1)
            custom_weight = (length if length else 100) * (11 - safe_rating) * noise

            self.G.add_edge(u, v, 
                            weight=custom_weight, 
                            length=length, 
                            geometry=json.dumps(coords))
            
            self.nodes_coords[u] = coords[0]
            self.nodes_coords[v] = coords[-1]
                
        conn.close()
        print(f"Graph loaded! Number of nodes: {self.G.number_of_nodes()}")

    def find_nearest_node(self, lon, lat):
        """Finds the nearest node, taking into account the curvature of the Earth."""
        nearest_node = None
        min_dist = float('inf')
        
        # Correction factor for latitude (Kraków ~50 degrees)
        cos_lat = math.cos(math.radians(lat))
        
        for node_id, coords in self.nodes_coords.items():
            node_lon, node_lat = coords[0], coords[1]
            
            # Corrected Pythagoras (local approximation)
            dx = (node_lon - lon) * cos_lat
            dy = (node_lat - lat)
            dist = dx**2 + dy**2
            
            if dist < min_dist:
                min_dist = dist
                nearest_node = node_id
                
        return nearest_node

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