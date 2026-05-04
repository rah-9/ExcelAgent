"""
Planner Module — Generate step-by-step intent-based execution plans.
"""

import json
import re
from typing import Optional, List
import requests

from core.logger import AgentLogger
from models.data_models import (
    Plan, PlanStep, StructuredTask, TaskType, ExecutionMode
)


class PlannerModule:
    """Generate and manage execution plans using LLM (Ollama)."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.ollama_config = config.get("ollama", {})
        self.base_url = self.ollama_config.get("base_url", "http://localhost:11434")
        self.model = self.ollama_config.get("model", "llama3")
        self.timeout = self.ollama_config.get("timeout", 120)
        self.temperature = self.ollama_config.get("temperature", 0.1)

    def create_plan(self, task: StructuredTask, execution_mode: ExecutionMode = ExecutionMode.DIRECT) -> Plan:
        self.logger.info(f"Creating plan for task: {task.task.value}, mode: {execution_mode.value}")

        plan = self._llm_plan(task, execution_mode)

        if plan is None or not plan.steps:
            self.logger.warning("LLM planning failed, using rule-based planner")
            plan = self._rule_based_plan(task, execution_mode)

        plan = self._compress_plan(plan)

        self.logger.info(f"Plan created: {len(plan.steps)} steps")
        for step in plan.steps:
            self.logger.debug(f"  Step {step.step_id}: {step.intent} → {step.target} (Idempotent: {step.is_idempotent})")

        return plan

    def _compress_plan(self, plan: Plan) -> Plan:
        """Merge redundant steps and flag idempotent actions."""
        if not plan.steps:
            return plan

        compressed_steps = []
        last_intent = None
        
        for step in plan.steps:
            # Simple Plan Compression: Remove consecutive identical formatting commands
            if step.intent == last_intent and step.intent in ["format_cells", "auto_column_width"]:
                self.logger.debug(f"Compressing redundant step: {step.intent}")
                continue

            # Idempotency tagging
            if step.intent in ["write_headers", "create_workbook", "save_file", "format_cells"]:
                step.is_idempotent = True

            compressed_steps.append(step)
            last_intent = step.intent

        # Re-assign IDs
        for i, step in enumerate(compressed_steps, 1):
            step.step_id = i

        plan.steps = compressed_steps
        return plan

    def replan(self, task: StructuredTask, failed_step: PlanStep, error: str,
               execution_mode: ExecutionMode) -> Plan:
        self.logger.info(f"Replanning after failure at step {failed_step.step_id}: {error}")

        plan = self._llm_replan(task, failed_step, error, execution_mode)

        if plan is None or not plan.steps:
            self.logger.warning("LLM replanning failed, using adjusted rule-based plan")
            plan = self._rule_based_plan(task, execution_mode)
            if "UI" in error or "pyautogui" in error.lower() or "screen mismatch" in error.lower():
                plan.execution_mode = ExecutionMode.DIRECT
            elif "openpyxl" in error.lower() or "direct" in error.lower():
                plan.execution_mode = ExecutionMode.UI

        return plan

    def _llm_plan(self, task: StructuredTask, mode: ExecutionMode) -> Optional[Plan]:
        prompt = self._build_plan_prompt(task, mode)
        try:
            response = self._call_ollama(prompt)
            if response:
                return self._parse_plan_response(response, task, mode)
        except Exception as e:
            self.logger.error(f"LLM planning error: {e}")
        return None

    def _llm_replan(self, task: StructuredTask, failed_step: PlanStep,
                    error: str, mode: ExecutionMode) -> Optional[Plan]:
        prompt = f"""The previous execution plan failed. Context:
Task: {task.description}
Failed Step: {failed_step.step_id} - {failed_step.intent}
Error: {error}
Execution Mode: {mode.value}

Generate a corrected intent-based execution plan as a JSON array:
[{{ "step_id": 1, "intent": "write_workbook", "target": "excel", "params": {{}} }}]"""

        try:
            response = self._call_ollama(prompt)
            if response:
                return self._parse_plan_response(response, task, mode)
        except Exception:
            return None

    def _build_plan_prompt(self, task: StructuredTask, mode: ExecutionMode) -> str:
        truncated_data = json.dumps(task.data[:5], default=str)
        return f"""Create a detailed intent-based execution plan for this Excel task:
Task Type: {task.task.value}
Description: {task.description}
Columns: {task.columns}
Output File: {task.output_filename}
Execution Mode: {mode.value}

Generate plan as JSON array of intents (e.g. create_workbook, write_headers, write_data, format_cells, save_file):
[
  {{"step_id": 1, "intent": "create_workbook", "target": "workbook", "params": {{"filename": "{task.output_filename}"}}}},
  {{"step_id": 2, "intent": "write_headers", "target": "sheet", "params": {{"columns": {json.dumps(task.columns)}}}}},
  {{"step_id": 3, "intent": "write_data", "target": "sheet", "params": {{"rows": {len(task.data)}}}}},
  {{"step_id": 4, "intent": "format_cells", "target": "sheet", "params": {{"bold": true}}}},
  {{"step_id": 5, "intent": "save_file", "target": "workbook", "params": {{"filename": "{task.output_filename}"}}}}
]
Respond ONLY with the JSON array."""

    def _call_ollama(self, prompt: str) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": 4096},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception:
            return None

    def _parse_plan_response(self, response: str, task: StructuredTask, mode: ExecutionMode) -> Optional[Plan]:
        json_str = self._extract_json_array(response)
        if not json_str: return None
        try:
            steps_data = json.loads(json_str)
            steps = []
            for i, s in enumerate(steps_data):
                steps.append(PlanStep(
                    step_id=s.get("step_id", i + 1),
                    intent=s.get("intent", s.get("action", "unknown")),
                    target=s.get("target", ""),
                    params=s.get("params", {}),
                ))
            return Plan(task_type=task.task, steps=steps, execution_mode=mode)
        except json.JSONDecodeError:
            return None

    def _extract_json_array(self, text: str) -> Optional[str]:
        patterns = [r"```json\s*(\[.*?\])\s*```", r"```\s*(\[.*?\])\s*```", r"(\[.*\])"]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue
        return None

    def _rule_based_plan(self, task: StructuredTask, mode: ExecutionMode) -> Plan:
        steps = [
            PlanStep(step_id=1, intent="create_workbook", target="workbook", params={"filename": task.output_filename}),
            PlanStep(step_id=2, intent="write_headers", target="active_sheet", params={"columns": task.columns}),
            PlanStep(step_id=3, intent="write_data", target="active_sheet", params={"data": task.data}),
            PlanStep(step_id=4, intent="format_cells", target="active_sheet", params={"auto_width": True, "bold": True}),
            PlanStep(step_id=5, intent="save_file", target="workbook", params={"filename": task.output_filename}),
        ]
        return Plan(task_type=task.task, steps=steps, execution_mode=mode)
