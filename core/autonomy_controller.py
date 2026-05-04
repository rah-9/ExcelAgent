"""
Autonomy Controller — Orchestrates retry limits, threshold checks, and fallback mechanisms.
"""

from typing import Dict, Any
from core.logger import AgentLogger
from models.data_models import AgentState, AgentPhase


class AutonomyController:
    """Manages the autonomous execution limits and decision points."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        agent_config = config.get("agent", {})
        self.max_retries = agent_config.get("max_retries", 3)
        self.ask_user_threshold = agent_config.get("ask_user_threshold", 3)
        self.autonomy_level = agent_config.get("autonomy_level", "high")

    def should_retry(self, state: AgentState) -> bool:
        """Determine if the agent is allowed to retry an operation."""
        if self.autonomy_level == "low":
            self.logger.info("Autonomy is low: escalating to user immediately.")
            return False

        if state.retry_count < self.max_retries:
            self.logger.info(f"Retry allowed. Current retries: {state.retry_count}/{self.max_retries}")
            return True
        else:
            self.logger.warning(f"Max retries ({self.max_retries}) reached. Escalating to user.")
            return False

    def check_escalation(self, state: AgentState) -> AgentPhase:
        """Check if we need to escalate to the user."""
        if state.retry_count >= self.ask_user_threshold:
            state.user_input_requested = True
            state.user_input_query = "I have encountered repeated failures. Please provide guidance or abort."
            return AgentPhase.ASK_USER
        
        return AgentPhase.FAILED

    def handle_user_escalation(self, query: str, state: AgentState) -> Any:
        """Prompt the user for manual intervention."""
        self.logger.warning(f"ESCALATION: {query}")
        try:
            response = input("\n[USER INPUT REQUIRED] -> ")
        except (EOFError, KeyboardInterrupt):
            response = "abort"
            
        from models.data_models import RetryAction
        if "abort" in response.lower() or "stop" in response.lower() or "no" in response.lower():
            return RetryAction.ABORT
        return RetryAction.REPLAN

    def handle_user_input(self, state: AgentState, user_response: str) -> AgentPhase:
        """Process user feedback to resume or abort."""
        self.logger.info(f"User provided input: {user_response}")
        user_response = user_response.lower()

        if "abort" in user_response or "stop" in user_response:
            return AgentPhase.FAILED
        elif "retry" in user_response:
            state.retry_count = 0  # Reset retries on explicit user retry request
            return AgentPhase.PLAN # Replan based on what we have
        else:
            # Assume user gave instructions, try replanning with them
            state.retry_count = 0
            self.logger.info("Resuming execution based on user feedback.")
            return AgentPhase.PLAN
