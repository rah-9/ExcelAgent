"""
Image preprocessor — OpenCV-based pipeline for OCR optimization.
"""

import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional
from core.logger import AgentLogger


class ImagePreprocessor:
    """Preprocess images for better OCR results."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config.get("perception", {}).get("preprocessing", {})
        self.logger = logger

    def process(self, image: np.ndarray) -> np.ndarray:
        self.logger.info(f"Preprocessing image: shape={image.shape}")

        processed = image.copy()

        if self.config.get("grayscale", True):
            if len(processed.shape) == 3:
                processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
                self.logger.debug("Converted to grayscale")

        scale = self.config.get("scale_factor", 2.0)
        if scale > 1.0:
            h, w = processed.shape[:2]
            new_w, new_h = int(w * scale), int(h * scale)
            processed = cv2.resize(
                processed, (new_w, new_h), interpolation=cv2.INTER_CUBIC
            )
            self.logger.debug(f"Scaled image by {scale}x → {new_w}x{new_h}")

        if self.config.get("denoise", True):
            kernel_size = self.config.get("blur_kernel", 3)
            if len(processed.shape) == 2:
                processed = cv2.GaussianBlur(processed, (kernel_size, kernel_size), 0)
                processed = cv2.fastNlMeansDenoising(
                    processed, None, h=10, templateWindowSize=7, searchWindowSize=21
                )
            else:
                processed = cv2.fastNlMeansDenoisingColored(
                    processed, None, h=10, hColor=10, templateWindowSize=7, searchWindowSize=21
                )
            self.logger.debug("Applied denoising")

        if self.config.get("deskew", True):
            processed = self._deskew(processed)

        if self.config.get("threshold", True):
            if len(processed.shape) == 3:
                processed = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            processed = cv2.adaptiveThreshold(
                processed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 11, 2
            )
            self.logger.debug("Applied adaptive threshold")

        return processed

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 10:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5:
            self.logger.debug(f"Skew angle {angle:.2f}° — too small, skipping deskew")
            return image

        self.logger.debug(f"Deskewing by {angle:.2f}°")
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, m, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated

    def preprocess_file(self, file_path: str) -> np.ndarray:
        image = cv2.imread(file_path)
        if image is None:
            raise ValueError(f"Cannot read image: {file_path}")
        return self.process(image)

    def preprocess_pil(self, pil_image: Image.Image) -> np.ndarray:
        image = np.array(pil_image)
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.ndim == 3 and image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
        return self.process(image)
