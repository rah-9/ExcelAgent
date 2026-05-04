"""
Agent Logger — structured logging with Rich console + file rotation.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


class AgentLogger:
    """Dual-sink logger: Rich console + rotating file."""

    _instance: Optional["AgentLogger"] = None

    def __init__(self, config: dict):
        self.config = config.get("logging", {})
        self.log_dir = self.config.get("dir", "logs")
        self.level = self.config.get("level", "INFO")
        self.timeline_history = []
        os.makedirs(self.log_dir, exist_ok=True)
        self.logger = logging.getLogger("ExcelAgent")
        self.logger.setLevel(getattr(logging, config.get("logging", {}).get("level", "DEBUG")))

        # Prevent duplicate handlers
        if self.logger.handlers:
            return

        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(module)-20s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Console handler with Rich if available
        if config.get("logging", {}).get("console", True):
            try:
                from rich.logging import RichHandler
                console_handler = RichHandler(
                    rich_tracebacks=True,
                    markup=True,
                    show_path=False,
                )
                console_handler.setFormatter(
                    logging.Formatter("%(message)s", datefmt="%H:%M:%S")
                )
            except ImportError:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(fmt)
            self.logger.addHandler(console_handler)

        # File handler with rotation
        log_file = os.path.join(
            self.log_dir,
            os.path.basename(config.get("logging", {}).get("file", "agent.log")),
        )
        max_bytes = config.get("logging", {}).get("max_file_size_mb", 50) * 1024 * 1024
        backup_count = config.get("logging", {}).get("backup_count", 5)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        self.logger.addHandler(file_handler)

    @classmethod
    def get_instance(cls, config: dict = None) -> "AgentLogger":
        if cls._instance is None and config is not None:
            cls._instance = cls(config)
        return cls._instance

    def debug(self, msg, **kw):
        self.logger.debug(msg, **kw)

    def info(self, msg, **kw):
        self.logger.info(msg, **kw)

    def warning(self, msg, **kw):
        self.logger.warning(msg, **kw)

    def error(self, msg, **kw):
        self.logger.error(msg, **kw)

    def critical(self, msg, **kw):
        self.logger.critical(msg, **kw)

    def step(self, step_num: int, total: int, action: str):
        self.logger.info(f"[STEP {step_num}/{total}] {action}")

    def decision(self, reason: str, choice: str):
        self.logger.info(f"[DECISION] Reason: {reason} -> Choice: {choice}")

    def retry(self, attempt: int, max_attempts: int, reason: str):
        self.logger.warning(f"[RETRY {attempt}/{max_attempts}] {reason}")

    def error_recovery(self, module: str, error: str, action: str):
        self.logger.error(f"[RECOVERY] Module={module} Error='{error}' Action='{action}'")

    def update_timeline(self, step: int, intent: str, status: str, mode: str, error: str = None):
        """Add an event to the failure timeline."""
        entry = f"Step {step} [{mode.upper()}]: {intent} -> {status}"
        if error:
            entry += f" (Error: {error})"
        self.timeline_history.append(entry)

    def print_timeline(self):
        """Print the execution timeline history."""
        try:
            from rich.console import Console
            from rich.panel import Panel
            console = Console()
            history_str = "\n".join(self.timeline_history)
            if history_str:
                console.print(Panel(history_str, title="Execution Timeline", border_style="blue"))
        except ImportError:
            self.logger.info("--- Execution Timeline ---")
            for entry in self.timeline_history:
                self.logger.info(entry)
            self.logger.info("--------------------------")

    def live_status(self, phase: str, step: int, total_steps: int, mode: str, status: str):
        """CLI Observability Layer."""
        try:
            from rich.console import Console
            console = Console()
            step_str = f"Step {step}/{total_steps}" if total_steps > 0 else "Initializing"
            console.print(
                f"[bold magenta][{phase.upper()}][/bold magenta] {step_str} | "
                f"[bold cyan]Mode: {mode.upper()}[/bold cyan] | "
                f"[bold yellow]Status: {status}[/bold yellow]"
            )
        except ImportError:
            self.logger.info(f"[{phase.upper()}] Step {step}/{total_steps} | Mode: {mode.upper()} | Status: {status}")
