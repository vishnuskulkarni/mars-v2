from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal
from datetime import datetime
import uuid


class FeedbackEntry(BaseModel):
    feedback: str
    timestamp: datetime = Field(default_factory=datetime.now)
    previous_output: str
    revised_output: str = ""


class AgentResult(BaseModel):
    agent_name: str
    status: Literal["pending", "running", "complete", "error"] = "pending"
    output: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    revision_count: int = 0


class ResearchSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_question: str
    literature_files: List[str] = []
    data_files: List[str] = []
    status: Literal["pending", "running", "complete", "error"] = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    agent_results: Dict[str, AgentResult] = {}
    synthesis: Optional[str] = None
    feedback_history: Dict[str, List[FeedbackEntry]] = {}


class AgentEvent(BaseModel):
    agent: str = ""
    type: Literal["status", "chunk", "complete", "error", "report_ready"] = "status"
    content: Optional[str] = None
    progress: Optional[int] = None
    session_id: Optional[str] = None


class SubmitRequest(BaseModel):
    research_question: str


class SubmitResponse(BaseModel):
    session_id: str


class SessionSummary(BaseModel):
    session_id: str
    research_question: str
    status: str
    created_at: datetime


class FeedbackRequest(BaseModel):
    agent: str
    feedback: str
