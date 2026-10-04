from routing import RoutingEngine
import json

print("--- Testing routing engine ---")

# 1. Initializing the engine (should start loading the graph from the database)
engine = RoutingEngine()
engine.load_graph_from_db()

# Coordinates of the center of Krakow (Main Market Square)
test_lon = 19.9383
test_lat = 50.0614
distance = 3000

print(f"\nGenerating the route: start=[{test_lon}, {test_lat}], distance={distance}m")

# 2. Generating the route
route = engine.generate_loop(test_lon, test_lat, total_distance_m=distance)

# 3. Displaying the results
if route and "coordinates" in route:
    print("\n✅ Success! The route has been generated.")
    print(f"Type of object: {route['type']}")
    print(f"Number of generated points of the route: {len(route['coordinates'])}")

    # Displaying the first 5 and last 5 coordinates, to not clutter the console
    print("First 5 points:")
    for p in route['coordinates'][:5]:
        print(f"  {p}")
    print("...")
    print("Last 5 points:")
    for p in route['coordinates'][-5:]:
        print(f"  {p}")

    # Optional: Saving the full route to a file to check in the browser (e.g. geojson.io)
    with open("test_route.geojson", "w") as f:
        json.dump(route, f)
    print("\n💾 Full GeoJSON saved to 'test_route.geojson'. You can upload it to geojson.io!")
else:
    print("\n❌ Error: The route could not be generated. Check the database or start coordinates.")