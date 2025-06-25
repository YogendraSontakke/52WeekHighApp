import streamlit as st
import pandas as pd
from db_utils import get_all_dates, get_data_for_date

def main():
    st.title("📅 Daily 52-Week Highs Viewer")

    dates = get_all_dates()
    if not dates:
        st.warning("No data available.")
        return

    # Select mode of date selection
    date_mode = st.radio("Select Date Mode", ["Single Date", "Date Range", "All Dates"])

    if date_mode == "Single Date":
        selected_date = st.selectbox("Select a date", dates)
        # Load data for the selected date only
        daily_df = get_data_for_date(selected_date)

    elif date_mode == "Date Range":
        min_date, max_date = dates[0], dates[-1]
        start_date = st.date_input("Start date", pd.to_datetime(min_date), min_value=pd.to_datetime(min_date), max_value=pd.to_datetime(max_date))
        end_date = st.date_input("End date", pd.to_datetime(max_date), min_value=pd.to_datetime(min_date), max_value=pd.to_datetime(max_date))

        # Validate date order
        if start_date > end_date:
            st.error("Start date must be before or equal to end date.")
            return

        # Convert dates to strings matching your date format in db_utils (assuming 'YYYY-MM-DD')
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Filter dates in the range
        selected_dates = [d for d in dates if start_str <= d <= end_str]
        if not selected_dates:
            st.warning("No data available in the selected date range.")
            return

        # Load and concatenate data for all selected dates
        dfs = [get_data_for_date(d) for d in selected_dates]
        daily_df = pd.concat(dfs, ignore_index=True)

    else:  # All Dates
        # Load and concatenate data for all dates
        dfs = [get_data_for_date(d) for d in dates]
        daily_df = pd.concat(dfs, ignore_index=True)

    if daily_df.empty:
        st.warning("No data available for the selected date(s).")
        return

    # --- Industry Filter (same as before)
    industries = sorted(daily_df["industry"].dropna().unique().tolist())
    industries.insert(0, "All")
    selected_industry = st.selectbox("Filter by Industry", industries)

    filtered_df = daily_df.copy()
    if selected_industry != "All":
        filtered_df = filtered_df[filtered_df["industry"] == selected_industry]

    # Show count and date info
    if date_mode == "Single Date":
        date_info = selected_date
    elif date_mode == "Date Range":
        date_info = f"{start_str} to {end_str}"
    else:
        date_info = "All Dates"

    st.markdown(
        f"Showing **{len(filtered_df)}** records for **{date_info}**"
        + (f" in **{selected_industry}**" if selected_industry != "All" else "")
    )

    if filtered_df.empty:
        st.info("No records match the filters.")
        return

    # --- Grouped Display by Industry (unchanged)
    st.markdown("### 🏭 Grouped View by Industry")

    grouped = (
        filtered_df
        .sort_values(["industry", "market_cap"], ascending=[True, False])
        .groupby("industry")
    )

    for industry, group_df in grouped:
        st.markdown(f"#### 🏷️ {industry} ({len(group_df)} companies)")
        st.dataframe(
            group_df.drop(columns=["industry"]),  # avoid repeating industry
            use_container_width=True,
        )

    # --- Download
    filename_date_part = date_info.replace(" ", "_").replace("to", "-").lower()
    st.download_button(
        "📥 Download CSV",
        data=filtered_df.to_csv(index=False),
        file_name=f"highs_{filename_date_part}_{selected_industry if selected_industry != 'All' else 'all'}.csv"
    )
