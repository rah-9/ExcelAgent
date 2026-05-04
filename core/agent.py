"""
Excel Automation Agent — Main execution loop and state machine.
"""

import signal
import sys
from typing import Optional, Any
from core.logger import AgentLogger
from core.autonomy_controller import AutonomyController
from core.state_manager import StateManager
from models.data_models import AgentState, AgentPhase, InputType, RetryAction, KillSwitchState
from modules.input_module import InputModule
from modules.perception_module import PerceptionModule
from modules.interpreter_module import InterpreterModule
from modules.planner_module import PlannerModule
from modules.executor_module import ExecutorModule
from modules.verifier_module import VerifierModule
from modules.reflection_module import ReflectionModule
from modules.memory_module import MemoryManager
from modules.execution_policy import ExecutionPolicyEngine

class ExcelAgent:
    """Core orchestrator for the autonomous Excel agent."""

    def __init__(self, config: dict):
        self.config = config
        self.logger = AgentLogger(config)
        
        self.state_manager = StateManager(config, self.logger)
        self.event_bus = self.state_manager.event_bus
        self.state = self.state_manager.state
        
        self.autonomy_controller = AutonomyController(config, self.logger)
        self.execution_policy = ExecutionPolicyEngine(config, self.logger)

        self.input_module = InputModule(config, self.logger)
        self.perception_module = PerceptionModule(config, self.logger)
        self.interpreter_module = InterpreterModule(config, self.logger)
        self.planner_module = PlannerModule(config, self.logger)
        self.executor_module = ExecutorModule(config, self.logger, event_bus=self.event_bus)
        self.verifier_module = VerifierModule(config, self.logger)
        self.reflection_module = ReflectionModule(config, self.logger, event_bus=self.event_bus)
        self.memory_manager = MemoryManager(config, self.logger)

        self._setup_kill_switch()

    def _setup_kill_switch(self):
        """Setup hard stop via KeyboardInterrupt (SIGINT)."""
        def signal_handler(sig, frame):
            self.logger.warning("\n[HARD STOP] Keyboard Interrupt received! Aborting immediately.")
            self.event_bus.publish("kill_switch_triggered", {"state": KillSwitchState.HARD_STOP})
            sys.exit(1)
        signal.signal(signal.SIGINT, signal_handler)

    def _set_phase(self, phase: AgentPhase):
        self.event_bus.publish("phase_changed", {"phase": phase})
        self.logger.info(f"Transitioned to phase: {phase.value}")

    def run(self, source: str) -> bool:
        self.logger.info("Starting autonomous loop...")
        self.state.input_path = source

        while self.state.phase not in [AgentPhase.DONE, AgentPhase.FAILED]:
            
            # Check soft kill switch
            if self.state.kill_switch != KillSwitchState.ACTIVE:
                self.logger.warning("Kill switch is active. Halting loop.")
                self.state.phase = AgentPhase.FAILED
                break

            if self.state.phase == AgentPhase.PERCEIVE:
                self._perceive()
            elif self.state.phase == AgentPhase.INTERPRET:
                self._interpret()
            elif self.state.phase == AgentPhase.PLAN:
                self._plan()
            elif self.state.phase == AgentPhase.EXECUTE:
                self._execute()
            elif self.state.phase == AgentPhase.VERIFY:
                self._verify()
            elif self.state.phase == AgentPhase.REFLECT:
                self._reflect()
            elif self.state.phase == AgentPhase.ASK_USER:
                if not self._ask_user():
                    self._set_phase(AgentPhase.FAILED)

            # Checkpoint the state after every phase
            self.memory_manager.save_checkpoint("latest", self.state.model_dump())

        # Print the execution timeline for observability
        self.logger.print_timeline()

        return self.state.phase == AgentPhase.DONE

    def _perceive(self):
        try:
            _, self.state.input_type, content = self.input_module.load(self.state.input_path)
            self.state.raw_text = self.perception_module.extract(content, self.state.input_type)
            if not self.state.raw_text:
                raise ValueError("No text extracted from input.")
            self._set_phase(AgentPhase.INTERPRET)
        except Exception as e:
            self.state.error_history.append({"phase": AgentPhase.PERCEIVE, "error": str(e)})
            self._set_phase(AgentPhase.REFLECT)

    def _interpret(self):
        try:
            task = self.interpreter_module.interpret(self.state.raw_text, self.state.input_path)
            self.state.structured_task = task
            self.event_bus.publish("update_confidence", {"interpretation": task.confidence})
            self._set_phase(AgentPhase.PLAN)
        except Exception as e:
            self.state.error_history.append({"phase": AgentPhase.INTERPRET, "error": str(e)})
            self._set_phase(AgentPhase.REFLECT)

    def _plan(self):
        try:
            # Policy Engine dictates mode
            self.state.execution_mode = self.execution_policy.determine_mode(self.state)
            
            plan = self.planner_module.create_plan(self.state.structured_task, self.state.execution_mode)
            self.state.plan = plan
            self.event_bus.publish("update_confidence", {"planning": plan.planning_confidence})
            self._set_phase(AgentPhase.EXECUTE)
        except Exception as e:
            self.state.error_history.append({"phase": AgentPhase.PLAN, "error": str(e)})
            self._set_phase(AgentPhase.REFLECT)

    def _execute(self):
        success, msg = self.executor_module.execute_plan(self.state.plan, self.state.structured_task, state=self.state)
        
        # Check if kill switch was triggered during execution
        if self.state.kill_switch != KillSwitchState.ACTIVE:
            self._set_phase(AgentPhase.FAILED)
            return

        if success:
            self.state.output_path = self.executor_module.direct_executor.current_file or \
                                     self.state.structured_task.output_filename
            self._set_phase(AgentPhase.VERIFY)
        else:
            self.event_bus.publish("error_recorded", {"phase": AgentPhase.EXECUTE, "error": msg})
            self._set_phase(AgentPhase.REFLECT)

    def _verify(self):
        result = self.verifier_module.verify(self.state.output_path, self.state.structured_task)
        self.state.verification_result = result
        self.event_bus.publish("update_confidence", {"verification": result.verification_confidence})

        if result.passed:
            # Memory learning feedback loop
            from models.data_models import MemoryEntry
            entry = MemoryEntry(task_signature=self.state.structured_task.description, successful_plan=self.state.plan)
            self.memory_manager.store_workflow(entry, verification_score=result.verification_confidence)
            self._set_phase(AgentPhase.DONE)
        else:
            self.event_bus.publish("error_recorded", {"phase": AgentPhase.VERIFY, "error": str(result.issues)})
            self._set_phase(AgentPhase.REFLECT)

    def _reflect(self):
        last_error = self.state.error_history[-1]["error"] if self.state.error_history else "Unknown error"
        action = self.reflection_module.decide_action(self.state, last_error)

        if not self.autonomy_controller.should_retry(self.state):
            self._set_phase(AgentPhase.ASK_USER)
            return

        self.state.retry_count += 1
        self.logger.retry(self.state.retry_count, self.state.max_retries, f"Action: {action.value}")

        if action == RetryAction.SWITCH_MODE:
            self._set_phase(AgentPhase.PLAN)
        elif action == RetryAction.RE_INTERPRET:
            self._set_phase(AgentPhase.INTERPRET)
        elif action == RetryAction.FIX_FORMATTING:
            self._set_phase(AgentPhase.PLAN)
        elif action == RetryAction.RETRY_ACTION:
            self._set_phase(AgentPhase.EXECUTE)
        elif action == RetryAction.REPLAN:
            self._set_phase(AgentPhase.PLAN)
        else:
            self._set_phase(AgentPhase.ASK_USER)

    def _ask_user(self) -> bool:
        if not self.config.get("agent", {}).get("human_in_the_loop", True):
            self.logger.warning("Human in the loop disabled. Agent failing.")
            return False

        action = self.autonomy_controller.handle_user_escalation(
            "Max retries reached or critical failure. How should we proceed?",
            self.state
        )
        if action == RetryAction.ABORT:
            return False
            
        self.state.retry_count = 0  # Reset retries if user intervenes
        self._set_phase(AgentPhase.PLAN)
        return True
