"""
Digital Twin Dashboard for IoV Task Allocation
════════════════════════════════════════════════
Run:  streamlit run dashboard.py
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import time

from physical_layer import SUMOPhysicalLayer, StandalonePhysicalLayer, TRACI_AVAILABLE
from digital_twin import DigitalTwinLayer
from gwo_optimizer import run_gwo
import config as cfg

# ═══════════════════════════════════════
# Page Config
# ═══════════════════════════════════════
st.set_page_config(
    page_title="Digital Twin — IoV Task Allocation",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════
# CSS
# ═══════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    .stApp { background-color: #0a0e17; color: #e0e0e0; }
    .main-header {
        background: linear-gradient(135deg, #0d1b2a 0%, #1b263b 50%, #0d1b2a 100%);
        border: 1px solid #1e3a5f; border-radius: 12px; padding: 20px 30px;
        margin-bottom: 20px; text-align: center;
    }
    .main-header h1 { color: #4fc3f7; font-family: 'JetBrains Mono'; font-size: 26px; margin: 0; letter-spacing: 2px; }
    .main-header p { color: #90caf9; font-size: 13px; margin: 5px 0 0 0; }
    .mc {
        background: linear-gradient(145deg, #111827, #1a2332);
        border: 1px solid #1e3a5f; border-radius: 10px; padding: 14px 16px; margin: 4px 0;
    }
    .mc .l { color: #78909c; font-size: 10px; text-transform: uppercase; letter-spacing: 1.5px; font-family: 'JetBrains Mono'; }
    .mc .v { color: #4fc3f7; font-size: 24px; font-weight: 700; font-family: 'JetBrains Mono'; }
    .mc .s { color: #546e7a; font-size: 10px; }
    .sync-bar {
        background: #111827; border: 1px solid #1e3a5f; border-radius: 8px; padding: 10px;
        display: flex; justify-content: space-around; align-items: center; margin-top: 10px;
    }
    .sync-badge {
        display: inline-block; background: #1b5e20; color: #a5d6a7; padding: 3px 10px;
        border-radius: 20px; font-size: 11px; font-family: 'JetBrains Mono';
        animation: pulse 2s infinite;
    }
    @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.6;} }
    .sh { color: #4fc3f7; font-family: 'JetBrains Mono'; font-size: 15px;
          border-bottom: 1px solid #1e3a5f; padding-bottom: 5px; margin: 18px 0 10px 0; letter-spacing: 1px; }
    div[data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #1e3a5f; }
    .stTabs [data-baseweb="tab"] {
        background-color: #111827; border: 1px solid #1e3a5f; border-radius: 8px;
        color: #90caf9; font-family: 'JetBrains Mono';
    }
    .stTabs [aria-selected="true"] { background-color: #1e3a5f !important; color: #4fc3f7 !important; }
</style>
""", unsafe_allow_html=True)

PLOT_LAYOUT = dict(
    plot_bgcolor='#0d1117', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family='JetBrains Mono', color='#78909c'),
    margin=dict(l=50, r=20, t=40, b=40),
)
GRID_AXIS = dict(gridcolor='rgba(255,255,255,0.05)')


def mc(label, value, sub=""):
    st.markdown(f'<div class="mc"><div class="l">{label}</div><div class="v">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


# ═══════════════════════════════════════
# Session State
# ═══════════════════════════════════════
if "physical" not in st.session_state:
    st.session_state.physical = None
    st.session_state.dt = None
    st.session_state.gwo_result = None
    st.session_state.history = []
    st.session_state.step = 0
    st.session_state.mode = "standalone"


def init_sim(mode, n_vehicles):
    if mode == "sumo-gui" and TRACI_AVAILABLE:
        st.session_state.physical = SUMOPhysicalLayer(use_gui=True)
    elif mode == "sumo" and TRACI_AVAILABLE:
        st.session_state.physical = SUMOPhysicalLayer(use_gui=False)
    else:
        st.session_state.physical = StandalonePhysicalLayer(num_vehicles=n_vehicles)
    st.session_state.dt = DigitalTwinLayer()
    st.session_state.gwo_result = None
    st.session_state.history = []
    st.session_state.step = 0
    st.session_state.mode = mode


def run_one_step():
    phy = st.session_state.physical
    dt = st.session_state.dt

    state = phy.step()
    st.session_state.step = phy.time_step

    sync = dt.sync_from_physical(state, time.time())

    gwo = run_gwo(phy.tasks, w1=cfg.FITNESS_W1)
    st.session_state.gwo_result = gwo

    for i, t in enumerate(phy.tasks):
        if i < len(gwo["best_allocation"]):
            t.allocated_to = gwo["best_allocation"][i]

    rsu_loads = [0] * len(phy.rsus)
    for i, t in enumerate(phy.tasks):
        if t.allocated_to is not None:
            idx = int(t.rsu_id.split("_")[1]) - 1
            if t.allocated_to == cfg.LOC_RSU:
                rsu_loads[idx] += 1
            elif t.allocated_to == cfg.LOC_NEIGHBOR_MBS:
                rsu_loads[idx] += 2
    for i, r in enumerate(phy.rsus):
        r.current_load = rsu_loads[i]

    st.session_state.history.append({
        "step": phy.time_step,
        "fitness": gwo["best_fitness"],
        "latency": gwo["final_metrics"]["total_latency"],
        "energy": gwo["final_metrics"]["total_energy"],
        "load_imbalance": gwo["final_metrics"]["load_imbalance"],
        "served": gwo["final_metrics"]["served"],
        "avg_aoi": sync.get("avg_aoi", 0),
        "vehicles": state["num_vehicles"],
        "tasks": state["num_tasks"],
    })


# ═══════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙️ Controls")

    modes = ["standalone"]
    if TRACI_AVAILABLE:
        modes = ["sumo-gui", "sumo", "standalone"]
    mode = st.selectbox("Mode", modes, index=len(modes)-1)

    n_veh = st.slider("Vehicles", 10, 210, 50, step=10)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Init", use_container_width=True):
            init_sim(mode, n_veh)
            st.rerun()
    with c2:
        if st.button("▶️ Step", use_container_width=True):
            if st.session_state.physical:
                run_one_step()
                st.rerun()

    n_steps = st.slider("Multi-step", 1, 20, 5)
    if st.button(f"⏩ Run {n_steps} Steps", use_container_width=True):
        if st.session_state.physical:
            for _ in range(n_steps):
                run_one_step()
            st.rerun()

    st.markdown("---")
    st.markdown("### 🐺 GWO")
    cfg.GWO_POPULATION = st.slider("Population", 10, 100, 30)
    cfg.GWO_MAX_ITERATIONS = st.slider("Iterations", 20, 200, 100)
    cfg.FITNESS_W1 = st.slider("w₁ (Latency)", 0.0, 1.0, 0.5, 0.1)

    st.markdown("---")
    if st.session_state.dt:
        ss = st.session_state.dt.get_sync_stats()
        st.markdown(f"""
        <div style="background:#1b5e20; border:1px solid #4caf50; border-radius:8px;
                    padding:8px; text-align:center;">
            <span class="sync-badge">● DT ACTIVE</span><br/>
            <span style="font-size:11px; color:#a5d6a7; font-family:'JetBrains Mono';">
            Syncs: {ss['total_syncs']} | AoI: {ss['avg_aoi']:.3f}s</span>
        </div>
        """, unsafe_allow_html=True)

    sumo_note = "SUMO available ✓" if TRACI_AVAILABLE else "SUMO not found — using standalone"
    st.caption(sumo_note)

    if st.session_state.dt:
        ditto_st = st.session_state.dt.get_ditto_status()
        if ditto_st["connected"]:
            st.markdown(f"""
            <div style="background:#0d47a1; border:1px solid #1565c0; border-radius:8px;
                        padding:8px; text-align:center; margin-top:8px;">
                <span style="color:#90caf9; font-family:'JetBrains Mono'; font-size:11px;">
                🔵 ECLIPSE DITTO ACTIVE<br/>
                Things: {ditto_st['things_count']} | API: localhost:8080
                </span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("Ditto: offline — using in-memory DT")


# ═══════════════════════════════════════
# HEADER
# ═══════════════════════════════════════
st.markdown("""
<div class="main-header">
    <h1>🌐 DIGITAL TWIN — IoV TASK ALLOCATION</h1>
    <p>Physical Layer ↔ State Sync ↔ DT Layer ↔ GWO Optimization ↔ Execution</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.physical:
    st.info("👈 Select mode and click **Init** to start.")
    st.stop()

phy = st.session_state.physical
dt = st.session_state.dt
gwo = st.session_state.gwo_result
ss = dt.get_sync_stats()

# ═══════════════════════════════════════
# TOP METRICS
# ═══════════════════════════════════════
m = st.columns(8)
with m[0]: mc("STEP", st.session_state.step)
with m[1]: mc("SOURCE", st.session_state.mode.upper())
with m[2]: mc("VEHICLES", len(phy.vehicles))
with m[3]: mc("TASKS", len(phy.tasks))
with m[4]: mc("DT SYNCS", ss["total_syncs"])
with m[5]: mc("FITNESS", f"{gwo['best_fitness']:.4f}" if gwo else "—")
with m[6]: mc("AVG AoI", f"{ss['avg_aoi']:.3f}s")
with m[7]: mc("DT BACKEND", ss.get("backend", "memory").upper())

# ═══════════════════════════════════════
# TABS
# ═══════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🗺️ Physical & DT", "🐺 GWO Optimization",
    "📊 Task Allocation", "📡 RSU Status", "📈 History", "🔵 Eclipse Ditto"
])


# ─── TAB 1: Physical + DT side by side ───
with tab1:
    cP, cD = st.columns(2)

    def _draw_map(fig, rsus_data, vehicles_data, rsu_color, veh_color, rsu_prefix=""):
        for r in rsus_data:
            rx, ry, cov = r["x"], r["y"], r["coverage"]
            theta = np.linspace(0, 2*np.pi, 60)
            fig.add_trace(go.Scatter(
                x=(rx + cov*np.cos(theta)).tolist(),
                y=(ry + cov*np.sin(theta)).tolist(),
                mode='lines', line=dict(color=f'rgba({rsu_color},0.25)', width=1, dash='dash'),
                showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(
                x=[rx], y=[ry], mode='markers+text',
                marker=dict(size=16, color=f'rgb({rsu_color})', symbol='triangle-up'),
                text=[f"{rsu_prefix}{r['id']}"], textposition='top center',
                textfont=dict(size=9), showlegend=False))

        # MBS
        fig.add_trace(go.Scatter(
            x=[cfg.MBS_CONFIG["x"]], y=[cfg.MBS_CONFIG["y"]],
            mode='markers+text',
            marker=dict(size=20, color='#ff9800', symbol='star'),
            text=[f'{rsu_prefix}MBS'], textposition='top center',
            textfont=dict(size=9), showlegend=False))

        if vehicles_data:
            fig.add_trace(go.Scatter(
                x=[v["x"] for v in vehicles_data],
                y=[v["y"] for v in vehicles_data],
                mode='markers',
                marker=dict(size=6, color=f'rgb({veh_color})', symbol='circle'),
                text=[f"{v['id']}<br>RSU:{v.get('connected_rsu','?')}" for v in vehicles_data],
                hoverinfo='text', showlegend=False))

        bnd = cfg.ROAD_BOUNDS
        fig.update_layout(
            xaxis=dict(range=[bnd["x_min"]-50, bnd["x_max"]+50], **GRID_AXIS, title='X (m)'),
            yaxis=dict(range=[bnd["y_min"]-50, bnd["y_max"]+50], **GRID_AXIS, title='Y (m)', scaleanchor='x'),
            height=480, **PLOT_LAYOUT)

    with cP:
        st.markdown('<div class="sh">🏗️ PHYSICAL LAYER</div>', unsafe_allow_html=True)
        fig_p = go.Figure()
        phys_rsus = [{"id": r.id, "x": r.x, "y": r.y, "coverage": r.coverage} for r in phy.rsus]
        phys_vehs = [v.to_dict() for v in phy.vehicles]
        _draw_map(fig_p, phys_rsus, phys_vehs, "33,150,243", "76,175,80")
        st.plotly_chart(fig_p, use_container_width=True)

    with cD:
        st.markdown('<div class="sh">🪞 DIGITAL TWIN (Mirror)</div>', unsafe_allow_html=True)
        fig_d = go.Figure()
        dt_state = dt.get_exposed_state()
        dt_rsus = [{"id": rid, "x": t["properties"]["x"], "y": t["properties"]["y"],
                     "coverage": t["properties"]["coverage"]}
                    for rid, t in dt_state["rsus"].items()]
        dt_vehs = dt.get_vehicle_positions()
        _draw_map(fig_d, dt_rsus, dt_vehs, "0,230,118", "0,230,118", "DT:")
        st.plotly_chart(fig_d, use_container_width=True)

    st.markdown(f"""
    <div class="sync-bar">
        <span class="sync-badge">● STATE SYNC ACTIVE</span>
        <span style="color:#78909c; font-family:'JetBrains Mono'; font-size:11px;">
        Vehicles: <b style="color:#4fc3f7">{ss['vehicles_synced']}</b> |
        RSUs: <b style="color:#4fc3f7">{ss['rsus_synced']}</b> |
        Ditto: <b style="color:#42a5f5">{ss.get('ditto_synced', 0)}</b> |
        Total: <b style="color:#4fc3f7">{ss['total_syncs']}</b> |
        Avg AoI: <b style="color:#4fc3f7">{ss['avg_aoi']:.3f}s</b> |
        Max AoI: <b style="color:#4fc3f7">{ss['max_aoi']:.3f}s</b> |
        Backend: <b style="color:#42a5f5">{ss.get('backend','memory')}</b></span>
    </div>
    """, unsafe_allow_html=True)


# ─── TAB 2: GWO ───
with tab2:
    if not gwo:
        st.info("Run a step first.")
    else:
        conv_df = pd.DataFrame(gwo["convergence"])
        c1, c2 = st.columns(2)

        with c1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=conv_df["iteration"], y=conv_df["fitness"],
                                     mode='lines', line=dict(color='#4fc3f7', width=2),
                                     fill='tozeroy', fillcolor='rgba(79,195,247,0.08)'))
            fig.update_layout(title="Fitness Convergence", height=340,
                              xaxis=dict(title="Iteration", **GRID_AXIS),
                              yaxis=dict(title="Fitness", **GRID_AXIS), **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=conv_df["iteration"], y=conv_df["latency"],
                                     mode='lines', line=dict(color='#ff7043', width=2),
                                     fill='tozeroy', fillcolor='rgba(255,112,67,0.08)'))
            fig.update_layout(title="Latency Convergence (ms)", height=340,
                              xaxis=dict(title="Iteration", **GRID_AXIS),
                              yaxis=dict(title="Latency (ms)", **GRID_AXIS), **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        c3, c4 = st.columns(2)
        with c3:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=conv_df["iteration"], y=conv_df["a_parameter"],
                                     mode='lines', line=dict(color='#ab47bc', width=2)))
            fig.update_layout(title="Parameter 'a' (Explore → Exploit)", height=300,
                              xaxis=dict(**GRID_AXIS), yaxis=dict(**GRID_AXIS), **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        with c4:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=conv_df["iteration"], y=conv_df["load_imbalance"],
                                     mode='lines', line=dict(color='#66bb6a', width=2),
                                     fill='tozeroy', fillcolor='rgba(102,187,106,0.08)'))
            fig.update_layout(title="Load Imbalance Convergence", height=300,
                              xaxis=dict(**GRID_AXIS), yaxis=dict(**GRID_AXIS), **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="sh">📋 FINAL RESULTS</div>', unsafe_allow_html=True)
        r = gwo["final_metrics"]
        cc = st.columns(5)
        with cc[0]: mc("BEST FITNESS", f"{gwo['best_fitness']:.4f}")
        with cc[1]: mc("LATENCY", f"{r['total_latency']:.0f} ms")
        with cc[2]: mc("ENERGY", f"{r['total_energy']:.0f} mJ")
        with cc[3]: mc("LOAD IMB.", f"{r['load_imbalance']:.4f}")
        with cc[4]: mc("SERVED", f"{r['served']}/{len(phy.tasks)}")


# ─── TAB 3: Task Allocation ───
with tab3:
    if not gwo:
        st.info("Run a step first.")
    else:
        st.markdown('<div class="sh">📋 ALLOCATION DISTRIBUTION</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)

        with c1:
            as_ = gwo["allocation_summary"]
            fig = go.Figure(data=[go.Pie(
                labels=list(as_.keys()), values=list(as_.values()), hole=0.5,
                marker=dict(colors=['#4caf50','#2196f3','#ff9800','#e91e63'],
                            line=dict(color='#0d1117', width=2)),
                textfont=dict(color='white', family='JetBrains Mono'))])
            fig.update_layout(title="Tasks by Location", height=380, **PLOT_LAYOUT,
                              legend=dict(font=dict(color='#90caf9')))
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            rsu_alloc = {}
            for t in phy.tasks:
                rsu = t.rsu_id
                loc = cfg.LOCATION_NAMES.get(t.allocated_to, "Unassigned")
                rsu_alloc.setdefault(rsu, {})
                rsu_alloc[rsu][loc] = rsu_alloc[rsu].get(loc, 0) + 1

            if rsu_alloc:
                rows = [{"RSU": r, "Location": l, "Count": c}
                        for r, locs in rsu_alloc.items() for l, c in locs.items()]
                fig = px.bar(pd.DataFrame(rows), x="RSU", y="Count", color="Location",
                             color_discrete_map={"Vehicle Cache":"#4caf50","Primary RSU":"#2196f3",
                                                 "Neighbor RSU/MBS":"#ff9800","Cloud":"#e91e63",
                                                 "Unassigned":"#757575"}, barmode='stack')
                fig.update_layout(title="Per-RSU Allocation", height=380, **PLOT_LAYOUT,
                                  xaxis=dict(**GRID_AXIS), yaxis=dict(**GRID_AXIS),
                                  legend=dict(font=dict(color='#90caf9')))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="sh">📄 TASK TABLE</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([t.to_dict() for t in phy.tasks[:60]]),
                     use_container_width=True, height=300)


# ─── TAB 4: RSU Status ───
with tab4:
    st.markdown('<div class="sh">📡 RSU STATUS — DT MONITORED</div>', unsafe_allow_html=True)
    cols = st.columns(len(phy.rsus))
    for i, rsu in enumerate(phy.rsus):
        with cols[i]:
            info = rsu.to_dict()
            st.markdown(f"""
            <div style="background:#111827; border:1px solid #1e3a5f; border-radius:10px;
                        padding:12px; text-align:center;">
                <div style="color:#2196f3; font-size:16px; font-weight:700; font-family:'JetBrains Mono';">{rsu.id}</div>
                <div style="color:#546e7a; font-size:10px;">({rsu.x}, {rsu.y})</div>
            </div>""", unsafe_allow_html=True)

            fig_g = go.Figure(go.Indicator(
                mode="gauge+number", value=info["utilization_pct"],
                title={"text": "Util %", "font": {"size": 11, "color": "#78909c"}},
                number={"font": {"size": 22, "color": "#4fc3f7"}},
                gauge=dict(axis=dict(range=[0,100], tickcolor='#546e7a'),
                           bar=dict(color='#4fc3f7'), bgcolor='#1a2332', bordercolor='#1e3a5f',
                           steps=[dict(range=[0,40], color='rgba(76,175,80,0.15)'),
                                  dict(range=[40,70], color='rgba(255,152,0,0.15)'),
                                  dict(range=[70,100], color='rgba(244,67,54,0.15)')])))
            fig_g.update_layout(height=180, margin=dict(l=15,r=15,t=30,b=5), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_g, use_container_width=True)
            mc("LOAD", f"{info['load']} tasks")
            mc("VEHICLES", f"{info['vehicles_served']}")

    if gwo:
        st.markdown('<div class="sh">📊 LOAD COMPARISON</div>', unsafe_allow_html=True)
        loads = gwo["final_metrics"]["rsu_loads"]
        names = [r["id"] for r in cfg.RSU_CONFIG]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=names, y=loads,
                             marker=dict(color=['#2196f3','#4caf50','#ff9800']),
                             text=[f"{l:.0f}" for l in loads], textposition='outside',
                             textfont=dict(color='#90caf9')))
        mean_l = np.mean(loads) if loads else 0
        fig.add_hline(y=mean_l, line_dash="dash", line_color="#e91e63",
                      annotation_text=f"Mean: {mean_l:.1f}", annotation_font=dict(color='#e91e63'))
        fig.update_layout(title="GWO Task Load per RSU", height=320,
                          xaxis=dict(**GRID_AXIS), yaxis=dict(title="Tasks", **GRID_AXIS), **PLOT_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)


# ─── TAB 5: History ───
with tab5:
    if not st.session_state.history:
        st.info("Run multiple steps to see trends.")
    else:
        st.markdown('<div class="sh">📈 PERFORMANCE OVER TIME</div>', unsafe_allow_html=True)
        hdf = pd.DataFrame(st.session_state.history)

        c1, c2 = st.columns(2)
        with c1:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=hdf["step"], y=hdf["fitness"], mode='lines+markers',
                                     name='Fitness', line=dict(color='#4fc3f7', width=2),
                                     marker=dict(size=5)), secondary_y=False)
            fig.add_trace(go.Scatter(x=hdf["step"], y=hdf["latency"], mode='lines+markers',
                                     name='Latency', line=dict(color='#ff7043', width=2),
                                     marker=dict(size=5)), secondary_y=True)
            fig.update_layout(title="Fitness & Latency", height=330, **PLOT_LAYOUT,
                              legend=dict(font=dict(color='#90caf9')))
            fig.update_xaxes(**GRID_AXIS); fig.update_yaxes(**GRID_AXIS)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=hdf["step"], y=hdf["energy"], mode='lines+markers',
                                     name='Energy', line=dict(color='#66bb6a', width=2),
                                     marker=dict(size=5)), secondary_y=False)
            fig.add_trace(go.Scatter(x=hdf["step"], y=hdf["load_imbalance"], mode='lines+markers',
                                     name='Load Imb.', line=dict(color='#ab47bc', width=2),
                                     marker=dict(size=5)), secondary_y=True)
            fig.update_layout(title="Energy & Load Imbalance", height=330, **PLOT_LAYOUT,
                              legend=dict(font=dict(color='#90caf9')))
            fig.update_xaxes(**GRID_AXIS); fig.update_yaxes(**GRID_AXIS)
            st.plotly_chart(fig, use_container_width=True)

        # AoI
        st.markdown('<div class="sh">⏱️ AGE OF INFORMATION</div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hdf["step"], y=hdf["avg_aoi"], mode='lines+markers',
                                 line=dict(color='#ffd54f', width=2), marker=dict(size=7)))
        fig.add_hline(y=cfg.AOI_THRESHOLD, line_dash="dash", line_color="#f44336",
                      annotation_text=f"Threshold: {cfg.AOI_THRESHOLD}s",
                      annotation_font=dict(color='#f44336'))
        fig.update_layout(title="DT Sync Freshness", height=280,
                          xaxis=dict(title="Step", **GRID_AXIS),
                          yaxis=dict(title="Avg AoI (s)", **GRID_AXIS), **PLOT_LAYOUT)
        st.plotly_chart(fig, use_container_width=True)

        # Vehicle count over time
        st.markdown('<div class="sh">🚗 NETWORK DYNAMICS</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hdf["step"], y=hdf["vehicles"], mode='lines+markers',
                                     line=dict(color='#4caf50', width=2), marker=dict(size=5),
                                     name='Vehicles'))
            fig.update_layout(title="Active Vehicles", height=250,
                              xaxis=dict(**GRID_AXIS), yaxis=dict(**GRID_AXIS), **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hdf["step"], y=hdf["tasks"], mode='lines+markers',
                                     line=dict(color='#2196f3', width=2), marker=dict(size=5),
                                     name='Tasks'))
            fig.update_layout(title="Active Tasks", height=250,
                              xaxis=dict(**GRID_AXIS), yaxis=dict(**GRID_AXIS), **PLOT_LAYOUT)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="sh">📋 DATA TABLE</div>', unsafe_allow_html=True)
        st.dataframe(hdf.round(4), use_container_width=True)


# ─── TAB 6: Eclipse Ditto ───
with tab6:
    st.markdown('<div class="sh">🔵 ECLIPSE DITTO — DIGITAL TWIN PLATFORM</div>', unsafe_allow_html=True)

    ditto_status = dt.get_ditto_status()

    if ditto_status["connected"]:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0d47a1, #1565c0); border: 1px solid #1e88e5;
                    border-radius: 12px; padding: 20px; margin-bottom: 15px;">
            <div style="color: #bbdefb; font-family: 'JetBrains Mono'; font-size: 12px; letter-spacing: 1px;">
                ECLIPSE DITTO STATUS</div>
            <div style="color: #e3f2fd; font-size: 22px; font-weight: 700; font-family: 'JetBrains Mono';
                        margin: 5px 0;">● CONNECTED</div>
            <div style="color: #90caf9; font-size: 12px; font-family: 'JetBrains Mono';">
                API: {ditto_status['url']} | Things: {ditto_status['things_count']}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Show all Things in Ditto
        st.markdown('<div class="sh">📦 THINGS IN DITTO</div>', unsafe_allow_html=True)
        if "things" in ditto_status:
            for tid in ditto_status["things"]:
                thing_data = dt.verify_ditto_sync(tid.replace("org.eclipse.ditto:", ""))
                if thing_data:
                    with st.expander(f"🔹 {tid}", expanded=False):
                        st.json(thing_data)

        # Live verification
        st.markdown('<div class="sh">🔄 LIVE SYNC VERIFICATION</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="color: #78909c; font-size: 12px; font-family: 'JetBrains Mono'; margin-bottom: 10px;">
            Reads directly from Ditto API to verify twins are synchronized.
        </div>
        """, unsafe_allow_html=True)

        vc1, vc2, vc3 = st.columns(3)
        for idx, rsu_cfg in enumerate(cfg.RSU_CONFIG):
            with [vc1, vc2, vc3][idx]:
                rsu_thing = dt.verify_ditto_sync(rsu_cfg["id"])
                if rsu_thing:
                    feats = rsu_thing.get("features", {})
                    load_props = feats.get("load", {}).get("properties", {})
                    sync_props = feats.get("sync", {}).get("properties", {})
                    st.markdown(f"""
                    <div style="background: #111827; border: 1px solid #1565c0; border-radius: 8px; padding: 12px;">
                        <div style="color: #1e88e5; font-family: 'JetBrains Mono'; font-weight: 700;">{rsu_cfg['id']}</div>
                        <div style="color: #78909c; font-size: 11px; font-family: 'JetBrains Mono'; margin-top: 5px;">
                            Load: {load_props.get('current_load', 0)}<br/>
                            Util: {load_props.get('utilization_pct', 0)}%<br/>
                            Last Sync: {sync_props.get('last_sync', 0):.3f}s
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    mc(rsu_cfg["id"], "No data", "Not in Ditto")

        # Ditto Architecture diagram
        st.markdown('<div class="sh">🏗️ ARCHITECTURE</div>', unsafe_allow_html=True)
        st.markdown("""
        ```
        ┌──────────────┐     TraCI      ┌───────────────┐    REST API     ┌──────────────────┐
        │  SUMO         │──────────────►│  Python App   │───────────────►│  Eclipse Ditto    │
        │  (Physical)   │               │               │                │  (DT Platform)    │
        │               │               │  • State Sync │   PUT /things  │  • Vehicle Things │
        │  210 vehicles │               │  • GWO Optim. │───────────────►│  • RSU Things     │
        │  16 intersect │               │  • Dashboard  │   GET /things  │  • MBS Thing      │
        └──────────────┘               └───────────────┘◄───────────────│  • Cloud Thing    │
                                                                         │                    │
                                                                         │  MongoDB Backend   │
                                                                         │  Nginx Proxy:8080  │
                                                                         └──────────────────┘
        ```
        """)

        # Sync stats
        st.markdown('<div class="sh">📊 DITTO SYNC METRICS</div>', unsafe_allow_html=True)
        dc1, dc2, dc3, dc4 = st.columns(4)
        with dc1: mc("TOTAL SYNCS", ss["total_syncs"])
        with dc2: mc("DITTO WRITES", ss.get("ditto_synced", 0), "last step")
        with dc3: mc("THINGS", ditto_status["things_count"])
        with dc4: mc("AVG AoI", f"{ss['avg_aoi']:.3f}s")

    else:
        st.markdown("""
        <div style="background: #1a1a2e; border: 1px solid #e65100; border-radius: 12px;
                    padding: 20px; text-align: center;">
            <div style="color: #ff9800; font-size: 18px; font-weight: 700;
                        font-family: 'JetBrains Mono';">⚠ ECLIPSE DITTO NOT CONNECTED</div>
            <div style="color: #78909c; font-size: 13px; margin-top: 10px; font-family: 'JetBrains Mono';">
                DT is running in memory mode. To enable Ditto:
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        **Setup Eclipse Ditto:**
        ```bash
        # 1. Make sure Docker Desktop is running
        # 2. Start Ditto services
        docker-compose up -d

        # 3. Wait ~30 seconds for all services to start
        # 4. Initialize Ditto with IoV Things
        python init_ditto.py

        # 5. Restart the dashboard
        streamlit run dashboard.py
        ```

        **Verify Ditto is running:**
        ```bash
        # Check services
        docker-compose ps

        # Check API
        curl http://localhost:8080/health
        ```
        """)

        st.info("The simulation works fine without Ditto — it just uses in-memory Digital Twins instead. "
                "Ditto adds a real enterprise DT platform layer that's visible via REST API.")


# ═══════════════════════════════════════
st.markdown("""
<div style="text-align:center; color:#37474f; font-size:10px; margin-top:25px;
            font-family:'JetBrains Mono'; border-top:1px solid #1e3a5f; padding-top:8px;">
    Task Allocation in Digital Twin Enabled IoV Using Grey Wolf Optimization |
    Physical Layer ↔ State Sync ↔ DT Layer ↔ GWO ↔ Execution
</div>
""", unsafe_allow_html=True)
