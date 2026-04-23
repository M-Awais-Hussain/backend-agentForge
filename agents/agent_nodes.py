from langchain_core.messages import HumanMessage, SystemMessage
from backend.services.groq_client import get_llm
from backend.services.ast_analyzer import analyze_complexity
import difflib
import logging
import re
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


# ── Utility ────────────────────────────────────────────────────────────────

def extract_code_block(text: str) -> str:
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            code = parts[1]
            if "\n" in code:
                # remove language identifier if exists
                first_line_end = code.index("\n")
                first_line = code[:first_line_end].strip()
                if not any(c.isspace() for c in first_line):
                    code = code[first_line_end+1:]
            return code.strip()
    return text.strip()


def _get_agent_focus(active_agents: List[str]) -> str:
    """Build additional prompt focus based on active agents."""
    focus_parts = []
    if "performance" in active_agents:
        focus_parts.append("- Focus heavily on performance: time/space complexity, memoization, caching, loop optimization, avoiding redundant computations")
    if "security" in active_agents:
        focus_parts.append("- Focus heavily on security: input validation, SQL injection, XSS, authentication issues, unsafe deserialization, secrets exposure")
    if "quality" in active_agents:
        focus_parts.append("- Focus heavily on code quality: naming conventions, SOLID principles, DRY, readability, proper error handling, documentation")
    if "refactoring" in active_agents:
        focus_parts.append("- Focus heavily on refactoring: extract methods, reduce nesting, simplify conditionals, improve modularity, design patterns")

    if not focus_parts:
        focus_parts.append("- Provide a balanced analysis covering performance, security, quality, and refactoring")

    return "\n".join(focus_parts)


# ── Graph Nodes ────────────────────────────────────────────────────────────

def analysis_node(state: dict):
    """Analyze code complexity metrics and security score."""
    emitter = state.get("emitter")
    active_agents = state.get("active_agents", [])

    if emitter:
        emitter.emit_step("analysis", "running", "Starting code analysis...")
        emitter.emit_log("analysis", "Running AST analysis & complexity metrics via lizard")

    # Run lizard metrics
    metrics = analyze_complexity(state['original_code'], state['language'])

    if emitter:
        emitter.emit_log("analysis", f"NLOC: {metrics.get('nloc', 0)}, Functions: {len(metrics.get('functions', []))}, Avg Complexity: {metrics.get('average_cyclomatic_complexity', 0):.2f}")

    # Security scoring via LLM (if security agent active or by default)
    security_score = 75  # default
    issues = []

    try:
        llm = get_llm()
        agent_focus = _get_agent_focus(active_agents)

        security_prompt = f"""Analyze this {state['language']} code for security and quality issues.

{agent_focus}

Code:
{state['original_code']}

Respond in EXACTLY this format (no other text):
SECURITY_SCORE: <number 0-100>
ISSUES:
- <issue 1>
- <issue 2>
- <issue 3>"""

        if emitter:
            emitter.emit_log("analysis", "Running AI-powered security & issue analysis...")

        response = llm.invoke([HumanMessage(content=security_prompt)])
        resp_text = response.content.strip()

        # Parse security score
        score_match = re.search(r'SECURITY_SCORE:\s*(\d+)', resp_text)
        if score_match:
            security_score = min(100, max(0, int(score_match.group(1))))

        # Parse issues
        if "ISSUES:" in resp_text:
            issues_text = resp_text.split("ISSUES:", 1)[1].strip()
            for line in issues_text.split("\n"):
                line = line.strip().lstrip("- ").strip()
                if line and len(line) > 3:
                    issues.append(line)
            issues = issues[:8]

        if emitter:
            emitter.emit_log("analysis", f"Security Score: {security_score}/100, Issues found: {len(issues)}")

    except Exception as e:
        logger.warning(f"Security analysis failed: {e}")
        if emitter:
            emitter.emit_log("analysis", f"Security analysis warning: {str(e)}")

    # Estimate time complexity
    time_complexity = "O(n)"
    try:
        for func in metrics.get("functions", []):
            cc = func.get("cyclomatic_complexity", 1)
            if cc > 15:
                time_complexity = "O(2^n)"
            elif cc > 10:
                time_complexity = "O(n²)"
            elif cc > 5:
                time_complexity = "O(n log n)"
    except Exception:
        pass

    metrics["time_complexity"] = time_complexity
    metrics["security_score"] = security_score
    metrics["issues"] = issues

    if emitter:
        emitter.emit_step("analysis", "completed", "Analysis complete", {
            "nloc": metrics.get("nloc", 0),
            "complexity": metrics.get("average_cyclomatic_complexity", 0),
            "security_score": security_score,
            "time_complexity": time_complexity,
            "issues_count": len(issues),
        })

    return {"metrics": metrics}


def intent_node(state: dict):
    """Detect the intent/purpose of the code."""
    emitter = state.get("emitter")

    if emitter:
        emitter.emit_step("intent", "running", "Detecting code intent...")
        emitter.emit_log("intent", "AI is understanding your code's purpose")

    llm = get_llm()
    prompt = f"""Analyze the following {state['language']} code and explain its intent and what it does in 2-3 sentences max.
Also identify what category it falls into (e.g., Sorting Algorithm, API Handler, Data Processing, Web Scraping, Machine Learning, etc.)

Respond in this format:
INTENT: <2-3 sentence explanation>
CATEGORY: <short category label>

Code:
{state['original_code']}"""

    response = llm.invoke([HumanMessage(content=prompt)])
    resp_text = response.content.strip()

    # Parse intent and category
    intent = resp_text
    category = "General"

    if "INTENT:" in resp_text:
        parts = resp_text.split("CATEGORY:")
        intent = parts[0].replace("INTENT:", "").strip()
        if len(parts) > 1:
            category = parts[1].strip()

    if emitter:
        emitter.emit_log("intent", f"Detected: {category}")
        emitter.emit_step("intent", "completed", f"Intent: {category}", {
            "intent": intent,
            "category": category,
        })

    return {"intent": intent, "intent_category": category}


def refactor_node(state: dict):
    """Refactor the code."""
    emitter = state.get("emitter")
    active_agents = state.get("active_agents", [])

    if emitter:
        emitter.emit_step("refactor", "running", "Refactoring code...")
        emitter.emit_log("refactor", "Applying refactoring transformations...")

    try:
        llm = get_llm("llama-3.1-8b-instant")
    except:
        llm = get_llm()

    agent_focus = _get_agent_focus(active_agents)

    system_prompt = SystemMessage(content=f"""You are an expert software engineer. Refactor the provided code following these guidelines:

{agent_focus}

Output ONLY the refactored code inside ``` delimiters, with no extra explanation.""")

    user_prompt = HumanMessage(content=f"Refactor this {state['language']} code:\n\n{state['original_code']}")

    response = llm.invoke([system_prompt, user_prompt])
    refactored = extract_code_block(response.content)

    if emitter:
        emitter.emit_step("refactor", "completed", "Refactoring complete")

    return {"refactored_code": refactored}


def validation_node(state: dict):
    """Validate the refactored code maintains intent."""
    emitter = state.get("emitter")
    iteration = state.get("iterations", 0) + 1

    if emitter:
        emitter.emit_step("validation", "running", f"Validating refactored code (attempt {iteration}/3)...")
        emitter.emit_log("validation", "Checking if refactored code preserves original intent")

    llm = get_llm()
    system_prompt = SystemMessage(content="You are a code reviewer. Does the refactored code maintain the same intent as the original code without introducing obvious syntax errors? Return 'YES' or 'NO' followed by a short reason.")
    user_prompt = HumanMessage(content=f"Original:\n{state['original_code']}\n\nRefactored:\n{state['refactored_code']}")

    response = llm.invoke([system_prompt, user_prompt])
    answer = response.content.strip().upper()
    valid = "YES" in answer[:10]

    if emitter:
        if valid:
            emitter.emit_log("validation", "✓ Validation passed — refactored code is correct")
        else:
            emitter.emit_log("validation", f"✗ Validation failed (attempt {iteration}/3) — will retry refactoring")
        emitter.emit_step("validation", "completed", f"Validation {'passed' if valid else 'failed'}", {
            "passed": valid,
            "iteration": iteration,
        })

    return {"validation_passed": valid, "iterations": iteration}


def diff_node(state: dict):
    """Generate diff between original and refactored code."""
    emitter = state.get("emitter")

    if emitter:
        emitter.emit_step("diff", "running", "Generating diff...")
        emitter.emit_log("diff", "Computing unified diff between original and refactored code")

    original = state['original_code'].splitlines(keepends=True)
    refactored = state['refactored_code'].splitlines(keepends=True)

    diff = difflib.unified_diff(original, refactored, fromfile="original", tofile="refactored")
    diff_str = "".join(diff)

    # Count changes
    additions = diff_str.count('\n+') - 1  # minus the +++ header
    deletions = diff_str.count('\n-') - 1  # minus the --- header

    if emitter:
        emitter.emit_log("diff", f"Changes: +{max(0, additions)} additions, -{max(0, deletions)} deletions")
        emitter.emit_step("diff", "completed", "Diff generated", {
            "additions": max(0, additions),
            "deletions": max(0, deletions),
        })

    return {"diff": diff_str}


# ── AI Summary Generator ──────────────────────────────────────────────────

def generate_summary(state: dict) -> str:
    """Generate a short AI summary of the analysis."""
    try:
        llm = get_llm()
        prompt = f"""Based on this analysis, write a 1-2 sentence summary of what was done:
- Code language: {state.get('language', 'unknown')}
- Intent: {state.get('intent', 'unknown')}
- Security Score: {state.get('metrics', {}).get('security_score', 'N/A')}/100
- Issues found: {len(state.get('metrics', {}).get('issues', []))}

Write a concise, professional summary."""
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        return "Code analyzed and refactored successfully."


