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

    daily_df = pd.DataFrame() # Initialize daily_df as an empty DataFrame

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
        if dfs: # Ensure there's data to concatenate
            daily_df = pd.concat(dfs, ignore_index=True)
            # --- Corrected: Use 'name' to drop duplicates ---
            # Check if 'name' column exists before attempting to drop duplicates
            if 'name' in daily_df.columns:
                daily_df.drop_duplicates(subset=['name'], inplace=True)
            else:
                st.error("Error: 'name' column not found in the DataFrame for unique identification. Please check your data source.")
                return # Stop execution if a critical column is missing
        else:
            st.warning("No data found for the selected date range after fetching.")
            return # Exit if no data
            
    else:  # All Dates
        # Load and concatenate data for all dates
        dfs = [get_data_for_date(d) for d in dates]
        if dfs: # Ensure there's data to concatenate
            daily_df = pd.concat(dfs, ignore_index=True)
            # --- Corrected: Use 'name' to drop duplicates ---
            # Check if 'name' column exists before attempting to drop duplicates
            if 'name' in daily_df.columns:
                daily_df.drop_duplicates(subset=['name'], inplace=True)
            else:
                st.error("Error: 'name' column not found in the DataFrame for unique identification. Please check your data source.")
                return # Stop execution if a critical column is missing
        else:
            st.warning("No data found for all dates after fetching.")
            return # Exit if no data

    if daily_df.empty:
        st.warning("No data available for the selected date(s) after processing.")
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
    st.markdown("---") # Add a separator for better visual organization
    st.markdown("### 🏭 Grouped View by Industry")

    # Ensure 'industry' column exists before grouping
    if 'industry' not in filtered_df.columns:
        st.error("Error: 'industry' column not found. Cannot group by industry.")
        return

    grouped = (
        filtered_df
        .sort_values(["industry", "market_cap"], ascending=[True, False])
        .groupby("industry")
    )

    for industry, group_df in grouped:
        st.markdown(f"#### 🏷️ {industry} ({len(group_df)} companies)")
        # Create a copy to avoid SettingWithCopyWarning and drop 'industry' for display
        display_df = group_df.copy()
        if 'industry' in display_df.columns: # Ensure 'industry' column is present before dropping
            display_df = display_df.drop(columns=["industry"])
        st.dataframe(
            display_df,
            use_container_width=True,
        )

    # --- Download
    filename_date_part = date_info.replace(" ", "_").replace("to", "-").lower()
    st.download_button(
        "📥 Download CSV",
        data=filtered_df.to_csv(index=False),
        file_name=f"highs_{filename_date_part}_{selected_industry if selected_industry != 'All' else 'all'}.csv"
    )

if __name__ == "__main__":
    main()
