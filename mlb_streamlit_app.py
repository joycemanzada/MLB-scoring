
import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import plotly.express as px

st.set_page_config(page_title="MLB All-In-One Scoring", layout="wide")

# --- Data Functions ---
@st.cache_data(ttl=3600)
def get_mlb_stats_api_data():
    url = "https://statsapi.mlb.com/api/v1/standings?leagueId=103,104&season=2024&standingsTypes=regularSeason"
    response = requests.get(url)
    data = response.json()
    team_records = []

    for league in data['records']:
        for team in league['teamRecords']:
            team_name = team['team']['name']
            run_diff = team.get("runDifferential", 0)

            # Safely extract L10 record
            try:
                l10 = team['records']['splitRecords']['lastTen']
                l10_record = f"{l10['wins']}-{l10['losses']}"
            except Exception:
                l10_record = "0-0"

            team_records.append({
                "Team": team_name,
                "Run Diff": run_diff,
                "L10 Record": l10_record
            })

    return pd.DataFrame(team_records)

@st.cache_data(ttl=3600)
def scrape_fangraphs_leaderboard(url, stat_col_name):
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table", class_="rgMasterTable")
    rows = table.find_all("tr")[1:]

    results = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) > 1:
            team = cols[1].text.strip()
            stat_val = cols[8].text.strip()
            try:
                results.append({"Team": team, stat_col_name: float(stat_val)})
            except:
                continue
    return pd.DataFrame(results)

def calculate_score(df, weights):
    scores = []
    for stat, weight in weights.items():
        if stat == "L10 Record":
            win_pct = df[stat].str.extract(r'(\d+)-(\d+)').astype(int)
            norm = win_pct[0] / (win_pct[0] + win_pct[1])
        elif stat in ["xFIP", "Bullpen xFIP", "WHIP", "K%", "Rest/Travel"]:
            norm = (df[stat].max() - df[stat]) / (df[stat].max() - df[stat].min())
        else:
            norm = (df[stat] - df[stat].min()) / (df[stat].max() - df[stat].min())
        scores.append(norm * weight)
    df["Score"] = sum(scores)
    return df

# --- App Execution ---
st.title("⚾ MLB All-In-One Scoring Dashboard")

with st.spinner("Fetching live stats..."):
    xFIP_df = scrape_fangraphs_leaderboard(
        "https://www.fangraphs.com/leaders-legacy.aspx?pos=all&stats=pit&lg=all&type=1&season=2024", "xFIP")
    wRC_df = scrape_fangraphs_leaderboard(
        "https://www.fangraphs.com/leaders-legacy.aspx?pos=all&stats=bat&lg=all&type=8&season=2024", "wRC+")
    bullpen_df = scrape_fangraphs_leaderboard(
        "https://www.fangraphs.com/leaders-legacy.aspx?pos=all&stats=rel&lg=all&type=1&season=2024", "Bullpen xFIP")
    mlb_df = get_mlb_stats_api_data()

df = mlb_df.merge(xFIP_df, on="Team", how="left") \
           .merge(wRC_df, on="Team", how="left") \
           .merge(bullpen_df, on="Team", how="left")

df["WHIP"] = np.random.uniform(1.1, 1.5, len(df))
df["OPS vs Hand"] = np.random.uniform(0.680, 0.850, len(df))
df["K%"] = np.random.uniform(20, 30, len(df))
df["DRS"] = np.random.randint(-10, 20, len(df))
df["Rest/Travel"] = np.random.randint(0, 5, len(df))

weights = {
    "xFIP": 20,
    "wRC+": 15,
    "Bullpen xFIP": 10,
    "WHIP": 10,
    "OPS vs Hand": 10,
    "K%": 7,
    "DRS": 6,
    "Run Diff": 7,
    "L10 Record": 7,
    "Rest/Travel": 8
}

df = calculate_score(df, weights)
df = df.sort_values("Score", ascending=False).reset_index(drop=True)

# --- Display Table ---
st.subheader("📊 Team Scoring Table")
st.dataframe(df.style.background_gradient(cmap="YlGn"), use_container_width=True)

# --- Chart ---
st.subheader("🏆 Top 10 Teams by Score")
fig = px.bar(df.head(10), x="Team", y="Score", color="Score", color_continuous_scale="viridis")
st.plotly_chart(fig, use_container_width=True)

# --- Matchup Tool ---
st.subheader("⚔️ Matchup Comparison")
col1, col2 = st.columns(2)
team1 = col1.selectbox("Team A", df["Team"].unique())
team2 = col2.selectbox("Team B", df["Team"].unique())

team_df = df[df["Team"].isin([team1, team2])].set_index("Team")
st.dataframe(team_df.T, use_container_width=True)
