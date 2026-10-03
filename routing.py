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

        # Assuming that the table 'edges' has these columns  (leaving for update)
        cursor.execute("SELECT start_node, end_node, length, rating, geometry FROM edges")
        
        for row in cursor.fetchall():
            u, v, length, rating, geometry_str = row
            
            # creating our custom weight inplace!


            #--------------------------------------------------------
            #or adding a stop node instead of noise

            # Szum (0.9 - 1.1) sprawia, że przy tym samym dystansie i ocenie algorytm czasem 
            # wybierze inną trasę, żeby nie zanudzić użytkownika.
            noise = random.uniform(0.9, 1.1)
            custom_weight = length * (6 - rating) * noise

            #--------------------------------------------------------

            # Adding edge to the NetworkX graph
            self.G.add_edge(u, v, 
                            weight=custom_weight, 
                            length=length, 
                            geometry=geometry_str)
            
            # Żeby szukać węzłów po kliknięciu na mapie, potrzebujemy ich współrzędnych.
            # Bierzemy pierwszy i ostatni punkt z JSONa z geometrią:
            try:
                coords = json.loads(geometry_str)
                if coords:
                    self.nodes_coords[u] = coords[0]       # [lon, lat]
                    self.nodes_coords[v] = coords[-1]      # [lon, lat]
            except:
                pass
                
        conn.close()
        print(f"Graf załadowany! Ilość skrzyżowań (węzłów): {self.G.number_of_nodes()}")

    def find_nearest_node(self, lon, lat):
        """Szuka najbliższego skrzyżowania dla klikniętego przez usera punktu na mapie."""
        nearest_node = None
        min_dist = float('inf')
        
        for node_id, coords in self.nodes_coords.items():
            node_lon, node_lat = coords[0], coords[1]
            # Prosty pitagoras (wystarczający na małe odległości w mieście)
            dist = (node_lon - lon)**2 + (node_lat - lat)**2
            if dist < min_dist:
                min_dist = dist
                nearest_node = node_id
                
        return nearest_node

    def calculate_midpoint(self, lon, lat, distance_m, bearing_deg):
        """Matematycznie wylicza punkt oddalony o pół dystansu spaceru."""
        R = 6378137.0 
        lat_rad, lon_rad = math.radians(lat), math.radians(lon)
        bearing_rad = math.radians(bearing_deg)
        
        new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(distance_m/R) + 
                                math.cos(lat_rad) * math.sin(distance_m/R) * math.cos(bearing_rad))
        new_lon_rad = lon_rad + math.atan2(math.sin(bearing_rad) * math.sin(distance_m/R) * math.cos(lat_rad), 
                                           math.cos(distance_m/R) - math.sin(lat_rad) * math.sin(new_lat_rad))
        return math.degrees(new_lon_rad), math.degrees(new_lat_rad)

    def generate_loop(self, start_lon, start_lat, total_distance_m=3000):
        """Główny algorytm wyznaczania Pętli z Karaniem Tras!"""
        if self.G.number_of_nodes() == 0:
            self.load_graph_from_db()

        # 1. Obliczamy gdzie jest półmetek
        half_dist = total_distance_m / 2.0
        random_bearing = random.uniform(0, 360) # Gdziekolwiek wokół startu
        mid_lon, mid_lat = self.calculate_midpoint(start_lon, start_lat, half_dist, random_bearing)

        # 2. Znajdujemy najbliższe skrzyżowania
        start_node = self.find_nearest_node(start_lon, start_lat)
        mid_node = self.find_nearest_node(mid_lon, mid_lat)

        if not start_node or not mid_node:
            return None

        # 3. Trasa TAM
        try:
            path_there = nx.shortest_path(self.G, start=start_node, target=mid_node, weight='weight')
        except nx.NetworkXNoPath:
            return None # Nie da się dojść

        # 4. Kary! Podnosimy sztucznie wagę użytych ulic, by nie wracać tą samą drogą
        edges_to_restore = []
        for i in range(len(path_there) - 1):
            u, v = path_there[i], path_there[i+1]
            old_weight = self.G[u][v]['weight']
            self.G[u][v]['weight'] = old_weight * 100 # gigantyczna kara
            edges_to_restore.append((u, v, old_weight))

        # 5. Trasa Z POWROTEM
        try:
            path_back = nx.shortest_path(self.G, start=mid_node, target=start_node, weight='weight')
        except nx.NetworkXNoPath:
            path_back = [mid_node, start_node] # Fallback jeśli to np. ślepa uliczka

        # 6. Sprzątanie - cofamy kary, żeby kolejny użytkownik miał czysty graf
        for u, v, old_weight in edges_to_restore:
            self.G[u][v]['weight'] = old_weight

        # 7. Budowanie GeoJSONa dla Frontendu (sklejamy małe jsony z krawędzi)
        full_path_nodes = path_there + path_back[1:]
        geojson_coordinates = []
        
        for i in range(len(full_path_nodes) - 1):
            u, v = full_path_nodes[i], full_path_nodes[i+1]
            edge_geom = json.loads(self.G[u][v]['geometry'])
            # unikamy duplikowania punktów na skrzyżowaniach
            if i > 0:
                edge_geom = edge_geom[1:] 
            geojson_coordinates.extend(edge_geom)

        return {
            "type": "LineString",
            "coordinates": geojson_coordinates
        }