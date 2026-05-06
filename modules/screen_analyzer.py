"""
Screen Analyzer Module — Vision-based UI detection and validation.
"""

import cv2
import numpy as np
import time
from typing import Tuple, Optional
from mss import mss
import pygetwindow as gw

from core.logger import AgentLogger


class ScreenAnalyzer:
    """Uses OpenCV and screen capture to validate UI state before/after actions."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config.get("screen_analyzer", {})
        self.logger = logger
        self.enabled = self.config.get("enabled", True)
        self.sct = mss()

    def capture_screen(self) -> np.ndarray:
        """Captures the primary monitor screen and returns an OpenCV image."""
        monitor = self.sct.monitors[1]  # Monitor 1 is primary
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

    def is_excel_open_and_active(self) -> bool:
        """Check if an Excel window exists and is the active window."""
        if not self.enabled:
            return True

        try:
            active_window = gw.getActiveWindow()
            if active_window and "Excel" in active_window.title:
                self.logger.debug("Excel is the active window.")
                return True
            
            excel_windows = gw.getWindowsWithTitle("Excel")
            if excel_windows:
                self.logger.debug("Excel is open but not active. Attempting to activate...")
                excel_windows[0].activate()
                time.sleep(0.5)
                return True
                
        except Exception as e:
            self.logger.warning(f"Failed to check window state: {e}")
            
        self.logger.warning("Excel does not appear to be open or active.")
        return False

    def is_excel_active(self) -> bool:
        """
        Check if Excel is currently the active foreground window.
        Works on Windows.
        """
        try:
            import win32gui

            window = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(window)

            if not title:
                return False

            title = title.lower()

            # Excel windows usually contain these
            return "excel" in title or ".xlsx" in title

        except Exception:
            return False

    def is_correct_file_open(self, expected_filename: str) -> bool:
        """Check if the active Excel window title matches the expected filename."""
        if not self.enabled:
            return True
            
        try:
            active_window = gw.getActiveWindow()
            if active_window:
                # Excel titles often look like "filename.xlsx - Excel"
                if expected_filename.lower() in active_window.title.lower():
                    self.logger.debug(f"Correct file '{expected_filename}' is open.")
                    return True
        except Exception as e:
            self.logger.warning(f"Failed to check file open state: {e}")

        self.logger.warning(f"Expected file '{expected_filename}' does not appear to be active.")
        return False

    def match_template(self, template_path: str, threshold: float = 0.8) -> Optional[Tuple[int, int]]:
        """Find a template image on the screen and return its center coordinates."""
        if not self.enabled:
            return None

        img = self.capture_screen()
        try:
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                self.logger.warning(f"Template image not found: {template_path}")
                return None
                
            res = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= threshold)
            
            if len(loc[0]) > 0:
                # Match found
                pt = (loc[1][0], loc[0][0])
                h, w = template.shape[:2]
                center_x = pt[0] + w // 2
                center_y = pt[1] + h // 2
                self.logger.debug(f"Template matched at ({center_x}, {center_y}) with score {res[pt[1]][pt[0]]:.2f}")
                return (center_x, center_y)
                
            self.logger.debug("Template not found on screen.")
            return None
        except Exception as e:
            self.logger.error(f"Template matching failed: {e}")
            return None

    def wait_for_ui_change(self, timeout: float = 5.0) -> bool:
        """Wait for the screen to change significantly (e.g., waiting for load)."""
        if not self.enabled:
            time.sleep(timeout)
            return True

        self.logger.debug("Waiting for UI change...")
        start_img = self.capture_screen()
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            time.sleep(0.5)
            curr_img = self.capture_screen()
            diff = cv2.absdiff(start_img, curr_img)
            non_zero_count = np.count_nonzero(diff)
            
            if non_zero_count > (diff.size * 0.01): # 1% of pixels changed
                self.logger.debug("UI change detected.")
                return True
                
        self.logger.warning("UI change timeout reached.")
        return False

    def capture_and_compare(self, before_img: np.ndarray, threshold: float = 0.005) -> bool:
        """Visual Diffing: Return True if screen changed more than threshold percentage."""
        if not self.enabled:
            return True
        after_img = self.capture_screen()
        diff = cv2.absdiff(before_img, after_img)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh_diff = cv2.threshold(gray_diff, 25, 255, cv2.THRESH_BINARY)
        non_zero_count = np.count_nonzero(thresh_diff)
        changed_percentage = non_zero_count / thresh_diff.size
        
        self.logger.debug(f"Screen changed by {changed_percentage:.4%}")
        return changed_percentage > threshold

    def detect_text_written(self, before_img: np.ndarray) -> bool:
        """Specifically check if text writing caused a small localized UI update."""
        return self.capture_and_compare(before_img, threshold=0.0001)

    def detect_popup(self, before_img: np.ndarray) -> bool:
        """Detect a sudden large block change indicative of a popup dialog."""
        return self.capture_and_compare(before_img, threshold=0.02)
