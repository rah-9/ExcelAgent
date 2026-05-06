"""
Pydantic data models for agent state, tasks, plans, and memory.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ── Enums ──────────────────────────────────────────────────
class InputType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    UNKNOWN = "unknown"

class ExecutionMode(str, Enum):
    DIRECT = "direct"
    UI = "ui"
    VISUAL = "visual"

class TaskType(str, Enum):
    CREATE_EXCEL = "create_excel"
    EDIT_EXCEL = "edit_excel"
    EXTRACT_AND_CREATE = "extract_and_create"
    FORMAT_EXCEL = "format_excel"
    UNKNOWN = "unknown"

class AgentPhase(str, Enum):
    PERCEIVE = "perceive"
    INTERPRET = "interpret"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    REFLECT = "reflect"
    DONE = "done"
    FAILED = "failed"
    ASK_USER = "ask_user"

class RetryAction(str, Enum):
    RETRY_ACTION = "retry_action"
    REPLAN = "replan"
    SWITCH_MODE = "switch_mode"
    ASK_USER = "ask_user"
    ABORT = "abort"
    FIX_FORMATTING = "fix_formatting"
    RE_INTERPRET = "re_interpret"

class ErrorClassification(str, Enum):
    UI_FAILURE = "ui_failure"
    DATA_ERROR = "data_error"
    FORMAT_ERROR = "format_error"
    SYSTEM_ERROR = "system_error"
    UNKNOWN = "unknown"

class KillSwitchState(str, Enum):
    ACTIVE = "active"
    SOFT_STOP = "soft_stop"
    HARD_STOP = "hard_stop"

# ── Step / Plan ────────────────────────────────────────────
class PlanStep(BaseModel):
    step_id: int
    intent: str
    target: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    execution_confidence: float = 1.0
    is_idempotent: bool = False

class Plan(BaseModel):
    plan_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    task_type: TaskType = TaskType.UNKNOWN
    steps: List[PlanStep] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.DIRECT
    planning_confidence: float = 1.0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    status: str = "created"


# ── Structured Task ────────────────────────────────────────
class StructuredTask(BaseModel):
    task: TaskType = TaskType.UNKNOWN
    description: str = ""
    columns: List[str] = Field(default_factory=list)
    data: List[List[Any]] = Field(default_factory=list)
    formatting: Dict[str, Any] = Field(default_factory=dict)
    output_filename: str = "output.xlsx"
    source: str = ""
    confidence: float = 0.0        # Interpretation confidence
    raw_text: str = ""


# ── Verification Result ────────────────────────────────────
class VerificationResult(BaseModel):
    passed: bool = False
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)
    score: float = 0.0
    verification_confidence: float = 0.0 # Vision or Direct validation confidence


# ── Agent State ────────────────────────────────────────────
class AgentState(BaseModel):
    phase: AgentPhase = AgentPhase.PERCEIVE
    input_path: Optional[str] = None
    input_type: InputType = InputType.UNKNOWN
    raw_text: str = ""
    structured_task: Optional[StructuredTask] = None
    plan: Optional[Plan] = None
    current_step_idx: int = 0
    execution_mode: ExecutionMode = ExecutionMode.DIRECT
    verification_result: Optional[VerificationResult] = None
    retry_count: int = 0
    max_retries: int = 3
    error_history: List[Dict[str, Any]] = Field(default_factory=list)
    output_path: Optional[str] = None
    user_input_requested: bool = False
    user_input_query: str = ""
    kill_switch: KillSwitchState = KillSwitchState.ACTIVE
    
    # Confidence Propagation
    interpretation_confidence: float = 1.0
    planning_confidence: float = 1.0
    execution_confidence_overall: float = 1.0
    verification_confidence: float = 1.0


# ── Memory Entry ───────────────────────────────────────────
class MemoryEntry(BaseModel):
    task_signature: str = ""
    task_type: TaskType = TaskType.UNKNOWN
    plan_summary: str = ""
    execution_mode_used: ExecutionMode = ExecutionMode.DIRECT
    success: bool = False
    patterns: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    similarity_key: str = ""
