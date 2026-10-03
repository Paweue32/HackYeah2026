from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any


app = FastAPI()

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
    distanceKm: Optional[float] = None

Coordinate.model_rebuild()
RoutePayload.model_rebuild()

@app.post("/map/")
def process_map_route(payload: RoutePayload):
    print("Received payload:", payload)
    
    routes = []
    if payload.mode == "two_points" and payload.start and payload.destination:
            s_lat, s_lng = payload.start.lat, payload.start.lng
            d_lat, d_lng = payload.destination.lat, payload.destination.lng

            route1 = [
                {"lat": s_lat, "lng": s_lng},
                {"lat": (s_lat + d_lat) / 2, "lng": (s_lng + d_lng) / 2},
                {"lat": d_lat, "lng": d_lng}
            ]

            route2 = [
                {"lat": s_lat, "lng": s_lng},
                {"lat": s_lat + (d_lat - s_lat) * 0.3 + 0.006, "lng": s_lng + (d_lng - s_lng) * 0.3 - 0.006},
                {"lat": s_lat + (d_lat - s_lat) * 0.7 + 0.006, "lng": s_lng + (d_lng - s_lng) * 0.7 - 0.006},
                {"lat": d_lat, "lng": d_lng}
            ]

            route3 = [
                {"lat": s_lat, "lng": s_lng},
                {"lat": s_lat + (d_lat - s_lat) * 0.3 - 0.006, "lng": s_lng + (d_lng - s_lng) * 0.3 + 0.006},
                {"lat": s_lat + (d_lat - s_lat) * 0.7 - 0.006, "lng": s_lng + (d_lng - s_lng) * 0.7 + 0.006},
                {"lat": d_lat, "lng": d_lng}
            ]

            routes = [route1, route2, route3]

    elif payload.mode == "point_distance" and payload.point:
            p_lat, p_lng = payload.point.lat, payload.point.lng
            # Approx conversion: 1 km ~ 0.009 degrees latitude
            offset = (payload.distanceKm or 3) * 0.008

            # Route 1: Heading North-East
            route1 = [
                {"lat": p_lat, "lng": p_lng},
                {"lat": p_lat + offset * 0.5, "lng": p_lng + offset * 0.3},
                {"lat": p_lat + offset, "lng": p_lng + offset * 0.6}
            ]

            # Route 2: Heading South-East
            route2 = [
                {"lat": p_lat, "lng": p_lng},
                {"lat": p_lat - offset * 0.4, "lng": p_lng + offset * 0.5},
                {"lat": p_lat - offset * 0.8, "lng": p_lng + offset * 0.8}
            ]

            # Route 3: Heading West
            route3 = [
                {"lat": p_lat, "lng": p_lng},
                {"lat": p_lat + offset * 0.2, "lng": p_lng - offset * 0.5},
                {"lat": p_lat - offset * 0.3, "lng": p_lng - offset * 0.9}
            ]

            routes = [route1, route2, route3]

    return {
        "status": "success",
        "message": "3 test routes calculated",
        "routes": routes
    }
