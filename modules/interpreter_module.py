"""
Interpreter Module — Convert raw text into structured JSON task using LLM (Ollama).
"""

import json
import re
from typing import Optional, Dict, Any
import requests
import os

from core.logger import AgentLogger
from models.data_models import StructuredTask, TaskType


class InterpreterModule:
    """Convert raw text into structured task using local LLM via Ollama."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.ollama_config = config.get("ollama", {})
        self.base_url = self.ollama_config.get("base_url", "http://localhost:11434")
        self.model = self.ollama_config.get("model", "llama3")
        self.timeout = self.ollama_config.get("timeout", 120)
        self.temperature = self.ollama_config.get("temperature", 0.1)

    def interpret(self, raw_text: str, source: str = "") -> StructuredTask:
        self.logger.info(f"Interpreting raw text ({len(raw_text)} chars) from: {source}")

        structured = self._llm_interpret(raw_text, source)

        if structured is None or structured.confidence < 0.3:
            self.logger.warning("LLM interpretation failed or low confidence, trying rule-based...")
            structured = self._rule_based_interpret(raw_text, source)

        if structured is None:
            structured = StructuredTask(
                task=TaskType.EXTRACT_AND_CREATE,
                description="Extract data and create Excel",
                raw_text=raw_text,
                source=source,
                confidence=0.1,
            )

        self.logger.info(
            f"Interpretation complete: task={structured.task.value}, "
            f"columns={len(structured.columns)}, rows={len(structured.data)}, "
            f"confidence={structured.confidence:.2f}"
        )
        return structured

    def _llm_interpret(self, raw_text: str, source: str) -> Optional[StructuredTask]:
        prompt = self._build_interpretation_prompt(raw_text)

        try:
            response = self._call_ollama(prompt, system=self._system_prompt())
            if response:
                return self._parse_llm_response(response, raw_text, source)
        except Exception as e:
            self.logger.error(f"LLM interpretation error: {e}")

        return None

    def _system_prompt(self) -> str:
        return """You are an expert data extraction assistant. Your job is to analyze raw text (which may be OCR output with errors) and convert it into a structured JSON format for creating Excel spreadsheets.

You must respond ONLY with valid JSON in this exact format:
{
  "task": "create_excel",
  "description": "Brief description of what the data is about",
  "columns": ["Column1", "Column2", "Column3"],
  "data": [["row1col1", "row1col2", "row1col3"], ["row2col1", "row2col2", "row2col3"]],
  "formatting": {"bold_headers": true, "auto_width": true},
  "output_filename": "output.xlsx",
  "confidence": 0.9
}

Rules:
- Fix OCR errors intelligently (e.g., "Name" not "Narne")
- Identify table structure from delimiters
- Numeric values should be numbers
- Remove empty/meaningless rows
- confidence is 0.0-1.0
- Respond ONLY with the JSON object"""

    def _build_interpretation_prompt(self, raw_text: str) -> str:
        max_chars = 6000
        truncated = raw_text[:max_chars]
        if len(raw_text) > max_chars:
            truncated += f"\n... [truncated, {len(raw_text)} total chars]"

        return f"""Analyze the following text and extract it into a structured Excel-ready format:

--- RAW TEXT START ---
{truncated}
--- RAW TEXT END ---

Extract the data and respond with the JSON structure."""

    def _call_ollama(self, prompt: str, system: str = "") -> Optional[str]:
        self.logger.debug(f"Calling Ollama model: {self.model}")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.ollama_config.get("max_tokens", 4096),
                "num_gpu_layers": self.ollama_config.get("gpu_layers", 20),
                "num_thread": self.ollama_config.get("cpu_threads", 4),
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            self.logger.error(f"Ollama API error: {e}")
            return None

    def _parse_llm_response(self, response: str, raw_text: str, source: str) -> Optional[StructuredTask]:
        json_str = self._extract_json(response)
        if not json_str:
            return None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            data = self._fix_json(json_str)
            if data is None:
                return None

        try:
            task_type = TaskType.EXTRACT_AND_CREATE
            if "task" in data:
                try:
                    task_type = TaskType(data["task"])
                except ValueError:
                    pass

            return StructuredTask(
                task=task_type,
                description=data.get("description", ""),
                columns=data.get("columns", []),
                data=data.get("data", []),
                formatting=data.get("formatting", {}),
                output_filename=data.get("output_filename", "output.xlsx"),
                source=source,
                confidence=float(data.get("confidence", 0.5)),
                raw_text=raw_text,
            )
        except Exception as e:
            self.logger.error(f"StructuredTask creation error: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[str]:
        patterns = [
            r"```json\s*(\{.*?\})\s*```",
            r"```\s*(\{.*?\})\s*```",
            r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match)
                    return match
                except json.JSONDecodeError:
                    continue
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            return None

    def _fix_json(self, json_str: str) -> Optional[dict]:
        fixed = re.sub(r",\s*([}\]])", r"\1", json_str)
        fixed = fixed.replace("'", '"')
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None

    def _rule_based_interpret(self, raw_text: str, source: str) -> StructuredTask:
        self.logger.info("Using rule-based interpretation")
        lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
        if not lines:
            return StructuredTask(task=TaskType.UNKNOWN, raw_text=raw_text, source=source, confidence=0.0)

        delimiter, _ = self._detect_delimiter(lines)
        columns = []
        data_rows = []

        for i, line in enumerate(lines):
            cells = [c.strip() for c in line.split(delimiter)] if delimiter else self._fixed_width_parse(line)
            if i == 0 and self._looks_like_header(cells):
                columns = cells
            else:
                data_rows.append([self._try_numeric(cell) for cell in cells])

        if not columns and data_rows:
            columns = [str(c) for c in data_rows.pop(0)]

        output_filename = self._generate_filename(source, columns)

        return StructuredTask(
            task=TaskType.EXTRACT_AND_CREATE if columns else TaskType.CREATE_EXCEL,
            description=f"Data extracted from {source}" if source else "Extracted data",
            columns=columns,
            data=data_rows,
            source=source,
            confidence=0.5 if columns and data_rows else 0.2,
            raw_text=raw_text,
            output_filename=output_filename,
        )

    def _detect_delimiter(self, lines: list) -> tuple:
        candidates = {"\t": 0, "|": 0, ",": 0, ";": 0}
        for line in lines[:20]:
            for delim in candidates:
                candidates[delim] += line.count(delim)
        best = max(candidates, key=candidates.get) if any(candidates.values()) else None
        return best, candidates

    def _fixed_width_parse(self, line: str) -> list:
        parts = re.split(r"\s{2,}", line.strip())
        return [p.strip() for p in parts if p.strip()]

    def _looks_like_header(self, cells: list) -> bool:
        if not cells: return False
        non_numeric = sum(1 for c in cells if not self._is_numeric(c))
        ratio = non_numeric / len(cells) if cells else 0
        avg_len = sum(len(str(c)) for c in cells) / len(cells)
        return ratio > 0.7 and avg_len < 30

    @staticmethod
    def _is_numeric(value) -> bool:
        try:
            float(str(value).replace(",", "").replace("$", "").strip())
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _try_numeric(value):
        s = str(value).replace(",", "").replace("$", "").replace("%", "").strip()
        try:
            return float(s) if "." in s else int(s)
        except (ValueError, TypeError):
            return value

    def _generate_filename(self, source: str, columns: list) -> str:
        if source and source != "text_input":
            basename = os.path.splitext(os.path.basename(source))[0]
            return f"{basename}_extracted.xlsx"
        elif columns:
            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", str(columns[0]))[:30]
            return f"{safe_name}_data.xlsx"
        return "output.xlsx"
