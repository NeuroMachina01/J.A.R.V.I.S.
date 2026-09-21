import streamlit as st
import pandas as pd
import plotly.express as px
import re
import os

st.set_page_config(page_title="JARVIS Evals Dashboard", layout="wide")

st.title("📊 JARVIS Agentic Evaluation Dashboard")
st.markdown("Automated Benchmarking & LLM-as-a-Judge reporting for JARVIS architectures.")

@st.cache_data
def load_data():
    log_path = "tests/eval_output.log"
    if not os.path.exists(log_path):
        return pd.DataFrame()

    with open(log_path, "r", encoding="utf-16", errors="ignore") as f:
        content = f.read()
    
    # Remove null bytes from powershell encoding quirks
    content = content.replace('\x00', '')

    tests = []
    blocks = content.split("[TEST ")
    for block in blocks[1:]:
        try:
            test_num_match = re.search(r"^(\d+)\]\s*Query:\s*\"(.*?)\"", block)
            expected_match = re.search(r"-> Expected Agent\s*:\s*(.*)", block)
            actual_match = re.search(r"-> Actual Agent\s*:\s*(.*?)\s*\[(.*?)\]", block)
            latency_match = re.search(r"-> Latency\s*:\s*(\d+)ms\s*\[(.*?)\]", block)
            score_match = re.search(r"-> Judge Score\s*:\s*(\d+)/5\s*\[(.*?)\]\s*\((.*?)\)", block, re.DOTALL)
            
            if test_num_match and expected_match and actual_match and latency_match and score_match:
                tests.append({
                    "Test ID": int(test_num_match.group(1)),
                    "Query": test_num_match.group(2).strip(),
                    "Expected Agent": expected_match.group(1).strip(),
                    "Actual Agent": actual_match.group(1).strip(),
                    "Routing": actual_match.group(2).strip(),
                    "Latency (ms)": int(latency_match.group(1)),
                    "Latency Status": latency_match.group(2).strip(),
                    "Score": int(score_match.group(1)),
                    "Score Status": score_match.group(2).strip(),
                    "Feedback": score_match.group(3).strip().replace('\n', ' ')
                })
        except Exception as e:
            continue
            
    return pd.DataFrame(tests)

df = load_data()

if df.empty:
    st.warning("No evaluation data found. Please run the evaluation pipeline first.")
else:
    # ----------------- TOP LEVEL METRICS -----------------
    st.markdown("### Top-Level Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    total_tests = len(df)
    pass_rate = (len(df[df["Score"] >= 4]) / total_tests) * 100
    avg_latency = df["Latency (ms)"].mean()
    routing_acc = (len(df[df["Routing"] == "PASS"]) / total_tests) * 100
    
    col1.metric("Total Evals Run", total_tests)
    col2.metric("Overall Pass Rate (Score ≥ 4)", f"{pass_rate:.1f}%")
    col3.metric("Average Latency", f"{avg_latency:.0f} ms", delta_color="inverse")
    col4.metric("Routing Accuracy", f"{routing_acc:.1f}%")
    
    st.divider()

    # ----------------- VISUALIZATIONS -----------------
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("#### LLM-as-a-Judge Scores")
        # Ensure all scores 1-5 exist for the pie chart
        score_counts = df["Score"].value_counts().reset_index()
        score_counts.columns = ["Score", "Count"]
        
        fig_scores = px.pie(
            score_counts, 
            values="Count", 
            names="Score", 
            color="Score",
            color_discrete_map={5: "#2ecc71", 4: "#27ae60", 3: "#f1c40f", 2: "#e67e22", 1: "#e74c3c"},
            hole=0.4
        )
        st.plotly_chart(fig_scores, use_container_width=True)

    with colB:
        st.markdown("#### Agent Latency Analysis")
        # Color code latency: Green < 2000, Yellow < 5000, Red > 5000
        df["Latency Color"] = df["Latency (ms)"].apply(lambda x: "Fast (<2s)" if x < 2000 else ("Medium (2-5s)" if x < 5000 else "Slow (>5s)"))
        
        fig_latency = px.bar(
            df, 
            x="Test ID", 
            y="Latency (ms)", 
            color="Latency Color",
            color_discrete_map={"Fast (<2s)": "#2ecc71", "Medium (2-5s)": "#f1c40f", "Slow (>5s)": "#e74c3c"},
            hover_data=["Query", "Actual Agent"]
        )
        st.plotly_chart(fig_latency, use_container_width=True)
        
    st.divider()

    # ----------------- DATA TABLE -----------------
    st.markdown("### Evaluation Traces")
    st.markdown("Examine the raw reasoning and feedback from the Judge LLM.")
    
    # Styled dataframe
    def color_score(val):
        color = 'green' if val >= 4 else ('orange' if val == 3 else 'red')
        return f'color: {color}; font-weight: bold'
        
    def color_routing(val):
        color = 'green' if val == 'PASS' else 'red'
        return f'color: {color}; font-weight: bold'

    styled_df = df[["Test ID", "Query", "Expected Agent", "Actual Agent", "Routing", "Score", "Latency (ms)", "Feedback"]].style \
        .applymap(color_score, subset=['Score']) \
        .applymap(color_routing, subset=['Routing'])
        
    st.dataframe(styled_df, use_container_width=True, height=400)
