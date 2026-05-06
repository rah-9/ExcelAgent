# ExcelAgent

ExcelAgent is an autonomous Python agent that converts raw input from text, PDF, or image sources into formatted Excel spreadsheets.

It uses a multi-stage pipeline with local LLM interpretation, OCR-based perception, intent-based planning, and both direct and UI-driven Excel execution modes. The agent is designed to run locally with Ollama and Tesseract OCR.

## What it does (Version 2)

- Reads text, PDF, image, CSV, Markdown, or raw text input
- Extracts structured data using OCR + image preprocessing
- Interprets content into a JSON-based spreadsheet task via local Ollama model
- Generates an execution plan for Excel creation
- Executes the plan using **Hybrid Execution Engine (V2)**:
  - **Phase 1**: `openpyxl` constructs the spreadsheet safely in backend memory.
  - **Phase 2**: `VisualExecutor` launches a brand new Excel UI, acquires OS-level focus, and perfectly replays the typing, formatting, and saving steps exactly like a human operator.
  - **Phase 3**: Silently persists the true output to disk ensuring deterministic data integrity even if UI replay fails.
- Verifies output and applies retry/reflection logic on failures
- Stores checkpoints and long-term workflow memory for repeated patterns

## Core architecture

- `main.py` — entrypoint and config loader
- `core/agent.py` — orchestrates the autonomous state machine
- `core/autonomy_controller.py` — retry, escalation, and human-in-the-loop decision logic
- `core/state_manager.py` — global state, event bus, and timeline tracking
- `models/data_models.py` — pydantic task/plan/state models
- `modules/` — functional pipeline modules:
  - `input_module.py` — input normalization and type detection
  - `perception_module.py` — OCR/image/PDF extraction pipeline
  - `interpreter_module.py` — LLM-based structured task creation
  - `planner_module.py` — LLM/rule-based plan generation
  - `executor_module.py` — executes plan steps in direct or UI mode
  - `verifier_module.py` — validates output Excel correctness
  - `reflection_module.py` — failure classification and recovery action
  - `memory_module.py` — checkpointing and long-term pattern storage
  - `execution_policy.py` — chooses execution mode based on confidence and task size
  - `screen_analyzer.py` — UI state validation and action guard support
- `utils/` — helpers for Excel formatting and image preprocessing
- `config.yaml` — runtime settings and paths

## Requirements

- Python 3.x
- `pip install -r requirements.txt`
- Tesseract OCR installed and configured (`perception.tesseract_cmd` in `config.yaml`)
- Ollama installed and local model pulled:
  ```bash
  ollama pull llama3
  ```

## Configuration

Update `config.yaml` to suit your environment:

- `agent.max_retries` / `autonomy_level`
- `ollama.model`, `base_url`, GPU/thread options
- `perception.tesseract_cmd`, OCR languages, and preprocessing
- `executor.default_mode` and UI timing settings
- `screen_analyzer.enabled` for UI safety checks
- `verification.confidence_threshold` and validation rules
- `paths.input_dir`, `paths.output_dir`, `paths.memory_dir`, `paths.log_dir`

## Run the agent

From the repository root:

```bash
python main.py <input-file-or-text>
```

If no argument is provided, the agent will:

- look for a file in `input/`
- automatically process the first available file
- otherwise prompt for raw text input

### Example

```bash
python main.py input/sample_student_data.pdf
```

## Output

- Excel files are written to `output/`
- logs are written to `logs/`
- memory and checkpoints are persisted in `memory/`

## Build a standalone executable

```bash
pyinstaller build.spec
```

## Notes

- The agent is designed for local execution and does not require cloud APIs.
- It supports both direct spreadsheet creation and GUI-driven Excel automation as a fallback.
- A human escalation path is included for repeated failures or low-confidence conditions.
- Long-term memory is used to store verified workflows and improve repeated task handling.

## Project layout

```text
README.md
main.py
config.yaml
build.spec
requirements.txt
core/
modules/
models/
utils/
input/
output/
memory/
logs/
```
