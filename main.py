import streamlit as st

# Import the main functions from both apps
from streamlit_entry import main as entry_main
from streamlit_dashboard_sqlite import main as dashboard_main

def main():
    """Combined Streamlit app with sidebar navigation."""
    
    # Configure the page
    st.set_page_config(
        page_title="Construction Management System",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Sidebar navigation
    st.sidebar.title("🏗️ Construction Management")
    st.sidebar.markdown("---")
    
    # Navigation options
    page = st.sidebar.selectbox(
        "Choose a page:",
        ["📝 Data Entry", "📊 Dashboard"],
        index=0
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.markdown("**Data Entry**: Create and save daily construction reports")
    st.sidebar.markdown("**Dashboard**: View and analyze saved reports")
    
    # Route to the selected page
    if page == "📝 Data Entry":
        st.title("📝 Site Daily Report - Data Entry")
        entry_main()
    elif page == "📊 Dashboard":
        st.title("📊 Construction Reports Dashboard")
        dashboard_main()

if __name__ == "__main__":
    main()
