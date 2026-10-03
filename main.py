from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from typing import Annotated


app = FastAPI()

@app.get("/map/")
async def testing_call(start: str, dest: str) -> list:
    res : list[str] = []
    res.append(start)
    res.append(dest)
    return res

