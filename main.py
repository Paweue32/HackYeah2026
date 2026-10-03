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

class RoutePayload(BaseModel):
    mode: str
    start: Optional[Any] = None
    destination: Optional[Any] = None
    point: Optional[Any] = None
    distanceKm: Optional[float] = None

RoutePayload.model_rebuild()

@app.post("/map/")
def process_map_route(payload: RoutePayload):
    print("Received payload:", payload)
    
    if payload.mode == "two_points":
        return {
            "status": "success",
            "message": "Route calculated between points",
            "data": {"start": payload.start, "destination": payload.destination}
        }
    
    return {
        "status": "success",
        "message": "Distance calculated from point",
        "data": {"point": payload.point, "distanceKm": payload.distanceKm}
    }
