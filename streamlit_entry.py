import os
import json
import sqlite3
from datetime import date, datetime
from typing import List, Dict, Any, Tuple, Optional

import pandas as pd
import streamlit as st

DB_FILE = "construction_management.db"
JSON_DIR = "json_data"


def get_connection(db_path: str = DB_FILE) -> sqlite3.Connection:
    """Return a SQLite connection to the given database path.

    Ensures foreign keys are enabled.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist.

    This mirrors the schema in `construction_management.py` without deleting data.
    """
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL UNIQUE,
            location TEXT,
            start_date DATE,
            end_date DATE
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS DailyReports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            report_date DATE NOT NULL,
            weather TEXT,
            site_conditions TEXT,
            general_notes TEXT,
            prepared_by TEXT,
            FOREIGN KEY (project_id) REFERENCES Projects (project_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ManpowerLog (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            trade TEXT NOT NULL,
            number_of_workers INTEGER NOT NULL,
            hours_worked REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS EquipmentLog (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            equipment_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            hours_used REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS MaterialDeliveries (
            delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            material_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            supplier TEXT,
            ticket_number TEXT,
            FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS WorkActivities (
            activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            activity_description TEXT NOT NULL,
            status TEXT CHECK(status IN ('Not Started', 'In Progress', 'Completed', 'Delayed')),
            percent_complete INTEGER,
            notes TEXT,
            FOREIGN KEY (report_id) REFERENCES DailyReports (report_id)
        );
        """
    )

    conn.commit()


def ensure_json_dir(path: str = JSON_DIR) -> None:
    """Ensure the JSON output directory exists."""
    os.makedirs(path, exist_ok=True)


def list_json_files(path: str = JSON_DIR) -> List[str]:
    """List JSON files in the json_data directory sorted by newest first."""
    if not os.path.isdir(path):
        return []
    files = [f for f in os.listdir(path) if f.endswith(".json")]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(path, f)), reverse=True)
    return files


def build_payload(
    project_name: str,
    report_date: date,
    prepared_by: str,
    weather: str,
    site_conditions: str,
    general_notes: str,
    manpower_df: pd.DataFrame,
    equipment_df: pd.DataFrame,
    activities_df: pd.DataFrame,
    materials_df: pd.DataFrame,
) -> dict:
    """Build a JSON-serializable payload of the report and child rows."""
    return {
        "project_name": project_name,
        "report_date": report_date.isoformat() if report_date else None,
        "prepared_by": prepared_by,
        "weather": weather,
        "site_conditions": site_conditions,
        "general_notes": general_notes,
        "manpower": (manpower_df.replace({pd.NA: None}).to_dict(orient="records") if isinstance(manpower_df, pd.DataFrame) else []),
        "equipment": (equipment_df.replace({pd.NA: None}).to_dict(orient="records") if isinstance(equipment_df, pd.DataFrame) else []),
        "activities": (activities_df.replace({pd.NA: None}).to_dict(orient="records") if isinstance(activities_df, pd.DataFrame) else []),
        "materials": (materials_df.replace({pd.NA: None}).to_dict(orient="records") if isinstance(materials_df, pd.DataFrame) else []),
        "saved_at": datetime.utcnow().isoformat() + "Z",
    }


def _new_session_filename(report_date: date, path: str = JSON_DIR) -> str:
    """Compute a new session file name using date-time and a sequence number for the day."""
    ensure_json_dir(path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Count existing files for today to make a simple sequence suffix
    today_prefix = datetime.now().strftime("%Y%m%d")
    today_files = [f for f in list_json_files(path) if f.startswith(today_prefix)]
    seq = len(today_files) + 1
    return os.path.join(path, f"{stamp}-{seq:02d}.json")


def save_json_for_session(payload: dict) -> str:
    """Save or update the JSON file for the current Streamlit session.

    Returns the JSON file path used.
    """
    ensure_json_dir()
    # Reuse file within the same Streamlit session
    current_file: Optional[str] = st.session_state.get("current_json_file")
    if not current_file:
        # Create a new file for the session
        # Prefer report_date in name if present
        try:
            rd = payload.get("report_date")
            _ = datetime.fromisoformat(rd) if rd else None
        except Exception:
            rd = None
        current_file = _new_session_filename(datetime.now().date())
        st.session_state["current_json_file"] = current_file

    with open(current_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return current_file


def load_json_file(filepath: str) -> Optional[dict]:
    """Load a JSON file and return its dict contents, or None on failure."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def upsert_project(conn: sqlite3.Connection, project_name: str) -> int:
    """Insert project if not exists and return its project_id."""
    if not project_name:
        raise ValueError("Project name is required")

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO Projects (project_name) VALUES (?) ON CONFLICT(project_name) DO NOTHING;",
        (project_name,),
    )
    cur.execute("SELECT project_id FROM Projects WHERE project_name = ?;", (project_name,))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Failed to fetch or create project")
    return int(row[0])


def insert_report(
    conn: sqlite3.Connection,
    project_id: int,
    report_date: str,
    weather: str,
    site_conditions: str,
    general_notes: str,
    prepared_by: str,
) -> int:
    """Insert a daily report and return its report_id."""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO DailyReports (project_id, report_date, weather, site_conditions, general_notes, prepared_by)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (project_id, report_date, weather, site_conditions, general_notes, prepared_by),
    )
    cur.execute("SELECT last_insert_rowid();")
    return int(cur.fetchone()[0])


def bulk_insert(
    conn: sqlite3.Connection,
    report_id: int,
    manpower: List[Dict[str, Any]],
    equipment: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    materials: List[Dict[str, Any]],
) -> None:
    """Insert child table records for a report."""
    cur = conn.cursor()

    if manpower:
        cur.executemany(
            """
            INSERT INTO ManpowerLog (report_id, trade, number_of_workers, hours_worked)
            VALUES (?, ?, ?, ?);
            """,
            [
                (
                    report_id,
                    str(m.get("trade", "")).strip(),
                    int(m.get("number_of_workers", 0) or 0),
                    float(m.get("hours_worked", 0) or 0.0),
                )
                for m in manpower
                if str(m.get("trade", "")).strip() != ""
            ],
        )

    if equipment:
        cur.executemany(
            """
            INSERT INTO EquipmentLog (report_id, equipment_name, quantity, hours_used)
            VALUES (?, ?, ?, ?);
            """,
            [
                (
                    report_id,
                    str(e.get("equipment_name", "")).strip(),
                    int(e.get("quantity", 0) or 0),
                    float(e.get("hours_used", 0) or 0.0),
                )
                for e in equipment
                if str(e.get("equipment_name", "")).strip() != ""
            ],
        )

    if activities:
        cur.executemany(
            """
            INSERT INTO WorkActivities (report_id, activity_description, status, percent_complete, notes)
            VALUES (?, ?, ?, ?, ?);
            """,
            [
                (
                    report_id,
                    str(a.get("activity_description", "")).strip(),
                    str(a.get("status", "In Progress")),
                    int(a.get("percent_complete", 0) or 0),
                    str(a.get("notes", "")),
                )
                for a in activities
                if str(a.get("activity_description", "")).strip() != ""
            ],
        )

    if materials:
        cur.executemany(
            """
            INSERT INTO MaterialDeliveries (report_id, material_name, quantity, unit, supplier, ticket_number)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            [
                (
                    report_id,
                    str(m.get("material_name", "")).strip(),
                    float(m.get("quantity", 0) or 0.0),
                    str(m.get("unit", "")),
                    str(m.get("supplier", "")),
                    str(m.get("ticket_number", "")),
                )
                for m in materials
                if str(m.get("material_name", "")).strip() != ""
            ],
        )


def save_report(
    project_name: str,
    report_date: date,
    prepared_by: str,
    weather: str,
    site_conditions: str,
    general_notes: str,
    manpower_df: pd.DataFrame,
    equipment_df: pd.DataFrame,
    activities_df: pd.DataFrame,
    materials_df: pd.DataFrame,
) -> Tuple[bool, str]:
    """Persist the report and related logs to SQLite.

    Returns (ok, message).
    """
    # Early validations
    if not project_name:
        return False, "Project name is required."
    if report_date is None:
        return False, "Report date is required."

    conn = get_connection()
    try:
        init_db(conn)
        conn.execute("BEGIN TRANSACTION;")

        project_id = upsert_project(conn, project_name)
        report_id = insert_report(
            conn,
            project_id,
            report_date.isoformat(),
            weather,
            site_conditions,
            general_notes,
            prepared_by,
        )

        # Convert DataFrames to records
        manpower = manpower_df.replace({pd.NA: None}).to_dict(orient="records") if not manpower_df.empty else []
        equipment = equipment_df.replace({pd.NA: None}).to_dict(orient="records") if not equipment_df.empty else []
        activities = activities_df.replace({pd.NA: None}).to_dict(orient="records") if not activities_df.empty else []
        materials = materials_df.replace({pd.NA: None}).to_dict(orient="records") if not materials_df.empty else []

        bulk_insert(conn, report_id, manpower, equipment, activities, materials)

        conn.commit()
        return True, f"Report saved (ID: {report_id})."
    except Exception as e:
        conn.rollback()
        return False, f"Error saving report: {e}"
    finally:
        conn.close()


def main() -> None:
    """Streamlit app: Site Daily Report (SQLite)."""
    st.set_page_config(page_title="Site Daily Report (SQLite)", page_icon="🏗️", layout="wide")

    # Sidebar toolbar
    with st.sidebar:
        st.header("⚙️ Settings")
        # Light mode override: inject minimal CSS to lighten background if desired
        light_mode = st.toggle("Light mode override", value=False, help="Apply a simple CSS override to use a light background.")

        st.divider()
        st.subheader("📁 JSON Sessions")
        files = list_json_files()
        selected_file = st.selectbox("Previous sessions", options=["(none)"] + files, index=0)
        col_a, col_b = st.columns(2)
        with col_a:
            load_btn = st.button("Load to form", disabled=(selected_file == "(none)"))
        with col_b:
            clear_session_btn = st.button("New session", help="Start a new JSON session file on next save")

    if clear_session_btn:
        st.session_state.pop("current_json_file", None)
        st.success("New session will be created on next save.")

    if light_mode:
        st.markdown(
            """
            <style>
            /* Force light color scheme for Streamlit containers */
            :root, [data-testid="stAppViewContainer"], .stApp { color-scheme: light !important; }

            /* App background + default text */
            body, .stApp, .block-container { background-color: #ffffff !important; color: #000000 !important; }

            /* Top header */
            [data-testid="stHeader"], [data-testid="stToolbar"] { background: #ffffff !important; color: #000000 !important; }

            /* Sidebar background + text */
            [data-testid="stSidebar"] { background-color: #ffffff !important; }
            [data-testid="stSidebar"] *, [data-testid="stSidebar"] .stMarkdown p { color: #000000 !important; }

            /* Headings, labels, help text */
            h1, h2, h3, h4, h5, h6, label, .stMarkdown, .stCaption, .st-emotion-cache { color: #000000 !important; }
            .stMarkdown p, .stMarkdown span, .stMarkdown li { color: #000000 !important; }

            /* Inputs and editors */
            input, textarea, select { background-color: #ffffff !important; color: #000000 !important; }
            /* TextInput */
            .stTextInput > div > div > input { background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important; border-radius: 6px !important; box-shadow: none !important; }
            /* TextArea */
            .stTextArea textarea { background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important; border-radius: 6px !important; box-shadow: none !important; }
            /* NumberInput */
            .stNumberInput input { background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important; border-radius: 6px !important; box-shadow: none !important; }
            /* DateInput */
            .stDateInput input { background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important; border-radius: 6px !important; box-shadow: none !important; }
            /* Generic input (fallback) */
            input[type="text"], input[type="number"], input[type="search"], input[type="date"], textarea { border: 1px solid #ced4da !important; border-radius: 6px !important; box-shadow: none !important; }
            /* Focus state */
            input:focus, textarea:focus, [data-baseweb="select"] [role="combobox"]:focus { outline: 2px solid #86b7fe !important; outline-offset: 0 !important; border-color: #86b7fe !important; box-shadow: 0 0 0 0.2rem rgba(13,110,253,.15) !important; }
            ::placeholder { color: #6c757d !important; opacity: 1 !important; }

            /* Selectbox (BaseWeb) */
            [data-baseweb="select"] { color: #000000 !important; }
            [data-baseweb="select"] [role="combobox"] { background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important; border-radius: 6px !important; box-shadow: none !important; }
            [data-baseweb="select"] [role="listbox"] { background-color: #ffffff !important; color: #000000 !important; }
            [data-baseweb="select"] svg, [data-baseweb="select"] svg path { fill: #000000 !important; }
            /* Selectbox popup (appears in a portal) */
            [data-baseweb="popover"] { background-color: #ffffff !important; color: #000000 !important; }
            [data-baseweb="popover"] [role="listbox"] { background-color: #ffffff !important; color: #000000 !important; }
            [data-baseweb="popover"] [role="option"] { background-color: #ffffff !important; color: #000000 !important; }

            /* Buttons */
            .stButton > button { background-color: #f1f3f5 !important; color: #000000 !important; border: 1px solid #ced4da !important; }
            .stButton > button:hover { background-color: #e9ecef !important; }
            .stButton > button:disabled { background-color: #e9ecef !important; color: #6c757d !important; border-color: #dee2e6 !important; }

            /* Tabs/expanders/alerts */
            .stTabs, .stTabs * { color: #000000 !important; }
            .stExpander, .stExpander * { color: #000000 !important; }
            .stAlert, .stMetric { color: #000000 !important; }

            /* Data editor grid */
            [data-testid="stDataEditor"] * { color: #000000 !important; }
            [data-testid="stDataEditorGrid"] { background-color: #ffffff !important; }
            [data-testid="stDataEditorGrid"] .cell { background-color: #ffffff !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.title("🏗️ Site Daily Report (SQLite)")
    st.caption("Fill out the details and save to a local SQLite database file.")

    # Initialize default store values (distinct from widget keys) so we can load JSON safely
    st.session_state.setdefault("project_name_store", "Transmission Line Upgrade - Section 5")
    st.session_state.setdefault("report_date_store", date.today())
    st.session_state.setdefault("prepared_by_store", "")
    st.session_state.setdefault("weather_store", "")
    st.session_state.setdefault("site_conditions_store", "")
    st.session_state.setdefault("general_notes_store", "")
    st.session_state.setdefault("activities_store", pd.DataFrame(columns=["activity_description", "status", "percent_complete", "notes"]))
    st.session_state.setdefault("manpower_store", pd.DataFrame(columns=["trade", "number_of_workers", "hours_worked"]))
    st.session_state.setdefault("equipment_store", pd.DataFrame(columns=["equipment_name", "quantity", "hours_used"]))
    st.session_state.setdefault("materials_store", pd.DataFrame(columns=["material_name", "quantity", "unit", "supplier", "ticket_number"]))

    # If user chose a previous JSON and clicked load, populate the form state
    if load_btn and selected_file != "(none)":
        data = load_json_file(os.path.join(JSON_DIR, selected_file))
        if data:
            st.session_state["project_name_store"] = data.get("project_name", st.session_state["project_name_store"])
            try:
                st.session_state["report_date_store"] = datetime.fromisoformat(data.get("report_date")).date() if data.get("report_date") else st.session_state["report_date_store"]
            except Exception:
                pass
            st.session_state["prepared_by_store"] = data.get("prepared_by", "")
            st.session_state["weather_store"] = data.get("weather", "")
            st.session_state["site_conditions_store"] = data.get("site_conditions", "")
            st.session_state["general_notes_store"] = data.get("general_notes", "")
            st.session_state["activities_store"] = pd.DataFrame(data.get("activities", []))
            st.session_state["manpower_store"] = pd.DataFrame(data.get("manpower", []))
            st.session_state["equipment_store"] = pd.DataFrame(data.get("equipment", []))
            st.session_state["materials_store"] = pd.DataFrame(data.get("materials", []))
            st.success(f"Loaded session from {selected_file}")

    with st.form("report_form", clear_on_submit=False):
        st.subheader("General Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            project_name = st.text_input(
                "Project Name", value=st.session_state["project_name_store"], key="project_name"
            )
        with col2:
            report_date = st.date_input("Report Date", value=st.session_state["report_date_store"], key="report_date")
        with col3:
            prepared_by = st.text_input("Prepared By", value=st.session_state["prepared_by_store"], key="prepared_by")

        weather = st.text_input("Weather", value=st.session_state["weather_store"], placeholder="e.g., Sunny, 32°C, Light Wind", key="weather")
        site_conditions = st.text_area(
            "Site Conditions",
            value=st.session_state["site_conditions_store"],
            placeholder="e.g., Ground is dry, access roads are clear.",
            key="site_conditions",
        )
        general_notes = st.text_area("General Notes", value=st.session_state["general_notes_store"], placeholder="Optional notes...", key="general_notes")

        st.markdown("---")
        st.subheader("Work Activities")
        activities_df = st.data_editor(
            st.session_state["activities_store"],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "activity_description": st.column_config.TextColumn("Description", required=False),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["In Progress", "Completed", "Delayed", "Not Started"],
                    default="In Progress",
                ),
                "percent_complete": st.column_config.NumberColumn(
                    "% Complete", min_value=0, max_value=100
                ),
                "notes": st.column_config.TextColumn("Notes"),
            },
            key="activities_df",
        )

        st.subheader("Manpower")
        manpower_df = st.data_editor(
            st.session_state["manpower_store"],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "trade": st.column_config.TextColumn("Trade"),
                "number_of_workers": st.column_config.NumberColumn(
                    "Workers", min_value=0
                ),
                "hours_worked": st.column_config.NumberColumn(
                    "Hours", min_value=0.0, step=0.5
                ),
            },
            key="manpower_df",
        )

        st.subheader("Equipment")
        equipment_df = st.data_editor(
            st.session_state["equipment_store"],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "equipment_name": st.column_config.TextColumn("Equipment"),
                "quantity": st.column_config.NumberColumn("Qty", min_value=0),
                "hours_used": st.column_config.NumberColumn(
                    "Hours Used", min_value=0.0, step=0.5
                ),
            },
            key="equipment_df",
        )

        st.subheader("Materials")
        materials_df = st.data_editor(
            st.session_state["materials_store"],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "material_name": st.column_config.TextColumn("Material"),
                "quantity": st.column_config.NumberColumn("Qty", min_value=0.0, step=0.5),
                "unit": st.column_config.TextColumn("Unit"),
                "supplier": st.column_config.TextColumn("Supplier"),
                "ticket_number": st.column_config.TextColumn("Ticket #"),
            },
            key="materials_df",
        )

        save_btn = st.form_submit_button("Save Daily Report", type="primary")

    if save_btn:
        ok, msg = save_report(
            project_name=project_name,
            report_date=report_date,
            prepared_by=prepared_by,
            weather=weather,
            site_conditions=site_conditions,
            general_notes=general_notes,
            manpower_df=manpower_df,
            equipment_df=equipment_df,
            activities_df=activities_df,
            materials_df=materials_df,
        )
        if ok:
            st.success(msg)
            st.info(
                f"Saved to {DB_FILE}. You can share this file or analyze it with the dashboard."
            )
            # Also write/update JSON for this session
            payload = build_payload(
                project_name,
                report_date,
                prepared_by,
                weather,
                site_conditions,
                general_notes,
                manpower_df,
                equipment_df,
                activities_df,
                materials_df,
            )
            json_path = save_json_for_session(payload)
            st.success(f"Session JSON saved: {json_path}")
        else:
            st.error(msg)


if __name__ == "__main__":
    main()
