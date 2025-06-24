import streamlit as st
from db_utils import get_all_dates, get_data_for_date

def main():
    st.title("📅 Daily 52-Week Highs Viewer")

    dates = get_all_dates()
    if not dates:
        st.warning("No data available.")
        return

    selected_date = st.selectbox("Select a date", dates)
    daily_df = get_data_for_date(selected_date)

    st.markdown(f"Showing **{len(daily_df)}** records for **{selected_date}**")
    st.dataframe(daily_df, use_container_width=True)

    st.download_button(
        "📥 Download Daily CSV",
        data=daily_df.to_csv(index=False),
        file_name=f"highs_{selected_date}.csv"
    )
