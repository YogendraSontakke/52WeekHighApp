import streamlit as st
import pandas as pd
from db_utils import get_all_dates, get_data_for_date
import datetime
from dateutil.relativedelta import relativedelta

def main():
    st.title("📅 Daily 52-Week Highs Viewer")

    dates = get_all_dates()
    if not dates:
        st.warning("No data available.")
        return

    # Convert to datetime objects for reliable sorting.
    dates = sorted([pd.to_datetime(d).date() for d in dates])
    
    min_date_available = dates[0]
    max_date_available = dates[-1]

    # Select mode of date selection, with "Date Range" as default
    date_mode = st.radio(
        "Select Date Mode", 
        ["Single Date", "Date Range", "All Dates"],
        index=1  # Set "Date Range" as default
    )

    daily_df = pd.DataFrame() # Initialize daily_df

    if date_mode == "Single Date":
        # Default to the latest date
        selected_date = st.selectbox(
            "Select a date", 
            dates, 
            index=len(dates) - 1,
            format_func=lambda date: date.strftime("%Y-%m-%d") # Format for display
        )
        daily_df = get_data_for_date(selected_date.strftime("%Y-%m-%d"))
        
    elif date_mode == "Date Range":
        st.subheader("Date Range Selection")

        # Set default values
        end_date_default = max_date_available
        start_date_default = min_date_available
        
        # Use columns for a cleaner layout
        col1, col2 = st.columns([1, 2])

        with col1:
            range_method = st.radio(
                "Define range by:",
                ("Presets", "Last 'y' days", "Last 'x' months")
            )

        with col2:
            if range_method == "Presets":
                preset = st.radio(
                    "Select preset period:",
                    ("1 Day", "Last 7 Days", "Last 14 Days", "Last 1 Month", "Last 3 Months", "Last 6 Months")
                )
                if preset == "1 Day":
                    start_date_default = max_date_available
                elif preset == "Last 7 Days":
                    start_date_default = max_date_available - relativedelta(days=6)
                elif preset == "Last 14 Days":
                    start_date_default = max_date_available - relativedelta(days=13)
                elif preset == "Last 1 Month":
                    start_date_default = max_date_available - relativedelta(months=1)
                elif preset == "Last 3 Months":
                    start_date_default = max_date_available - relativedelta(months=3)
                elif preset == "Last 6 Months":
                    start_date_default = max_date_available - relativedelta(months=6)

            elif range_method == "Last 'y' days":
                num_days = st.number_input("Enter days (y):", min_value=1, value=7)
                start_date_default = max_date_available - relativedelta(days=num_days - 1)
            
            elif range_method == "Last 'x' months":
                num_months = st.number_input("Enter months (x):", min_value=1, value=3)
                start_date_default = max_date_available - relativedelta(months=num_months)

        # Ensure calculated start date is not before the earliest available date
        if start_date_default < min_date_available:
            start_date_default = min_date_available
            st.caption(f"Note: Range start adjusted to the earliest available date: {min_date_available.strftime('%Y-%m-%d')}")

        df = add_screener_links(df)  # <-- convert just before display
        st.markdown(df.to_markdown(index=False), unsafe_allow_html=True)
        
        st.markdown("---")
        st.write("You can adjust the final dates below:")

        start_date = st.date_input(
            "Start date", 
            value=start_date_default,
            min_value=min_date_available, 
            max_value=max_date_available
        )
        end_date = st.date_input(
            "End date", 
            value=end_date_default,
            min_value=min_date_available, 
            max_value=max_date_available
        )

        # Validate date order
        if start_date > end_date:
            st.error("Start date must be before or equal to end date.")
            return

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        selected_dates_str = [d.strftime("%Y-%m-%d") for d in dates if start_date <= d <= end_date]
        if not selected_dates_str:
            st.warning("No data available in the selected date range.")
            return

        dfs = [get_data_for_date(d_str) for d_str in selected_dates_str]
        if dfs:
            daily_df = pd.concat(dfs, ignore_index=True)
            if 'name' in daily_df.columns:
                daily_df.drop_duplicates(subset=['name'], inplace=True)
            else:
                st.error("Error: 'name' column not found.")
                return 
        else:
            st.warning("No data found for the selected date range after fetching.")
            return
            
    else:  # All Dates
        all_dates_str = [d.strftime("%Y-%m-%d") for d in dates]
        dfs = [get_data_for_date(d_str) for d_str in all_dates_str]
        if dfs: 
            daily_df = pd.concat(dfs, ignore_index=True)
            if 'name' in daily_df.columns:
                daily_df.drop_duplicates(subset=['name'], inplace=True)
            else:
                st.error("Error: 'name' column not found.")
                return 
        else:
            st.warning("No data found for all dates after fetching.")
            return

    if daily_df.empty:
        st.warning("No data available for the selected date(s) after processing.")
        return

    # --- Industry Filter
    industries = sorted(daily_df["industry"].dropna().unique().tolist())
    industries.insert(0, "All")
    selected_industry = st.selectbox("Filter by Industry", industries)

    filtered_df = daily_df.copy()
    if selected_industry != "All":
        filtered_df = filtered_df[filtered_df["industry"] == selected_industry]

    # --- Show count and date info
    if date_mode == "Single Date":
        date_info = selected_date.strftime("%Y-%m-%d")
    elif date_mode == "Date Range":
        date_info = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    else:
        date_info = "All Dates"

    st.markdown(
        f"Showing **{len(filtered_df)}** records for **{date_info}**"
        + (f" in **{selected_industry}**" if selected_industry != "All" else "")
    )

    if filtered_df.empty:
        st.info("No records match the filters.")
        return

    # --- Grouped Display by Industry
    st.markdown("---") 
    st.markdown("### 🏭 Grouped View by Industry")

    if 'industry' not in filtered_df.columns:
        st.error("Error: 'industry' column not found.")
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
