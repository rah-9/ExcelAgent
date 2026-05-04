"""
Perception Module — OCR + image processing + PDF text extraction.
"""

import os
import tempfile
from typing import List, Optional
from PIL import Image

from core.logger import AgentLogger
from models.data_models import InputType
from utils.image_preprocessor import ImagePreprocessor


def cv2_to_pil(cv2_image):
    """Convert OpenCV image to PIL Image."""
    import cv2
    if len(cv2_image.shape) == 2:
        return Image.fromarray(cv2_image)
    rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


class PerceptionModule:
    """Extract raw text from PDF, image, or text input using OCR."""

    def __init__(self, config: dict, logger: AgentLogger):
        self.config = config
        self.logger = logger
        self.perception_config = config.get("perception", {})
        self.preprocessor = ImagePreprocessor(config, logger)
        self._setup_tesseract()

    def _setup_tesseract(self):
        tesseract_cmd = self.perception_config.get("tesseract_cmd", "tesseract")
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            pytesseract.get_tesseract_version()
            self.logger.info("Tesseract OCR engine ready")
        except Exception as e:
            self.logger.warning(f"Tesseract not found at '{tesseract_cmd}': {e}")
            self.logger.warning("Install Tesseract: https://github.com/tesseract-ocr/tesseract")

    def extract(self, input_path: str, input_type: str, raw_content: str = "") -> str:
        self.logger.info(f"Extracting text from {input_type}: {input_path[:80]}")

        if input_type == "text":
            return self._extract_from_text(raw_content)
        elif input_type == "image":
            return self._extract_from_image(input_path)
        elif input_type == "pdf":
            return self._extract_from_pdf(input_path)
        else:
            self.logger.error(f"Unsupported input type: {input_type}")
            return ""

    def _extract_from_text(self, content: str) -> str:
        self.logger.info(f"Text input: {len(content)} characters")
        return content

    def _extract_from_image(self, image_path: str) -> str:
        self.logger.info(f"Running OCR on image: {image_path}")

        import pytesseract

        processed = self.preprocessor.preprocess_file(image_path)
        if len(processed.shape) == 2:
            pil_image = Image.fromarray(processed)
        else:
            pil_image = Image.fromarray(cv2_to_pil(processed))

        languages = self.perception_config.get("languages", ["eng"])
        lang_str = "+".join(languages)

        best_text = ""
        psm_modes = [6, 4, 3]

        for psm in psm_modes:
            try:
                config_str = f"--psm {psm} --oem 3"
                text = pytesseract.image_to_string(pil_image, lang=lang_str, config=config_str)
                if len(text.strip()) > len(best_text.strip()):
                    best_text = text
                    self.logger.debug(f"PSM {psm} yielded {len(text)} chars")
            except Exception as e:
                self.logger.warning(f"OCR PSM {psm} failed: {e}")
                continue

        try:
            data = pytesseract.image_to_data(pil_image, lang=lang_str, output_type=pytesseract.Output.DICT)
            table_text = self._reconstruct_table_from_ocr_data(data)
            if len(table_text.strip()) > len(best_text.strip()):
                best_text = table_text
                self.logger.info("OCR data mode produced better results")
        except Exception:
            pass

        self.logger.info(f"OCR extracted {len(best_text)} characters")
        return best_text

    def _extract_from_pdf(self, pdf_path: str) -> str:
        self.logger.info(f"Processing PDF: {pdf_path}")
        text = self._pdf_text_extract(pdf_path)
        if text.strip():
            self.logger.info(f"Direct PDF text extraction: {len(text)} characters")
            return text

        self.logger.info("Direct extraction empty, converting PDF to images for OCR...")
        images = self._pdf_to_images(pdf_path)
        all_text = []

        import pytesseract

        for i, pil_image in enumerate(images):
            self.logger.info(f"OCR on page {i + 1}/{len(images)}")
            processed = self.preprocessor.preprocess_pil(pil_image)

            if len(processed.shape) == 2:
                processed_pil = Image.fromarray(processed)
            else:
                processed_pil = Image.fromarray(cv2_to_pil(processed))

            languages = self.perception_config.get("languages", ["eng"])
            lang_str = "+".join(languages)

            page_text = pytesseract.image_to_string(processed_pil, lang=lang_str)
            all_text.append(f"--- Page {i + 1} ---\n{page_text}")

        combined = "\n\n".join(all_text)
        self.logger.info(f"PDF OCR extracted {len(combined)} characters across {len(images)} pages")
        return combined

    def _pdf_text_extract(self, pdf_path: str) -> str:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except ImportError:
            self.logger.debug("PyMuPDF not available")
        except Exception as e:
            self.logger.warning(f"PyMuPDF extraction failed: {e}")

        try:
            from pdfminer.high_level import extract_text
            return extract_text(pdf_path)
        except ImportError:
            pass
        except Exception as e:
            self.logger.warning(f"pdfminer extraction failed: {e}")

        return ""

    def _pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, dpi=300)
            self.logger.info(f"Converted PDF to {len(images)} images")
            return images
        except Exception as e:
            self.logger.error(f"PDF to image conversion failed: {e}")
            return []

    def _reconstruct_table_from_ocr_data(self, data: dict) -> str:
        words = []
        n_boxes = len(data["text"])
        for i in range(n_boxes):
            text = data["text"][i].strip()
            if text:
                words.append({
                    "text": text,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "w": data["width"][i],
                    "h": data["height"][i],
                    "conf": data["conf"][i],
                })

        if not words:
            return ""

        words.sort(key=lambda w: (w["y"], w["x"]))
        rows = []
        current_row = [words[0]]
        y_threshold = 15

        for word in words[1:]:
            if abs(word["y"] - current_row[0]["y"]) < y_threshold:
                current_row.append(word)
            else:
                rows.append(sorted(current_row, key=lambda w: w["x"]))
                current_row = [word]
        rows.append(sorted(current_row, key=lambda w: w["x"]))

        lines = []
        for row in rows:
            lines.append("\t".join(w["text"] for w in row))

        return "\n".join(lines)
