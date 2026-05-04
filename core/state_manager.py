"""
State Manager Module — Single Source of Truth & EventBus for the Agent.
"""

from typing import Callable, Dict, List, Any
from core.logger import AgentLogger
from models.data_models import AgentState


class EventBus:
    """Pub/Sub messaging system for decoupling modules."""
    def __init__(self, logger: AgentLogger):
        self.logger = logger
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        self.logger.debug(f"Subscribed to event: {event_type}")

    def publish(self, event_type: str, payload: Any = None):
        self.logger.debug(f"Event published: {event_type}")
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(payload)
                except Exception as e:
                    self.logger.error(f"Error in event subscriber for {event_type}: {e}")


class StateManager:
    """Single Source of Truth holding AgentState and reacting to events."""
    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.state = AgentState()
        self.event_bus = EventBus(logger)
        
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        # Allow modules to emit events that update the global state directly
        self.event_bus.subscribe("update_confidence", self._handle_confidence_update)
        self.event_bus.subscribe("kill_switch_triggered", self._handle_kill_switch)
        self.event_bus.subscribe("error_recorded", self._handle_error_recorded)
        self.event_bus.subscribe("phase_changed", self._handle_phase_changed)
        self.event_bus.subscribe("timeline_update", self._handle_timeline_update)

    def _handle_timeline_update(self, payload: dict):
        self.logger.update_timeline(
            step=payload.get("step", 0),
            intent=payload.get("intent", ""),
            status=payload.get("status", ""),
            mode=payload.get("mode", ""),
            error=payload.get("error", None)
        )

    def _handle_confidence_update(self, payload: dict):
        """Update confidence levels dynamically."""
        if "interpretation" in payload:
            self.state.interpretation_confidence = payload["interpretation"]
        if "planning" in payload:
            self.state.planning_confidence = payload["planning"]
        if "execution" in payload:
            self.state.execution_confidence_overall = payload["execution"]
        if "verification" in payload:
            self.state.verification_confidence = payload["verification"]

    def _handle_kill_switch(self, payload: dict):
        """Update kill switch state."""
        switch_state = payload.get("state")
        if switch_state:
            self.state.kill_switch = switch_state
            self.logger.warning(f"Kill Switch State Updated: {switch_state.value}")

    def _handle_error_recorded(self, payload: dict):
        """Record a newly emitted error."""
        self.state.error_history.append(payload)

    def _handle_phase_changed(self, payload: dict):
        """Update current agent phase."""
        phase = payload.get("phase")
        if phase:
            self.state.phase = phase
