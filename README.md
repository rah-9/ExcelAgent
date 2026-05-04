# Excel Automation Agent

A FULLY AUTONOMOUS Excel Automation Agent built in Python. This agent uses local LLMs (via Ollama) and an advanced perception system to automatically interpret input files (PDFs, Images, Text) and generate properly formatted Excel spreadsheets.

## Features
- **Perception Module**: Advanced OCR and text extraction (PyTesseract, OpenCV).
- **Dual Execution**: Uses OpenPyXL (Direct) or PyAutoGUI (UI Fallback) with a Screen Analyzer layer.
- **Safety & Confidence**: Implements Execution Guards and robust Confidence Scoring to determine retry/replan strategies.
- **Memory**: Both short-term state memory and long-term pattern reuse for identical data formats.
- **Fully Local**: No cloud APIs needed.

## Setup

1. Install Ollama and pull `llama3`: `ollama pull llama3`
2. Run `setup.bat` (Windows) or `setup.sh` (Linux/Mac).
3. Ensure Tesseract OCR is installed and available in your PATH.
4. Execute with `python main.py`.

## Build Executable
Run `pyinstaller build.spec` to create a standalone binary.
