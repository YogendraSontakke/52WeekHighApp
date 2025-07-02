import streamlit as st
import pandas as pd
from db_utils import get_momentum_summary, get_sparkline_data, add_screener_links
import plotly.graph_objects as go


def main():
    st.title("🏆 Top Performing Companies by Sector")

    df = get_momentum_summary()

    metric_choice = st.radio(
        "📈 Choose Activity Metric", ["hits_7", "hits_30", "hits_60"], horizontal=True
    )

    # --- Sector Hit Counts ---------------------------------------------
    sector_hits = (
        df.groupby("industry")[metric_choice]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={metric_choice: "total_hits"})
    )

    st.markdown(f"### 🧭 Click to Select One or More Sectors (by **{metric_choice}**)")

    # --- Sector‑Selection State ----------------------------------------
    if "selected_sectors" not in st.session_state or st.session_state.get(
        "metric_used"
    ) != metric_choice:
        st.session_state.selected_sectors = set()
        st.session_state.metric_used = metric_choice
        for _, row in sector_hits.iterrows():
            if row["total_hits"] >= 50:  # auto‑select hot sectors
                st.session_state.selected_sectors.add(row["industry"])

    if st.button("🧹 Clear Selection"):
        st.session_state.selected_sectors.clear()

    # --- Pretty Buttons -------------------------------------------------
    st.markdown(
        """
    <style>
    button[kind="primary"]{
        font-size:0.8rem!important;padding:4px 8px!important;margin:3px!important;
        border-radius:6px;white-space:nowrap;
    }
    .hot{background:#ff4d4d;color:white!important;}
    .warm{background:#ffa500;color:white!important;}
    .cool{background:#d9d9d9;color:black!important;}
    </style>
    """,
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    for i, row in sector_hits.iterrows():
        sector, hits = row["industry"], int(row["total_hits"])
        emoji, color_class = (
            ("🔥", "hot")
            if hits >= 50
            else ("✨", "warm")
            if hits >= 20
            else ("", "cool")
        )
        label = f"{emoji} {sector} ({hits})"
        if cols[i % 5].button(label, key=f"{sector}_{metric_choice}"):
            if sector in st.session_state.selected_sectors:
                st.session_state.selected_sectors.remove(sector)
            else:
                st.session_state.selected_sectors.add(sector)

    selected_sectors = list(st.session_state.selected_sectors)
    if not selected_sectors:
        st.info("Please select one or more sectors to view top performers.")
        return

    # --- Filter & Sort --------------------------------------------------
    filtered_df = df[df["industry"].isin(selected_sectors)].sort_values(
        by=["industry", "%_gain_mc"], ascending=[True, False]
    )

    st.markdown(
        f"### 📊 Showing **{len(filtered_df)}** companies from {len(selected_sectors)} selected sector(s)"
    )

    # --- Display Table with Links --------------------------------------
    display_df = add_screener_links(
        filtered_df[
            [
                "industry",
                "name",
                "nse_code",
                "bse_code",
                "market_cap",
                "%_gain_mc",
                "hits_7",
                "hits_30",
                "hits_60",
                "first_seen_date",
            ]
        ].copy()
    )
    st.markdown(display_df.to_markdown(index=False), unsafe_allow_html=True)

    st.download_button(
        "📥 Download CSV",
        data=filtered_df.to_csv(index=False),
        file_name=f"top_performers_{metric_choice}.csv",
    )

    # --- Sparklines -----------------------------------------------------
    st.markdown("### 📈 Company Momentum Sparklines (52‑Week‑High Presence)")

    spark_df = get_sparkline_data()
    spark_df = spark_df[spark_df["name"].isin(filtered_df["name"])]

    all_dates = pd.date_range(spark_df["date"].min(), spark_df["date"].max())

    for company in filtered_df["name"]:
        company_data = spark_df[spark_df["name"] == company]
        presence_series = pd.Series(0, index=all_dates)
        presence_series[company_data["date"]] = 1

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=presence_series.index,
                y=presence_series.values,
                mode="lines",
                line=dict(width=2),
                name=company,
            )
        )
        fig.update_layout(
            height=80,
            margin=dict(l=20, r=20, t=10, b=20),
            yaxis=dict(visible=False),
            xaxis=dict(visible=False),
            showlegend=False,
        )

        st.markdown(f"**{company}**")
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
