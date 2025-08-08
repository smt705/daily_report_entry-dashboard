import os
import sqlite3
from datetime import datetime
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

DB_FILE_DEFAULT = "construction_management.db"


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def load_tables(conn: sqlite3.Connection) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all required tables into DataFrames.

    Returns: (projects, reports, manpower, equipment, materials, activities)
    """
    projects = pd.read_sql_query("SELECT * FROM Projects", conn)
    reports = pd.read_sql_query("SELECT * FROM DailyReports", conn)
    manpower = pd.read_sql_query("SELECT * FROM ManpowerLog", conn)
    equipment = pd.read_sql_query("SELECT * FROM EquipmentLog", conn)
    materials = pd.read_sql_query("SELECT * FROM MaterialDeliveries", conn)
    activities = pd.read_sql_query("SELECT * FROM WorkActivities", conn)
    return projects, reports, manpower, equipment, materials, activities


def select_report_ui(projects: pd.DataFrame, reports: pd.DataFrame) -> Optional[int]:
    """Render selectors for project and report date; return selected report_id or None."""
    if projects.empty or reports.empty:
        st.warning("No projects or reports found in the database.")
        return None

    # Join to get project names for reports
    joined = reports.merge(projects, how="left", left_on="project_id", right_on="project_id")
    joined["report_date"] = pd.to_datetime(joined["report_date"], errors="coerce")

    project_names = joined["project_name"].dropna().unique().tolist()
    project_name = st.selectbox("Project", options=project_names)

    proj_reports = joined[joined["project_name"] == project_name].copy()
    if proj_reports.empty:
        st.info("No reports for the selected project.")
        return None

    proj_reports = proj_reports.sort_values("report_date", ascending=False)
    date_labels = proj_reports["report_date"].dt.strftime("%Y-%m-%d").tolist()
    label_to_id = dict(zip(date_labels, proj_reports["report_id"].tolist()))

    date_label = st.selectbox("Report Date", options=date_labels)
    return label_to_id.get(date_label)


def show_report_details(
    report_id: int,
    projects: pd.DataFrame,
    reports: pd.DataFrame,
    manpower: pd.DataFrame,
    equipment: pd.DataFrame,
    materials: pd.DataFrame,
    activities: pd.DataFrame,
) -> None:
    """Render details for a single report using tabs."""
    r = reports[reports["report_id"] == report_id]
    if r.empty:
        st.error("Selected report not found.")
        return

    r = r.iloc[0]
    project = projects[projects["project_id"] == r["project_id"]]
    project_name = project.iloc[0]["project_name"] if not project.empty else "Unknown Project"

    report_date = r["report_date"]
    try:
        report_date_str = datetime.fromisoformat(str(report_date)).strftime("%Y-%m-%d")
    except Exception:
        report_date_str = str(report_date)

    st.header(f"Report: {project_name} — {report_date_str}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Prepared By", r.get("prepared_by", "N/A"))
    c2.metric("Weather", r.get("weather", "N/A"))
    c3.metric("Site Conditions", r.get("site_conditions", "N/A"))

    st.markdown("---")

    tab_activities, tab_manpower, tab_equipment, tab_materials, tab_notes = st.tabs(
        ["Work Activities", "Manpower", "Equipment", "Materials", "Notes"]
    )

    with tab_activities:
        df = activities[activities["report_id"] == report_id].copy()
        if df.empty:
            st.info("No work activities logged.")
        else:
            st.dataframe(df.drop(columns=["report_id", "activity_id"], errors="ignore"), use_container_width=True)

    with tab_manpower:
        df = manpower[manpower["report_id"] == report_id].copy()
        if df.empty:
            st.info("No manpower logged.")
        else:
            st.dataframe(df.drop(columns=["report_id", "log_id"], errors="ignore"), use_container_width=True)
            if {"trade", "hours_worked"}.issubset(df.columns):
                st.subheader("Manpower Hours by Trade")
                chart = df.groupby("trade")["hours_worked"].sum()
                st.bar_chart(chart)

    with tab_equipment:
        df = equipment[equipment["report_id"] == report_id].copy()
        if df.empty:
            st.info("No equipment logged.")
        else:
            st.dataframe(df.drop(columns=["report_id", "log_id"], errors="ignore"), use_container_width=True)

    with tab_materials:
        df = materials[materials["report_id"] == report_id].copy()
        if df.empty:
            st.info("No materials delivered.")
        else:
            st.dataframe(df.drop(columns=["report_id", "delivery_id"], errors="ignore"), use_container_width=True)

    with tab_notes:
        st.subheader("General Notes")
        st.markdown(f"> {r.get('general_notes', 'No general notes provided.')} ")


def main() -> None:
    """Streamlit dashboard for local SQLite daily reports."""
    st.set_page_config(page_title="Construction Dashboard (SQLite)", page_icon="📊", layout="wide")

    st.title("📊 Construction Site Daily Report Dashboard (SQLite)")
    st.caption("Reading from a local SQLite database file.")

    db_path = st.sidebar.text_input("SQLite DB Path", value=DB_FILE_DEFAULT)
    reload_btn = st.sidebar.button("Reload Database")

    if not os.path.exists(db_path):
        st.warning(f"Database not found at '{db_path}'. Use the entry app to create/save reports first.")
        return

    try:
        conn = get_connection(db_path)
        with st.spinner("Loading data..."):
            projects, reports, manpower, equipment, materials, activities = load_tables(conn)
    except Exception as e:
        st.error(f"Failed to load database: {e}")
        return
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # Optional: show basic stats
    with st.expander("Database Summary", expanded=False):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Projects", len(projects))
        c2.metric("Reports", len(reports))
        c3.metric("Manpower Logs", len(manpower))
        c4.metric("Equipment Logs", len(equipment))
        c5.metric("Material Deliveries", len(materials))
        c6.metric("Activities", len(activities))

    report_id = select_report_ui(projects, reports)
    if not report_id:
        st.info("Select a project and report date to view details.")
        return

    show_report_details(report_id, projects, reports, manpower, equipment, materials, activities)


if __name__ == "__main__":
    main()
