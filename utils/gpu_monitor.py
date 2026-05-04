"""
GPU Monitor — Track VRAM usage, decide CPU/GPU execution paths.
"""

import subprocess
from typing import Dict

from core.logger import AgentLogger


class GPUMonitor:
    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.gpu_config = config.get("gpu", {})
        self.enabled = self.gpu_config.get("enabled", True)
        self.vram_limit_mb = self.gpu_config.get("vram_limit_mb", 2048)

    def get_gpu_info(self) -> Dict:
        info = {
            "available": False,
            "name": "Unknown",
            "vram_total_mb": 0,
            "vram_used_mb": 0,
            "vram_free_mb": 0,
            "utilization_pct": 0,
        }

        if not self.enabled:
            return info

        try:
            result = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(", ")
                if len(parts) >= 5:
                    info["available"] = True
                    info["name"] = parts[0].strip()
                    info["vram_total_mb"] = int(float(parts[1].strip()))
                    info["vram_used_mb"] = int(float(parts[2].strip()))
                    info["vram_free_mb"] = int(float(parts[3].strip()))
                    info["utilization_pct"] = int(float(parts[4].strip()))
        except Exception:
            pass

        return info

    def should_use_gpu(self) -> bool:
        if not self.enabled:
            return False

        info = self.get_gpu_info()
        if not info["available"]:
            return False

        if info["vram_free_mb"] < self.vram_limit_mb:
            self.logger.warning(
                f"Low VRAM: {info['vram_free_mb']}MB free. Switching to CPU mode."
            )
            return False

        return True

    def optimize_for_low_end_gpu(self) -> Dict:
        info = self.get_gpu_info()
        settings = {
            "use_gpu": self.should_use_gpu(),
            "ollama_gpu_layers": 0,
            "image_batch_size": 1,
            "ocr_dpi": 200,
            "preprocessing_scale": 1.5,
        }

        if info["available"]:
            vram_free = info["vram_free_mb"]
            if vram_free >= 3000:
                settings["ollama_gpu_layers"] = 20
            elif vram_free >= 2000:
                settings["ollama_gpu_layers"] = 10
            elif vram_free >= 1000:
                settings["ollama_gpu_layers"] = 5

        return settings
