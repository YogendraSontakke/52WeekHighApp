import streamlit as st
import pandas as pd
from db_utils import get_all_dates, get_data_for_date
import datetime # Import datetime for date objects

def main():
    st.title("📅 Daily 52-Week Highs Viewer")

    dates = get_all_dates()
    if not dates:
        st.warning("No data available.")
        return

    # Ensure dates are sorted in ascending order (important for min_date, max_date)
    # Convert to datetime objects for reliable sorting.
    dates = sorted([pd.to_datetime(d).date() for d in dates])
																					  
																										 
																		 
    
    # Now, min_date will reliably be the earliest date and max_date the latest
    min_date_available = dates[0]
    max_date_available = dates[-1]

    # Select mode of date selection
    date_mode = st.radio("Select Date Mode", ["Single Date", "Date Range", "All Dates"])

    daily_df = pd.DataFrame() # Initialize daily_df as an empty DataFrame

    if date_mode == "Single Date":
        # To default to the latest date, we set the index of the selectbox
        # to the last element of the sorted `dates` list.
        selected_date = st.selectbox(
            "Select a date", 
            dates, 
            index=len(dates) - 1
        )
        # Ensure get_data_for_date can handle datetime.date objects or convert
        daily_df = get_data_for_date(selected_date.strftime("%Y-%m-%d")) # Convert back to string for db_utils if it expects string
        
    elif date_mode == "Date Range":
        # Use the reliably sorted min_date_available and max_date_available
        start_date = st.date_input(
            "Start date", 
            value=min_date_available, # Default to the earliest available date
            min_value=min_date_available, 
            max_value=max_date_available
        )
        end_date = st.date_input(
            "End date", 
            value=max_date_available, # Default to the latest available date
            min_value=min_date_available, 
            max_value=max_date_available
        )

        # Validate date order (user input validation)
        if start_date > end_date:
            st.error("Start date must be before or equal to end date.")
            return

        # Convert dates to strings matching your date format in db_utils (assuming 'YYYY-MM-DD')
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Filter dates in the range (from the original `dates` list which is now sorted and converted)
        selected_dates_str = [d.strftime("%Y-%m-%d") for d in dates if start_date <= d <= end_date]
        if not selected_dates_str:
            st.warning("No data available in the selected date range.")
            return

        # Load and concatenate data for all selected dates
        dfs = [get_data_for_date(d_str) for d_str in selected_dates_str]
        if dfs: # Ensure there's data to concatenate
            daily_df = pd.concat(dfs, ignore_index=True)
            if 'name' in daily_df.columns:
                daily_df.drop_duplicates(subset=['name'], inplace=True)
            else:
                st.error("Error: 'name' column not found in the DataFrame for unique identification. Please check your data source.")
                return 
        else:
            st.warning("No data found for the selected date range after fetching.")
            return
            
    else:  # All Dates
        # Load and concatenate data for all dates
        # Convert dates back to string for get_data_for_date
        all_dates_str = [d.strftime("%Y-%m-%d") for d in dates]
        dfs = [get_data_for_date(d_str) for d_str in all_dates_str]
        if dfs: 
            daily_df = pd.concat(dfs, ignore_index=True)
            if 'name' in daily_df.columns:
                daily_df.drop_duplicates(subset=['name'], inplace=True)
            else:
                st.error("Error: 'name' column not found in the DataFrame for unique identification. Please check your data source.")
                return 
        else:
            st.warning("No data found for all dates after fetching.")
            return

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
        date_info = selected_date.strftime("%Y-%m-%d") # Format for display
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
    st.markdown("---") 
    st.markdown("### 🏭 Grouped View by Industry")

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
        display_df = group_df.copy()
        if 'industry' in display_df.columns:
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
