import streamlit as st
import pandas as pd
import sqlite3
from db_utils import get_momentum_summary, get_sparkline_data. add_screener_links
import plotly.graph_objects as go

def main():
    st.title("🏆 Top Performing Companies by Sector")

    # Load momentum summary data
    df = get_momentum_summary()

    # Metric toggle
    metric_choice = st.radio(
        "📈 Choose Activity Metric",
        ["hits_7", "hits_30", "hits_60"],
        horizontal=True
    )

    # Compute sector hit counts based on selected metric
    sector_hits = (
        df.groupby("industry")[metric_choice]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={metric_choice: "total_hits"})
    )

    st.markdown(f"### 🧭 Click to Select One or More Sectors (by **{metric_choice}**)")

    # Initialize session state on metric change
    if "selected_sectors" not in st.session_state or st.session_state.get("metric_used") != metric_choice:
        st.session_state.selected_sectors = set()
        st.session_state.metric_used = metric_choice
        # Auto-select hot sectors (hits >= 50)
        for _, row in sector_hits.iterrows():
            if row["total_hits"] >= 50:
                st.session_state.selected_sectors.add(row["industry"])

    # Clear selection button
    if st.button("🧹 Clear Selection"):
        st.session_state.selected_sectors.clear()

    # Inject compact and color-coded button styles
    st.markdown("""
    <style>
    button[kind="primary"] {
        font-size: 0.8rem !important;
        padding: 4px 8px !important;
        margin: 3px !important;
        border-radius: 6px;
        white-space: nowrap;
    }
    .hot { background-color: #ff4d4d; color: white !important; }
    .warm { background-color: #ffa500; color: white !important; }
    .cool { background-color: #d9d9d9; color: black !important; }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(5)
    for i, row in sector_hits.iterrows():
        sector = row["industry"]
        hits = int(row["total_hits"])

        if hits >= 50:
            emoji = "🔥"
            color_class = "hot"
        elif hits >= 20:
            emoji = "✨"
            color_class = "warm"
        else:
            emoji = ""
            color_class = "cool"

        label = f"{emoji} {sector} ({hits})"
        key = f"{sector}_{metric_choice}"

        if cols[i % 5].button(label, key=key):
            if sector in st.session_state.selected_sectors:
                st.session_state.selected_sectors.remove(sector)
            else:
                st.session_state.selected_sectors.add(sector)

    selected_sectors = list(st.session_state.selected_sectors)

    if not selected_sectors:
        st.info("Please select one or more sectors to view top performers.")
        return

    # Filter data by selected sectors and sort
    filtered_df = df[df["industry"].isin(selected_sectors)].sort_values(
        by=["industry", "%_gain_mc"], ascending=[True, False]
    )
    
    filtered_df = add_screener_links(filtered_df)

    st.markdown(f"### 📊 Showing **{len(filtered_df)}** companies from {len(selected_sectors)} selected sector(s)")

    st.markdown(
        filtered_df[["industry", "name", "nse_code", "bse_code", "market_cap", "%_gain_mc", "hits_7", "hits_30", "hits_60", "first_seen_date"]]
        .to_markdown(index=False),
        unsafe_allow_html=True
    )

    st.download_button(
        "📥 Download CSV",
        data=filtered_df.to_csv(index=False),
        file_name=f"top_performers_{metric_choice}.csv"
    )

    # --- Sparklines for momentum trends ---
    st.markdown("### 📈 Company Momentum Sparklines (52-Week High Presence)")

    spark_df = get_sparkline_data()
    spark_df = spark_df[spark_df["name"].isin(filtered_df["name"])]

    all_dates = pd.date_range(spark_df["date"].min(), spark_df["date"].max())

    for company in filtered_df["name"]:
        company_data = spark_df[spark_df["name"] == company]
        presence_series = pd.Series(0, index=all_dates)
        presence_series[company_data["date"]] = 1

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=presence_series.index,
            y=presence_series.values,
            mode="lines",
            line=dict(color="royalblue", width=2),
            name=company
        ))
        fig.update_layout(
            height=80,
            margin=dict(l=20, r=20, t=10, b=20),
            yaxis=dict(visible=False),
            xaxis=dict(visible=False),
            showlegend=False,
        )

        st.markdown(f"**{company}**")
        st.plotly_chart(fig, use_container_width=True)
