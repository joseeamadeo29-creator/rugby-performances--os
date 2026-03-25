"""
main.py  ─  Rugby Performance OS  v4 (Franchise Edition)
==========================================================
5 NEW CAPABILITIES:
  1. Squad Management    — multi-athlete with player_id, sidebar selector
  2. Spatial Heatmaps    — Plotly 2D density on top-down pitch view
  3. ACWR                — Acute:Chronic Workload Ratio injury prevention
  4. Centroid Tracking   — persistent player ID across video frames
  5. Bilingual ES/EN     — full i18n toggle in sidebar

Run:  streamlit run main.py
"""

# ── Standard ──────────────────────────────────────────────────────────────────
import os, io, tempfile, calendar
from datetime import datetime, date

# ── Third-Party ───────────────────────────────────────────────────────────────
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image

# ── Local Modules ─────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(__file__))

from modules.i18n import t, get_lang

from modules.data_manager import (
    ensure_data_dir,
    load_players, save_player, delete_player, get_player_name,
    save_physical_entry, load_physical_log,
    save_measures_entry, load_measures_log,
    save_pr_entry, load_pr_log,
    save_journal_entry, load_journal, check_burnout_alert,
    load_schedule, save_event, delete_event, get_today_event_types,
    generate_pdf_report, calculate_acwr,
)
from modules.tactics_engine import (
    get_advice, list_events,
    RugbyEventDetector, TeamClusterer, CentroidTracker,
    HeatmapStore,
    run_yolo_on_frame, draw_detections,
    frame_skip_generator, export_annotated_frame,
    Detection, FrameEvent,
)
from modules.nutrition import (
    bulking_targets, get_meal_timing_advice,
    epley_1rm, compute_all_1rms,
    check_fat_gain_alert, build_radar_data,
    acwr_zone_meta,
)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
ensure_data_dir()

# ── Session state defaults ────────────────────────────────────────────────────
if "lang"            not in st.session_state: st.session_state["lang"]            = "en"
if "active_player"   not in st.session_state: st.session_state["active_player"]   = "default"
if "heatmap_store"   not in st.session_state: st.session_state["heatmap_store"]   = HeatmapStore()
if "tracker"         not in st.session_state: st.session_state["tracker"]         = CentroidTracker()
if "frame_rgb"       not in st.session_state: st.session_state["frame_rgb"]       = None
if "frame_w"         not in st.session_state: st.session_state["frame_w"]         = 1280
if "frame_h"         not in st.session_state: st.session_state["frame_h"]         = 720


# ═══════════════════════════════════════════════════════════════════════════════
#  CACHED LOADERS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=60)
def _phys(pid):   return load_physical_log(pid)

@st.cache_data(ttl=60)
def _prs(pid):    return load_pr_log(pid)

@st.cache_data(ttl=60)
def _jrnl(pid):   return load_journal(pid)

@st.cache_data(ttl=30)
def _sched():     return load_schedule()

@st.cache_data(ttl=60)
def _meas(pid):   return load_measures_log(pid)

@st.cache_data(ttl=120)
def _players():   return load_players()

@st.cache_resource
def _yolo():
    try:
        from ultralytics import YOLO
        return YOLO("yolov8n.pt")
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Rugby Performance OS",
    page_icon="🏉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
#  CSS  — Glassmorphism Dark (identical to v3, preserved exactly)
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');
:root {
    --bg:    #0e1117; --bg1: #13151c; --bg2: #1a1d27; --bg3: #20232e;
    --green: #2ecc71; --gdim: rgba(46,204,113,.12); --gglow: rgba(46,204,113,.25);
    --gold:  #f1c40f; --blue: #3498db; --red: #e74c3c;
    --text:  #e8eaf0; --muted: #5a6070; --border: rgba(255,255,255,.07);
    --glass: rgba(255,255,255,.04); --glasss: rgba(255,255,255,.07);
    --r: 14px; --rs: 8px;
}
*, *::before, *::after { box-sizing: border-box; }
html,body,.stApp,.main,
[data-testid="stAppViewContainer"],[data-testid="stMain"] {
    font-family:'Inter',-apple-system,sans-serif!important;
    background-color:var(--bg)!important; color:var(--text)!important;
}
[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#0a0c12,#0e1117)!important;
    border-right:1px solid var(--border);
}
.glass {
    background:var(--glass); border:1px solid var(--border);
    border-radius:var(--r);
    box-shadow:0 8px 32px rgba(0,0,0,.5),inset 0 1px 0 rgba(255,255,255,.05);
    backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px);
    padding:20px 22px; margin-bottom:14px;
    transition:border-color .2s,box-shadow .2s;
}
.glass:hover { border-color:rgba(255,255,255,.12); box-shadow:0 12px 40px rgba(0,0,0,.65); }
.kpi {
    background:linear-gradient(135deg,var(--glasss),var(--glass));
    border:1px solid var(--border); border-radius:var(--r);
    padding:22px 18px 16px; text-align:center;
    box-shadow:0 4px 20px rgba(0,0,0,.4);
}
.alert-r { background:rgba(231,76,60,.10); border:1px solid rgba(231,76,60,.35);
            border-radius:var(--r); padding:14px 18px; margin-bottom:14px; }
.alert-g { background:rgba(46,204,113,.08); border:1px solid rgba(46,204,113,.28);
            border-radius:var(--r); padding:14px 18px; margin-bottom:14px; }
.alert-y { background:rgba(241,196,15,.08); border:1px solid rgba(241,196,15,.30);
            border-radius:var(--r); padding:14px 18px; margin-bottom:14px; }
.sh {
    color:var(--green); font-size:9.5px; font-weight:800;
    letter-spacing:3px; text-transform:uppercase;
    padding-bottom:6px; border-bottom:1px solid var(--border); margin-bottom:12px;
}
.cp {
    background:rgba(46,204,113,.05); border-left:3px solid var(--green);
    padding:9px 14px; margin:5px 0; border-radius:0 var(--rs) var(--rs) 0;
    font-size:13px; line-height:1.55; color:#ccd;
}
.stTabs [data-baseweb="tab-list"] { background:var(--bg2); border-radius:10px; gap:2px; padding:4px; }
.stTabs [data-baseweb="tab"] {
    background:transparent; color:var(--muted); border-radius:7px;
    font-weight:700; font-size:12px; padding:8px 14px;
}
.stTabs [aria-selected="true"] {
    background:var(--green)!important; color:#000!important;
    box-shadow:0 0 12px var(--gglow);
}
.stButton>button {
    font-family:'Inter',sans-serif!important;
    background:linear-gradient(135deg,#2ecc71,#27ae60)!important;
    color:#000!important; font-weight:800!important; font-size:13px!important;
    border:none!important; border-radius:10px!important;
    min-height:44px!important; padding:10px 20px!important; width:100%;
    box-shadow:0 4px 15px rgba(46,204,113,.2);
    transition:transform .15s,box-shadow .15s;
}
.stButton>button:hover { transform:translateY(-2px); box-shadow:0 8px 25px rgba(46,204,113,.35)!important; }
.stTextInput input,.stNumberInput input,.stTextArea textarea,.stSelectbox>div {
    font-family:'Inter',sans-serif!important; background:var(--bg2)!important;
    border:1px solid var(--border)!important; border-radius:var(--rs)!important;
    color:var(--text)!important; font-size:14px!important; min-height:42px;
}
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background:var(--gold)!important; border-color:var(--gold)!important;
    box-shadow:0 0 8px rgba(241,196,15,.4);
}
[data-testid="stMetricValue"] { font-family:'Inter',sans-serif!important; font-weight:900; }
::-webkit-scrollbar { width:5px; }
::-webkit-scrollbar-track { background:var(--bg1); }
::-webkit-scrollbar-thumb { background:var(--bg3); border-radius:10px; }
.cal { background:var(--glass); border:1px solid var(--border); border-radius:9px; padding:6px 5px; min-height:80px; }
.cal-today { border:1.5px solid var(--green)!important; background:var(--gdim); }
@media(max-width:768px){
    h1,h2{font-size:1.3rem!important;}
    .stTabs [data-baseweb="tab"]{font-size:11px;padding:6px 9px;}
    .kpi,.glass{padding:14px 12px;}
}
/* ACWR progress bar */
.acwr-bar-wrap { background:#1a1d27; border-radius:20px; height:12px; width:100%; overflow:hidden; margin:8px 0; }
.acwr-bar-fill { height:100%; border-radius:20px; transition:width .4s ease; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    # ── Language toggle ───────────────────────────────────────────────────────
    lang_btn_label = t("lang_toggle")
    if st.button(lang_btn_label, key="lang_btn"):
        st.session_state["lang"] = "es" if st.session_state["lang"] == "en" else "en"
        st.rerun()

    lang = get_lang()

    st.markdown(f"""
    <div style='text-align:center;padding:16px 0 8px;'>
        <div style='font-size:44px;line-height:1;'>🏉</div>
        <div style='color:#2ecc71;font-size:15px;font-weight:900;
                    letter-spacing:4px;margin-top:8px;'>RUGBY OS</div>
        <div style='color:#2a2e3a;font-size:9px;letter-spacing:4px;margin-top:3px;'>
            {t("app_subtitle")}
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── Squad selector ────────────────────────────────────────────────────────
    st.markdown(f"<div class='sh'>{t('select_player')}</div>", unsafe_allow_html=True)
    players = _players()

    if players:
        player_options = {p["name"]: p["id"] for p in players}
        # Add default solo-player option
        player_options = {"— Solo Player —": "default"} | player_options
        sel_name = st.selectbox(
            t("select_player"),
            list(player_options.keys()),
            label_visibility="collapsed",
        )
        st.session_state["active_player"] = player_options[sel_name]
    else:
        st.caption("No players yet. Add in Squad tab.")
        st.session_state["active_player"] = "default"

    pid = st.session_state["active_player"]

    st.markdown("---")

    # ── Navigation ────────────────────────────────────────────────────────────
    nav = st.radio(
        t("nav_label"), label_visibility="collapsed",
        options=[
            t("nav_dashboard"), t("nav_squad"),
            t("nav_tactics"),   t("nav_physical"),
            t("nav_journal"),   t("nav_schedule"),
        ],
    )

    st.markdown("---")

    # ── Live KPIs ─────────────────────────────────────────────────────────────
    st.markdown(f"<div class='sh'>{t('live_kpis')}</div>", unsafe_allow_html=True)

    phys_df = _phys(pid)
    pr_df   = _prs(pid)
    jrnl_df = _jrnl(pid)

    w_val   = f"{float(phys_df.sort_values('date').iloc[-1]['weight_kg']):.1f} kg" if not phys_df.empty else "—"
    st.metric(t("weight_label"), w_val)

    if not pr_df.empty:
        pr1rm = compute_all_1rms(pr_df)
        best  = pr1rm["squat_1rm"].max() if "squat_1rm" in pr1rm.columns else 0
        st.metric(t("squat_1rm_label"), f"{best:.1f} kg" if best else "—")
    else:
        st.metric(t("squat_1rm_label"), "—")

    avg_p = jrnl_df["performance_score"].mean() if not jrnl_df.empty else None
    st.metric(t("avg_perf_label"), f"{avg_p:.1f}/10" if avg_p else "—")

    # Today events
    today_evs = get_today_event_types(pid)
    if today_evs:
        EV_CLR = {"Match Day":"#e74c3c","Rugby Training":"#3498db",
                  "Workout":"#2ecc71","Rest Day":"#5a6070"}
        for ev in today_evs:
            c = EV_CLR.get(ev, "#888")
            st.markdown(f"""
            <div style='padding:5px 10px;margin:3px 0;background:rgba(255,255,255,.04);
                        border-left:3px solid {c};border-radius:0 6px 6px 0;
                        font-size:11px;color:{c};font-weight:700;'>
                {t(ev) if ev in ["Match Day","Rugby Training","Workout","Rest Day"] else ev}
            </div>
            """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style='color:#2a2e3a;font-size:10px;text-align:center;margin-top:16px;'>
        {datetime.now().strftime("%A, %d %B %Y")}
    </div>
    """, unsafe_allow_html=True)


# ── Shared Plotly layout ──────────────────────────────────────────────────────
PL = dict(
    template="plotly_dark", paper_bgcolor="#13151c", plot_bgcolor="#13151c",
    font=dict(family="Inter, sans-serif", size=11),
    xaxis=dict(gridcolor="#1a1d27", zeroline=False),
    yaxis=dict(gridcolor="#1a1d27", zeroline=False),
    margin=dict(t=10, b=40, l=50, r=10),
)


# ═══════════════════════════════════════════════════════════════════════════════
#  🏠  DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

if nav == t("nav_dashboard"):
    lang = get_lang()
    st.markdown(f"""
    <h2 style='color:#2ecc71;font-weight:900;margin-bottom:2px;'>{t("dashboard_title")}</h2>
    <p style='color:#5a6070;font-size:13px;'>{t("dashboard_sub")}</p>
    """, unsafe_allow_html=True)

    phys_df = _phys(pid); pr_df = _prs(pid); jrnl_df = _jrnl(pid)

    # Alerts
    if check_burnout_alert(jrnl_df):
        st.markdown(f"""
        <div class='alert-r'>
            <strong style='color:#e74c3c;'>{t("burnout_title")}</strong><br>
            <span style='color:#ccc;font-size:13px;'>{t("burnout_body")}</span>
        </div>""", unsafe_allow_html=True)

    fat_alert = check_fat_gain_alert(phys_df, pr_df)
    if fat_alert["alert"]:
        st.markdown(f"""
        <div class='alert-y'>
            <strong style='color:#f1c40f;'>{t("fat_gain_title")}</strong><br>
            <span style='color:#ccc;font-size:13px;'>{fat_alert["message"]}</span>
        </div>""", unsafe_allow_html=True)

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        curr  = float(phys_df.sort_values("date").iloc[-1]["weight_kg"]) if not phys_df.empty else None
        delta = fat_alert.get("weight_delta", 0)
        dclr  = "#2ecc71" if delta >= 0 else "#e74c3c"
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        st.markdown(f"""<div class='kpi'>
            <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2.5px;'>{t("kpi_body_weight")}</div>
            <div style='font-size:30px;font-weight:900;color:#fff;margin:8px 0 4px;'>
                {f"{curr:.1f}" if curr else "—"}<span style='font-size:13px;color:#3a3e4a;'> kg</span></div>
            <div style='font-size:11px;color:{dclr};font-weight:700;'>
                {f"{arrow} {abs(delta):.1f} kg" if delta else t("no_history")}</div>
        </div>""", unsafe_allow_html=True)

    with k2:
        best_sq = None
        if not pr_df.empty:
            pr1rm = compute_all_1rms(pr_df)
            if "squat_1rm" in pr1rm.columns: best_sq = pr1rm["squat_1rm"].max()
        st.markdown(f"""<div class='kpi'>
            <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2.5px;'>{t("kpi_squat_1rm")}</div>
            <div style='font-size:30px;font-weight:900;color:#f1c40f;margin:8px 0 4px;'>
                {f"{best_sq:.1f}" if best_sq else "—"}<span style='font-size:13px;color:#3a3e4a;'> kg</span></div>
            <div style='font-size:11px;color:#5a6070;font-weight:700;'>{t("epley_label")}</div>
        </div>""", unsafe_allow_html=True)

    with k3:
        avg_p = jrnl_df["performance_score"].mean() if not jrnl_df.empty else None
        pclr  = "#2ecc71" if avg_p and avg_p>=7.5 else "#f1c40f" if avg_p and avg_p>=5 else "#e74c3c"
        st.markdown(f"""<div class='kpi'>
            <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2.5px;'>{t("kpi_avg_perf")}</div>
            <div style='font-size:30px;font-weight:900;color:{pclr if avg_p else "#3a3e4a"};margin:8px 0 4px;'>
                {f"{avg_p:.1f}" if avg_p else "—"}<span style='font-size:13px;color:#3a3e4a;'>/10</span></div>
            <div style='font-size:11px;color:#5a6070;font-weight:700;'>{len(jrnl_df)} {t("entries_label")}</div>
        </div>""", unsafe_allow_html=True)

    with k4:
        today_evs = get_today_event_types(pid)
        ev_lbl    = today_evs[0] if today_evs else t("Rest Day")
        ev_clr    = {"Match Day":"#e74c3c","Rugby Training":"#3498db",
                     "Workout":"#2ecc71","Rest Day":"#5a6070"}.get(ev_lbl,"#888")
        st.markdown(f"""<div class='kpi'>
            <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2.5px;'>{t("kpi_today")}</div>
            <div style='font-size:18px;font-weight:900;color:{ev_clr};margin:10px 0 4px;line-height:1.2;'>
                {t(ev_lbl) if ev_lbl in ["Match Day","Rugby Training","Workout","Rest Day"] else ev_lbl}</div>
            <div style='font-size:11px;color:#5a6070;'>{datetime.now().strftime("%d %b %Y")}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── ACWR Widget ───────────────────────────────────────────────────────────
    st.markdown(f"<div class='sh'>{t('acwr_section')}</div>", unsafe_allow_html=True)
    acwr_data = calculate_acwr(pid)
    zmeta     = acwr_zone_meta(acwr_data["zone"], lang)

    if acwr_data["acwr"] is None:
        st.markdown(f"""<div class='glass' style='padding:14px;'>
            <div style='color:#5a6070;font-size:13px;'>{t("acwr_no_data")}</div>
        </div>""", unsafe_allow_html=True)
    else:
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1:
            st.markdown(f"""<div class='glass' style='text-align:center;padding:16px;'>
                <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2px;'>ACWR</div>
                <div style='font-size:28px;font-weight:900;color:{zmeta["color"]};margin:6px 0;'>
                    {acwr_data["acwr"]:.2f}</div>
                <div style='color:{zmeta["color"]};font-size:11px;font-weight:700;'>
                    {zmeta["label"]}</div>
                <div class='acwr-bar-wrap'><div class='acwr-bar-fill'
                    style='width:{zmeta["bar_pct"]}%;background:{zmeta["color"]};'></div></div>
            </div>""", unsafe_allow_html=True)
        with ac2:
            st.markdown(f"""<div class='glass' style='text-align:center;padding:16px;'>
                <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2px;'>ACUTE</div>
                <div style='font-size:24px;font-weight:900;color:#e8eaf0;margin:6px 0;'>
                    {acwr_data["acute_load"]}</div>
                <div style='color:#5a6070;font-size:10px;'>units / 7 days</div>
            </div>""", unsafe_allow_html=True)
        with ac3:
            st.markdown(f"""<div class='glass' style='text-align:center;padding:16px;'>
                <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2px;'>CHRONIC</div>
                <div style='font-size:24px;font-weight:900;color:#e8eaf0;margin:6px 0;'>
                    {acwr_data["chronic_avg"]}</div>
                <div style='color:#5a6070;font-size:10px;'>avg units / week</div>
            </div>""", unsafe_allow_html=True)
        with ac4:
            st.markdown(f"""<div class='glass' style='padding:14px;'>
                <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2px;
                            margin-bottom:6px;'>ADVICE</div>
                <div style='color:#ccc;font-size:12px;line-height:1.5;'>
                    {zmeta["advice"]}</div>
            </div>""", unsafe_allow_html=True)

        if acwr_data["zone"] == "danger":
            st.markdown(f"""<div class='alert-r'>
                🚨 <strong style='color:#e74c3c;'>{t("acwr_danger")}</strong>
                — {zmeta["advice"]}</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Trend charts
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"<div class='sh'>{t('weight_trend')}</div>", unsafe_allow_html=True)
        if not phys_df.empty and len(phys_df) >= 2:
            fig = go.Figure(go.Scatter(
                x=phys_df.sort_values("date")["date"],
                y=phys_df.sort_values("date")["weight_kg"],
                mode="lines+markers",
                line=dict(color="#2ecc71",width=2.5), marker=dict(size=7,color="#2ecc71"),
                fill="tozeroy", fillcolor="rgba(46,204,113,.05)",
            ))
            fig.update_layout(**PL, height=220)
            st.plotly_chart(fig, use_container_width=True)
        else: st.info(t("log_2_more"))

    with c2:
        st.markdown(f"<div class='sh'>{t('perf_sentiment')}</div>", unsafe_allow_html=True)
        if not jrnl_df.empty and len(jrnl_df) >= 2:
            ss = pd.to_numeric(jrnl_df["sentiment"],errors="coerce").fillna(0)*10
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=jrnl_df["timestamp"],y=ss,name="Sentiment×10",
                marker_color=["#2ecc71" if v>0 else "#e74c3c" for v in ss],opacity=.5))
            fig2.add_trace(go.Scatter(
                x=jrnl_df["timestamp"],
                y=pd.to_numeric(jrnl_df["performance_score"],errors="coerce"),
                mode="lines+markers",name="Performance",
                line=dict(color="#3498db",width=2.5),marker=dict(size=8,color="#3498db"),
            ))
            fig2.add_hline(y=7.5,line_dash="dot",line_color="#2ecc71",opacity=.3)
            fig2.update_layout(**PL,height=220,barmode="overlay",
                               legend=dict(bgcolor="rgba(0,0,0,0)",font_size=10))
            st.plotly_chart(fig2, use_container_width=True)
        else: st.info(t("log_2_journal"))

    # PDF
    st.markdown(f"<div class='sh'>{t('pdf_section')}</div>", unsafe_allow_html=True)
    if st.button(t("pdf_button")):
        with st.spinner(t("pdf_building")):
            pdf_bytes = generate_pdf_report(phys_df, pr_df, jrnl_df,
                                            player_name=get_player_name(pid))
        if pdf_bytes:
            st.download_button(t("pdf_download"), data=pdf_bytes,
                               file_name=f"rugby_report_{pid}_{date.today()}.pdf",
                               mime="application/pdf")
        else:
            st.error(t("pdf_error"))


# ═══════════════════════════════════════════════════════════════════════════════
#  👥  SQUAD MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

elif nav == t("nav_squad"):
    lang = get_lang()
    st.markdown(f"""
    <h2 style='color:#3498db;font-weight:900;margin-bottom:2px;'>{t("squad_title")}</h2>
    <p style='color:#5a6070;font-size:13px;'>{t("squad_sub")}</p>
    """, unsafe_allow_html=True)

    sa, sb = st.columns([1, 2])

    with sa:
        st.markdown(f"<div class='sh'>{t('squad_add_section')}</div>", unsafe_allow_html=True)
        POSITIONS = [
            "Loosehead Prop (1)","Hooker (2)","Tighthead Prop (3)",
            "Lock (4)","Lock (5)","Blindside Flanker (6)",
            "Openside Flanker (7)","Number 8 (8)","Scrum-half (9)",
            "Fly-half (10)","Left Wing (11)","Inside Centre (12)",
            "Outside Centre (13)","Right Wing (14)","Fullback (15)",
        ]
        with st.form("add_player_form"):
            pname = st.text_input(t("player_name"), placeholder="José García")
            ppos  = st.selectbox(t("player_position"), POSITIONS)
            pnum  = st.number_input(t("player_number"), 1, 99, 1)
            pdob  = st.date_input(t("player_dob"), value=date(2000, 1, 1))
            if st.form_submit_button(t("player_save")):
                ok, new_pid = save_player(pname, ppos, pnum, str(pdob))
                if ok:
                    st.success(t("player_saved_ok"))
                    st.cache_data.clear(); st.rerun()
                else:
                    st.warning(t("player_exists"))

    with sb:
        players = _players()
        st.markdown(f"<div class='sh'>{t('squad_roster')}</div>", unsafe_allow_html=True)

        if not players:
            st.markdown(f"""<div class='glass' style='text-align:center;padding:40px;'>
                <div style='font-size:36px;'>👥</div>
                <div style='color:#3a3e4a;font-size:13px;margin-top:10px;'>{t("squad_empty")}</div>
            </div>""", unsafe_allow_html=True)
        else:
            for p in players:
                is_active = p["id"] == pid
                border_c  = "#2ecc71" if is_active else "#1a1d27"
                pc1, pc2  = st.columns([5, 1])
                with pc1:
                    st.markdown(f"""
                    <div class='glass' style='border-color:{border_c};padding:14px 16px;'>
                        <div style='display:flex;justify-content:space-between;align-items:center;'>
                            <div>
                                <span style='color:#e8eaf0;font-weight:800;font-size:15px;'>
                                    #{p["number"]} {p["name"]}
                                </span>
                                {"  <span style='color:#2ecc71;font-size:10px;font-weight:700;background:rgba(46,204,113,.12);padding:2px 7px;border-radius:10px;margin-left:6px;'>ACTIVE</span>" if is_active else ""}
                            </div>
                            <span style='color:#5a6070;font-size:12px;'>{p["position"]}</span>
                        </div>
                        <div style='color:#3a3e4a;font-size:11px;margin-top:6px;'>
                            DOB: {p.get("dob","—")}  ·  Added: {p.get("added","—")}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with pc2:
                    if st.button(t("squad_delete"), key=f"dp_{p['id']}"):
                        delete_player(p["id"])
                        st.cache_data.clear(); st.rerun()

        # Squad 1RM comparison bar chart
        players = _players()
        if len(players) > 1:
            st.markdown(f"<div class='sh' style='margin-top:18px;'>{t('squad_comparison')}</div>",
                        unsafe_allow_html=True)
            names, sq1rms = [], []
            for p in players:
                prd = load_pr_log(p["id"])
                if not prd.empty:
                    pr1 = compute_all_1rms(prd)
                    best = pr1["squat_1rm"].max() if "squat_1rm" in pr1.columns else 0
                    names.append(p["name"]); sq1rms.append(best)
            if names:
                fig_cmp = go.Figure(go.Bar(
                    x=names, y=sq1rms, marker_color="#2ecc71",
                    text=[f"{v:.0f} kg" for v in sq1rms], textposition="outside",
                ))
                fig_cmp.update_layout(**PL, height=260,
                    yaxis=dict(title="Squat 1RM (kg)", gridcolor="#1a1d27"),
                    xaxis=dict(gridcolor="#1a1d27"))
                st.plotly_chart(fig_cmp, use_container_width=True)
            else:
                st.info(t("squad_no_pr"))


# ═══════════════════════════════════════════════════════════════════════════════
#  🎬  TACTICS LAB
# ═══════════════════════════════════════════════════════════════════════════════

elif nav == t("nav_tactics"):
    lang = get_lang()
    st.markdown(f"""
    <h2 style='color:#2ecc71;font-weight:900;margin-bottom:2px;'>{t("tactics_title")}</h2>
    <p style='color:#5a6070;font-size:13px;'>{t("tactics_sub")}</p>
    """, unsafe_allow_html=True)

    tv, ta = st.columns([3, 2])

    with tv:
        st.markdown(f"<div class='sh'>{t('video_input')}</div>", unsafe_allow_html=True)
        uploaded = st.file_uploader(t("upload_video"), type=["mp4","mov"], key="v4_upload")

        if uploaded:
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(uploaded.read()); tfile.flush()
            st.video(tfile.name)

            st.markdown(f"<div class='sh'>{t('analysis_controls')}</div>", unsafe_allow_html=True)
            ca, cb, cc = st.columns(3)
            with ca: frame_num = st.number_input(t("frame_label"), 0, 9999, 0, 1)
            with cb: skip_n    = st.selectbox(t("skip_label"), [1,2,3,5], index=2)
            with cc: run_det   = st.checkbox(t("yolo_label"), value=False)
            run_events  = st.checkbox(t("event_ai_label"),    value=False)
            run_teams   = st.checkbox(t("team_cluster_label"),value=False)

            if st.button(t("analyse_btn")):
                try:
                    import cv2
                    cap = cv2.VideoCapture(tfile.name)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, raw = cap.read(); cap.release()

                    if not ret:
                        st.error("Could not read that frame.")
                    else:
                        frame_rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
                        fh, fw    = frame_rgb.shape[:2]
                        st.session_state["frame_w"] = fw
                        st.session_state["frame_h"] = fh

                        dets:   list[Detection]  = []
                        events: list[FrameEvent] = []

                        if run_det:
                            model = _yolo()
                            if model:
                                dets = run_yolo_on_frame(model, frame_rgb)
                                # Persistent tracking
                                dets = st.session_state["tracker"].update(dets)
                                np_  = sum(1 for d in dets if d.label=="person")
                                nb_  = sum(1 for d in dets if d.label=="sports ball")
                                st.success(f"✅ {np_} {t('players_detected')} · {nb_} {t('balls_detected')}")
                            else:
                                st.warning("ultralytics not installed: pip install ultralytics")

                        if run_teams and dets:
                            cl = TeamClusterer()
                            cl.fit(frame_rgb, dets)
                            dets = cl.assign(dets)
                            hn = sum(1 for d in dets if d.team=="home")
                            an = sum(1 for d in dets if d.team=="away")
                            st.info(f"👕 {t('teams_detected')}: {hn} HOME 🟢  ·  {an} AWAY 🔵")

                        if run_events and dets:
                            detector = RugbyEventDetector(fps=25, skip_n=skip_n)
                            events   = detector.update(dets, frame_num)
                            # Store event coords in heatmap store
                            st.session_state["heatmap_store"].add(events, fw, fh)
                            if events:
                                for ev in events:
                                    ic = {"Tackle":"🔴","Ruck":"🔵","Scrum":"⚫","Line-out":"🟢"}.get(ev.event,"⚪")
                                    st.markdown(f"""<div class='alert-g' style='padding:10px 14px;'>
                                        <strong style='color:#2ecc71;'>{ic} {ev.event}</strong>
                                        <span style='color:#5a6070;font-size:11px;margin-left:8px;'>
                                            {ev.confidence:.0%} {t("confidence")}</span>
                                        <div style='color:#999;font-size:11px;margin-top:4px;'>
                                            {ev.details}</div>
                                    </div>""", unsafe_allow_html=True)
                            else:
                                st.info(t("no_events_frame"))

                        if dets:
                            frame_rgb = draw_detections(frame_rgb, dets, events)

                        st.session_state["frame_rgb"] = frame_rgb
                        st.image(frame_rgb, caption=f"Frame #{frame_num}", use_column_width=True)

                        st.markdown(f"""<div class='glass' style='padding:10px 14px;'>
                            <span style='color:#5a6070;font-size:10px;font-weight:800;letter-spacing:2px;'>
                                {t("frame_skip_info")}</span>
                            <span style='color:#2ecc71;font-weight:700;margin-left:8px;'>
                                {skip_n}× {t("faster_processing")}</span>
                            <span style='color:#3a3e4a;font-size:11px;margin-left:6px;'>
                                · {round(25/skip_n,1)} {t("eff_fps")}</span>
                        </div>""", unsafe_allow_html=True)

                except ImportError:
                    st.warning("OpenCV not installed: pip install opencv-python-headless")
                except Exception as e:
                    st.error(f"Error: {e}")

            # Telestrator
            if st.session_state["frame_rgb"] is not None:
                st.markdown(f"<div class='sh'>{t('telestrator_title')}</div>", unsafe_allow_html=True)
                try:
                    from streamlit_drawable_canvas import st_canvas
                    fi  = Image.fromarray(st.session_state["frame_rgb"])
                    mw  = 680
                    ch  = int(fi.height*mw/fi.width)
                    fi  = fi.resize((mw,ch))
                    t1,t2,t3 = st.columns(3)
                    with t1: tool = st.selectbox(t("draw_tool"),
                                                 ["freedraw","line","circle","rect","transform"],
                                                 format_func=lambda x:{"freedraw":"✏️","line":"➡️",
                                                 "circle":"⭕","rect":"▪️","transform":"🖱️"}.get(x,x))
                    with t2: stroke_c = st.color_picker(t("draw_color"), "#2ecc71")
                    with t3: stroke_w = st.slider(t("draw_width"), 1, 10, 3)
                    cr = st_canvas(fill_color="rgba(46,204,113,.08)",
                                   stroke_width=stroke_w, stroke_color=stroke_c,
                                   background_image=fi, update_streamlit=True,
                                   height=ch, width=mw, drawing_mode=tool, key="tel_v4")
                    if st.button(t("export_btn")):
                        ov = cr.image_data if cr.image_data is not None else None
                        png = export_annotated_frame(st.session_state["frame_rgb"], ov)
                        st.download_button(t("download_png"), data=png,
                                           file_name=f"tactics_{frame_num}.png", mime="image/png")
                except ImportError:
                    st.info("pip install streamlit-drawable-canvas")

            # ── Heatmap section ───────────────────────────────────────────────
            st.markdown("---")
            st.markdown(f"<div class='sh'>{t('heatmap_title')}</div>", unsafe_allow_html=True)
            st.caption(t("heatmap_sub"))

            hstore = st.session_state["heatmap_store"]
            if hstore.count() == 0:
                st.info(t("heatmap_no_data"))
            else:
                hcol1, hcol2 = st.columns([1,3])
                with hcol1:
                    ev_opts = [t("heatmap_all")] + list_events()
                    hev_sel = st.selectbox(t("heatmap_event_filter"), ev_opts)
                    if st.button("🗑️ Clear Heatmap"):
                        hstore.clear(); st.rerun()
                    st.markdown(f"""<div class='glass' style='padding:12px;'>
                        <div style='color:#5a6070;font-size:10px;font-weight:800;letter-spacing:2px;'>
                            EVENTS</div>
                        <div style='font-size:22px;font-weight:900;color:#2ecc71;margin-top:4px;'>
                            {hstore.count()}</div>
                    </div>""", unsafe_allow_html=True)
                with hcol2:
                    filter_val = "All" if hev_sel == t("heatmap_all") else hev_sel
                    fig_hm = hstore.build_plotly_heatmap(filter_event=filter_val, lang=lang)
                    if fig_hm:
                        st.plotly_chart(fig_hm, use_container_width=True)
                    else:
                        st.info(f"No '{filter_val}' events recorded yet.")

        else:
            st.markdown(f"""<div class='glass' style='text-align:center;padding:60px 20px;'>
                <div style='font-size:56px;'>🎬</div>
                <div style='color:#3a3e4a;font-size:14px;margin-top:12px;'>
                    {t("upload_prompt")}</div>
            </div>""", unsafe_allow_html=True)

    with ta:
        st.markdown(f"<div class='sh'>{t('manual_tag')}</div>", unsafe_allow_html=True)
        sel = st.selectbox(t("tag_event"), [t("tag_select")] + list_events())
        if sel and sel != t("tag_select"):
            adv = get_advice(sel)
            if adv:
                st.markdown(f"""<div style='color:{adv["color"]};font-size:15px;
                    font-weight:800;padding:6px 0 10px;'>{adv["title"]}</div>""",
                    unsafe_allow_html=True)
                with st.expander(t("checkpoints_title"), expanded=True):
                    for cp in adv["checkpoints"]:
                        st.markdown(f"<div class='cp'>{cp}</div>", unsafe_allow_html=True)
                st.markdown(f"""<div class='glass' style='background:rgba(241,196,15,.06);
                    border-color:rgba(241,196,15,.2);padding:11px 14px;'>
                    <div style='font-size:13px;color:#f1c40f;'>{adv["tip"]}</div>
                </div>""", unsafe_allow_html=True)
                with st.expander(t("drills_title")):
                    for d in adv.get("drills",[]):
                        st.markdown(f"""<div style='padding:6px 10px;margin:3px 0;
                            background:rgba(52,152,219,.08);border-left:3px solid #3498db;
                            border-radius:0 6px 6px 0;font-size:12px;color:#ccc;'>
                            🔹 {d}</div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class='glass' style='text-align:center;padding:36px;'>
                <div style='font-size:32px;'>🏉</div>
                <div style='color:#3a3e4a;font-size:12px;margin-top:10px;'>
                    {t("select_event_prompt")}</div>
            </div>""", unsafe_allow_html=True)

        # AI logic legend
        st.markdown(f"<div class='sh' style='margin-top:16px;'>{t('ai_event_logic')}</div>",
                    unsafe_allow_html=True)
        for icon, clr, desc_en, desc_es in [
            ("🔴 Tackle","#e74c3c",
             "2 opponents < 60px · ball v < 0.5 m/s",
             "2 rivales < 60px · v balón < 0.5 m/s"),
            ("🔵 Ruck","#2ecc71",
             "≥3 players in 80px of ball · 12+ frames",
             "≥3 jugadores en 80px del balón · 12+ frames"),
            ("⚫ Scrum","#f1c40f",
             "2 opposing clusters facing ± x-axis",
             "2 grupos opuestos enfrentados en eje x"),
            ("🟢 Line-out","#3498db",
             "2 parallel rows, 30–140px gap, 60%+ y-overlap",
             "2 filas paralelas, gap 30-140px, 60%+ superposición"),
        ]:
            desc = desc_es if get_lang()=="es" else desc_en
            st.markdown(f"""<div style='padding:7px 11px;margin:4px 0;
                background:rgba(255,255,255,.03);border-left:3px solid {clr};border-radius:0 6px 6px 0;'>
                <div style='font-size:12px;color:{clr};font-weight:700;'>{icon}</div>
                <div style='font-size:10px;color:#5a6070;margin-top:2px;'>{desc}</div>
            </div>""", unsafe_allow_html=True)

        # Tracking info
        st.markdown(f"<div class='sh' style='margin-top:12px;'>{t('tracking_id_label')}</div>",
                    unsafe_allow_html=True)
        tracker = st.session_state["tracker"]
        n_active = len(tracker._centroids)
        st.markdown(f"""<div class='glass' style='padding:12px 14px;'>
            <div style='color:#5a6070;font-size:10px;font-weight:800;letter-spacing:2px;'>ACTIVE TRACKS</div>
            <div style='font-size:22px;font-weight:900;color:#2ecc71;margin:4px 0;'>{n_active}</div>
            <div style='color:#5a6070;font-size:11px;'>
                Next ID: #{tracker._next_id}  ·  Max dist: {CentroidTracker.MAX_DIST}px
            </div>
        </div>""", unsafe_allow_html=True)
        if st.button("🔄 Reset Tracker"):
            st.session_state["tracker"] = CentroidTracker()
            st.success("Tracker reset.")


# ═══════════════════════════════════════════════════════════════════════════════
#  💪  PHYSICAL HUB
# ═══════════════════════════════════════════════════════════════════════════════

elif nav == t("nav_physical"):
    lang = get_lang()
    st.markdown(f"""
    <h2 style='color:#f1c40f;font-weight:900;margin-bottom:2px;'>{t("physical_title")}</h2>
    <p style='color:#5a6070;font-size:13px;'>{t("physical_sub")}</p>
    """, unsafe_allow_html=True)

    s1, s2, s3, s4 = st.tabs([t("tab_log_data"),t("tab_1rm_charts"),
                               t("tab_measures"),t("tab_nutrition")])

    with s1:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div class='sh'>{t('anthropo_section')}</div>", unsafe_allow_html=True)
            with st.form("anthro_v4"):
                wt = st.number_input(t("weight_kg"),  60.0,180.0,100.0,.5)
                ht = st.number_input(t("height_cm"), 150.0,220.0,185.0,.5)
                bf = st.number_input(t("body_fat_pct"),3.0,40.0,15.0,.1)
                if st.form_submit_button(t("save_btn")):
                    if save_physical_entry(wt,ht,bf,pid):
                        st.success(t("save_ok")); st.cache_data.clear(); st.rerun()
                    else: st.error(t("validation_fail"))
            phys = _phys(pid)
            if not phys.empty:
                st.dataframe(phys.tail(5).sort_values("date",ascending=False),
                             use_container_width=True, hide_index=True)

        with c2:
            st.markdown(f"<div class='sh'>{t('prs_section')}</div>", unsafe_allow_html=True)
            st.caption(t("prs_caption"))
            with st.form("prs_v4"):
                ck, cr = st.columns(2)
                with ck:
                    sq=st.number_input("🏋️ Squat (kg)",      40.0,400.0,140.0,2.5)
                    bp=st.number_input("🤜 Bench (kg)",       40.0,300.0,110.0,2.5)
                    dl=st.number_input("⬆️ Deadlift (kg)",    60.0,500.0,180.0,2.5)
                    pc=st.number_input("⚡ Power Clean (kg)", 30.0,250.0, 90.0,2.5)
                with cr:
                    sqr=st.number_input(t("reps_label"),1,20,3,key="sqr4")
                    bpr=st.number_input(t("reps_label"),1,20,5,key="bpr4")
                    dlr=st.number_input(t("reps_label"),1,20,3,key="dlr4")
                    pcr=st.number_input(t("reps_label"),1,20,3,key="pcr4")
                if st.form_submit_button(t("save_btn")):
                    ok = save_pr_entry(sq,sqr,bp,bpr,dl,dlr,pc,pcr,pid)
                    if ok:
                        st.success(f"{t('save_ok')} Squat 1RM → **{epley_1rm(sq,sqr)} kg**")
                        st.cache_data.clear(); st.rerun()
                    else: st.error(t("validation_fail"))

    with s2:
        pr_df2  = _prs(pid); phys_df2 = _phys(pid)
        if pr_df2.empty: st.info(t("log_2_prs"))
        else:
            pr1rm = compute_all_1rms(pr_df2)
            st.markdown(f"<div class='sh'>{t('1rm_chart_title')}</div>", unsafe_allow_html=True)
            fig = go.Figure()
            for col,clr,lbl in [("squat_1rm","#2ecc71","Squat"),("bench_1rm","#f1c40f","Bench"),
                                 ("deadlift_1rm","#3498db","Deadlift"),("power_clean_1rm","#e74c3c","Power Clean")]:
                if col in pr1rm.columns:
                    fig.add_trace(go.Scatter(x=pr1rm["date"],y=pr1rm[col],mode="lines+markers",
                        name=lbl,line=dict(color=clr,width=2.5),marker=dict(size=8,color=clr)))
            fig.update_layout(**PL,height=300,legend=dict(bgcolor="rgba(0,0,0,0)"),
                              yaxis=dict(title="kg",gridcolor="#1a1d27"))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(t("epley_caption"))
            if not phys_df2.empty:
                merged = pd.merge(phys_df2[["date","weight_kg"]],
                                  pr1rm[["date","squat_1rm"]].dropna(),on="date",how="inner")
                if len(merged)>=2:
                    st.markdown(f"<div class='sh'>{t('scatter_title')}</div>", unsafe_allow_html=True)
                    fig2 = px.scatter(merged,x="weight_kg",y="squat_1rm",trendline="ols",
                        labels={"weight_kg":"Body Weight (kg)","squat_1rm":"Squat 1RM (kg)"},
                        color_discrete_sequence=["#f1c40f"],template="plotly_dark")
                    fig2.update_layout(**PL,height=260)
                    st.plotly_chart(fig2, use_container_width=True)

    with s3:
        cm1,cm2 = st.columns(2)
        with cm1:
            st.markdown(f"<div class='sh'>{t('measures_section')}</div>", unsafe_allow_html=True)
            with st.form("meas_v4"):
                qd=st.number_input(t("quad_cm"), 30.0,100.0,58.0,.5)
                am=st.number_input(t("arm_cm"),  20.0, 60.0,40.0,.5)
                ch=st.number_input(t("chest_cm"),60.0,160.0,105.0,.5)
                st.caption(t("measure_caption"))
                if st.form_submit_button(t("save_btn")):
                    if save_measures_entry(qd,am,ch,pid):
                        st.success(t("save_ok")); st.cache_data.clear(); st.rerun()
                    else: st.error(t("validation_fail"))
            meas = _meas(pid)
            if not meas.empty:
                st.dataframe(meas.tail(5).sort_values("date",ascending=False),
                             use_container_width=True, hide_index=True)
        with cm2:
            meas = _meas(pid); radar = build_radar_data(meas)
            if radar:
                st.markdown(f"<div class='sh'>{t('radar_title')}</div>", unsafe_allow_html=True)
                cats = radar["categories"]+[radar["categories"][0]]
                figr = go.Figure()
                figr.add_trace(go.Scatterpolar(r=radar["reference"]+[radar["reference"][0]],
                    theta=cats,fill="toself",name="Elite Ref",
                    line=dict(color="#f1c40f",dash="dot"),fillcolor="rgba(241,196,15,.05)"))
                figr.add_trace(go.Scatterpolar(r=radar["values"]+[radar["values"][0]],
                    theta=cats,fill="toself",name="You",
                    line=dict(color="#2ecc71"),fillcolor="rgba(46,204,113,.12)"))
                figr.update_layout(
                    polar=dict(radialaxis=dict(visible=True,range=[0,120],
                               gridcolor="#1a1d27",tickfont_size=9),
                               angularaxis=dict(gridcolor="#1a1d27"),bgcolor="#13151c"),
                    paper_bgcolor="#13151c",template="plotly_dark",height=290,
                    margin=dict(t=30,b=20,l=30,r=30),
                    legend=dict(bgcolor="rgba(0,0,0,0)",font_size=11),
                    font=dict(family="Inter,sans-serif"))
                st.plotly_chart(figr, use_container_width=True)
                st.caption(t("radar_caption"))
                for k,v in radar["raw"].items():
                    st.markdown(f"""<div style='display:flex;justify-content:space-between;
                        padding:5px 10px;border-bottom:1px solid #1a1d27;font-size:12px;'>
                        <span style='color:#5a6070;'>{k}</span>
                        <span style='color:#e8eaf0;font-weight:700;'>{v:.1f} cm</span>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info(t("log_measure"))
            meas = _meas(pid)
            if not meas.empty and len(meas)>=2:
                st.markdown(f"<div class='sh' style='margin-top:16px;'>{t('growth_title')}</div>",
                            unsafe_allow_html=True)
                figm = go.Figure()
                for col,clr,lbl in [("quad_cm","#2ecc71","Quad"),("arm_cm","#f1c40f","Arm"),
                                     ("chest_cm","#3498db","Chest")]:
                    figm.add_trace(go.Scatter(x=meas.sort_values("date")["date"],
                        y=pd.to_numeric(meas.sort_values("date")[col],errors="coerce"),
                        mode="lines+markers",name=lbl,
                        line=dict(color=clr,width=2),marker=dict(size=6,color=clr)))
                figm.update_layout(**PL,height=220,legend=dict(bgcolor="rgba(0,0,0,0)"),
                                   yaxis=dict(title="cm"))
                st.plotly_chart(figm, use_container_width=True)

    with s4:
        today_evs = get_today_event_types(pid)
        is_hard   = any(e in {"Match Day","Rugby Training"} for e in today_evs)
        if is_hard:
            st.markdown(f"""<div class='alert-g' style='padding:12px 16px;'>
                <strong style='color:#2ecc71;'>{t("cal_sync_active")}</strong>
                — {" + ".join(today_evs)}<br>
                <span style='color:#888;font-size:12px;'>{t("tdee_boost")} · {t("carb_priority")}</span>
            </div>""", unsafe_allow_html=True)
        n1,n2 = st.columns([1,1])
        with n1:
            nw  = st.number_input(t("weight_kg"),  60.0,180.0,100.0,.5, key="nw4")
            nh  = st.number_input(t("height_cm"), 150.0,220.0,185.0,.5, key="nh4")
            act = st.selectbox(t("activity_label"),
                               ["very_active","extra_active","moderately_active"],
                               format_func=lambda x:{
                                   "moderately_active":t("act_moderate"),
                                   "very_active":t("act_very"),
                                   "extra_active":t("act_extra")}.get(x,x))
        with n2:
            tgts = bulking_targets(nw,nh,act,today_events=today_evs)
            boost_tag = ('<span style="background:#2ecc71;color:#000;font-size:9px;'
                         'font-weight:800;padding:2px 7px;border-radius:10px;margin-left:8px;">+20% TDEE</span>'
                         if is_hard else "")
            st.markdown(f"""<div class='kpi' style='text-align:left;'>
                <div style='color:#5a6070;font-size:9px;font-weight:800;letter-spacing:2.5px;'>
                    {t("daily_target")} {boost_tag}</div>
                <div style='font-size:32px;font-weight:900;color:#2ecc71;margin:8px 0 4px;'>
                    {tgts["bulking_calories"]:,}<span style='font-size:13px;color:#3a3e4a;'> kcal</span></div>
                <div style='font-size:11px;color:#3a3e4a;'>
                    BMR {tgts["bmr"]} · TDEE {tgts["adjusted_tdee"]} · +400 surplus</div>
            </div>""", unsafe_allow_html=True)
            m1,m2,m3 = st.columns(3)
            with m1: st.metric(t("protein_label"),f"{tgts['protein_g']}g",delta=f"{tgts['protein_kcal']} kcal")
            with m2: st.metric(t("carbs_label"),  f"{tgts['carb_g']}g",  delta=f"{tgts['carb_kcal']} kcal")
            with m3: st.metric(t("fat_label"),     f"{tgts['fat_g']}g",   delta=f"{tgts['fat_kcal']} kcal")
            figm = go.Figure(go.Pie(
                labels=["Protein","Carbs","Fat"],
                values=[tgts["protein_kcal"],tgts["carb_kcal"],tgts["fat_kcal"]],
                hole=.62, marker=dict(colors=["#2ecc71","#f1c40f","#3498db"]),
                textinfo="label+percent", textfont=dict(size=11,color="white"),
            ))
            figm.update_layout(template="plotly_dark",paper_bgcolor="#13151c",height=210,
                margin=dict(t=5,b=5,l=5,r=5),showlegend=False,
                annotations=[dict(text="Macros",font_size=12,showarrow=False,font_color="#5a6070")])
            st.plotly_chart(figm, use_container_width=True)
        st.markdown(f"<div class='sh'>{t('meal_timing')}</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, meal in enumerate(get_meal_timing_advice(lang)):
            with cols[i%3]:
                st.markdown(f"""<div class='glass' style='padding:11px 13px;'>
                    <div style='color:#f1c40f;font-size:9px;font-weight:800;letter-spacing:1.5px;'>
                        {meal["window"]}</div>
                    <div style='color:#888;font-size:11.5px;margin-top:5px;line-height:1.45;'>
                        {meal["rec"]}</div>
                </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  📓  JOURNAL
# ═══════════════════════════════════════════════════════════════════════════════

elif nav == t("nav_journal"):
    lang = get_lang()
    st.markdown(f"""
    <h2 style='color:#3498db;font-weight:900;margin-bottom:2px;'>{t("journal_title")}</h2>
    <p style='color:#5a6070;font-size:13px;'>{t("journal_sub")}</p>
    """, unsafe_allow_html=True)
    jrnl_df = _jrnl(pid)
    if check_burnout_alert(jrnl_df):
        st.markdown(f"""<div class='alert-r'>
            🚨 <strong style='color:#e74c3c;'>{t("active_rest_rec")}</strong><br>
            <span style='color:#ccc;font-size:13px;'>{t("active_rest_body")}</span>
        </div>""", unsafe_allow_html=True)
    cf,ch = st.columns([2,3])
    with cf:
        POSITIONS = ["Loosehead Prop (1)","Hooker (2)","Tighthead Prop (3)","Lock (4)","Lock (5)",
                     "Blindside Flanker (6)","Openside Flanker (7)","Number 8 (8)","Scrum-half (9)",
                     "Fly-half (10)","Left Wing (11)","Inside Centre (12)","Outside Centre (13)",
                     "Right Wing (14)","Fullback (15)"]
        st.markdown(f"<div class='sh'>{t('post_match_entry')}</div>", unsafe_allow_html=True)
        with st.form("jrnl_v4"):
            pos = st.selectbox(t("position_played"), POSITIONS)
            sc  = st.slider(t("performance_slider"), 1, 10, 7)
            sc_clr = "#e74c3c" if sc<5 else "#f1c40f" if sc<8 else "#2ecc71"
            st.markdown(f"""<div style='text-align:center;padding:6px;'>
                <span style='font-size:38px;font-weight:900;color:{sc_clr};'>{sc}</span>
                <span style='font-size:14px;color:#3a3e4a;'>/10</span></div>""",
                unsafe_allow_html=True)
            notes = st.text_area(t("notes_label"), height=190,
                                 placeholder=t("notes_placeholder"))
            if st.form_submit_button(t("save_entry_btn"), use_container_width=True):
                if notes.strip():
                    ok = save_journal_entry(pos, sc, notes, pid)
                    if ok:
                        st.cache_data.clear()
                        st.success(t("entry_saved")); st.rerun()
                    else: st.error(t("save_failed"))
                else: st.warning(t("add_notes_warn"))
    with ch:
        if jrnl_df.empty:
            st.markdown(f"""<div class='glass' style='text-align:center;padding:60px;'>
                <div style='font-size:44px;'>📓</div>
                <div style='color:#3a3e4a;font-size:13px;margin-top:10px;'>{t("no_journal")}</div>
            </div>""", unsafe_allow_html=True)
        else:
            for _,row in jrnl_df.sort_values("timestamp",ascending=False).iterrows():
                score = int(row.get("performance_score",0)) if pd.notna(row.get("performance_score")) else 0
                sent  = float(row.get("sentiment",0)) if pd.notna(row.get("sentiment")) else 0
                sc    = "#e74c3c" if score<5 else "#f1c40f" if score<8 else "#2ecc71"
                sl    = t("sentiment_positive") if sent>.05 else t("sentiment_negative") if sent<-.05 else t("sentiment_neutral")
                sl_c  = "#2ecc71" if sent>.05 else "#e74c3c" if sent<-.05 else "#5a6070"
                with st.expander(f"{'🟢' if score>=8 else '🟡' if score>=5 else '🔴'}  "
                                 f"{row.get('timestamp','')}  ·  {score}/10  ·  {sl}"):
                    st.markdown(f"""<div style='display:flex;gap:20px;margin-bottom:12px;align-items:center;'>
                        <div style='color:{sc};font-size:28px;font-weight:900;'>{score}/10</div>
                        <div>
                            <div style='color:{sl_c};font-size:12px;font-weight:700;'>{sl}</div>
                            <div style='color:#5a6070;font-size:11px;'>
                                {t("polarity_label")}: {sent:+.3f}</div>
                        </div>
                        <div style='color:#5a6070;font-size:11px;margin-left:auto;'>
                            {row.get("position","—")}</div>
                    </div>""", unsafe_allow_html=True)
                    st.markdown(row.get("notes",""))


# ═══════════════════════════════════════════════════════════════════════════════
#  📅  SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════════

elif nav == t("nav_schedule"):
    lang = get_lang()
    st.markdown(f"""
    <h2 style='color:#e74c3c;font-weight:900;margin-bottom:2px;'>{t("schedule_title")}</h2>
    <p style='color:#5a6070;font-size:13px;'>{t("schedule_sub")}</p>
    """, unsafe_allow_html=True)

    EV_CLR  = {"Workout":"#2ecc71","Rugby Training":"#3498db","Match Day":"#e74c3c","Rest Day":"#5a6070"}
    EV_ICON = {"Workout":"🏋️","Rugby Training":"🏉","Match Day":"🏆","Rest Day":"😴"}
    EV_KEYS = list(EV_CLR.keys())

    TEMPLATES = {
        "Lower Body Power":    "Back Squat 5×5 @ 80%\nRomanian Deadlift 4×8\nBulgarian Split Squat 3×10\nBox Jumps 4×5",
        "Upper Body Strength": "Bench Press 5×5 @ 80%\nBarbell Row 4×8\nOverhead Press 3×10\nPull-ups 4×AMRAP",
        "Full Body Power":     "Power Clean 5×3\nDeadlift 4×5 @ 85%\nPush Press 3×8\nFarmer Carry 4×40m",
        "Active Recovery":     "Foam Rolling 15min\nMobility Work 20min\nLight Swim 30min\nStatic Stretch 15min",
        "Custom":              "",
    }

    cf2, cc = st.columns([1,2])
    with cf2:
        st.markdown(f"<div class='sh'>{t('add_event')}</div>", unsafe_allow_html=True)
        with st.form("sched_v4"):
            edate  = st.date_input(t("event_date"), date.today())
            etype  = st.selectbox(t("event_type"), EV_KEYS,
                                  format_func=lambda x: t(x) if x in ["Match Day","Rugby Training","Workout","Rest Day"] else x)
            if etype == "Workout":
                tmpl   = st.selectbox(t("event_template"), list(TEMPLATES.keys()))
                defdet = TEMPLATES[tmpl]
            else: defdet = ""
            det = st.text_area(t("event_details"), value=defdet, height=130)
            if st.form_submit_button(t("add_event_btn"), use_container_width=True):
                if save_event(str(edate), etype, det, pid):
                    st.success(t("event_added")); st.cache_data.clear(); st.rerun()

    with cc:
        st.markdown(f"<div class='sh'>{t('monthly_calendar')}</div>", unsafe_allow_html=True)
        today = date.today()
        d1,d2 = st.columns(2)
        import calendar as cal_mod
        MONTHS_ES = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio",
                     "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        with d1: sel_m = st.selectbox(t("month_label"), range(1,13),
                                       index=today.month-1,
                                       format_func=lambda m: MONTHS_ES[m] if lang=="es" else cal_mod.month_name[m])
        with d2: sel_y = st.number_input(t("year_label"), 2024, 2030, today.year)
        all_evs = load_schedule()
        by_date: dict = {}
        for ev in all_evs:
            if ev.get("player_id","default") in (pid, "default"):
                by_date.setdefault(ev["date"],[]).append(ev)
        hdrs = st.columns(7)
        DAY_NAMES_EN = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        DAY_NAMES_ES = ["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]
        dn_list = DAY_NAMES_ES if lang=="es" else DAY_NAMES_EN
        for i,dn in enumerate(dn_list):
            hdrs[i].markdown(f"<div style='text-align:center;color:#2a2e3a;font-size:9px;"
                             f"font-weight:800;letter-spacing:1.5px;'>{dn}</div>",
                             unsafe_allow_html=True)
        for week in cal_mod.monthcalendar(sel_y, sel_m):
            wk = st.columns(7)
            for ci,dn in enumerate(week):
                with wk[ci]:
                    if dn==0:
                        st.markdown("<div style='min-height:80px'></div>",unsafe_allow_html=True)
                        continue
                    ds   = f"{sel_y}-{sel_m:02d}-{dn:02d}"
                    it   = ds==str(today)
                    evs  = by_date.get(ds,[])
                    cls  = "cal-today" if it else "cal"
                    ev_h = ""
                    for ev in evs[:2]:
                        c2 = EV_CLR.get(ev["type"],"#888")
                        i2 = EV_ICON.get(ev["type"],"📌")
                        ev_lbl = t(ev["type"]) if ev["type"] in EV_KEYS else ev["type"]
                        ev_h += (f"<div style='font-size:8.5px;color:{c2};"
                                 f"background:rgba(255,255,255,.04);border-radius:3px;"
                                 f"padding:1px 4px;margin-top:2px;overflow:hidden;"
                                 f"white-space:nowrap;text-overflow:ellipsis;'>{i2} {ev_lbl}</div>")
                    if len(evs)>2: ev_h+=f"<div style='font-size:8px;color:#2a2e3a;'>+{len(evs)-2}</div>"
                    dc = "#2ecc71" if it else "#e8eaf0"
                    st.markdown(f"<div class='{cls}'><div style='text-align:right;color:{dc};"
                                f"font-size:12px;font-weight:800;'>{dn}</div>{ev_h}</div>",
                                unsafe_allow_html=True)

    st.markdown(f"<div class='sh' style='margin-top:20px;'>{t('all_events')}</div>",
                unsafe_allow_html=True)
    if not all_evs:
        st.info(t("no_events"))
    else:
        for ev in sorted(all_evs, key=lambda e:e["date"], reverse=True):
            if ev.get("player_id","default") not in (pid,"default"): continue
            c2 = EV_CLR.get(ev["type"],"#888")
            ic = EV_ICON.get(ev["type"],"📌")
            ev_type_lbl = t(ev["type"]) if ev["type"] in EV_KEYS else ev["type"]
            with st.expander(f"{ic} **{ev['date']}** — {ev_type_lbl}"):
                ea,eb = st.columns([5,1])
                with ea:
                    st.markdown(f"""<div style='border-left:3px solid {c2};padding:8px 14px;'>
                        <div style='color:{c2};font-size:12px;font-weight:700;margin-bottom:6px;'>
                            {ic} {ev_type_lbl}  ·  {ev["date"]}</div>
                        <div style='color:#bbb;font-size:12px;white-space:pre-line;line-height:1.6;'>
{ev.get("details", t("no_details"))}
                        </div></div>""", unsafe_allow_html=True)
                with eb:
                    if st.button(t("delete_btn"), key=f"d4_{ev['id']}"):
                        delete_event(ev["id"]); st.rerun()
