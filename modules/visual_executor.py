"""
Visual Executor Module — Pure Presentation Layer for Hybrid Execution System.
VISUAL MODE EXECUTION CONTRACT:
1. DirectExecutor MUST execute the FULL plan end-to-end first.
2. VisualExecutor MUST run ONLY AFTER Direct execution completes successfully.
3. VisualExecutor MUST NOT depend on plan steps, executor state, or runtime UI state.
4. VisualExecutor MUST use ONLY StructuredTask and an immutable replay_data snapshot.
5. VisualExecutor failure MUST NOT affect output file, verification result, or system state.
"""

import os
import time
import json
import random
import platform
import subprocess
from typing import Any, List, Optional
from datetime import datetime

import pyautogui
from core.logger import AgentLogger
from models.data_models import StructuredTask
from modules.screen_analyzer import ScreenAnalyzer

# Safety first
pyautogui.FAILSAFE = True


class VisualExecutor:
    """Replays a StructuredTask visually using human-like interaction."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.screen_analyzer = ScreenAnalyzer(config, logger)
        
        # Configuration
        visual_config = config.get("executor", {}).get("visual", {})
        self.typing_speed = visual_config.get("typing_speed", 0.05)
        self.move_duration = visual_config.get("move_duration", 0.3)
        self.step_delay = visual_config.get("step_delay", 0.2)
        self.mode = visual_config.get("mode", "demo")
        self.safe_mode = visual_config.get("safe_mode", True)
        self.dry_run = visual_config.get("dry_run", False)
        
        self.input_locked = False
        
        # Step level timeout constraint
        self.STEP_TIMEOUT = 10

    def wait_ui(self, t=0.5):
        import time
        time.sleep(t)

    def close_existing_excel(self):
        """Stateless preparation: Ensure no conflicting Excel instances."""
        if platform.system() == "Windows":
            os.system("taskkill /IM excel.exe >nul 2>&1")
            self.wait_ui(1.0)
            os.system("taskkill /F /IM excel.exe >nul 2>&1")
        elif platform.system() == "Darwin":
            os.system("pkill -f 'Microsoft Excel'")
        self.wait_ui(1.0)

    def ensure_excel_focus(self):
        import pyautogui, time
        screen_w, screen_h = pyautogui.size()
        
        for _ in range(5):
            pyautogui.hotkey("alt", "tab")
            self.wait_ui(1)
            
            pyautogui.click(screen_w // 2, screen_h // 2)
            self.wait_ui(1)
            
            if self.screen_analyzer.is_excel_active():
                # confirm stability
                for _ in range(3):
                    if not self.screen_analyzer.is_excel_active():
                        return False
                    self.wait_ui(0.5)
                return True
        return False

    def prepare_excel(self, task: StructuredTask) -> bool:
        """INIT & PREPARE state machine transition."""
        self.close_existing_excel()
        
        if platform.system() == "Windows":
            import subprocess
            excel_path = r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"
            
            if not os.path.exists(excel_path):
                excel_path = r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE"
                
            if not os.path.exists(excel_path):
                print("[VISUAL] Excel not found → aborting")
                return False
                
            subprocess.Popen(excel_path)
            self.wait_ui(5)
            
            if not self.ensure_excel_focus():
                print("[VISUAL] Failed to focus Excel → abort")
                return False
                
            # FORCE NEW WORKBOOK (START FROM EMPTY SHEET ONLY)
            pyautogui.hotkey("ctrl", "n")
            self.wait_ui(2)
            
            # FOCUS REINFORCEMENT
            pyautogui.hotkey("alt", "tab")
            self.wait_ui(1)
            pyautogui.click(pyautogui.size()[0]//2, pyautogui.size()[1]//2)
            self.wait_ui(1)
            
        elif platform.system() == "Darwin":
            os.system("open -a 'Microsoft Excel'")
            self.wait_ui(5)
            
            if not self.ensure_excel_focus():
                print("[VISUAL] Failed to focus Excel → abort")
                return False
        
        # RESET EXCEL MODE (VERY IMPORTANT)
        pyautogui.press("esc")
        self.wait_ui(0.3)
        pyautogui.press("esc")
        self.wait_ui(0.3)
        
        # FORCE CURSOR TO A1
        pyautogui.hotkey("ctrl", "home")
        self.wait_ui(1)
        
        # ADD TEST WRITE (CRITICAL DEBUG STEP)
        print("[VISUAL] Testing typing...")
        pyautogui.write("TEST", interval=0.1)
        self.wait_ui(1)
        pyautogui.press("tab")
        self.wait_ui(0.5)
        pyautogui.hotkey("shift", "tab")
        self.wait_ui(0.5)
        pyautogui.hotkey("ctrl", "z")
        self.wait_ui(0.5)
        
        return True

    def write_headers(self, task: StructuredTask):
        """WRITE_HEADERS state."""
        for col, header in enumerate(task.columns):
            print(f"[VISUAL] Writing header: {header}")
            
            pyautogui.write(header[0], interval=0.2)
            self.wait_ui(0.3)
            
            if len(header) > 1:
                pyautogui.write(header[1:], interval=0.05)
                
            pyautogui.press("tab")
            self.wait_ui(0.2)
            
        pyautogui.press("enter")
        self.wait_ui(0.5)

    def write_rows(self, replay_data: List[List[Any]]):
        """WRITE_ROWS state."""
        for i, row in enumerate(replay_data):
            print(f"[VISUAL] Writing row {i+1}")
            
            for cell in row:
                pyautogui.write(str(cell), interval=0.05)
                self.wait_ui(0.2)
                
                pyautogui.press("tab")
                self.wait_ui(0.2)
                
            pyautogui.press("enter")
            self.wait_ui(0.3)

    def save_excel(self, filename: str):
        """SAVE state with smart save handling."""
        pyautogui.hotkey("ctrl", "s")
        self.wait_ui(1)
        
        output_dir = os.path.abspath(self.config.get("paths", {}).get("output_dir", "output"))
        os.makedirs(output_dir, exist_ok=True)
        abs_path = os.path.join(output_dir, "VISUAL_" + filename)
        
        pyautogui.write(abs_path, interval=0.02)
        self.wait_ui(0.5)
        
        pyautogui.press("enter")
        self.wait_ui(1)
        
        # FINAL RESET
        pyautogui.hotkey("ctrl", "home")
        self.wait_ui(0.5)

    def replay(self, task: StructuredTask, replay_data: tuple):
        """
        Main Replay State Machine.
        Executes entirely independent of the executor plan.
        """
        if self.dry_run:
            self.logger.info(f"[VISUAL] DRY RUN: Would write: {' -> '.join(task.columns)}")
            return

        print("===================================")
        print("[VISUAL MODE ACTIVE]")
        print("===================================")
        print("[VISUAL] Do NOT touch mouse/keyboard")
        
        self.input_locked = True
        
        try:
            # STATE: INIT & PREPARE
            if not self.prepare_excel(task):
                return
                
            # STATE: WRITE_HEADERS
            self.write_headers(task)
            
            # STATE: WRITE_ROWS
            data_list = [list(row) for row in replay_data]
            self.write_rows(data_list)
            
            # STATE: SAVE
            self.save_excel(task.output_filename)
            
            print("[VISUAL] Replay complete")
            try:
                pyautogui.alert("Excel generation complete", "Visual Replay")
            except Exception:
                pass
                
        except KeyboardInterrupt:
            self.logger.warning("[VISUAL] Replay Interrupted via Keyboard! Gracefully stopping.")
        except Exception as e:
            self.logger.error(f"[VISUAL] Replay failed (Data is safe): {e}")
        finally:
            self.input_locked = False
            print("===================================")
