import streamlit as st
import pandas as pd
from db_utils import get_momentum_summary, get_historical_market_cap
from plot_utils import market_cap_line_chart

def main():
    st.title("📈 Momentum Summary")

    df = get_momentum_summary()
    if df.empty:
        st.warning("No momentum data available.")
        return

    # Rename columns to more meaningful names
    df = df.rename(columns={
        "hits_7": "weekly_hits",
        "hits_30": "monthly_hits",
        "hits_60": "bi_monthly_hits"
    })

    # --- Sidebar for Filters ---
    st.sidebar.header("Filters")
    
    industries = ["All"] + sorted(df['industry'].dropna().unique().tolist())
    selected_industry = st.sidebar.selectbox("Filter by Industry", industries)
    
    min_hits = st.sidebar.slider("Minimum Monthly Hits (last 30 days)", 0, 30, 1)
    min_gain = st.sidebar.slider("Min % Market Cap Gain Since First Seen", 0, 500, 0)

    # Filter the DataFrame based on sidebar selections
    filtered_df = df.copy()
    if selected_industry != "All":
        filtered_df = filtered_df[filtered_df['industry'] == selected_industry]

    filtered_df = filtered_df[
        (filtered_df['monthly_hits'] >= min_hits) &
        (filtered_df['%_gain_mc'] >= min_gain)
    ]

    st.markdown(f"Showing **{len(filtered_df)}** companies meeting criteria.")

    # --- Grouping Logic ---
    grouping_options = ["None", "industry", "sector"]
    valid_grouping_options = [opt for opt in grouping_options if opt == "None" or opt in filtered_df.columns]
    
    group_by_col = st.selectbox(
        "Group by", 
        valid_grouping_options, 
        index=valid_grouping_options.index("industry") if "industry" in valid_grouping_options else 0
    )

    st.markdown("---")

    # Display grouped or ungrouped data
    if group_by_col != "None":
        st.markdown(f"### 🏭 Grouped View by {group_by_col.capitalize()}")
        grouped = (
            filtered_df
            .sort_values([group_by_col, "monthly_hits", "weekly_hits"], ascending=[True, False, False])
            .groupby(group_by_col)
        )
        for group_name, group_df in grouped:
            st.markdown(f"#### 🏷️ {group_name} ({len(group_df)} companies)")
            display_df = group_df.copy().drop(columns=[group_by_col])
            st.dataframe(display_df, use_container_width=True)
    else:
        st.dataframe(filtered_df.sort_values(by=["monthly_hits", "weekly_hits"], ascending=False), use_container_width=True)

    # --- Download Button ---
    st.download_button("📥 Download CSV", filtered_df.to_csv(index=False), "momentum_summary.csv")

    st.markdown("---")

    # --- Market Cap Trend Chart ---
    st.header("Market Cap Trend")
    if not filtered_df.empty:
        selected_stock = st.selectbox(
            "Select Company to View Market Cap Trend", 
            options=sorted(filtered_df["name"].unique()),
            key="market_cap_stock_selector"
        )
        if selected_stock:
            show_market_cap_trend(selected_stock)
    else:
        st.info("No companies to display market cap trend.")

def show_market_cap_trend(selected_stock):
    """Fetches and displays the market cap trend for a selected stock."""
    try:
        hist_data = get_historical_market_cap()
        stock_data = hist_data[hist_data["name"] == selected_stock]
        if not stock_data.empty:
            fig = market_cap_line_chart(stock_data, selected_stock)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No market cap data available for {selected_stock}")
    except Exception as e:
        st.error(f"Could not load market cap data. Error: {e}")

if __name__ == "__main__":
    main()