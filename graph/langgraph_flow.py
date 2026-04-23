from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict, Any, Optional, List
from backend.agents.agent_nodes import (
    intent_node, analysis_node, refactor_node, validation_node, diff_node,
    generate_summary
)
from backend.api.event_emitter import EventEmitter
import tempfile
import os
import asyncio
import logging
from backend.services.ast_analyzer import analyze_complexity

logger = logging.getLogger(__name__)


# ── Graph State ────────────────────────────────────────────────────────────

class GraphState(TypedDict):
    original_code: str
    language: str
    intent: Optional[str]
    intent_category: Optional[str]
    refactored_code: Optional[str]
    diff: Optional[str]
    metrics: Optional[Dict[str, Any]]
    validation_passed: Optional[bool]
    iterations: Optional[int]
    active_agents: Optional[List[str]]
    emitter: Optional[Any]  # EventEmitter instance


# ── Conditional Edge ───────────────────────────────────────────────────────

def should_loop(state: GraphState):
    if state.get("validation_passed", False):
        return "diff"
    if state.get("iterations", 0) >= 3:
        return "diff"
    return "refactor"


# ── Graph Builder ──────────────────────────────────────────────────────────

def create_graph():
    """Create the standard LangGraph workflow."""
    workflow = StateGraph(GraphState)

    workflow.add_node("intent", intent_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("refactor", refactor_node)
    workflow.add_node("validation", validation_node)
    workflow.add_node("diff", diff_node)

    workflow.set_entry_point("analysis")
    workflow.add_edge("analysis", "intent")
    workflow.add_edge("intent", "refactor")
    workflow.add_edge("refactor", "validation")

    workflow.add_conditional_edges(
        "validation",
        should_loop,
        {
            "refactor": "refactor",
            "diff": "diff"
        }
    )

    workflow.add_edge("diff", END)

    return workflow.compile()


# ── Synchronous Processing (backward compat) ──────────────────────────────

def process_code(code: str, language: str, mode: str = "analyze") -> dict:
    graph = create_graph()
    initial_state = {
        "original_code": code,
        "language": language,
        "iterations": 0
    }

    # Run the graph
    app = graph.invoke(initial_state)

    return {
        "intent": app.get("intent", ""),
        "refactored_code": app.get("refactored_code", ""),
        "diff": app.get("diff", ""),
        "metrics": app.get("metrics", {})
    }


# ── Streaming Processing ──────────────────────────────────────────────────

async def process_code_streaming(
    code: str,
    language: str,
    agents: List[str],
    emitter: EventEmitter
):
    """
    Run the LangGraph workflow in a background thread while emitting events.
    The emitter's queue is read by the SSE endpoint.
    """
    try:
        graph = create_graph()
        initial_state = {
            "original_code": code,
            "language": language,
            "iterations": 0,
            "active_agents": agents,
            "emitter": emitter,
        }

        emitter.emit_log("system", f"Starting analysis pipeline with agents: {', '.join(agents) if agents else 'all'}")

        # Run the synchronous graph in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: graph.invoke(initial_state))

        # Generate summary
        emitter.emit_log("system", "Generating AI summary...")
        summary = await loop.run_in_executor(None, lambda: generate_summary(result))

        # Build final structured response
        metrics = result.get("metrics", {})
        final_result = {
            "summary": summary,
            "intent": result.get("intent", ""),
            "intent_category": result.get("intent_category", "General"),
            "complexity": {
                "time": metrics.get("time_complexity", "O(n)"),
                "cyclomatic": metrics.get("average_cyclomatic_complexity", 0),
            },
            "issues": metrics.get("issues", []),
            "refactored_code": result.get("refactored_code", ""),
            "diff": result.get("diff", ""),
            "security_score": metrics.get("security_score", 75),
            "metrics": {
                "nloc": metrics.get("nloc", 0),
                "token_count": metrics.get("token_count", 0),
                "average_cyclomatic_complexity": metrics.get("average_cyclomatic_complexity", 0),
                "functions": metrics.get("functions", []),
            },
            "logs": [{"message": l["message"], "step": l["step"], "timestamp": l["timestamp"]} for l in emitter.logs],
            "agent_trace": emitter.agent_trace,
        }

        emitter.emit_result(final_result)

    except Exception as e:
        logger.error(f"Streaming processing error: {e}")
        emitter.emit_error("system", f"Processing failed: {str(e)}")
        emitter.emit_result({"error": str(e)})

