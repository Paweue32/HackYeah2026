import osmnx as ox
import sqlite3
import random

def generate_mock_data():
    print("Downloading graph for selected area of Krakow (This may take a while)...")
    place = "Stare Miasto, Kraków, Poland" 
    
    try:
        G = ox.graph_from_place(place, network_type="walk")
    except Exception as e:
        print(f"Error downloading OSM data: {e}")
        return

    print("Graph downloaded! Extracting nodes...")
    nodes = []
    
    for node_id, data in G.nodes(data=True):
        lat = data['y']
        lon = data['x']
        # creating unique IDs with rounded coordinates to 4 decimal places
        custom_node_id = f"{lat:.4f}_{lon:.4f}"
        
        # generating random rating from 1 to 5
        rating = random.randint(1, 5)
        
        nodes.append((custom_node_id, lat, lon, rating, 1, rating))

    print(f"Extracted {len(nodes)} nodes. Saving to SQLite database...")

    # Saving to SQLite database
    conn = sqlite3.connect('hackathon_map.db')
    cursor = conn.cursor()

    cursor.executemany('''
        INSERT OR IGNORE INTO nodes (node_id, lat, lon, sum_ratings, ratings_count, avg_rating)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', nodes)

    conn.commit()
    conn.close()
    print("Done! Nodes in Krakow are ready.")

if __name__ == "__main__":
    generate_mock_data()