
# pyzappiti Implementation Plan

## Overview
This document outlines a step-by-step plan to implement the **pyzappiti** asynchronous Python client library for the Zappiti REST API (v4.24.253). It covers project setup, package structure, coding tasks, testing, documentation, and release.

---

## 1. Project Initialization
1. **Repository Setup**  
   - Create a new Git repository named `pyzappiti`.  
   - Add `.gitignore` for Python, VSCode, and build artifacts.  
   - Initialize a `README.md` with project description and status badge.

2. **Package Configuration**  
   - Create `pyproject.toml` (PEP 621) with metadata:  
     - Name: `pyzappiti`  
     - Version: `0.1.0`  
     - Dependencies: `httpx>=0.23.0`, `pydantic>=1.10.0`  
     - Optional: `pytest`, `flake8`, `mypy`.

3. **Dev Environment**  
   - Set up virtual environment.  
   - Install dev dependencies.  
   - Configure `pre-commit` hooks: `black`, `isort`, `flake8`.

---

## 2. Package Structure

```
pyzappiti/
├── __init__.py
├── config.py
├── client.py
├── models/
│   ├── __init__.py
│   ├── common.py
│   ├── zappiti_service.py
│   ├── general.py
│   ├── playback.py
│   ├── control.py
│   └── library.py
├── services/
│   ├── __init__.py
│   ├── zappiti_service.py
│   ├── general.py
│   ├── playback.py
│   ├── control.py
│   └── library.py
└── tests/
    ├── __init__.py
    ├── test_client.py
    ├── test_models.py
    └── test_services.py
```

---

## 3. Configuration Module (`config.py`)
- Load environment variables: `PYZAPPITI_API_KEY`, `PYZAPPITI_TIMEOUT`.  
- Validate API key presence on import.

---

## 4. HTTP Client (`client.py`)
- Implement `HTTPClient` class using `httpx.AsyncClient`.  
- Methods:
  - `async post(path: str, json: dict, resp_model: Type[BaseModel]) -> BaseModel`
  - `async close()`
- Common error handling: `resp.raise_for_status()`.

---

## 5. Models (`models/*.py`)
- Create Pydantic classes for each Swagger definition:
  - `common.py`: `ErrorCode`, `BaseResponse`, enums (`MediaType`, `SeenState`, `ButtonType`, `MenuType`).
  - `zappiti_service.py`: `CheckZappitiServiceRequest/Result`, `InstallZappitiServiceRequest/Result`, `StartZappitiServiceRequest/Result`.
  - `general.py`: `ConnectionDetailsRequest/Result`, `IsAliveRequest/Result`.
  - `playback.py`: `LastMediaRequest/Result` (nested `Media` and `TechnicalInfo`), `IsPlayingRequest/Result`, `StartVideoRequest/Result`.
  - `control.py`: `LaunchAppRequest/Result`.
  - `library.py`: `MediaRequest/Result`, `MenuRequest/Result`, plus `Button`, `Menu`.

---

## 6. Services (`services/*.py`)
- Implement async service classes (no “API” suffix):
  - `ZappitiService`: `check()`, `install()`, `start()`.
  - `General`: `connection_details()`, `is_alive()`.
  - `Playback`: `last_media()`, `is_playing()`, `start_video()`.
  - `Control`: `launch_app()`.
  - `Library`: `media()`, `menu()`.

---

## 7. Testing
- Use `pytest`:
  - Mock HTTP responses using `respx` or `pytest-httpx`.
  - Test model parsing for sample JSON.
  - Service class methods should assert correct request path and response model.

---

## 8. Documentation
- Update `README.md`:
  - Installation instructions (`pip install pyzappiti`).
  - Quickstart example code.
- Generate API docs via `pdoc` or `mkdocs`.
- Host docs on GitHub Pages.

---

## 9. CI/CD
- Configure GitHub Actions:
  - Run lint (`flake8`), type-check (`mypy`), tests.
  - Build and publish to PyPI on tagged release.

---

## 10. Release Plan
1. **Alpha**: core functionality (service, general, playback).  
2. **Beta**: control & library modules, nested models support.  
3. **RC**: full test coverage, docs finalized.  
4. **v1.0.0**: stable release.

---

*End of implementation plan.*
