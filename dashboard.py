import os
from datetime import datetime

import duckdb
import firebase_admin
import pandas as pd
import streamlit as st
from firebase_admin import credentials, firestore

# --- Configuration ---
# This is the path to your service account key file.
# Ensure this file is in the same directory as your script.
CREDENTIALS_FILE = "firebase-credentials.json"

# --- Page Configuration ---
st.set_page_config(
    page_title="Construction Project Dashboard",
    page_icon="🏗️",
    layout="wide",
)

# --- Firebase Initialization ---
# This function initializes Firebase Admin SDK.
# It uses st.cache_resource to ensure it only runs once.


@st.cache_resource
def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using the service account credentials.
    Returns the Firestore database client.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        st.error(
            f"FATAL: Firebase credentials file not found at '{CREDENTIALS_FILE}'. Please follow the setup instructions.")
        st.stop()

    try:
        cred = credentials.Certificate(CREDENTIALS_FILE)
        # Check if the app is already initialized to prevent errors on script rerun.
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        return db
    except Exception as e:
        st.error(f"Failed to initialize Firebase: {e}")
        st.stop()

# --- Data Fetching ---
# This function fetches all daily reports for a specific user.
# It uses st.cache_data to cache the results and avoid refetching on every interaction.


@st.cache_data(ttl=300)  # Cache data for 5 minutes
def fetch_all_reports(_db, app_id, user_id):
    """
    Fetches all daily reports from Firestore for a given app_id and user_id.
    Returns a list of report documents.
    """
    if not app_id or not user_id:
        return []
    try:
        collection_path = f"artifacts/{app_id}/users/{user_id}/daily_reports"
        docs = _db.collection(collection_path).stream()
        reports = [doc.to_dict() for doc in docs]
        return reports
    except Exception as e:
        st.error(f"Error fetching data from Firestore: {e}")
        return []

# --- Main Application ---


def main():
    """
    The main function that runs the Streamlit application.
    """
    db = initialize_firebase()

    st.title("🏗️ Construction Site Daily Report Dashboard")
    st.markdown(
        "This dashboard visualizes the data entered through the Site Daily Report web app.")

    # --- Sidebar for Inputs ---
    with st.sidebar:
        st.header("⚙️ Controls")

        # In a real app, you might get this from the environment or a config file.
        app_id = st.text_input("Enter your App ID", value="default-app-id")

        # The user ID is displayed on the data entry web app.
        user_id = st.text_input(
            "Enter your User ID",
            help="You can find your User ID on the data entry web app.")

        if not user_id:
            st.warning("Please enter your User ID to load data.")
            st.stop()

        st.info(
            "🔄 Data automatically refreshes every 5 minutes. You can force a refresh by clearing the cache.")
        if st.button("Clear Cache & Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # --- Fetch and Process Data ---
    all_reports_data = fetch_all_reports(db, app_id, user_id)

    if not all_reports_data:
        st.warning(
            "No reports found for the provided User ID. Please check the ID or submit a report via the web app.")
        st.stop()

    # Convert fetched data to a Pandas DataFrame
    # We use json_normalize to flatten the nested lists of dicts (manpower,
    # equipment, etc.)
    reports_df = pd.json_normalize(all_reports_data)

    # Convert reportDate to datetime objects for sorting
    reports_df['reportDate'] = pd.to_datetime(reports_df['reportDate'])
    reports_df = reports_df.sort_values(by='reportDate', ascending=False)

    # --- Sidebar Filtering ---
    with st.sidebar:
        st.header("📊 Filters")
        # Allow user to select a specific report by date
        report_dates = reports_df['reportDate'].dt.strftime('%Y-%m-%d').unique()
        selected_date_str = st.selectbox("Select a Report Date", options=report_dates)

    if not selected_date_str:
        st.info("Select a report date from the sidebar to view details.")
        st.stop()

    # Filter the DataFrame to the selected report
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    selected_report_series = reports_df[reports_df['reportDate'].dt.date ==
                                        selected_date].iloc[0]

    # --- Display Selected Report Details ---
    st.header(f"Displaying Report for: {selected_date_str}")
    st.markdown(f"**Project:** {selected_report_series.get('projectName', 'N/A')}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Prepared By", selected_report_series.get('preparedBy', 'N/A'))
    col2.metric("Weather", selected_report_series.get('weather', 'N/A'))
    col3.metric("Site Conditions", selected_report_series.get('siteConditions', 'N/A'))

    # --- Use DuckDB for analysis ---
    # Create a DuckDB connection from the main DataFrame
    con = duckdb.connect(database=':memory:', read_only=False)
    con.register('reports_df', reports_df)

    # --- Display Detailed Tables ---
    tab_activities, tab_manpower, tab_equipment, tab_materials, tab_notes = st.tabs([
        "Work Activities", "Manpower", "Equipment", "Materials", "Notes"
    ])

    with tab_activities:
        activities = selected_report_series.get('activities', [])
        if activities and isinstance(activities, list):
            st.dataframe(pd.DataFrame(activities), use_container_width=True)
        else:
            st.info("No work activities logged for this report.")

    with tab_manpower:
        manpower = selected_report_series.get('manpower', [])
        if manpower and isinstance(manpower, list):
            manpower_df = pd.DataFrame(manpower)
            # Ensure columns are numeric for calculations
            manpower_df['count'] = pd.to_numeric(manpower_df['count'])
            manpower_df['hours'] = pd.to_numeric(manpower_df['hours'])

            st.dataframe(manpower_df, use_container_width=True)

            st.subheader("Manpower Hours by Trade")
            # Create a simple bar chart
            chart_data = manpower_df.set_index('trade')['hours']
            st.bar_chart(chart_data)
        else:
            st.info("No manpower logged for this report.")

    with tab_equipment:
        equipment = selected_report_series.get('equipment', [])
        if equipment and isinstance(equipment, list):
            st.dataframe(pd.DataFrame(equipment), use_container_width=True)
        else:
            st.info("No equipment logged for this report.")

    with tab_materials:
        materials = selected_report_series.get('materials', [])
        if materials and isinstance(materials, list):
            st.dataframe(pd.DataFrame(materials), use_container_width=True)
        else:
            st.info("No materials delivered for this report.")

    with tab_notes:
        st.subheader("General Notes")
        st.markdown(
            f"> {
                selected_report_series.get(
                    'generalNotes',
                    'No general notes provided.')}")


if __name__ == "__main__":
    main()
