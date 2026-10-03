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
import json

app = FastAPI()
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
engine = RoutingEngine()
engine.load_graph_from_db()

@app.post("/generate/", status_code=200)
def process_route_generation(payload: RoutePayload, response: Response):
     routes = []
     if payload.mode == "two_points" and payload.start and payload.destination:
             s_lat, s_lng = payload.start.lat, payload.start.lng
             d_lat, d_lng = payload.destination.lat, payload.destination.lng

             coordinates = [
                  [s_lat, s_lng],
                  [(s_lat + d_lat)/2, (s_lng + d_lng)/2],
                  [d_lat, d_lng]
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

             coordinates = [
                  [s_lat, s_lng],
                  [s_lat + (d_lat - s_lat) * 0.3 + 0.006, s_lng + (d_lng - s_lng) * 0.3 - 0.006],
                  [s_lat + (d_lat - s_lat) * 0.7 + 0.006, s_lng + (d_lng - s_lng) * 0.7 - 0.006],
                  [d_lat, d_lng]
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

             coordinates = [
                  [s_lat, s_lng],
                  [s_lat + (d_lat - s_lat) * 0.3 - 0.006, s_lng + (d_lng - s_lng) * 0.3 + 0.006],
                  [s_lat + (d_lat - s_lat) * 0.7 - 0.006, s_lng + (d_lng - s_lng) * 0.7 + 0.006],
                  [d_lat, d_lng]
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
 
     elif payload.mode == "point_distance" and payload.point:
          p_lat, p_lng = payload.point.lat, payload.point.lng

          routes = [
               {
                    "type": "Feature",
                    "properties": {
                         "id": str(uuid.uuid4()),
                         "color": random.choice(color_list)
                    },
                    "geometry": engine.generate_loop(p_lng, p_lat, total_distance_m=payload.distance)
               }
               for _ in range(0, 3)
          ]

     for route in routes:
          active_routes[route["properties"]["id"]] = [1, 2, 3]
 
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