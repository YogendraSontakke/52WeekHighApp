import streamlit as st
from db_utils import get_momentum_summary

def main():
    st.title("🏆 Top Performing Companies by Sector")

    df = get_momentum_summary()

    # 🔝 Quick Select Top 10 Sectors by company count
    st.markdown("### ⚡ Quick Select Top 10 Sectors")

    top_sectors = df["industry"].value_counts().head(10).index.tolist()
    cols = st.columns(5)
    selected_sector = None

    for i, sector in enumerate(top_sectors):
        if cols[i % 5].button(sector):
            selected_sector = sector

    # 🧠 Fallback dropdown if none selected via button
    if not selected_sector:
        st.markdown("### 🧠 Or Select Any Sector")
        all_sectors = sorted(df["industry"].dropna().unique())
        selected_sector = st.selectbox("Select Sector", all_sectors)

    # 🎯 Display data for selected sector
    filtered_df = df[df["industry"] == selected_sector].sort_values(by="%_gain_mc", ascending=False)

    st.markdown(f"### 📊 Showing **{len(filtered_df)}** companies in **{selected_sector}**")
    st.dataframe(
        filtered_df[["name", "nse_code", "market_cap", "%_gain_mc", "hits_30", "first_seen_date"]],
        use_container_width=True
    )

    st.download_button(
        "📥 Download CSV",
        data=filtered_df.to_csv(index=False),
        file_name=f"{selected_sector}_top_performers.csv"
    )
