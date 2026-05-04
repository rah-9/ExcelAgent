"""
Reflection Module — Analyzes failures and decides recovery actions using a Decision Tree.
"""

from core.logger import AgentLogger
from core.state_manager import EventBus
from models.data_models import AgentState, RetryAction, AgentPhase, ErrorClassification


class ReflectionModule:
    """Analyzes failures and decides the next best action using explicit Error Classification."""

    def __init__(self, config: dict, logger: AgentLogger, event_bus: EventBus = None):
        self.config = config
        self.logger = logger
        self.event_bus = event_bus

    def classify_error(self, error_msg: str) -> ErrorClassification:
        error_lower = error_msg.lower()
        if any(term in error_lower for term in ["ui", "pyautogui", "action guard", "screen mismatch", "not active", "not open"]):
            return ErrorClassification.UI_FAILURE
        if any(term in error_lower for term in ["data mismatch", "missing row", "missing column", "empty"]):
            return ErrorClassification.DATA_ERROR
        if any(term in error_lower for term in ["format issue", "alignment", "bold", "color"]):
            return ErrorClassification.FORMAT_ERROR
        if any(term in error_lower for term in ["timeout", "hang", "freeze", "memory"]):
            return ErrorClassification.SYSTEM_ERROR
            
        return ErrorClassification.UNKNOWN

    def decide_action(self, state: AgentState, error_msg: str) -> RetryAction:
        self.logger.info(f"Reflecting on error: {error_msg}")
        
        error_type = self.classify_error(error_msg)
        self.logger.info(f"Classified error as: {error_type.value}")
        
        if self.event_bus:
            self.event_bus.publish("error_classified", {"error_type": error_type, "message": error_msg})

        # Phase-specific heuristics
        if state.phase == AgentPhase.VERIFY:
            if error_type == ErrorClassification.FORMAT_ERROR:
                self.logger.decision("Format mismatch detected", "Fix formatting only")
                return RetryAction.FIX_FORMATTING
            elif error_type == ErrorClassification.DATA_ERROR:
                self.logger.decision("Data missing or mismatched", "Re-interpret source data")
                return RetryAction.RE_INTERPRET
            else:
                self.logger.decision("Unknown verification failure", "Replan execution")
                return RetryAction.REPLAN

        if state.phase == AgentPhase.EXECUTE:
            if error_type == ErrorClassification.UI_FAILURE:
                self.logger.decision("UI execution failed or guarded", "Switch execution mode")
                return RetryAction.SWITCH_MODE
            elif "openpyxl" in error_msg.lower() or "direct execution" in error_msg.lower():
                self.logger.decision("Direct execution failed", "Switch execution mode")
                return RetryAction.SWITCH_MODE
            elif error_type == ErrorClassification.SYSTEM_ERROR or "timeout" in error_msg.lower() or "not found" in error_msg.lower():
                self.logger.decision("Transient/Timeout error detected", "Retry action")
                return RetryAction.RETRY_ACTION

        self.logger.decision("No specific rule matched", "Replan from scratch")
        return RetryAction.REPLAN
