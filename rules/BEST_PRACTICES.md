# Project Conventions — Work-Zone Traffic What-If Planner

You are building a **traditional Streamlit application**. There is **no AI inside this app** — do not add any LLM, agent, or model-inference features to the product.

## What we're building
A Streamlit tool that lets a transportation engineer model a highway **work zone** and see the traffic impact of lane closures under different demand scenarios.

## Stack & conventions
- Python 3.11+, Streamlit for UI, pandas/numpy for data, a plotting lib already used in our other apps (matplotlib or plotly — match the placeholder).
- **Separate the model from the UI.** All traffic math lives in `app/model.py` as pure, side-effect-free functions. `app/streamlit_app.py` only handles widgets, calls the model, and renders results.
- Keep dependencies minimal and pinned in `requirements.txt`. No new services.
- Docstrings on every public function; type hints throughout.

## Testing
- Tests live in `tests/` and use **pytest**.
- The **model module must have unit tests** with known-input/known-output cases (no-queue case, over-capacity queueing case, edge cases like zero open lanes).
- Test command: `pytest -q`. Do not consider the build done until it passes.

## Workflow rules
- Follow the approved spec in `plans/spec.md`. If it's missing, we are still in planning — propose the spec, don't build.
- Write tests for the model **before or alongside** implementation.
- Preserve existing file/folder structure and the placeholder app's deploy shape (it must run in our existing Streamlit docker unchanged).

## Out of scope (do not do)
- No AI/LLM features in the app.
- No deployment automation — we deploy the PR to our Streamlit docker manually.
- No new external data sources or paid APIs; use synthetic defaults or a single small bundled sample.
