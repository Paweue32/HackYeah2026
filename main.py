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
     engine.load_way_names()
     yield

app = FastAPI(lifespan=lifespan)
active_routes = TTLCache(maxsize=100000, ttl=2*60)

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
    count: int = 3  # how many suggestions to return, clamped to 1..MAX_ROUTES


class DiscardPayload(BaseModel):
    discarded_route_ids: list[str]

class RefreshPayload(BaseModel):
    prolonged_route_ids: list[str]

class FeedbackPayload(BaseModel):
    route_id: str
    grade: int

Coordinate.model_rebuild()
RoutePayload.model_rebuild()
DiscardPayload.model_rebuild()
RefreshPayload.model_rebuild()
FeedbackPayload.model_rebuild()


color_list = ["#FF0000", "#00FF00", "#0000FF", "#FF8C00", "#9333EA"]
MAX_ROUTES = len(color_list)

@app.post("/generate/", status_code=200)
def process_route_generation(payload: RoutePayload, response: Response):
     routes = []
     count = min(max(payload.count, 1), MAX_ROUTES)
     if payload.mode == "two_points" and payload.start and payload.destination:
             routes = engine.find_routes(payload.start.lng, payload.start.lat,
                                         payload.destination.lng, payload.destination.lat, count)
             if not routes:
                  response.status_code = status.HTTP_400_BAD_REQUEST
                  return {
                       "status": "failure",
                       "message": "No route between these points"
                  }
 
     elif payload.mode == "point_distance" and payload.point:
             # Round trips from the point that turn near the edge of a circle of radius `distance` around it
             routes = engine.find_loops_on_circle(payload.point.lng, payload.point.lat,
                                                  payload.distance or 3000, count)
             if not routes:
                  response.status_code = status.HTTP_400_BAD_REQUEST
                  return {
                       "status": "failure",
                       "message": "No route from this point"
                  }

     for i, route in enumerate(routes):
          route["properties"]["id"] = str(uuid.uuid4())
          route["properties"]["color"] = color_list[i % len(color_list)]

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
      for route_id in payload.prolonged_route_ids:
           if route_id in active_routes:
                active_routes[route_id] = active_routes[route_id]
           else:
               response.status_code = status.HTTP_400_BAD_REQUEST
               return {
                    "status": "failure",
                    "message": "The route ID is invalid. Perhaps it has timed out"
               }
      
      return {
           "status": "success"
      }
      

@app.get("/routes/{route_id}/names", status_code=200)
def process_route_names(route_id: str, response: Response):
      if route_id not in active_routes:
           response.status_code = status.HTTP_400_BAD_REQUEST
           return {
                "status": "failure",
                "message": "The route ID is invalid. Perhaps it has timed out"
           }

      return {
           "status": "success",
           "names": engine.route_names(active_routes[route_id])
      }

@app.post("/feedback/")
def process_route_feedback(payload: FeedbackPayload):
      if payload.route_id in active_routes:
           active_routes.pop(payload.route_id)
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