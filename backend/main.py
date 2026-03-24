import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from backend.config import get_settings
from backend.models import (
    ResearchSession,
    AgentEvent,
    SubmitResponse,
    SessionSummary,
    FeedbackRequest,
)
from backend.orchestrator import run_pipeline, run_feedback


# In-memory stores
sessions: Dict[str, ResearchSession] = {}
event_queues: Dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    yield


app = FastAPI(
    title="MARS — Multi-Agent Research System",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/submit", response_model=SubmitResponse)
async def submit_research(
    research_question: str = Form(...),
    literature_files: list[UploadFile] = File(default=[]),
    data_files: list[UploadFile] = File(default=[]),
):
    """Submit a new research question with optional literature and data files."""
    settings = get_settings()

    total_files = len(literature_files) + len(data_files)
    if total_files > settings.MAX_FILES:
        raise HTTPException(400, f"Too many files. Maximum is {settings.MAX_FILES}.")

    session = ResearchSession(research_question=research_question)
    session_dir = os.path.join("data", session.session_id)

    lit_paths = []
    data_paths = []

    for f in literature_files:
        if f.filename:
            file_path = os.path.join(session_dir, f.filename)
            os.makedirs(session_dir, exist_ok=True)
            content = await f.read()
            with open(file_path, "wb") as fh:
                fh.write(content)
            lit_paths.append(file_path)

    for f in data_files:
        if f.filename:
            file_path = os.path.join(session_dir, f.filename)
            os.makedirs(session_dir, exist_ok=True)
            content = await f.read()
            with open(file_path, "wb") as fh:
                fh.write(content)
            data_paths.append(file_path)

    session.literature_files = lit_paths
    session.data_files = data_paths

    sessions[session.session_id] = session
    event_queues[session.session_id] = asyncio.Queue()

    asyncio.create_task(run_pipeline(session, event_queues[session.session_id]))

    return SubmitResponse(session_id=session.session_id)


@app.get("/api/status/{session_id}")
async def stream_status(session_id: str):
    """Stream agent status updates via Server-Sent Events."""
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    queue = event_queues.get(session_id)
    if not queue:
        raise HTTPException(404, "No event queue for session")

    async def event_generator():
        while True:
            try:
                event: AgentEvent = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {"event": "message", "data": event.model_dump_json()}
                if event.type == "report_ready":
                    break
                if event.type == "error" and event.agent == "pipeline":
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}

    return EventSourceResponse(event_generator())


@app.get("/api/state/{session_id}")
async def get_session_state(session_id: str):
    """Get current session state (non-streaming fallback)."""
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    return {
        "session_id": session.session_id,
        "status": session.status,
        "research_question": session.research_question,
        "agents": {
            name: {
                "status": result.status,
                "has_output": result.output is not None,
                "revision_count": result.revision_count,
            }
            for name, result in session.agent_results.items()
        },
    }


@app.get("/api/report/{session_id}")
async def get_report(session_id: str):
    """Get the full report for a completed session."""
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    if session.status != "complete":
        raise HTTPException(400, f"Session is not complete. Current status: {session.status}")

    # Use Output agent result as the primary report, fall back to synthesis
    output_result = session.agent_results.get("output")
    primary_report = (output_result.output if output_result and output_result.output else session.synthesis)

    return {
        "session_id": session.session_id,
        "research_question": session.research_question,
        "synthesis": primary_report,
        "agents": {
            name: {
                "status": result.status,
                "output": result.output,
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "revision_count": result.revision_count,
            }
            for name, result in session.agent_results.items()
        },
    }


@app.get("/api/report/{session_id}/export")
async def export_report(session_id: str):
    """Download the report as a markdown file."""
    report_path = os.path.join("reports", session_id, "report.md")
    if not os.path.exists(report_path):
        raise HTTPException(404, "Report not found")
    return FileResponse(report_path, filename=f"mars-report-{session_id[:8]}.md")


@app.get("/api/plots/{session_id}/{filename}")
async def get_plot(session_id: str, filename: str):
    """Serve a generated plot image."""
    plot_path = os.path.join("reports", session_id, "plots", filename)
    if not os.path.exists(plot_path):
        raise HTTPException(404, "Plot not found")
    return FileResponse(plot_path, media_type="image/png")


@app.get("/api/sessions")
async def list_sessions():
    """List all past sessions."""
    return [
        SessionSummary(
            session_id=s.session_id,
            research_question=s.research_question,
            status=s.status,
            created_at=s.created_at,
        )
        for s in sorted(sessions.values(), key=lambda x: x.created_at, reverse=True)
    ]


@app.post("/api/feedback/{session_id}")
async def submit_feedback(session_id: str, request: FeedbackRequest):
    """Submit feedback for an agent. Re-runs the agent and cascades downstream."""
    if session_id not in sessions:
        raise HTTPException(404, "Session not found")

    session = sessions[session_id]
    if session.status != "complete":
        raise HTTPException(400, "Session must be complete before providing feedback")

    valid_agents = list(session.agent_results.keys())
    if request.agent not in valid_agents:
        raise HTTPException(400, f"Invalid agent. Choose from: {valid_agents}")

    # Create a fresh event queue for the feedback run
    event_queues[session_id] = asyncio.Queue()
    session.status = "running"

    asyncio.create_task(run_feedback(session, request.agent, request.feedback, event_queues[session_id]))

    return {"status": "revising", "agent": request.agent}
