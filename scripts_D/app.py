# -*- coding: utf-8 -*-
import json
import os as _os
import sys
import tempfile
from pathlib import Path

import streamlit as st

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts_D.visualization import (
    _OPINION_COLORS, _OPINION_ZH,
    get_agent_table_data, get_debate_summary,
    get_event_info, get_timeline_data,
    render_metrics, render_social_graph, render_social_graph_pyvis,
)

st.set_page_config(
    page_title="AlTown - Multi-Agent Social Simulator",
    page_icon="\U0001f3db",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_data
def _load_state_from_path(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _opinion_color(opinion):
    return _OPINION_COLORS.get(opinion, "#95a5a6")

if "state" not in st.session_state:
    demo_path = _PROJECT_ROOT / "output_D" / "demo_state.json"
    if demo_path.exists():
        st.session_state.state = _load_state_from_path(str(demo_path))
    else:
        st.session_state.state = {"event": {}, "agents": {}, "messages": [], "relationships": {}, "debate": {}, "metrics": {}, "timeline": []}

st.sidebar.title("AlTown")
st.sidebar.caption("Multi-Agent Debate & Memory Evolution Social Simulator")
st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader("Load state.json", type=["json"])
if uploaded_file is not None:
    raw = json.loads(uploaded_file.read().decode("utf-8"))
    st.session_state.state = raw
    st.sidebar.success(f"Loaded {len(raw.get('agents',{}))} agents, {len(raw.get('messages',[]))} messages")

st.sidebar.markdown("---")
if st.sidebar.button("Load demo data"):
    demo_path = _PROJECT_ROOT / "output_D" / "demo_state.json"
    if demo_path.exists():
        st.session_state.state = _load_state_from_path(str(demo_path))
        st.rerun()
    else:
        st.sidebar.error("demo_state.json not found")

st.sidebar.markdown("---")
evt = get_event_info(st.session_state.state)
if evt:
    st.sidebar.info(evt.get("content", "(none)"))

st.title("AlTown: Multi-Agent Social Simulator")
st.markdown("---")

tab_agents, tab_messages, tab_graph, tab_metrics, tab_debate, tab_timeline = st.tabs([
    "Agent Status", "Message Log", "Social Graph", "Metrics", "Debate Details", "Timeline Replay",
])

state = st.session_state.state

with tab_agents:
    st.subheader("Agent Current Status")
    rows = get_agent_table_data(state)
    if rows:
        import pandas as pd
        df = pd.DataFrame(rows)
        def _clr(val):
            c = "#2ecc71" if val == "\u76f8\u4fe1" else "#e74c3c" if val == "\u4e0d\u76f8\u4fe1" else "#95a5a6"
            return f"background-color: {c}; color: white"
        styled = df.style.map(_clr, subset=["Opinion"])
        st.dataframe(styled, width='stretch', hide_index=True)
        cols = st.columns(3)
        ops = [r["Opinion"] for r in rows]
        cols[0].metric("Believe", ops.count("\u76f8\u4fe1"))
        cols[1].metric("Reject", ops.count("\u4e0d\u76f8\u4fe1"))
        cols[2].metric("Uncertain", ops.count("\u89c2\u671b"))
        with st.expander("Agent Memory Details"):
            for aid, a in state.get("agents", {}).items():
                st.markdown(f"**{a.get('name','')} ({aid})**")
                for m in a.get("memory", [])[-5:]:
                    st.caption(f"  T{m.get('timestep')} {m.get('content','')}")
    else:
        st.warning("No agent data in current state.")

with tab_messages:
    st.subheader("Message Log")
    msgs = state.get("messages", [])
    if msgs:
        max_ts = max(m.get("timestep", 0) for m in msgs)
        sel = st.select_slider("Filter by timestep", options=list(range(max_ts + 1)), value=max_ts)
        filtered = [m for m in msgs if m.get("timestep") == sel]
        agents = state.get("agents", {})
        for msg in filtered:
            sp = agents.get(msg.get("speaker",""), {}).get("name", msg.get("speaker",""))
            rv = agents.get(msg.get("receiver",""), {}).get("name", msg.get("receiver",""))
            c = msg.get("content",""); st2 = _OPINION_ZH.get(msg.get("stance",""),"")
            color = _opinion_color(msg.get("stance","uncertain"))
            st.markdown(
                f"<div style='padding:8px;margin:4px 0;border-left:4px solid {color};background:#f8f9fa;border-radius:4px;'>"
                f"<strong>{sp}</strong> -> <strong>{rv}</strong> "
                f"<span style='color:{color};font-weight:bold;'>[{st2}]</span> ({msg.get('confidence',0):.2f})<br>{c}</div>",
                unsafe_allow_html=True)
        if not filtered:
            st.caption("No messages at this timestep.")
    else:
        st.warning("No messages in current state.")

with tab_graph:
    st.subheader("Social Relationship Graph")
    col1, col2 = st.columns([3, 1])
    with col2:
        use_pyvis = st.toggle("Use interactive pyvis", value=False)
    with col1:
        if use_pyvis:
            hp = _os.path.join(tempfile.gettempdir(), "sg.html")
            r = render_social_graph_pyvis(state, hp)
            if r and _os.path.exists(r):
                with open(r, encoding="utf-8") as f:
                    st.components.v1.html(f.read(), height=650)
            else:
                st.warning("pyvis not available, fallback to static.")
                p = render_social_graph(state)
                if p: st.image(p, width='stretch')
        else:
            p = render_social_graph(state)
            if p: st.image(p, width='stretch')
            else: st.warning("Cannot render graph.")
    with st.expander("Legend"):
        st.markdown("- Green=Believe, Red=Reject, Gray=Uncertain")
        st.markdown("- Edge thickness = trust strength")

with tab_metrics:
    st.subheader("Experiment Metrics")
    p = render_metrics(state)
    if p: st.image(p, width='stretch')
    else: st.warning("No metrics data.")
    if state.get("metrics"):
        with st.expander("Raw metrics"):
            st.json(state["metrics"])

with tab_debate:
    st.subheader("Debate Details")
    debate = state.get("debate", {})
    if debate and debate.get("triggered"):
        st.success(f"Debate triggered | Rounds: {debate.get('round', 0)}")
        if debate.get("summary"):
            st.info(f"**Summary**: {debate['summary']}")
        votes = debate.get("votes", {})
        if votes:
            import pandas as pd
            agents = state.get("agents", {})
            rows = [{"Agent": agents.get(a,{}).get("name",a), "Vote": _OPINION_ZH.get(v.get("vote",""),""), "Confidence": v.get("confidence",0)} for a, v in votes.items()]
            st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        claims = debate.get("claims", [])
        if claims:
            agents = state.get("agents", {})
            for cl in claims[-8:]:
                an = agents.get(cl.get("agent",""),{}).get("name", cl.get("agent",""))
                color = _opinion_color(cl.get("stance","uncertain"))
                st.markdown(
                    f"<div style='padding:6px;margin:3px 0;border-left:4px solid {color};background:#f8f9fa;border-radius:4px;'>"
                    f"<strong>T{cl.get('timestep','?')} {an}</strong> "
                    f"<span style='color:{color};font-weight:bold;'>[{_OPINION_ZH.get(cl.get('stance',''),'')}]</span> "
                    f"({cl.get('confidence',0):.2f})<br>{cl.get('claim','')}</div>", unsafe_allow_html=True)
    else:
        st.warning("No debate triggered in current state.")

with tab_timeline:
    st.subheader("Timeline Replay")
    tl = state.get("timeline", [])
    if tl:
        sel = st.selectbox("Select timestep", [t["timestep"] for t in tl], index=len(tl)-1)
        snap = next((t for t in tl if t["timestep"] == sel), None)
        if snap:
            c1, c2, c3 = st.columns(3)
            c1.metric("Spread Rate", f"{snap.get('spread_rate',0):.0%}")
            c2.metric("Avg Confidence", f"{snap.get('average_confidence',0):.2f}")
            c3.metric("Messages", snap.get("message_count",0))
            ags = snap.get("agent_status", {})
            if ags:
                import pandas as pd
                agents = state.get("agents", {})
                rows = [{"Agent": agents.get(a,{}).get("name",a), "Opinion": _OPINION_ZH.get(s.get("opinion",""),""), "Confidence": s.get("confidence",0)} for a, s in ags.items()]
                st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
            with st.expander("Raw snapshot"):
                st.json(snap)
    else:
        st.warning("No timeline data.")

st.markdown("---")
st.caption("AlTown: Multi-Agent Social Simulator | D: Wu Minyang - Visualization & Demo")
