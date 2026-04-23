import os
import shutil

# Fix for GitPython "Bad git executable" issue on Windows
if not shutil.which("git"):
    common_git_paths = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
    ]
    for path in common_git_paths:
        if os.path.exists(path):
            os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = path
            break

os.environ["GIT_PYTHON_REFRESH"] = "quiet"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router

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
