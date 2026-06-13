import os
import json
from typing import Any

try:
    import networkx as nx
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False

try:
    from pyvis.network import Network
    _HAS_PYVIS = True
except ImportError:
    _HAS_PYVIS = False

_OPINION_COLORS = {"believe": "#2ecc71", "reject": "#e74c3c", "uncertain": "#95a5a6"}
_OPINION_ZH = {"believe": "相信", "reject": "不相信", "uncertain": "观望"}

# --- Chinese font fix for matplotlib ---
try:
    import matplotlib.font_manager as _fm
    _fm.findfont("Microsoft YaHei", fallback_to_default=False)
    _HAS_CN_FONT = True
except Exception:
    _HAS_CN_FONT = False

def _config_mpl_cn():
    if _HAS_CN_FONT:
        import matplotlib
        matplotlib.rcParams["font.family"] = "Microsoft YaHei"
        matplotlib.rcParams["axes.unicode_minus"] = False



def load_state(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def render_agent_table(state):
    agents = state.get("agents", {})
    if not agents:
        print("  (no agents)")
        return
    print("{:<12}{:<16}{:<20}{:<12}{:<10}{}".format("ID","Name","Role","Opinion","Conf","Trusted"))
    print("-" * 80)
    for aid, a in agents.items():
        op = _OPINION_ZH.get(a.get("opinion", "uncertain"), "")
        tr = ", ".join(a.get("trusted_agents", [])) or "None"
        print("{:<12}{:<16}{:<20}{:<12}{:<10.2f}{}".format(aid, a.get("name",""), a.get("role",""), op, a.get("confidence",0), tr))

def render_social_graph(state):
    _config_mpl_cn()
    if not _HAS_MPL:
        return None
    G = nx.Graph()
    agents = state.get("agents", {})
    for aid in agents:
        G.add_node(aid, label=agents[aid].get("name", aid), opinion=agents[aid].get("opinion", "uncertain"))
    for src, targets in state.get("relationships", {}).items():
        for tgt, info in targets.items():
            G.add_edge(src, tgt, weight=info.get("trust", 0.5))
    pos = nx.spring_layout(G, seed=42)
    fig, ax = plt.subplots(figsize=(8, 6))
    nc = [_OPINION_COLORS.get(G.nodes[n].get("opinion", "uncertain"), "#95a5a6") for n in G.nodes]
    ew = [max(G.edges[e].get("weight", 0.5) * 3, 0.5) for e in G.edges]
    nx.draw_networkx_nodes(G, pos, ax=ax, node_size=1200, node_color=nc, edgecolors="white", linewidths=1.5)
    nx.draw_networkx_edges(G, pos, ax=ax, width=ew, alpha=0.6, edge_color="#555")
    nx.draw_networkx_labels(G, pos, ax=ax, labels={n: G.nodes[n].get("label", n) for n in G.nodes}, font_size=10, font_weight="bold")
    patches = [mpatches.Patch(color=c, label=zh) for c, zh in zip(_OPINION_COLORS.values(), _OPINION_ZH.values())]
    ax.legend(handles=patches, loc="upper right", fontsize=9)
    ax.set_title("Agent Social Graph", fontsize=14, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()
    import tempfile
    p = os.path.join(tempfile.gettempdir(), "social_graph_D.png")
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

def render_metrics(state):
    _config_mpl_cn()
    if not _HAS_MPL:
        return None
    metrics = state.get("metrics", {})
    if not metrics:
        return None
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    spread = metrics.get("spread_rate", [])
    if spread:
        axes[0].plot([s["timestep"] for s in spread], [s["value"] for s in spread], marker="o", color="#3498db", linewidth=2)
        axes[0].set_title("Spread Rate"); axes[0].set_ylim(0, 1)
    avg_conf = metrics.get("average_confidence", [])
    if avg_conf:
        axes[1].plot([c["timestep"] for c in avg_conf], [c["value"] for c in avg_conf], marker="s", color="#9b59b6", linewidth=2)
        axes[1].set_title("Avg Confidence"); axes[1].set_ylim(0, 1)
    oc = metrics.get("opinion_count", [])
    if oc:
        ts = [o["timestep"] for o in oc]
        b = [o.get("believe", 0) for o in oc]
        r = [o.get("reject", 0) for o in oc]
        u = [o.get("uncertain", 0) for o in oc]
        axes[2].bar(ts, b, label="Believe", color="#2ecc71")
        axes[2].bar(ts, u, bottom=b, label="Uncertain", color="#95a5a6")
        bottom2 = [x + y for x, y in zip(b, u)]
        axes[2].bar(ts, r, bottom=bottom2, label="Reject", color="#e74c3c")
        axes[2].set_title("Opinion Distribution"); axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    import tempfile
    p = os.path.join(tempfile.gettempdir(), "metrics_D.png")
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p

print("visualization.py module loaded OK")


def get_agent_table_data(state):
    rows = []
    for aid, a in state.get("agents", {}).items():
        rows.append({
            "ID": aid,
            "Name": a.get("name", ""),
            "Role": a.get("role", ""),
            "Opinion": _OPINION_ZH.get(a.get("opinion", ""), a.get("opinion", "")),
            "Confidence": a.get("confidence", 0.0),
            "Trusted": ", ".join(a.get("trusted_agents", [])) or "None",
            "Memory": len(a.get("memory", [])),
        })
    return rows

def get_debate_summary(state):
    return state.get("debate", {})

def get_event_info(state):
    return state.get("event", {})

def get_timeline_data(state):
    return state.get("timeline", [])

def render_social_graph_pyvis(state, html_path="social_graph.html"):
    if not _HAS_PYVIS:
        return render_social_graph(state)
    from pyvis.network import Network
    agents = state.get("agents", {})
    net = Network(height="600px", width="100%", directed=False, notebook=False, bgcolor="#f8f9fa", font_color="#333")
    for aid, a in agents.items():
        color = _OPINION_COLORS.get(a.get("opinion", "uncertain"), "#95a5a6")
        title = f"{a.get('name','')} ({aid})"
        net.add_node(aid, label=a.get("name", aid), title=title, color=color, size=25)
    rels = state.get("relationships", {})
    for src, targets in rels.items():
        for tgt, info in targets.items():
            trust = info.get("trust", 0.5)
            net.add_edge(src, tgt, value=trust, title=f"Trust: {trust:.2f}", width=max(int(trust * 10), 1))
    opts = '{"physics":{"enabled":true,"solver":"forceAtlas2Based"}}'
    net.set_options(opts)
    net.save_graph(html_path)
    return html_path

def render_message_log(state):
    msgs = state.get("messages", [])
    if not msgs:
        print("  (no messages)")
        return
    agents = state.get("agents", {})
    for m in msgs:
        sp = agents.get(m.get("speaker",""), {}).get("name", m.get("speaker",""))
        rv = agents.get(m.get("receiver",""), {}).get("name", m.get("receiver",""))
        st = _OPINION_ZH.get(m.get("stance",""), m.get("stance",""))
        print(f"  [T{m.get('timestep',0)}] {sp} -> {rv} | {m.get('content','')} ({st}, {m.get('confidence',0):.2f})")

def load_state(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
