import streamlit as st
import pandas as pd
from db_utils import get_momentum_summary

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
        for _, row in sector_hits.iterrows():
            if row["total_hits"] >= 50:
                st.session_state.selected_sectors.add(row["industry"])

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🧹 Clear Selection"):
            st.session_state.selected_sectors.clear()

    with col2:
        if st.button("✅ Select All"):
            st.session_state.selected_sectors = set(sector_hits["industry"].tolist())
        

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

    # --- Grouped Display by Industry
    st.markdown("### 🏭 Grouped View by Industry")

    grouped = (
        filtered_df
        .sort_values(["industry", "%_gain_mc"], ascending=[True, False])
        .groupby("industry")
    )

    for industry, group_df in grouped:
        st.markdown(f"#### 🏷️ {industry} ({len(group_df)} companies)")
        display_df = group_df.copy()
        if 'industry' in display_df.columns:
            display_df = display_df.drop(columns=["industry"])
        st.dataframe(
            display_df[["name", "nse_code", "market_cap", "%_gain_mc", "hits_7", "hits_30", "hits_60", "first_seen_date"]],
            use_container_width=True,
        )

    # --- Download Button
    st.download_button(
        "📥 Download CSV",
        data=filtered_df.to_csv(index=False),
        file_name=f"top_performers_{metric_choice}.csv"
    )

if __name__ == "__main__":
    main()