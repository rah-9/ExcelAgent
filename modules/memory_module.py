"""
Memory Module — Short-term + Long-term memory with pattern reuse.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any

from core.logger import AgentLogger
from models.data_models import MemoryEntry, TaskType, ExecutionMode


class MemoryManager:
    """Manages short-term working memory and long-term pattern storage."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.memory_config = config.get("memory", {})
        self.memory_dir = config.get("paths", {}).get("memory_dir", "memory")
        self.checkpoints_dir = os.path.join(self.memory_dir, "checkpoints")
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.checkpoints_dir, exist_ok=True)

        self.short_term_file = os.path.join(
            self.memory_dir,
            self.memory_config.get("short_term_file", "short_term.json").split('/')[-1]
        )
        self.long_term_file = os.path.join(
            self.memory_dir,
            self.memory_config.get("long_term_file", "long_term.json").split('/')[-1]
        )

        self.short_term = self._load_json(self.short_term_file, {
            "current_step": 0,
            "last_action": "",
            "last_result": "",
            "error_count": 0,
            "context": {},
        })
        self.long_term = self._load_json(self.long_term_file, {"entries": []})

        self.logger.info("Memory manager initialized")

    def _load_json(self, path: str, default: Any) -> Any:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load memory from {path}: {e}")
        return default

    def _save_json(self, path: str, data: Any):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save memory to {path}: {e}")

    # ── Short-term memory ────────────────────────────────

    def update_short_term(self, **kwargs):
        self.short_term.update(kwargs)
        self.short_term["last_updated"] = datetime.now().isoformat()
        self._save_json(self.short_term_file, self.short_term)
        self.logger.debug(f"Short-term memory updated: {list(kwargs.keys())}")

    def get_short_term(self, key: str, default=None):
        return self.short_term.get(key, default)

    def increment_error_count(self):
        count = self.short_term.get("error_count", 0) + 1
        self.update_short_term(error_count=count)
        return count

    def reset_error_count(self):
        self.update_short_term(error_count=0)

    def get_context(self) -> Dict[str, Any]:
        return dict(self.short_term)

    # ── Checkpoints ──────────────────────────────────────

    def save_checkpoint(self, checkpoint_id: str, state_data: dict):
        """Save a checkpoint of the current execution state."""
        checkpoint_file = os.path.join(self.checkpoints_dir, f"checkpoint_{checkpoint_id}.json")
        self._save_json(checkpoint_file, state_data)
        self.logger.debug(f"Saved checkpoint: {checkpoint_file}")

    def load_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        """Load a checkpoint if it exists."""
        checkpoint_file = os.path.join(self.checkpoints_dir, f"checkpoint_{checkpoint_id}.json")
        return self._load_json(checkpoint_file, None)

    # ── Long-term memory ─────────────────────────────────

    def store_workflow(self, entry: MemoryEntry, verification_score: float = 1.0):
        if verification_score < 0.8:
            self.logger.warning(f"Verification score ({verification_score}) below 0.8. Skipping memory storage to prevent pollution.")
            return

        entries = self.long_term.get("entries", [])
        sig = entry.task_signature
        existing = [e for e in entries if e.get("task_signature") == sig]
        
        if existing:
            for i, e in enumerate(entries):
                if e.get("task_signature") == sig:
                    entries[i] = entry.model_dump()
                    break
        else:
            entries.append(entry.model_dump())

        max_entries = self.memory_config.get("max_long_term_entries", 100)
        if len(entries) > max_entries:
            entries = entries[-max_entries:]

        self.long_term["entries"] = entries
        self._save_json(self.long_term_file, self.long_term)
        self.logger.info(f"Stored workflow pattern: {sig}")

    def find_similar_pattern(self, task_type: TaskType, columns: List[str], description: str = "") -> Optional[MemoryEntry]:
        threshold = self.memory_config.get("similarity_threshold", 0.7)
        entries = self.long_term.get("entries", [])

        if not entries:
            return None

        best_match = None
        best_score = 0.0

        for entry_data in entries:
            try:
                entry = MemoryEntry(**entry_data)
                score = self._compute_similarity(entry, task_type, columns, description)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = entry
            except Exception:
                continue

        if best_match:
            self.logger.info(f"Found similar pattern (score={best_score:.2f}): {best_match.task_signature}")
        return best_match

    def _compute_similarity(self, entry: MemoryEntry, task_type: TaskType, columns: List[str], description: str) -> float:
        score = 0.0
        if entry.task_type == task_type:
            score += 0.3

        if columns and entry.patterns:
            entry_cols = [p for p in entry.patterns if p.startswith("col:")]
            if entry_cols:
                entry_col_names = {c[4:].lower() for c in entry_cols}
                current_col_names = {c.lower() for c in columns}
                if entry_col_names and current_col_names:
                    from rapidfuzz import fuzz
                    matches = 0
                    for curr in current_col_names:
                        best = max(fuzz.ratio(curr, ent) for ent in entry_col_names) if entry_col_names else 0
                        if best > 70:
                            matches += 1
                    col_score = matches / max(len(current_col_names), 1)
                    score += 0.5 * col_score

        if entry.success:
            score += 0.2

        return min(score, 1.0)

    @staticmethod
    def generate_signature(task_type: TaskType, columns: List[str]) -> str:
        key = f"{task_type.value}:{':'.join(sorted(c.lower() for c in columns))}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def persist(self):
        self._save_json(self.short_term_file, self.short_term)
        self._save_json(self.long_term_file, self.long_term)
        self.logger.debug("Memory persisted to disk")
