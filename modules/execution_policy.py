"""
Execution Policy Engine — Confidence-aware routing for execution modes.
"""

from core.logger import AgentLogger
from models.data_models import AgentState, ExecutionMode, StructuredTask


class ExecutionPolicyEngine:
    """Decides the optimal execution mode dynamically based on state & confidence."""
    
    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger

    def determine_mode(self, state: AgentState) -> ExecutionMode:
        """
        Policy Rules:
        - Interpretation confidence < 0.5 -> Direct Mode (safer, less likely to break UI if data is weird)
        - Rows > 50 -> Direct Mode (performance)
        - Execution confidence dropped heavily -> Switch Mode
        """
        task = state.structured_task
        if not task:
            return state.execution_mode
            
        self.logger.info("Evaluating Execution Policy...")

        # Rule 1: Low interpretation confidence
        if state.interpretation_confidence < 0.5:
            self.logger.decision("Low interpretation confidence", "DIRECT mode to prevent UI hallucination")
            return ExecutionMode.DIRECT

        # Rule 2: Large dataset
        if len(task.data) > 50:
            self.logger.decision("Large dataset (>50 rows)", "DIRECT mode for performance")
            return ExecutionMode.DIRECT

        # Rule 3: Execution confidence drop handling
        if state.execution_confidence_overall < 0.6 and state.retry_count > 0:
            new_mode = ExecutionMode.UI if state.execution_mode == ExecutionMode.DIRECT else ExecutionMode.DIRECT
            self.logger.decision(f"Execution confidence dropped ({state.execution_confidence_overall})", f"Switching to {new_mode.value}")
            return new_mode

        # Default to configured default mode or current mode
        self.logger.decision("No override policies triggered", f"Keeping current mode ({state.execution_mode.value})")
        return state.execution_mode
