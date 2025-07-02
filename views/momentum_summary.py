import streamlit as st
import pandas as pd
from db_utils import get_momentum_summary, get_historical_market_cap, add_screener_links
from plot_utils import market_cap_line_chart


def main():
    st.title("📈 Momentum Summary")

    df = get_momentum_summary()
    if df.empty:
        st.warning("No momentum data available.")
        return

    # --- Sidebar Filters ------------------------------------------------
    st.sidebar.header("Filters")

    industries = ["All"] + sorted(df["industry"].dropna().unique().tolist())
    selected_industry = st.sidebar.selectbox("Filter by Industry", industries)

    min_hits = st.sidebar.slider("Minimum hits in last 30 days", 0, 30, 1)
    min_gain = st.sidebar.slider("Min % Market‑Cap Gain Since First Seen", 0, 500, 0)

    # --- Filtering ------------------------------------------------------
    filtered_df = df.copy()
    if selected_industry != "All":
        filtered_df = filtered_df[filtered_df["industry"] == selected_industry]

    filtered_df = filtered_df[
        (filtered_df["hits_30"] >= min_hits) & (filtered_df["%_gain_mc"] >= min_gain)
    ]

    st.markdown(f"Showing **{len(filtered_df)}** companies meeting criteria.")

    # --- Grouping Choice -----------------------------------------------
    grouping_options = ["None", "industry", "sector"]
    valid_grouping_options = [
        opt for opt in grouping_options if opt == "None" or opt in filtered_df.columns
    ]
    group_by_col = st.selectbox(
        "Group by",
        valid_grouping_options,
        index=valid_grouping_options.index("industry")
        if "industry" in valid_grouping_options
        else 0,
    )

    st.markdown("---")

    # --- Display --------------------------------------------------------
    if group_by_col != "None":
        st.markdown(f"### 🏭 Grouped View by {group_by_col.capitalize()}")

        filtered_df[group_by_col] = filtered_df[group_by_col].fillna("None")

        grouped = (
            filtered_df
            .sort_values([group_by_col, "hits_30", "hits_7"], ascending=[True, False, False])
            .groupby(group_by_col)
        )

        for group_name, group_df in grouped:
            st.markdown(f"#### 🏷️ {group_name} ({len(group_df)} companies)")

            display_cols = [
                "name", "nse_code", "bse_code",
                "market_cap", "first_market_cap", "%_gain_mc",
                "hits_7", "hits_30", "hits_60", "first_seen_date"
            ]
            display_df = group_df[display_cols].copy()
            display_df = display_df.rename(columns={"%_gain_mc": "Δ% MCap"})
            display_df = add_screener_links(display_df)

            st.markdown(display_df.to_markdown(index=False), unsafe_allow_html=True)

    else:
        display_cols = [
            "industry", "name", "nse_code", "bse_code",
            "market_cap", "first_market_cap", "%_gain_mc",
            "hits_7", "hits_30", "hits_60", "first_seen_date"
        ]
        display_df = filtered_df[display_cols].copy()
        display_df = display_df.rename(columns={"%_gain_mc": "Δ% MCap"})
        display_df = add_screener_links(display_df)

        st.markdown(display_df.to_markdown(index=False), unsafe_allow_html=True)


    # --- Download -------------------------------------------------------
    st.download_button(
        "📥 Download CSV", filtered_df.to_csv(index=False), "momentum_summary.csv"
    )

    st.markdown("---")

    # --- Market‑Cap Trend ----------------------------------------------
    st.header("Market‑Cap Trend")
    if not filtered_df.empty:
        selected_stock = st.selectbox(
            "Select Company to View Market‑Cap Trend",
            options=sorted(filtered_df["name"].unique()),
            key="market_cap_stock_selector",
        )
        if selected_stock:
            show_market_cap_trend(selected_stock)
    else:
        st.info("No companies to display market‑cap trend.")


def show_market_cap_trend(selected_stock: str):
    try:
        hist_data = get_historical_market_cap()
        stock_data = hist_data[hist_data["name"] == selected_stock]
        if not stock_data.empty:
            fig = market_cap_line_chart(stock_data, selected_stock)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No market‑cap data available for {selected_stock}")
    except Exception as e:
        st.error(f"Could not load market‑cap data. Error: {e}")


if __name__ == "__main__":
    main()
