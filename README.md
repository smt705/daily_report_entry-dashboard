# Quickstart Guide

This guide will help you set up and run the project using the provided virtual environment.

## Prerequisites

- Python 3.8 or higher (tested with 3.13.5)
- [uv](https://docs.astral.sh/uv/) (uses `pyproject.toml` and `uv.lock`)
  - Install: `pip install uv` (or see uv docs for other installers)

## Setup

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install dependencies with uv (recommended):**

   This project is managed with `uv` using `pyproject.toml` and `uv.lock`.

   ```bash
   uv sync
   ```

   This will create/refresh `.venv` and install locked dependencies.

   Optional: if you prefer manual activation of the `.venv` created by uv:

   - Windows PowerShell:

     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```

   - macOS/Linux:

     ```bash
     source .venv/bin/activate
     ```

3. **(Alternative) Using pip directly (not required if using uv):**

    ```bash
    pip install -r requirements.txt
    ```

## Running the Project

1. **Run the Streamlit apps with uv (no manual activation needed):**

   - Data entry app (writes `construction_management.db`):

     ```bash
     uv run streamlit run streamlit_entry.py --server.port 8501
     ```

   - Dashboard app (reads `construction_management.db`):

     ```bash
     uv run streamlit run streamlit_dashboard_sqlite.py --server.port 8502
     ```

   Tips:
   - If the DB file does not exist yet, use the entry app to save a first report.
   - Optionally, seed a demo DB by running:

     ```bash
     uv run python construction_management.py
     ```

2. **(Alternative) Run with activated `.venv`:**

   - Windows PowerShell:

     ```powershell
     .\.venv\Scripts\Activate.ps1
     python -m streamlit run streamlit_entry.py --server.port 8501
     python -m streamlit run streamlit_dashboard_sqlite.py --server.port 8502
     ```

   - macOS/Linux:

     ```bash
     source .venv/bin/activate
     python -m streamlit run streamlit_entry.py --server.port 8501
     python -m streamlit run streamlit_dashboard_sqlite.py --server.port 8502
     ```

## Conclusion

You have successfully set up and run the project. For further development, make sure to activate the virtual environment and install any new dependencies as needed.