from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Depends, Request, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any
import uuid
import time
from cachetools import TTLCache
import random

from routing import RoutingEngine


engine = RoutingEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
     # Graph is loaded once into RAM; every request is then only in-memory computation
     engine.load_graph_from_db()
     yield

app = FastAPI(lifespan=lifespan)
active_routes = TTLCache(maxsize=100, ttl=30*60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Coordinate(BaseModel):
    lat: float
    lng: float

class RoutePayload(BaseModel):
    mode: str
    start: Optional[Coordinate] = None
    destination: Optional[Coordinate] = None
    point: Optional[Coordinate] = None
    distance: Optional[float] = None


class DiscardPayload(BaseModel):
    discarded_route_ids: list[str]

class RefreshPayload(BaseModel):
    prolonged_route_id: str

class FeedbackPayload(BaseModel):
    route_id: str
    grade: int

Coordinate.model_rebuild()
RoutePayload.model_rebuild()
DiscardPayload.model_rebuild()
RefreshPayload.model_rebuild()
FeedbackPayload.model_rebuild()


color_list = ["#FF0000", "#00FF00", "#0000FF"]

@app.post("/generate/", status_code=200)
def process_route_generation(payload: RoutePayload, response: Response):
     routes = []
     if payload.mode == "two_points" and payload.start and payload.destination:
             route = engine.find_route(payload.start.lng, payload.start.lat,
                                       payload.destination.lng, payload.destination.lat)
             if route is None:
                  response.status_code = status.HTTP_400_BAD_REQUEST
                  return {
                       "status": "failure",
                       "message": "No route between these points"
                  }

             route["properties"]["id"] = str(uuid.uuid4())
             route["properties"]["color"] = random.choice(color_list)
             routes = [route]
 
     elif payload.mode == "point_distance" and payload.point:
             p_lat, p_lng = payload.point.lat, payload.point.lng
             distance_km = (payload.distance or 3000) / 1000.0
             offset = distance_km * 0.008
 
             # Route 1: Heading North-East

             coordinates = [
                  [p_lat, p_lng],
                  [p_lat + offset * 0.5, p_lng + offset * 0.3],
                  [p_lat + offset, p_lng + offset * 0.6]
             ]

             route1 = {
                  "type": "Feature",
                  "properties": {
                       "id": str(uuid.uuid4()),
                       "color": random.choice(color_list)
                  },
                  "geometry": {
                       "type": "LineString",
                       "coordinates": [[curr_lng, curr_lat] for [curr_lat, curr_lng] in coordinates]
                  }
             }
 
             # Route 2: Heading South-East

             coordinates = [
                  [p_lat, p_lng],
                  [p_lat - offset * 0.4, p_lng + offset * 0.5],
                  [p_lat - offset * 0.8, p_lng + offset * 0.8]
             ]

             route2 = {
                  "type": "Feature",
                  "properties": {
                       "id": str(uuid.uuid4()),
                       "color": random.choice(color_list)
                  },
                  "geometry": {
                       "type": "LineString",
                       "coordinates": [[curr_lng, curr_lat] for [curr_lat, curr_lng] in coordinates]
                  }
             }
 
             # Route 3: Heading West

             coordinates = [
                  [p_lat, p_lng],
                  [p_lat + offset * 0.2, p_lng - offset * 0.5],
                  [p_lat - offset * 0.3, p_lng - offset * 0.9]
             ]

             route3 = {
                  "type": "Feature",
                  "properties": {
                       "id": str(uuid.uuid4()),
                       "color": random.choice(color_list)
                  },
                  "geometry": {
                       "type": "LineString",
                       "coordinates": [[curr_lng, curr_lat] for [curr_lat, curr_lng] in coordinates]
                  }
             }
 
             routes = [route1, route2, route3]

     for route in routes:
          active_routes[route["properties"]["id"]] = route["properties"].get("way_ids", [1, 2, 3])
 
     return {
          "type": "FeatureCollection",
          "features": routes
     }

@app.post("/discard/", status_code=200)
def process_suggestion_discard(payload: DiscardPayload, response: Response):
      for route_id in payload.discarded_route_ids:
           if route_id not in active_routes:
                response.status_code = status.HTTP_400_BAD_REQUEST
                return {
                     "status": "failure",
                     "message": "At least one route ID is invalid"
                }
      for route_id in payload.discarded_route_ids:
           if route_id in active_routes:
                active_routes.pop(route_id)

      return {
           "status": "success"
      }

@app.post("/refresh/", status_code=200)
def process_refresh_path(payload: RefreshPayload, response: Response):
      if payload.prolonged_route_id in active_routes:
           active_routes[payload.prolonged_route_id] = active_routes[payload.prolonged_route_id]
           return {
                "status": "success"
           }

      response.status_code = status.HTTP_400_BAD_REQUEST
      return {
           "status": "failure",
           "message": "The route ID is invalid. Perhaps it has timed out"
      }

@app.post("/feedback/")
def process_route_feedback(payload: FeedbackPayload):
      return {
            "Place": "holder"
      }


# do celow testowych
@app.post("/seed/")
def process_seed():
     for i in range(10):
          active_routes[str(uuid.uuid4())] = [3, 4, 5]

@app.post("/lookup/")
def process_lookup():
     print(active_routes)