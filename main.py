from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from typing import Annotated

from routing import RoutingEngine

# 1. Initializing the engine globally.
# We do this outside the endpoint, so that the server loads the 72 thousand roads into RAM only once (at startup).
# Thanks to this, generating a route for a user will take a fraction of a second!
print("⏳ Running the engine and loading the graph...")
routing_engine = RoutingEngine(db_path='hackathon_map.db')
routing_engine.load_graph_from_db()

app = FastAPI()

@app.get("/map/")
async def generate_map_route(start_lon: float, start_lat: float, distance_m: int = 3000):
    """
    Endpoint for the frontend. Takes the longitude and latitude and the distance.
    Returns the route in GeoJSON format.
    """
    route = routing_engine.generate_loop(start_lon, start_lat, total_distance_m=distance_m)
    
    if not route or "error" in route:
        return {"status": "error", "message": "The route could not be generated. Change the starting point."}
        
    return {
        "status": "success",
        "route": route
    }

#if we want to download more districts (and the topology will change), we can use this endpoint
@app.post("/admin/reload-graph/")
async def reload_graph_endpoint():
    """Forces reloading the database of roads into RAM."""
    routing_engine.G.clear() # Clears the old graph in RAM
    routing_engine.nodes_coords.clear()
    routing_engine.load_graph_from_db() # Loads the new one from the database
    return {"status": "success", "message": "Graph updated!"}
