import os
import shutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(title="AgentForge — AI Developer Platform API")

# Configure CORS (with SSE support)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Cache-Control", "Connection"],
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AgentForge API is running", "version": "3.0.0"}
