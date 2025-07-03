import streamlit as st
from pathlib import Path
import importlib

st.set_page_config(page_title="52-Week High Tracker", layout="wide")

# Sidebar navigation
st.sidebar.title("📊 Navigation")
page_options = {
    "📅 Daily Highs Viewer": "daily_viewer",
    "📈 Momentum Summary": "momentum_summary",
#    "🏆 Top Performers": "top_performers_grouped",
#    "🔥 Sector Heatmap": "sector_heatmap",
}

page_selection = st.sidebar.radio("Go to", list(page_options.keys()))

# Dynamically import and run selected view
selected_module_name = page_options[page_selection]
module = importlib.import_module(f"views.{selected_module_name}")
if hasattr(module, "main"):
    module.main()
else:
    st.error(f"Module `{selected_module_name}` does not have a `main()` function.")
