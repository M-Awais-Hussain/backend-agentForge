from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sse_starlette.sse import EventSourceResponse
from graph.langgraph_flow import process_code, process_code_streaming
from api.event_emitter import EventEmitter
import asyncio

router = APIRouter()


# ── Request / Response Models ──────────────────────────────────────────────

class CodeRequest(BaseModel):
    code: str
    language: str

class StreamRequest(BaseModel):
    code: str
    language: str
    agents: List[str] = []

class AgentResponse(BaseModel):
    intent: str
    refactored_code: str
    diff: str
    metrics: Dict[str, Any]


# ── Legacy REST Endpoints (backward compat) ────────────────────────────────

@router.post("/analyze", response_model=AgentResponse)
async def analyze_code(request: CodeRequest):
    try:
        result = process_code(request.code, request.language, mode="analyze")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refactor", response_model=AgentResponse)
async def refactor_code(request: CodeRequest):
    try:
        result = process_code(request.code, request.language, mode="refactor")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── SSE Streaming Endpoints ───────────────────────────────────────────────

@router.post("/stream")
async def stream_analysis(request: StreamRequest):
    """
    SSE endpoint for real-time code analysis and refactoring.
    Streams structured events as the LangGraph workflow executes.
    """
    emitter = EventEmitter()

    async def event_generator():
        # Start processing in background
        task = asyncio.create_task(
            process_code_streaming(
                code=request.code,
                language=request.language,
                agents=request.agents,
                emitter=emitter
            )
        )

        # Stream events from the emitter
        async for event_data in emitter.stream():
            yield {"data": event_data}

        # Ensure the task completes
        await task

    return EventSourceResponse(event_generator())
