"""
Input Module — auto-detect input type, read files, and prepare for processing.
"""

import os
import mimetypes
from typing import Tuple, Optional
from core.logger import AgentLogger


class InputModule:
    """Accept file or text input. Automatically detect type."""

    SUPPORTED_EXTENSIONS = {
        ".pdf": "pdf",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".bmp": "image",
        ".tiff": "image",
        ".tif": "image",
        ".gif": "image",
        ".webp": "image",
        ".txt": "text",
        ".csv": "text",
        ".md": "text",
        ".json": "text",
    }

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.input_dir = config.get("paths", {}).get("input_dir", "input")
        os.makedirs(self.input_dir, exist_ok=True)

    def detect_type(self, source: str) -> str:
        if os.path.isfile(source):
            ext = os.path.splitext(source)[1].lower()
            if ext in self.SUPPORTED_EXTENSIONS:
                detected = self.SUPPORTED_EXTENSIONS[ext]
                self.logger.info(f"Detected input type: {detected} from extension '{ext}'")
                return detected

            mime, _ = mimetypes.guess_type(source)
            if mime:
                if "pdf" in mime:
                    return "pdf"
                elif "image" in mime:
                    return "image"
                elif "text" in mime:
                    return "text"

            self.logger.warning(f"Could not determine type for: {source}, defaulting to text")
            return "text"

        if os.path.isdir(source):
            files = [
                os.path.join(source, f)
                for f in os.listdir(source)
                if os.path.isfile(os.path.join(source, f))
            ]
            if files:
                self.logger.info(f"Directory detected, processing {len(files)} file(s)")
                for f in sorted(files):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in self.SUPPORTED_EXTENSIONS:
                        self.logger.info(f"Selected file: {f}")
                        return self.SUPPORTED_EXTENSIONS[ext]

        if len(source) > 0 and not os.path.exists(source):
            self.logger.info("Detected raw text input")
            return "text"

        return "unknown"

    def load(self, source: str) -> Tuple[str, str, str]:
        self.logger.info(f"Loading input: {source[:100]}...")

        input_type = self.detect_type(source)

        if input_type == "unknown":
            self.logger.error(f"Cannot determine input type for: {source}")
            return source, "unknown", ""

        if input_type == "text" and not os.path.isfile(source):
            return "text_input", "text", source

        if os.path.isfile(source):
            if input_type == "text":
                try:
                    with open(source, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self.logger.info(f"Read text file: {len(content)} characters")
                    return source, "text", content
                except Exception as e:
                    self.logger.error(f"Failed to read text file: {e}")
                    return source, "text", ""

            abs_path = os.path.abspath(source)
            self.logger.info(f"Binary input ready: {abs_path}")
            return abs_path, input_type, abs_path

        return source, input_type, source
