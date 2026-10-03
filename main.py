from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from typing import Annotated
from database import database, models

# Tworzenie tabel w bazie SQLite przy uruchomieniu aplikacji
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

@app.get("/map/")
async def testing_call(start: str, dest: str) -> list:
    res : list[str] = []
    res.append(start)
    res.append(dest)
    return res

