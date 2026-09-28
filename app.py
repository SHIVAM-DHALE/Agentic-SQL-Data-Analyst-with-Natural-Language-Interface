"""Enterprise Streamlit frontend for the Agentic SQL Analytics Platform."""

from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import pandas as pd
import plotly.express as px
import streamlit as st

from api_client import (
    change_password_api,
    clear_history_api,
    dashboard_metrics_api,
    dataset_api,
    dataset_download_api,
    dataset_preview_api,
    datasets_api,
    delete_dataset_api,
    delete_history_api,
    download_report_api,
    forgot_password_api,
    health_api,
    history_api,
    login_api,
    me_api,
    monthly_revenue_api,
    orders_by_status_api,
    register_api,
    rename_dataset_api,
    reset_password_api,
    revenue_by_category_api,
    revenue_by_country_api,
    run_demo_query_api,
    run_query_api,
    top_products_api,
    upload_dataset_api,
)
from frontend_utils import (
    available_chart_types,
    build_chart,
    chart_columns,
    chart_recommendation,
    coerce_for_visualization,
    compact_number,
    currency,
    friendly_datetime,
    friendly_name,
    password_strength,
    report_markdown,
    result_dataframe,
    safe_html,
    style_figure,
    suggested_questions,
)


APP_NAME = "Agentic SQL Analyst"
APP_TAGLINE = "Secure, AI-assisted analytics for business data"
NAVIGATION = [
    "Home",
    "Demo Dashboard",
    "My Datasets",
    "Upload Dataset",
    "Query Studio",
    "Results",
    "Query History",
    "Reports",
    "Profile & Security",
    "Project Info",
]
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_UPLOAD_ROWS = 100_000
DEMO_QUESTIONS = [
    "What is the total revenue?",
    "Show revenue by product category",
    "Which five products generated the most revenue?",
    "Show order count by status",
    "Compare revenue by customer country",
    "Show the monthly revenue trend",
]

PAGE_META = {
    "Home": ("Analytics workspace", "Welcome to your decision intelligence hub", "Move from a business question to governed, explainable analysis in one workspace."),
    "Demo Dashboard": ("Executive performance", "Ecommerce demo dashboard", "Monitor the preloaded business dataset with live KPIs and interactive performance views."),
    "My Datasets": ("Data workspace", "Your governed datasets", "Inspect, profile, query, rename, export, and safely manage every dataset you own."),
    "Upload Dataset": ("Data onboarding", "Import a new dataset", "Validate a CSV or Excel workbook, preview its shape, and create a private analytics table."),
    "Query Studio": ("Agentic analysis", "Ask a business question", "Generate table-scoped read-only SQL, evaluate it, execute it, and explain the result."),
    "Results": ("Analysis output", "Results and visualizations", "Review the insight, interactive chart, source data, SQL policy checks, and report artifact."),
    "Query History": ("Audit trail", "Query history", "Search, filter, reopen, and rerun your private analysis history."),
    "Reports": ("Decision records", "Report center", "Package analysis context, SQL, results, quality, and retrieval metadata for review."),
    "Profile & Security": ("Account controls", "Profile and security", "Review your identity, update your password, and control this authenticated session."),
    "Project Info": ("System overview", "How the platform works", "Understand the governed query pipeline, safety boundaries, RAG, and evaluation layers."),
}


st.set_page_config(
    page_title=APP_NAME,
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    :root {
        --canvas: #F4F7FB;
        --surface: #FFFFFF;
        --surface-soft: #F8FAFC;
        --ink: #0F172A;
        --muted: #64748B;
        --line: #E2E8F0;
        --line-strong: #CBD5E1;
        --primary: #4F46E5;
        --primary-dark: #3730A3;
        --primary-soft: #EEF2FF;
        --success: #059669;
        --warning: #D97706;
        --danger: #DC2626;
        --sidebar: #0B1020;
        --sidebar-soft: #131A2D;
    }

    #MainMenu, footer, .stDeployButton {visibility: hidden;}
    .stApp {background: var(--canvas); color: var(--ink);}
    .block-container {max-width: 1540px; padding: 1.35rem 2.25rem 3rem;}
    section[data-testid="stSidebar"] {background: var(--sidebar); border-right: 1px solid #1E293B;}
    section[data-testid="stSidebar"] > div {padding-top: 1rem;}
    section[data-testid="stSidebar"] * {color: #E2E8F0;}
    section[data-testid="stSidebar"] div[role="radiogroup"] label {
        border: 1px solid transparent; border-radius: 9px; padding: 7px 9px; margin: 1px 0;
    }
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background: rgba(148,163,184,.10); border-color: rgba(148,163,184,.15);
    }
    section[data-testid="stSidebar"] .stButton button {
        background: var(--sidebar-soft); color: #F8FAFC; border-color: #334155;
    }
    section[data-testid="stSidebar"] .stButton button:hover {border-color: #818CF8; color: #FFFFFF;}

    .brand {padding: 2px 0 17px;}
    .brand-row {display:flex; align-items:center; gap:11px;}
    .brand-mark {
        width:40px; height:40px; border-radius:11px; display:flex; align-items:center; justify-content:center;
        background:linear-gradient(135deg,#6366F1,#2563EB); color:white; font-size:18px; font-weight:900;
        box-shadow:0 12px 30px rgba(79,70,229,.36);
    }
    .brand-name {font-size:17px; font-weight:850; color:#FFFFFF; line-height:1.2;}
    .brand-copy {font-size:11px; color:#94A3B8; margin-top:3px;}
    .user-card {background:var(--sidebar-soft); border:1px solid #273449; border-radius:11px; padding:12px 13px; margin:13px 0 15px;}
    .user-overline {font-size:10px; text-transform:uppercase; letter-spacing:.09em; color:#94A3B8; font-weight:800;}
    .user-title {font-size:14px; color:#FFFFFF; font-weight:800; margin-top:4px; overflow-wrap:anywhere;}
    .user-email {font-size:11px; color:#94A3B8; overflow-wrap:anywhere; margin-top:2px;}
    .sidebar-status {display:flex; gap:7px; align-items:center; font-size:11px; color:#A7F3D0; margin-top:10px;}
    .status-dot {height:7px; width:7px; border-radius:50%; background:#10B981; box-shadow:0 0 0 3px rgba(16,185,129,.12);}

    .page-head {
        background:rgba(255,255,255,.94); border:1px solid var(--line); border-radius:14px; padding:22px 24px;
        margin-bottom:19px; box-shadow:0 1px 3px rgba(15,23,42,.04);
    }
    .eyebrow {color:var(--primary); text-transform:uppercase; letter-spacing:.09em; font-size:11px; font-weight:850; margin-bottom:7px;}
    .page-title {font-size:29px; line-height:1.18; color:var(--ink); font-weight:850; letter-spacing:-.02em;}
    .page-copy {font-size:14px; line-height:1.6; color:var(--muted); max-width:900px; margin-top:5px;}
    .page-badges {display:flex; flex-wrap:wrap; gap:7px; margin-top:14px;}
    .pill {display:inline-flex; align-items:center; padding:5px 9px; border-radius:999px; font-size:11px; font-weight:750; border:1px solid var(--line); background:#F8FAFC; color:#475569;}
    .pill.good {background:#ECFDF5; border-color:#A7F3D0; color:#047857;}
    .pill.blue {background:var(--primary-soft); border-color:#C7D2FE; color:#4338CA;}
    .pill.warn {background:#FFFBEB; border-color:#FDE68A; color:#B45309;}
    .pill.bad {background:#FEF2F2; border-color:#FECACA; color:#B91C1C;}

    .metric-card {background:var(--surface); border:1px solid var(--line); border-radius:13px; padding:17px 18px; min-height:122px; box-shadow:0 1px 2px rgba(15,23,42,.035);}
    .metric-card:hover {border-color:#C7D2FE; box-shadow:0 12px 28px rgba(15,23,42,.055); transform:translateY(-1px); transition:.18s ease;}
    .metric-label {color:var(--muted); font-size:12px; font-weight:750;}
    .metric-value {color:var(--ink); font-size:27px; line-height:1.2; font-weight:880; margin:9px 0 5px;}
    .metric-note {color:#94A3B8; font-size:11px; line-height:1.4;}

    .hero {
        background:linear-gradient(125deg,#111827 0%,#1E1B4B 52%,#1D4ED8 130%); border:1px solid #273449;
        color:#FFFFFF; border-radius:17px; padding:30px 32px; box-shadow:0 18px 44px rgba(15,23,42,.15); overflow:hidden;
    }
    .hero-kicker {color:#C7D2FE; text-transform:uppercase; letter-spacing:.1em; font-size:11px; font-weight:850;}
    .hero-title {font-size:34px; font-weight:900; line-height:1.12; max-width:700px; margin:9px 0 11px; letter-spacing:-.025em;}
    .hero-copy {color:#D6E4FF; font-size:14px; line-height:1.65; max-width:720px;}
    .hero-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:9px; margin-top:22px;}
    .hero-point {background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.12); border-radius:10px; padding:11px 12px; font-size:11px; font-weight:750; color:#EEF2FF;}

    .section-label {font-size:18px; font-weight:850; color:var(--ink); margin:4px 0;}
    .section-copy {font-size:12px; color:var(--muted); line-height:1.55; margin-bottom:12px;}
    .feature-card {background:#FFFFFF; border:1px solid var(--line); border-radius:13px; padding:18px; min-height:145px;}
    .feature-index {height:30px; width:30px; display:flex; align-items:center; justify-content:center; border-radius:9px; background:var(--primary-soft); color:var(--primary); font-size:11px; font-weight:900;}
    .feature-title {color:var(--ink); font-size:14px; font-weight:850; margin:12px 0 5px;}
    .feature-copy {color:var(--muted); font-size:12px; line-height:1.55;}
    .insight-card {background:linear-gradient(110deg,#EEF2FF,#F8FAFC); border:1px solid #C7D2FE; border-left:4px solid var(--primary); border-radius:11px; padding:17px 19px; color:#1E293B; font-size:14px; line-height:1.7;}
    .empty-state {background:#F8FAFC; border:1px dashed var(--line-strong); border-radius:13px; text-align:center; padding:28px; color:var(--muted); font-size:13px; line-height:1.6;}
    .schema-chip {display:inline-block; border:1px solid var(--line); background:#FFFFFF; color:#334155; border-radius:7px; padding:5px 8px; margin:3px 4px 3px 0; font-size:11px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
    .quality-row {display:flex; align-items:flex-start; gap:10px; padding:11px 0; border-bottom:1px solid #EEF2F7;}
    .quality-icon {height:22px; min-width:22px; display:flex; align-items:center; justify-content:center; border-radius:50%; font-size:11px; font-weight:900;}
    .quality-icon.pass {background:#D1FAE5; color:#047857;}.quality-icon.fail {background:#FEE2E2; color:#B91C1C;}
    .quality-name {font-size:12px; font-weight:800; color:#1E293B;}.quality-msg {font-size:11px; color:#64748B; margin-top:2px; line-height:1.45;}
    .auth-spacer {height:4vh; min-height:20px; max-height:55px;}
    .auth-hero {min-height:520px; display:flex; flex-direction:column; justify-content:space-between; background:linear-gradient(145deg,#0B1020,#1E1B4B 58%,#1D4ED8); border-radius:18px; padding:34px; color:white; box-shadow:0 24px 60px rgba(15,23,42,.2);}
    .auth-title {font-size:38px; font-weight:900; line-height:1.1; letter-spacing:-.03em; margin:12px 0;}
    .auth-copy {font-size:14px; line-height:1.7; color:#D7E3FF; max-width:510px;}
    .auth-points {display:grid; grid-template-columns:1fr 1fr; gap:9px; margin-top:25px;}
    .auth-point {background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.13); border-radius:10px; padding:12px; font-size:11px; font-weight:750; color:#EEF2FF;}
    .auth-trust {color:#A5B4FC; font-size:11px; line-height:1.55; margin-top:26px;}
    .auth-form {background:#FFFFFF; border:1px solid var(--line); border-radius:18px; min-height:520px; padding:28px; box-shadow:0 12px 36px rgba(15,23,42,.07);}
    .auth-form-title {font-size:23px; font-weight:880; color:var(--ink); margin-bottom:5px;}.auth-form-copy {color:var(--muted); font-size:12px; line-height:1.55; margin-bottom:14px;}

    div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:13px !important; border-color:var(--line) !important; background:#FFFFFF; box-shadow:0 1px 2px rgba(15,23,42,.03);}
    div[data-testid="stDataFrame"] {border:1px solid var(--line); border-radius:10px; overflow:hidden;}
    div[data-testid="stTabs"] div[role="tablist"] {gap:7px; border-bottom:1px solid var(--line); padding-bottom:8px; margin-bottom:12px;}
    div[data-testid="stTabs"] button[role="tab"] {border:1px solid var(--line); border-radius:999px; padding:7px 14px; min-height:38px; color:#475569; background:#FFFFFF; font-weight:750;}
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {color:#4338CA; border-color:#C7D2FE; background:#EEF2FF;}
    .stButton > button, .stDownloadButton > button {border-radius:9px; min-height:40px; font-weight:750;}
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {background:var(--primary); border-color:var(--primary); color:white;}
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {background:var(--primary-dark); border-color:var(--primary-dark);}
    input, textarea {border-radius:9px !important;}

    @media(max-width:900px){
        .block-container{padding:1rem}.hero-title,.auth-title{font-size:28px}.hero-grid,.auth-points{grid-template-columns:1fr}.page-title{font-size:24px}.auth-hero,.auth-form{min-height:auto}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


STATE_DEFAULTS = {
    "token": None,
    "user": None,
    "page": "Home",
    "selected_dataset_id": None,
    "analysis_mode": "Ecommerce Demo",
    "last_result": None,
    "auth_view": "login",
    "auth_notice": None,
    "query_text": "",
    "dataset_downloads": {},
    "report_downloads": {},
    "inspected_dataset_id": None,
}
for state_key, default_value in STATE_DEFAULTS.items():
    st.session_state.setdefault(state_key, default_value)

# Apply pending navigation before the corresponding sidebar widget is created.
pending_page = st.session_state.pop("_navigation_target", None)
if pending_page in NAVIGATION:
    st.session_state.page = pending_page
    st.session_state.nav_choice = pending_page


def navigate(page: str) -> None:
    st.session_state._navigation_target = page
    st.rerun()


def end_session(message: str | None = None) -> None:
    st.session_state.clear()
    for state_key, default_value in STATE_DEFAULTS.items():
        st.session_state[state_key] = default_value
    if message:
        st.session_state.auth_notice = message
    st.rerun()


def api_error(response: dict[str, Any] | None, *, show: bool = True) -> bool:
    response = response or {"error": "The API returned no response."}
    if not response.get("error"):
        return False
    if response.get("status_code") == 401 and st.session_state.get("token"):
        end_session("Your secure session expired. Sign in again to continue.")
        return True
    if show:
        st.error(str(response.get("error")))
        if response.get("request_id"):
            st.caption(f"Support reference: {response['request_id']}")
    return True


def page_header(page: str, badges: list[tuple[str, str]] | None = None) -> None:
    eyebrow, title, copy = PAGE_META[page]
    badge_html = "".join(f'<span class="pill {safe_html(kind)}">{safe_html(label)}</span>' for label, kind in (badges or []))
    st.markdown(
        f"""
        <div class="page-head">
          <div class="eyebrow">{safe_html(eyebrow)}</div>
          <div class="page-title">{safe_html(title)}</div>
          <div class="page-copy">{safe_html(copy)}</div>
          <div class="page-badges">{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: str) -> None:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{safe_html(label)}</div><div class="metric-value">{safe_html(value)}</div><div class="metric-note">{safe_html(note)}</div></div>',
        unsafe_allow_html=True,
    )


def feature_card(index: str, title: str, copy: str) -> None:
    st.markdown(
        f'<div class="feature-card"><div class="feature-index">{safe_html(index)}</div><div class="feature-title">{safe_html(title)}</div><div class="feature-copy">{safe_html(copy)}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    st.markdown(f'<div class="empty-state">{safe_html(message)}</div>', unsafe_allow_html=True)


def section_heading(title: str, copy: str = "") -> None:
    st.markdown(f'<div class="section-label">{safe_html(title)}</div><div class="section-copy">{safe_html(copy)}</div>', unsafe_allow_html=True)


def normalize_records(response: dict[str, Any]) -> pd.DataFrame:
    data = response.get("data", []) if isinstance(response, dict) else []
    return pd.DataFrame(data if isinstance(data, list) else [])


def selected_dataset(datasets: list[dict[str, Any]]) -> dict[str, Any] | None:
    selected_id = st.session_state.get("selected_dataset_id")
    return next((item for item in datasets if item.get("id") == selected_id), None)


def auth_hero() -> None:
    st.markdown(
        """
        <div class="auth-hero">
          <div>
            <div class="hero-kicker">Agentic SQL Analyst</div>
            <div class="auth-title">From plain English<br>to trusted SQL analysis.</div>
            <div class="auth-copy">Sign in to explore the preloaded ecommerce dataset or analyze your own CSV and Excel data with generated PostgreSQL, interactive charts, business insights, quality checks, and reports.</div>
            <div class="auth-points">
              <div class="auth-point">Read-only SQL policy</div>
              <div class="auth-point">Private dataset ownership</div>
              <div class="auth-point">RAG-assisted schema context</div>
              <div class="auth-point">Quality evaluation</div>
              <div class="auth-point">Interactive Plotly views</div>
              <div class="auth-point">Auditable reports</div>
            </div>
          </div>
          <div class="auth-trust">JWT-protected access · Validated SQL · No cross-dataset queries · Safe error handling</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login_register() -> None:
    st.markdown('<div class="auth-form-title">Welcome to Agentic SQL Analyst</div><div class="auth-form-copy">Sign in or create an account to open the ecommerce demo and your private dataset workspace.</div>', unsafe_allow_html=True)
    notice = st.session_state.pop("auth_notice", None)
    if notice:
        st.info(notice)
    login_tab, register_tab = st.tabs(["Sign in", "Create account"])
    with login_tab:
        show_login_password = st.checkbox("Show password", key="show_login_password")
        with st.form("login_form"):
            email = st.text_input("Work email", placeholder="you@company.com", autocomplete="email")
            password = st.text_input("Password", type="default" if show_login_password else "password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in securely", type="primary", width="stretch")
        if submitted:
            if not email.strip() or not password:
                st.warning("Enter your email and password.")
            else:
                with st.spinner("Verifying your account…"):
                    response = login_api(email.strip(), password)
                if not api_error(response):
                    token = response.get("access_token")
                    identity = me_api(token)
                    if not token or api_error(identity):
                        st.error("Your account was verified, but the secure session could not be initialized.")
                    else:
                        st.session_state.token = token
                        st.session_state.user = identity
                        st.session_state.page = "Home"
                        st.rerun()
        left, right = st.columns([1, 1])
        with left:
            if st.button("Forgot password?", key="open_forgot", width="stretch"):
                st.session_state.auth_view = "forgot"
                st.rerun()
        with right:
            st.caption("Sessions expire automatically for your protection.")

    with register_tab:
        full_name = st.text_input("Full name", placeholder="Your name", key="register_name", max_chars=200)
        register_email = st.text_input("Work email", placeholder="you@company.com", key="register_email", autocomplete="email")
        show_registration_password = st.checkbox("Show passwords", key="show_registration_password")
        register_password = st.text_input("Create password", type="default" if show_registration_password else "password", key="register_password", autocomplete="new-password", max_chars=128)
        confirm_password = st.text_input("Confirm password", type="default" if show_registration_password else "password", key="confirm_password", autocomplete="new-password", max_chars=128)
        score, label, improvements = password_strength(register_password)
        st.progress(score / 5 if register_password else 0, text=f"Password strength: {label if register_password else 'not entered'}")
        if register_password and improvements and score < 4:
            st.caption("Suggested: " + "; ".join(improvements[:2]) + ".")
        consent = st.checkbox("I agree to use this workspace only for data I am authorized to analyze.", key="registration_consent")
        if st.button("Create secure account", type="primary", key="register_submit", width="stretch"):
            problems = []
            if not full_name.strip():
                problems.append("Enter your full name")
            if not register_email.strip():
                problems.append("Enter your email")
            if score < 4:
                problems.append("Choose a stronger password")
            if register_password != confirm_password:
                problems.append("Passwords do not match")
            if not consent:
                problems.append("Confirm the authorized-use statement")
            if problems:
                st.warning(" · ".join(problems))
            else:
                with st.spinner("Creating your private workspace…"):
                    response = register_api(register_email.strip(), full_name.strip(), register_password)
                if not api_error(response):
                    st.success("Account created. You can now sign in.")


def render_forgot_password() -> None:
    st.markdown('<div class="auth-form-title">Reset your password</div><div class="auth-form-copy">Enter your account email. For privacy, the response is the same whether or not an account exists.</div>', unsafe_allow_html=True)
    with st.form("forgot_password_form"):
        email = st.text_input("Account email", placeholder="you@company.com", autocomplete="email")
        submitted = st.form_submit_button("Send reset instructions", type="primary", width="stretch")
    if submitted:
        if not email.strip():
            st.warning("Enter your email address.")
        else:
            with st.spinner("Preparing secure reset instructions…"):
                response = forgot_password_api(email.strip())
            if not api_error(response):
                st.success(response.get("message") or "If an account matches that email, reset instructions have been sent.")
                development_link = response.get("reset_link") or response.get("development_reset_link")
                if development_link:
                    with st.expander("Local development reset link"):
                        st.caption("This is returned only when the backend is explicitly configured for development.")
                        st.code(development_link)
    if st.button("Back to sign in", key="forgot_back", width="stretch"):
        st.session_state.auth_view = "login"
        st.rerun()


def render_reset_password(reset_token: str) -> None:
    st.markdown('<div class="auth-form-title">Choose a new password</div><div class="auth-form-copy">Reset links are short-lived and single-use. A successful reset invalidates existing sessions.</div>', unsafe_allow_html=True)
    token_value = reset_token or st.text_input("Reset token", type="password", help="Paste the token from your reset instructions.")
    show_password = st.checkbox("Show passwords", key="show_reset_password")
    new_password = st.text_input("New password", type="default" if show_password else "password", key="new_reset_password", autocomplete="new-password")
    confirm = st.text_input("Confirm new password", type="default" if show_password else "password", key="confirm_reset_password", autocomplete="new-password")
    score, label, improvements = password_strength(new_password)
    st.progress(score / 5 if new_password else 0, text=f"Password strength: {label if new_password else 'not entered'}")
    if st.button("Reset password", type="primary", key="reset_submit", width="stretch"):
        if not token_value:
            st.warning("A reset token is required.")
        elif score < 4:
            st.warning("Choose a stronger password before continuing.")
        elif new_password != confirm:
            st.warning("Passwords do not match.")
        else:
            with st.spinner("Securing your account…"):
                response = reset_password_api(token_value, new_password)
            if not api_error(response):
                st.session_state.auth_view = "login"
                try:
                    st.query_params.clear()
                except AttributeError:
                    pass
                st.session_state.auth_notice = "Password reset complete. Sign in with your new password."
                st.rerun()
    if st.button("Back to sign in", key="reset_back", width="stretch"):
        st.session_state.auth_view = "login"
        st.rerun()


def render_authentication() -> None:
    reset_token_value: Any = st.query_params.get("reset_token", "")
    if isinstance(reset_token_value, list):
        reset_token_value = reset_token_value[0] if reset_token_value else ""
    if reset_token_value:
        st.session_state.auth_view = "reset"
    st.markdown('<div class="auth-spacer"></div>', unsafe_allow_html=True)
    hero_column, form_column = st.columns([1.12, 0.88], gap="large")
    with hero_column:
        auth_hero()
    with form_column:
        with st.container(border=True):
            if st.session_state.auth_view == "forgot":
                render_forgot_password()
            elif st.session_state.auth_view == "reset":
                render_reset_password(str(reset_token_value or ""))
            else:
                render_login_register()


def render_sidebar(user: dict[str, Any], datasets: list[dict[str, Any]]) -> None:
    with st.sidebar:
        st.markdown(
            '<div class="brand"><div class="brand-row"><div class="brand-mark">A</div><div><div class="brand-name">Agentic SQL</div><div class="brand-copy">Analytics control plane</div></div></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="user-card"><div class="user-overline">Authenticated workspace</div><div class="user-title">{safe_html(user.get("full_name") or "Analyst")}</div><div class="user-email">{safe_html(user.get("email") or "")}</div><div class="sidebar-status"><span class="status-dot"></span>Secure session active</div></div>',
            unsafe_allow_html=True,
        )

        st.caption("WORKSPACE")
        current_page = st.session_state.page if st.session_state.page in NAVIGATION else "Home"
        st.session_state.setdefault("nav_choice", current_page)
        if st.session_state.nav_choice not in NAVIGATION:
            st.session_state.nav_choice = current_page
        choice = st.radio("Navigation", NAVIGATION, label_visibility="collapsed", key="nav_choice")
        if choice != st.session_state.page:
            st.session_state.page = choice
            st.rerun()

        st.divider()
        st.caption("ACTIVE DATA CONTEXT")
        mode_label = "Demo ecommerce" if st.session_state.analysis_mode == "Ecommerce Demo" else "Uploaded dataset"
        st.markdown(f'<span class="pill blue">{safe_html(mode_label)}</span>', unsafe_allow_html=True)
        if datasets:
            ids = [item["id"] for item in datasets]
            if st.session_state.selected_dataset_id not in ids:
                st.session_state.selected_dataset_id = ids[0]
            st.session_state.setdefault("sidebar_dataset_widget", st.session_state.selected_dataset_id)
            if st.session_state.sidebar_dataset_widget not in ids:
                st.session_state.sidebar_dataset_widget = st.session_state.selected_dataset_id
            sidebar_dataset = st.selectbox(
                "Selected dataset",
                ids,
                format_func=lambda item_id: next((item["dataset_name"] for item in datasets if item["id"] == item_id), str(item_id)),
                key="sidebar_dataset_widget",
            )
            st.session_state.selected_dataset_id = sidebar_dataset
        else:
            st.caption("No uploaded datasets yet")

        st.divider()
        if st.button("Sign out", width="stretch", key="sidebar_signout"):
            end_session("You have been signed out securely.")


def load_history(show_error: bool = False, dataset_id: int | None = None) -> list[dict[str, Any]]:
    response = history_api(st.session_state.token, dataset_id=dataset_id)
    if api_error(response, show=show_error):
        return []
    return response.get("history", [])


def render_home(datasets: list[dict[str, Any]]) -> None:
    page_header(
        "Home",
        [("Read-only SQL", "good"), ("Owner-scoped data", "blue"), ("RAG + evaluation", "blue")],
    )
    user = st.session_state.user or {}
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-kicker">Private analytics workspace</div>
          <div class="hero-title">Welcome back, {safe_html((user.get('full_name') or 'Analyst').split()[0])}.</div>
          <div class="hero-copy">Explore a ready-to-use ecommerce model or bring your own CSV and Excel data. Every generated statement is validated as read-only and constrained to its authorized table before execution.</div>
          <div class="hero-grid">
            <div class="hero-point">01 · Ask in plain English</div>
            <div class="hero-point">02 · Inspect governed SQL</div>
            <div class="hero-point">03 · Share a decision-ready report</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    action_left, action_middle, action_right, _ = st.columns([1, 1, 1, 2])
    with action_left:
        if st.button("Open Query Studio", type="primary", width="stretch"):
            navigate("Query Studio")
    with action_middle:
        if st.button("Upload data", width="stretch"):
            navigate("Upload Dataset")
    with action_right:
        if st.button("View demo dashboard", width="stretch"):
            navigate("Demo Dashboard")

    history = load_history(show_error=False)
    total_rows = sum(int(item.get("row_count") or 0) for item in datasets)
    latest_activity = history[0].get("created_at") if history else None
    st.write("")
    metric_columns = st.columns(4)
    with metric_columns[0]:
        metric_card("Private datasets", compact_number(len(datasets)), "Only datasets owned by this account")
    with metric_columns[1]:
        metric_card("Managed rows", compact_number(total_rows), "Across imported analytics tables")
    with metric_columns[2]:
        metric_card("Saved analyses", compact_number(len(history)), "Private query audit trail")
    with metric_columns[3]:
        metric_card("Latest activity", friendly_datetime(latest_activity) if latest_activity else "No runs yet", "Most recent successful analysis")

    st.write("")
    section_heading("Enterprise analytics, end to end", "The experience combines governed execution with transparent AI assistance.")
    features = [
        ("01", "Natural language to SQL", "Schema-aware generation turns business questions into PostgreSQL without exposing prompt internals."),
        ("02", "Policy-first execution", "A table allowlist, read-only parser, timeout, and result limit protect every query path."),
        ("03", "RAG transparency", "See whether fixed project knowledge, schema context, or dataset metadata supported the generation."),
        ("04", "SQL quality checks", "Separate safety, execution, relevance, and result-alignment signals support informed review."),
    ]
    feature_columns = st.columns(4)
    for column, values in zip(feature_columns, features):
        with column:
            feature_card(*values)

    st.write("")
    onboarding, recent = st.columns([0.85, 1.15], gap="large")
    with onboarding:
        with st.container(border=True):
            section_heading("Workspace readiness", "Complete these steps to unlock the full private-data workflow.")
            readiness = [
                (True, "Account secured", "JWT identity is active for this session."),
                (bool(datasets), "Dataset uploaded", "Import CSV or XLSX data to create a private table."),
                (bool(history), "First analysis complete", "Ask a question and inspect its quality panel."),
            ]
            for complete, title, note in readiness:
                status = "Complete" if complete else "Next"
                kind = "good" if complete else "warn"
                st.markdown(f'<span class="pill {kind}">{status}</span> &nbsp; **{title}**')
                st.caption(note)
    with recent:
        with st.container(border=True):
            section_heading("Recent analysis", "Your newest saved questions, never another user's history.")
            if not history:
                empty_state("No saved analysis yet. Start in Query Studio with the demo model or one of your datasets.")
            else:
                for item in history[:4]:
                    dataset_name = next((dataset["dataset_name"] for dataset in datasets if dataset["id"] == item.get("dataset_id")), "Ecommerce demo")
                    st.markdown(f"**{safe_html(item.get('question') or 'Untitled analysis')}**", unsafe_allow_html=True)
                    st.caption(f"{dataset_name} · {friendly_datetime(item.get('created_at'), include_time=True)}")
                    st.divider()


def _dashboard_call(call: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    return call(st.session_state.token)


def render_demo_dashboard() -> None:
    page_header(
        "Demo Dashboard",
        [("Live PostgreSQL", "good"), ("4-table ecommerce model", "blue"), ("All-time view", "")],
    )
    if st.button("Refresh dashboard", key="refresh_dashboard"):
        st.rerun()

    with st.spinner("Loading executive metrics…"):
        responses = {
            "metrics": _dashboard_call(dashboard_metrics_api),
            "category": _dashboard_call(revenue_by_category_api),
            "products": _dashboard_call(top_products_api),
            "status": _dashboard_call(orders_by_status_api),
            "country": _dashboard_call(revenue_by_country_api),
            "monthly": _dashboard_call(monthly_revenue_api),
        }
    if any(response.get("status_code") == 401 for response in responses.values()):
        api_error(next(response for response in responses.values() if response.get("status_code") == 401))
        return
    unavailable = [name for name, response in responses.items() if response.get("error")]
    if unavailable:
        panel_labels = {
            "metrics": "Executive KPIs",
            "category": "Revenue by category",
            "products": "Top products",
            "status": "Order status mix",
            "country": "Revenue by country",
            "monthly": "Monthly revenue trend",
        }
        failed_labels = [panel_labels[name] for name in unavailable]
        if len(unavailable) == len(responses):
            st.warning("The ecommerce demo dashboard could not be loaded. Confirm the backend and PostgreSQL demo tables are available.")
        else:
            st.warning(f"Unavailable dashboard panel{'s' if len(failed_labels) != 1 else ''}: {', '.join(failed_labels)}. Other live panels are shown below.")

    metrics = responses["metrics"] if not responses["metrics"].get("error") else {}
    revenue = metrics.get("total_revenue", 0)
    orders = metrics.get("total_orders", 0)
    average_order_value = metrics.get("average_order_value")
    if average_order_value is None:
        average_order_value = float(revenue or 0) / float(orders or 1)
    completion_rate = metrics.get("completion_rate")
    if completion_rate is not None:
        completion_text = f"{float(completion_rate):.1f}%"
    else:
        completion_text = "Unavailable"

    first_metrics = st.columns(3)
    with first_metrics[0]:
        metric_card("Total revenue", currency(revenue), "Gross merchandise revenue")
    with first_metrics[1]:
        metric_card("Total orders", compact_number(orders), "Orders across all statuses")
    with first_metrics[2]:
        metric_card("Average order value", currency(average_order_value), "Revenue per recorded order")
    second_metrics = st.columns(3)
    with second_metrics[0]:
        metric_card("Customers", compact_number(metrics.get("total_customers", 0)), "Distinct customer records")
    with second_metrics[1]:
        metric_card("Products", compact_number(metrics.get("total_products", 0)), "Active product catalog")
    with second_metrics[2]:
        metric_card("Completion rate", completion_text, "Completed orders as a share of total")

    category_df = normalize_records(responses["category"])
    products_df = normalize_records(responses["products"])
    status_df = normalize_records(responses["status"])
    country_df = normalize_records(responses["country"])
    monthly_df = normalize_records(responses["monthly"])

    st.write("")
    with st.expander("Dashboard filters", expanded=False):
        filter_left, filter_right = st.columns(2)
        with filter_left:
            category_values = category_df.get("category", pd.Series(dtype=str)).dropna().astype(str).tolist()
            selected_categories = st.multiselect("Categories", category_values, default=category_values, key="dashboard_categories")
            if selected_categories and "category" in category_df:
                category_df = category_df[category_df["category"].astype(str).isin(selected_categories)]
        with filter_right:
            status_values = status_df.get("status", pd.Series(dtype=str)).dropna().astype(str).tolist()
            selected_statuses = st.multiselect("Order statuses", status_values, default=status_values, key="dashboard_statuses")
            if selected_statuses and "status" in status_df:
                status_df = status_df[status_df["status"].astype(str).isin(selected_statuses)]
        st.caption("Filters apply to the matching aggregate panels. Date filtering requires a date-range dashboard endpoint; the monthly chart currently shows all available periods.")

    trend_column, status_column = st.columns([1.35, 0.65], gap="large")
    with trend_column:
        with st.container(border=True):
            section_heading("Revenue trend", "Monthly revenue movement across the demo commerce model.")
            if monthly_df.empty:
                empty_state("The monthly revenue trend is currently unavailable. The remaining ecommerce dashboard panels are unaffected.")
            else:
                date_column = next((column for column in monthly_df if any(token in column.lower() for token in ("month", "date", "period"))), monthly_df.columns[0])
                value_column = next((column for column in monthly_df if "revenue" in column.lower()), monthly_df.columns[-1])
                monthly_df[date_column] = pd.to_datetime(monthly_df[date_column], errors="coerce")
                monthly_df = monthly_df.sort_values(date_column)
                fig = px.area(monthly_df, x=date_column, y=value_column, markers=True, color_discrete_sequence=["#4F46E5"])
                st.plotly_chart(style_figure(fig, "Monthly revenue", 390), width="stretch", config={"displaylogo": False})
    with status_column:
        with st.container(border=True):
            section_heading("Order status mix", "Operational distribution by current order state.")
            if status_df.empty:
                empty_state("Order status data is unavailable.")
            else:
                status_name = "status" if "status" in status_df else status_df.columns[0]
                status_value = "total_orders" if "total_orders" in status_df else status_df.columns[-1]
                fig = px.pie(status_df, names=status_name, values=status_value, hole=0.58, color_discrete_sequence=px.colors.qualitative.Safe)
                fig.update_traces(
                    textinfo="percent",
                    textposition="inside",
                    hovertemplate="%{label}: %{value:,} orders (%{percent})<extra></extra>",
                )
                fig = style_figure(fig, "", 390)
                fig.update_layout(
                    title=None,
                    margin={"l": 12, "r": 12, "t": 18, "b": 72},
                    legend={
                        "orientation": "h",
                        "yanchor": "top",
                        "y": -0.04,
                        "xanchor": "center",
                        "x": 0.5,
                    },
                )
                st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

    category_column, products_column = st.columns(2, gap="large")
    with category_column:
        with st.container(border=True):
            section_heading("Revenue by category", "Category contribution to overall commerce performance.")
            if category_df.empty:
                empty_state("Category revenue data is unavailable.")
            else:
                category_name = "category" if "category" in category_df else category_df.columns[0]
                revenue_name = "revenue" if "revenue" in category_df else category_df.columns[-1]
                fig = px.bar(category_df.sort_values(revenue_name, ascending=False), x=category_name, y=revenue_name, color=category_name, color_discrete_sequence=px.colors.qualitative.Safe)
                fig.update_layout(showlegend=False)
                st.plotly_chart(style_figure(fig, "Category performance", 365), width="stretch", config={"displaylogo": False})
    with products_column:
        with st.container(border=True):
            section_heading("Top products", "Highest revenue-generating products in the demo model.")
            if products_df.empty:
                empty_state("Product performance data is unavailable.")
            else:
                product_name = "product_name" if "product_name" in products_df else products_df.columns[0]
                revenue_name = "revenue" if "revenue" in products_df else products_df.columns[-1]
                ordered = products_df.sort_values(revenue_name).tail(10)
                fig = px.bar(ordered, x=revenue_name, y=product_name, orientation="h", color=revenue_name, color_continuous_scale="Blues")
                fig.update_layout(coloraxis_showscale=False)
                st.plotly_chart(style_figure(fig, "Product revenue ranking", 365), width="stretch", config={"displaylogo": False})

    with st.container(border=True):
        section_heading("Revenue by country", "Geographic performance across customer markets.")
        if country_df.empty:
            empty_state("Country revenue data is unavailable.")
        else:
            country_name = "country" if "country" in country_df else country_df.columns[0]
            revenue_name = "revenue" if "revenue" in country_df else country_df.columns[-1]
            fig = px.bar(country_df.sort_values(revenue_name, ascending=False), x=country_name, y=revenue_name, color=revenue_name, color_continuous_scale="Blues")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_figure(fig, "Geographic revenue", 340), width="stretch", config={"displaylogo": False})

    with st.expander("Download dashboard data"):
        download_columns = st.columns(5)
        exports = [
            ("Categories", category_df, "revenue_by_category.csv"),
            ("Products", products_df, "top_products.csv"),
            ("Statuses", status_df, "orders_by_status.csv"),
            ("Countries", country_df, "revenue_by_country.csv"),
            ("Monthly", monthly_df, "monthly_revenue.csv"),
        ]
        for column, (label, frame, filename) in zip(download_columns, exports):
            with column:
                st.download_button(label, frame.to_csv(index=False).encode("utf-8"), filename, "text/csv", width="stretch", disabled=frame.empty)


def _dataset_profile_frame(dataset: dict[str, Any]) -> pd.DataFrame:
    profile = dataset.get("profile") or {}
    columns = profile.get("columns") or dataset.get("columns") or []
    output = []
    for column in columns:
        if not isinstance(column, dict):
            output.append({"Column": str(column), "Type": "Unknown", "Nulls": "—", "Distinct": "—"})
            continue
        statistics = column.get("statistics") or {}
        date_range = column.get("date_range") or {}
        output.append(
            {
                "Column": column.get("name"),
                "Type": column.get("type", "Unknown"),
                "Nulls": column.get("null_count", "—"),
                "Null %": column.get("null_percent", "—"),
                "Distinct": column.get("distinct_count", "—"),
                "Minimum": statistics.get("min", date_range.get("min", "—")),
                "Maximum": statistics.get("max", date_range.get("max", "—")),
                "Mean": statistics.get("mean", "—"),
            }
        )
    return pd.DataFrame(output)


def render_dataset_inspector(dataset: dict[str, Any]) -> None:
    dataset_id = int(dataset["id"])
    response = dataset_api(st.session_state.token, dataset_id)
    if api_error(response):
        return
    dataset = response
    profile = dataset.get("profile") or {}
    st.write("")
    with st.container(border=True):
        header_left, header_right = st.columns([1.6, 0.4])
        with header_left:
            section_heading(dataset.get("dataset_name", "Dataset profile"), "Schema, quality observations, sample records, and safe management controls.")
            st.caption(f"Imported {friendly_datetime(dataset.get('created_at'), include_time=True)} · Source file {dataset.get('original_filename', 'Unknown')}")
        with header_right:
            st.markdown('<span class="pill good">Ready to query</span>', unsafe_allow_html=True)

        profile_metrics = st.columns(4)
        with profile_metrics[0]:
            metric_card("Rows", compact_number(dataset.get("row_count")), "Imported records")
        with profile_metrics[1]:
            metric_card("Columns", compact_number(dataset.get("column_count") or len(dataset.get("columns") or [])), "Sanitized schema")
        with profile_metrics[2]:
            metric_card("Duplicate rows", compact_number(profile.get("duplicate_rows", 0)), "Profile-time detection")
        with profile_metrics[3]:
            metric_card("Last queried", friendly_datetime(dataset.get("last_queried_at")) if dataset.get("last_queried_at") else "Not queried", "Most recent analysis")

        warnings = profile.get("warnings") or []
        if warnings:
            st.warning("Data-quality observations: " + " · ".join(str(item) for item in warnings[:5]))
        else:
            st.success("No high-priority quality warnings were recorded during import profiling.")

        schema_tab, preview_tab, actions_tab = st.tabs(["Schema profile", "Data preview", "Manage"])
        with schema_tab:
            schema_frame = _dataset_profile_frame(dataset)
            if schema_frame.empty:
                empty_state("Schema metadata is not available for this dataset.")
            else:
                schema_search = st.text_input("Find a column", placeholder="Search name or type", key=f"schema_search_{dataset_id}").strip().lower()
                if schema_search:
                    schema_frame = schema_frame[
                        schema_frame.astype(str).apply(lambda row: row.str.lower().str.contains(schema_search, regex=False).any(), axis=1)
                    ]
                st.dataframe(schema_frame, width="stretch", hide_index=True)
        with preview_tab:
            preview_response = dataset_preview_api(st.session_state.token, dataset_id, limit=50)
            if not api_error(preview_response):
                preview = result_dataframe(preview_response.get("columns"), preview_response.get("rows"))
                if preview.empty:
                    empty_state("This dataset has no previewable records.")
                else:
                    st.caption(f"Showing up to 50 of {int(preview_response.get('row_count') or len(preview)):,} records.")
                    st.dataframe(preview, width="stretch", hide_index=True)
        with actions_tab:
            action_left, action_middle, action_right = st.columns(3, gap="large")
            with action_left:
                st.markdown("**Rename display name**")
                with st.form(f"rename_dataset_{dataset_id}"):
                    new_name = st.text_input("Dataset name", value=dataset.get("dataset_name", ""), max_chars=200, label_visibility="collapsed")
                    rename = st.form_submit_button("Save name", width="stretch")
                if rename:
                    if not new_name.strip():
                        st.warning("Dataset name cannot be empty.")
                    else:
                        rename_response = rename_dataset_api(st.session_state.token, dataset_id, new_name.strip())
                        if not api_error(rename_response):
                            st.success("Dataset name updated.")
                            st.rerun()
            with action_middle:
                st.markdown("**Download normalized data**")
                st.caption("The API prepares an authenticated CSV—no server path is exposed.")
                if st.button("Prepare CSV", key=f"prepare_dataset_{dataset_id}", width="stretch"):
                    with st.spinner("Preparing secure download…"):
                        download = dataset_download_api(st.session_state.token, dataset_id)
                    if not api_error(download):
                        st.session_state.dataset_downloads[dataset_id] = download
                download = st.session_state.dataset_downloads.get(dataset_id)
                if download:
                    st.download_button(
                        "Download CSV",
                        download["content"],
                        download.get("filename") or f"dataset_{dataset_id}.csv",
                        download.get("content_type") or "text/csv",
                        key=f"download_dataset_{dataset_id}",
                        type="primary",
                        width="stretch",
                    )
            with action_right:
                st.markdown("**Delete dataset**")
                st.caption("Deletes the private analytics table, metadata, and associated history.")
                confirmed = st.checkbox("I understand this cannot be undone", key=f"confirm_delete_{dataset_id}")
                if st.button("Delete permanently", key=f"delete_dataset_{dataset_id}", disabled=not confirmed, width="stretch"):
                    with st.spinner("Deleting dataset…"):
                        deletion = delete_dataset_api(st.session_state.token, dataset_id)
                    if not api_error(deletion):
                        st.session_state.inspected_dataset_id = None
                        st.session_state.dataset_downloads.pop(dataset_id, None)
                        if st.session_state.selected_dataset_id == dataset_id:
                            st.session_state.selected_dataset_id = None
                        st.success("Dataset deleted.")
                        st.rerun()


def render_datasets(datasets: list[dict[str, Any]]) -> None:
    page_header(
        "My Datasets",
        [(f"{len(datasets)} private dataset{'s' if len(datasets) != 1 else ''}", "blue"), ("Owner-scoped", "good")],
    )
    controls_left, controls_middle, controls_right = st.columns([1.35, 0.45, 0.45])
    with controls_left:
        dataset_search = st.text_input("Search datasets", placeholder="Search name or source filename", label_visibility="collapsed").strip().lower()
    with controls_middle:
        if st.button("Upload new", type="primary", width="stretch"):
            navigate("Upload Dataset")
    with controls_right:
        if st.button("Refresh", width="stretch"):
            st.rerun()

    visible = [
        item for item in datasets
        if not dataset_search
        or dataset_search in str(item.get("dataset_name", "")).lower()
        or dataset_search in str(item.get("original_filename", "")).lower()
    ]
    if not visible:
        empty_state("No datasets match this search." if datasets else "No private datasets yet. Upload CSV or Excel data to create your first governed workspace.")
        return

    for offset in range(0, len(visible), 2):
        columns = st.columns(2, gap="large")
        for column, dataset in zip(columns, visible[offset : offset + 2]):
            dataset_id = int(dataset["id"])
            with column:
                with st.container(border=True):
                    title_row, state_row = st.columns([1.4, 0.6])
                    with title_row:
                        st.subheader(dataset.get("dataset_name") or "Untitled dataset")
                        st.caption(dataset.get("original_filename") or "Imported data")
                    with state_row:
                        st.markdown('<span class="pill good">Ready</span>', unsafe_allow_html=True)
                    information = st.columns(3)
                    information[0].metric("Rows", compact_number(dataset.get("row_count")))
                    information[1].metric("Columns", compact_number(dataset.get("column_count") or len(dataset.get("columns") or [])))
                    information[2].metric("Type", str(dataset.get("file_type") or "data").upper())
                    column_names = [item.get("name") if isinstance(item, dict) else str(item) for item in dataset.get("columns", [])]
                    chips = "".join(f'<span class="schema-chip">{safe_html(name)}</span>' for name in column_names[:6])
                    if len(column_names) > 6:
                        chips += f'<span class="schema-chip">+{len(column_names) - 6} more</span>'
                    st.markdown(chips or '<span class="schema-chip">Schema unavailable</span>', unsafe_allow_html=True)
                    st.caption(f"Uploaded {friendly_datetime(dataset.get('created_at'))} · Last queried {friendly_datetime(dataset.get('last_queried_at')) if dataset.get('last_queried_at') else 'never'}")
                    inspect_column, query_column = st.columns(2)
                    with inspect_column:
                        if st.button("Inspect & manage", key=f"inspect_{dataset_id}", width="stretch"):
                            st.session_state.inspected_dataset_id = dataset_id
                            st.rerun()
                    with query_column:
                        if st.button("Query dataset", key=f"query_dataset_{dataset_id}", type="primary", width="stretch"):
                            st.session_state.selected_dataset_id = dataset_id
                            st.session_state.analysis_mode = "My Uploaded Dataset"
                            st.session_state.query_dataset_widget = dataset_id
                            navigate("Query Studio")

    inspected = next((item for item in datasets if item.get("id") == st.session_state.inspected_dataset_id), None)
    if inspected:
        render_dataset_inspector(inspected)


def _read_upload_preview(uploaded_file: Any, sheet_name: str | None = None) -> tuple[pd.DataFrame | None, str | None]:
    try:
        raw = uploaded_file.getvalue()
        if uploaded_file.name.lower().endswith(".csv"):
            return pd.read_csv(io.BytesIO(raw), nrows=50), None
        return pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name or 0, nrows=50), None
    except Exception:
        return None, "The file could not be previewed. Confirm that it is a valid CSV or XLSX file."


def render_upload_dataset() -> None:
    page_header(
        "Upload Dataset",
        [("CSV / XLSX", "blue"), ("20 MB maximum", ""), (f"{MAX_UPLOAD_ROWS:,} rows maximum", "")],
    )
    guidance, upload_area = st.columns([0.65, 1.35], gap="large")
    with guidance:
        with st.container(border=True):
            section_heading("Import safeguards", "Files are normalized before becoming queryable.")
            checks = [
                "Filename and worksheet input are treated as untrusted.",
                "Column names are sanitized and duplicates are disambiguated.",
                "Empty, oversized, unsupported, and malformed files are rejected.",
                "The resulting table is private to the authenticated owner.",
                "Profiling records nulls, distinct values, ranges, and warnings.",
            ]
            for index, check in enumerate(checks, 1):
                st.markdown(f"**{index:02d}** &nbsp; {check}")
            st.info("Excel workbooks can target a specific worksheet before import.")
    with upload_area:
        with st.container(border=True):
            section_heading("Choose source data", "Preview the structure before committing it to PostgreSQL.")
            uploaded = st.file_uploader("Drop a CSV or Excel workbook", type=["csv", "xlsx"], accept_multiple_files=False)
            if not uploaded:
                empty_state("Drop a file here or browse your device. Nothing is uploaded until you confirm the import.")
                return
            size = len(uploaded.getvalue())
            if size > MAX_UPLOAD_BYTES:
                st.error(f"This file is {size / 1024 / 1024:.1f} MB. The maximum allowed size is 20 MB.")
                return
            sheet_name = None
            sheet_names: list[str] = []
            if uploaded.name.lower().endswith(".xlsx"):
                try:
                    sheet_names = pd.ExcelFile(io.BytesIO(uploaded.getvalue())).sheet_names
                except Exception:
                    st.error("The workbook could not be read. Confirm that it is a valid XLSX file.")
                    return
                if sheet_names:
                    sheet_name = st.selectbox("Worksheet", sheet_names, key="upload_sheet")
            default_name = uploaded.name.rsplit(".", 1)[0][:200]
            dataset_name = st.text_input("Dataset display name", value=default_name, max_chars=200, key=f"upload_name_{uploaded.name}")
            preview, preview_error = _read_upload_preview(uploaded, sheet_name)
            if preview_error:
                st.error(preview_error)
                return
            if preview is None or preview.empty or not len(preview.columns):
                st.error("This file does not contain previewable data.")
                return
            preview_columns = st.columns(4)
            preview_columns[0].metric("File size", f"{size / 1024:.1f} KB")
            preview_columns[1].metric("Preview rows", f"{len(preview):,}")
            preview_columns[2].metric("Columns", f"{len(preview.columns):,}")
            preview_columns[3].metric("Worksheet", sheet_name or "CSV")
            duplicate_names = len(set(map(str, preview.columns))) != len(preview.columns)
            if duplicate_names:
                st.warning("Duplicate source columns were detected. The importer will assign unique sanitized names.")
            st.dataframe(preview, width="stretch", hide_index=True)
            st.caption("This bounded preview is read in the frontend; the backend independently validates the complete file.")
            if st.button("Import private dataset", type="primary", key="confirm_upload", width="stretch"):
                if not dataset_name.strip():
                    st.warning("Enter a dataset display name.")
                else:
                    with st.status("Creating your governed dataset…", expanded=True) as status:
                        st.write("Uploading through the authenticated API")
                        st.write("Validating size, structure, and row limits")
                        response = upload_dataset_api(st.session_state.token, dataset_name.strip(), uploaded, sheet_name)
                        if response.get("error"):
                            status.update(label="Import could not be completed", state="error")
                        else:
                            st.write("Profiling columns and creating the private table")
                            status.update(label="Dataset ready", state="complete")
                    if not api_error(response):
                        st.session_state.selected_dataset_id = response.get("id")
                        st.session_state.inspected_dataset_id = response.get("id")
                        st.session_state.analysis_mode = "My Uploaded Dataset"
                        st.success(f"Imported {int(response.get('row_count') or 0):,} rows across {int(response.get('column_count') or len(response.get('columns') or [])):,} columns.")
                        if st.button("Open dataset profile", key="post_upload_open", type="primary"):
                            navigate("My Datasets")


def _unsafe_question(question: str) -> bool:
    return bool(
        re.search(
            r"\b(delete|update|insert|drop|truncate|alter|create|replace|merge|grant|revoke|copy|execute|call)\b",
            question,
            re.IGNORECASE,
        )
    )


def _question_button(question: str, key: str) -> None:
    if st.button(question, key=key, width="stretch"):
        st.session_state.query_text = question


def _clear_query_text() -> None:
    st.session_state.query_text = ""


def render_query_studio(datasets: list[dict[str, Any]]) -> None:
    active_dataset = selected_dataset(datasets)
    page_header(
        "Query Studio",
        [("Natural language → PostgreSQL", "blue"), ("Read-only enforced", "good"), ("Correction loop", "")],
    )

    selector_left, context_right = st.columns([1.3, 0.7], gap="large")
    with selector_left:
        st.session_state.analysis_mode = st.radio(
            "Analysis mode",
            ["Ecommerce Demo", "My Uploaded Dataset"],
            index=0 if st.session_state.analysis_mode == "Ecommerce Demo" else 1,
            horizontal=True,
            key="query_mode_widget",
        )
    with context_right:
        if st.session_state.analysis_mode == "Ecommerce Demo":
            st.markdown('<span class="pill blue">customers · products · orders · order_items</span>', unsafe_allow_html=True)
        elif active_dataset:
            st.markdown(f'<span class="pill good">Selected: {safe_html(active_dataset.get("dataset_name"))}</span>', unsafe_allow_html=True)

    if st.session_state.analysis_mode == "My Uploaded Dataset":
        if not datasets:
            empty_state("Upload a dataset before opening the private-data query workflow.")
            if st.button("Upload a dataset", type="primary"):
                navigate("Upload Dataset")
            return
        dataset_ids = [item["id"] for item in datasets]
        if st.session_state.selected_dataset_id not in dataset_ids:
            st.session_state.selected_dataset_id = dataset_ids[0]
        st.session_state.setdefault("query_dataset_widget", st.session_state.selected_dataset_id)
        if st.session_state.query_dataset_widget not in dataset_ids:
            st.session_state.query_dataset_widget = st.session_state.selected_dataset_id
        query_dataset_id = st.selectbox(
            "Dataset",
            dataset_ids,
            format_func=lambda item_id: next(
                f"{item['dataset_name']} · {int(item.get('row_count') or 0):,} rows"
                for item in datasets
                if item["id"] == item_id
            ),
            key="query_dataset_widget",
        )
        st.session_state.selected_dataset_id = query_dataset_id
        active_dataset = selected_dataset(datasets)
        with st.expander("Schema context", expanded=True):
            schema_search = st.text_input("Search schema", placeholder="Find a column", key="query_schema_search").strip().lower()
            columns = active_dataset.get("columns", []) if active_dataset else []
            visible_columns = [
                column for column in columns
                if not schema_search or schema_search in str(column.get("name") if isinstance(column, dict) else column).lower()
            ]
            chips = "".join(
                f'<span class="schema-chip">{safe_html(column.get("name") if isinstance(column, dict) else column)} <span style="color:#94A3B8">{safe_html(column.get("type", "") if isinstance(column, dict) else "")}</span></span>'
                for column in visible_columns
            )
            st.markdown(chips or '<span class="schema-chip">No matching columns</span>', unsafe_allow_html=True)
            st.caption("Only this dataset's physical table is included in the SQL allowlist and correction context.")

    with st.container(border=True):
        section_heading("Suggested questions", "Choose a starting point or write a specific metric, grouping, time range, and filter.")
        suggestions = DEMO_QUESTIONS[:4] if st.session_state.analysis_mode == "Ecommerce Demo" else suggested_questions(active_dataset.get("columns") if active_dataset else [])
        suggestion_columns = st.columns(2)
        for index, question in enumerate(suggestions):
            with suggestion_columns[index % 2]:
                _question_button(question, f"suggestion_{st.session_state.analysis_mode}_{index}")

    with st.container(border=True):
        section_heading("Question composer", "The platform returns safe SQL and high-level processing metadata, never private model reasoning.")
        question = st.text_area(
            "Business question",
            key="query_text",
            height=130,
            max_chars=2000,
            placeholder="Example: Show total revenue by category, sorted highest to lowest",
        )
        composer_left, composer_middle, composer_right = st.columns([0.45, 0.45, 1.1])
        with composer_left:
            run_clicked = st.button("Run analysis", type="primary", width="stretch", key="run_analysis")
        with composer_middle:
            st.button("Clear", width="stretch", key="clear_question", on_click=_clear_query_text)
        with composer_right:
            st.caption("Tip: name the measure and grouping. For example, “average order value by country.”")

    if run_clicked:
        cleaned_question = " ".join(question.split())
        if not cleaned_question:
            st.warning("Enter a business question before running the analysis.")
            return
        if _unsafe_question(cleaned_question):
            st.error("This workspace accepts analytics questions only. Requests to modify data or database objects are blocked.")
            return
        if st.session_state.analysis_mode == "My Uploaded Dataset" and not active_dataset:
            st.warning("Select a dataset before running the analysis.")
            return

        with st.status("Running governed analysis…", expanded=True) as status:
            st.write("Reading the authorized schema and retrieving safe context")
            st.write("Generating PostgreSQL and enforcing the read-only table policy")
            if st.session_state.analysis_mode == "Ecommerce Demo":
                response = run_demo_query_api(st.session_state.token, cleaned_question)
                dataset_name = "Ecommerce demo"
                dataset_id = None
            else:
                response = run_query_api(st.session_state.token, int(active_dataset["id"]), cleaned_question)
                dataset_name = active_dataset.get("dataset_name", "Uploaded dataset")
                dataset_id = active_dataset.get("id")
            if response.get("error"):
                status.update(label="Analysis could not be completed", state="error")
            else:
                st.write("Executing inside a read-only transaction and evaluating result quality")
                st.write("Preparing insight, visualization metadata, history, and report")
                status.update(label="Analysis complete", state="complete")
        if not api_error(response):
            response["_ui_dataset_name"] = dataset_name
            response["_ui_mode"] = st.session_state.analysis_mode
            response["dataset_id"] = response.get("dataset_id", dataset_id)
            response["timestamp"] = response.get("generated_at") or response.get("created_at") or datetime.now(timezone.utc).isoformat()
            response["row_count"] = response.get("row_count", len(response.get("result") or []))
            st.session_state.last_result = response
            navigate("Results")

    if st.session_state.last_result:
        st.info("A completed analysis is available in Results.")
        if st.button("Open latest result", key="open_latest_result"):
            navigate("Results")


def _result_dataset_name(response: dict[str, Any], datasets: list[dict[str, Any]]) -> str:
    if response.get("_ui_dataset_name"):
        return str(response["_ui_dataset_name"])
    dataset_id = response.get("dataset_id")
    return next((item.get("dataset_name", "Uploaded dataset") for item in datasets if item.get("id") == dataset_id), "Ecommerce demo")


def render_result_summary(response: dict[str, Any], frame: pd.DataFrame, dataset_name: str) -> None:
    quality = response.get("quality_eval") or response.get("quality") or {}
    score = quality.get("score") if isinstance(quality, dict) else None
    summary_metrics = st.columns(4)
    with summary_metrics[0]:
        metric_card("Rows returned", compact_number(response.get("row_count", len(frame))), "Bounded result set")
    with summary_metrics[1]:
        execution_ms = response.get("execution_ms") or response.get("execution_time_ms")
        metric_card("Execution", f"{int(execution_ms):,} ms" if execution_ms is not None else "Completed", "Database execution time")
    with summary_metrics[2]:
        metric_card("SQL quality", f"{float(score):.0f}/100" if score is not None else "Unavailable", "Evaluation score, when executed")
    with summary_metrics[3]:
        metric_card("RAG context", "Used" if response.get("rag_used") else "Not used", "Safe retrieval metadata")

    st.write("")
    section_heading("Executive insight", "Grounded in the executed result; review the data and SQL for material decisions.")
    insight = response.get("insight") or "The query completed, but an AI-generated insight was not available. Review the returned data directly."
    st.markdown(f'<div class="insight-card">{safe_html(insight)}</div>', unsafe_allow_html=True)

    finding_column, context_column = st.columns([1.15, 0.85], gap="large")
    with finding_column:
        with st.container(border=True):
            section_heading("Analysis context", "What was analyzed and how to continue.")
            st.markdown(f"**Question**  \n{response.get('question') or 'Not recorded'}")
            st.markdown(f"**Dataset**  \n{dataset_name}")
            next_steps = quality.get("next_steps", []) if isinstance(quality, dict) else []
            if next_steps:
                st.markdown("**Review guidance**")
                for step in next_steps[:3]:
                    st.markdown(f"- {step}")
    with context_column:
        with st.container(border=True):
            section_heading("RAG transparency", "Only safe retrieval metadata is shown.")
            rag_used = bool(response.get("rag_used"))
            st.markdown(f'<span class="pill {"good" if rag_used else ""}">RAG used: {"Yes" if rag_used else "No"}</span>', unsafe_allow_html=True)
            sources = response.get("rag_sources") or []
            context_type = "Fixed project knowledge and ecommerce schema" if response.get("_ui_mode") == "Ecommerce Demo" else "Selected dataset metadata and schema"
            st.markdown(f"**Context type:** {context_type}")
            st.markdown(f"**Safe sources:** {', '.join(map(str, sources)) if sources else 'No source names returned'}")
            if response.get("retrieved_chunks") is not None:
                st.markdown(f"**Retrieved chunks:** {response['retrieved_chunks']}")
            st.caption("Full prompts, raw chunks, internal table names, and credentials are never displayed.")


def render_result_visualization(response: dict[str, Any], frame: pd.DataFrame) -> None:
    if frame.empty:
        empty_state("The query returned no rows, so there is nothing to visualize. Try broadening the filters.")
        return
    prepared = coerce_for_visualization(frame)
    numeric, dates, categories = chart_columns(prepared)
    recommendation = chart_recommendation(prepared, response.get("question", ""))
    fingerprint = str(response.get("history_id") or response.get("run_id") or response.get("timestamp") or "latest")[-16:]
    st.info(f"Recommended view: {recommendation['type']}. You can override the chart and encoding below.")
    controls = st.columns([0.9, 1, 1, 1, 0.85])
    with controls[0]:
        chart_type = st.selectbox("Chart", available_chart_types(prepared), key=f"chart_type_{fingerprint}")
    all_columns = [str(column) for column in prepared.columns]
    x_default = recommendation.get("x") if recommendation.get("x") in all_columns else (all_columns[0] if all_columns else None)
    with controls[1]:
        x_axis = st.selectbox("X axis", all_columns, index=all_columns.index(x_default) if x_default in all_columns else 0, key=f"chart_x_{fingerprint}")
    y_options = ["None"] + numeric
    y_default = recommendation.get("y") if recommendation.get("y") in numeric else (numeric[0] if numeric else "None")
    with controls[2]:
        y_axis_value = st.selectbox("Y axis", y_options, index=y_options.index(y_default), key=f"chart_y_{fingerprint}")
    color_options = ["None"] + categories
    color_default = recommendation.get("color") if recommendation.get("color") in categories else "None"
    with controls[3]:
        color_value = st.selectbox("Group / color", color_options, index=color_options.index(color_default), key=f"chart_color_{fingerprint}")
    with controls[4]:
        aggregation = st.selectbox("Aggregation", ["None", "Sum", "Average", "Count", "Min", "Max"], key=f"chart_agg_{fingerprint}")

    fig, effective = build_chart(
        prepared,
        response.get("question", ""),
        chart_type=chart_type,
        x=x_axis,
        y=None if y_axis_value == "None" else y_axis_value,
        color=None if color_value == "None" else color_value,
        aggregation=aggregation,
    )
    if effective.get("type") == "KPI":
        kpi_columns = st.columns(min(4, max(1, len(numeric))))
        for column, metric_name in zip(kpi_columns, numeric[:4]):
            with column:
                metric_card(friendly_name(metric_name), compact_number(prepared.iloc[0][metric_name]), "Single-row query result")
    elif fig is None:
        empty_state("A meaningful chart could not be inferred for this result shape. Use the Data tab to inspect the records.")
    else:
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "responsive": True})
        download_left, download_middle, download_right = st.columns([0.6, 0.6, 1.8])
        chart_html = fig.to_html(include_plotlyjs="cdn", full_html=True).encode("utf-8")
        with download_left:
            st.download_button("Interactive HTML", chart_html, "analysis_chart.html", "text/html", width="stretch")
        with download_middle:
            if st.button("Prepare PNG", key=f"prepare_png_{fingerprint}", width="stretch"):
                try:
                    st.session_state.setdefault("chart_pngs", {})[fingerprint] = fig.to_image(format="png", scale=2)
                except Exception:
                    st.info("PNG export is unavailable in this runtime. The interactive HTML export contains the complete chart.")
            png = st.session_state.get("chart_pngs", {}).get(fingerprint)
            if png:
                st.download_button("Download PNG", png, "analysis_chart.png", "image/png", key=f"download_png_{fingerprint}", width="stretch")
        with download_right:
            st.caption(f"Effective view: {effective.get('type')} · X: {effective.get('x') or 'automatic'} · Y: {effective.get('y') or 'automatic'}")


def render_result_data(response: dict[str, Any], frame: pd.DataFrame) -> None:
    if frame.empty:
        empty_state("No records matched this question.")
        return
    filter_column, page_size_column, page_column = st.columns([1.4, 0.35, 0.35])
    with filter_column:
        search = st.text_input("Filter returned rows", placeholder="Search across displayed values", key="result_table_search").strip().lower()
    filtered = frame
    if search:
        mask = frame.astype(str).apply(lambda column: column.str.lower().str.contains(search, regex=False)).any(axis=1)
        filtered = frame[mask]
    with page_size_column:
        page_size = st.selectbox("Rows per page", [25, 50, 100, 250], index=1, key="result_page_size")
    page_count = max(1, (len(filtered) + page_size - 1) // page_size)
    if int(st.session_state.get("result_page", 1)) > page_count:
        st.session_state.result_page = 1
    with page_column:
        page_number = int(st.number_input("Page", min_value=1, max_value=page_count, value=1, step=1, key="result_page"))
    start = (page_number - 1) * page_size
    st.caption(f"Showing {start + 1 if len(filtered) else 0:,}–{min(start + page_size, len(filtered)):,} of {len(filtered):,} matching rows.")
    st.dataframe(filtered.iloc[start : start + page_size], width="stretch", hide_index=True)
    st.download_button(
        "Download complete result as CSV",
        frame.to_csv(index=False).encode("utf-8"),
        "analysis_result.csv",
        "text/csv",
        type="primary",
        key="download_result_csv",
    )


def render_result_sql(response: dict[str, Any], dataset_name: str) -> None:
    sql = response.get("sql") or response.get("generated_sql") or ""
    badge_column, correction_column, table_column = st.columns(3)
    with badge_column:
        st.markdown('<span class="pill good">Read-only policy passed</span>', unsafe_allow_html=True)
    with correction_column:
        correction_used = bool(response.get("correction_used") or response.get("correction_attempted"))
        st.markdown(f'<span class="pill {"warn" if correction_used else ""}">Correction: {"used" if correction_used else "not required"}</span>', unsafe_allow_html=True)
    with table_column:
        st.markdown(f'<span class="pill blue">Allowed data: {safe_html(dataset_name)}</span>', unsafe_allow_html=True)
    st.code(sql or "-- Generated SQL was not returned by the API", language="sql", line_numbers=True)
    if sql:
        st.download_button("Download SQL", sql.encode("utf-8"), "analysis.sql", "text/plain", key="download_result_sql")
    st.caption("The UI intentionally shows the authorized dataset label—not its internal physical table identifier or generation prompt.")


def render_result_quality(response: dict[str, Any]) -> None:
    quality = response.get("quality_eval") or response.get("quality")
    if not isinstance(quality, dict) or not quality:
        empty_state("SQL quality evaluation was unavailable for this run. No score is inferred or displayed as a misleading zero.")
        return
    if quality.get("available") is False:
        empty_state("SQL quality evaluation did not run successfully for this analysis. The query result is still available, but no quality pass is claimed.")
        if quality.get("recommendation"):
            st.info(str(quality["recommendation"]))
        return
    score = quality.get("score")
    passed = quality.get("passed")
    top = st.columns(4)
    with top[0]:
        metric_card("Overall score", f"{float(score):.0f}/100" if score is not None else "Unavailable", "Checks actually executed")
    with top[1]:
        metric_card("Outcome", "Passed" if passed is True else "Review" if passed is False else "Unavailable", "Quality policy threshold")
    with top[2]:
        metric_card("Confidence", str(quality.get("confidence") or "Unavailable"), "Evaluator confidence")
    with top[3]:
        metric_card("Detected intent", str(quality.get("detected_label") or quality.get("detected_intent") or "Unavailable"), "Question classification")
    st.write("")
    checks = quality.get("checks") or []
    if checks:
        with st.container(border=True):
            section_heading("Executed checks", "Safety, executability, relevance, and result alignment are distinct signals.")
            for check in checks:
                if isinstance(check, dict):
                    check_passed = bool(check.get("passed"))
                    st.markdown(
                        f'<div class="quality-row"><div class="quality-icon {"pass" if check_passed else "fail"}">{"✓" if check_passed else "!"}</div><div><div class="quality-name">{safe_html(check.get("name") or "Quality check")}</div><div class="quality-msg">{safe_html(check.get("message") or "No additional detail")}</div></div></div>',
                        unsafe_allow_html=True,
                    )
    recommendation = quality.get("recommendation")
    if recommendation:
        st.info(str(recommendation))
    explanation = quality.get("explanation") or []
    if explanation:
        with st.expander("Evaluation explanation"):
            for item in explanation:
                st.markdown(f"- {item}")


def render_result_report(response: dict[str, Any], dataset_name: str) -> None:
    markdown_report = report_markdown(response, dataset_name)
    st.markdown("**Portable decision record**")
    st.caption("The report includes question, authorized dataset label, SQL, bounded result preview, insight, RAG status, quality score, and safety statement.")
    local_left, server_right = st.columns(2)
    with local_left:
        st.download_button(
            "Download Markdown report",
            markdown_report.encode("utf-8"),
            "agentic_sql_report.md",
            "text/markdown",
            type="primary",
            width="stretch",
        )
    history_id = response.get("history_id")
    with server_right:
        if history_id and response.get("report_available"):
            if st.button("Prepare authenticated report", key=f"prepare_report_{history_id}", width="stretch"):
                with st.spinner("Preparing report through the protected API…"):
                    download = download_report_api(st.session_state.token, int(history_id))
                if not api_error(download):
                    st.session_state.report_downloads[int(history_id)] = download
            server_report = st.session_state.report_downloads.get(int(history_id))
            if server_report:
                st.download_button(
                    "Download generated report",
                    server_report["content"],
                    server_report.get("filename") or "agentic_sql_report.txt",
                    server_report.get("content_type") or "application/octet-stream",
                    key=f"download_report_{history_id}",
                    width="stretch",
                )
        else:
            st.info("A server-generated report was not retained for this run. The portable Markdown report remains available.")
    with st.expander("Report preview"):
        st.markdown(markdown_report)


def render_results(datasets: list[dict[str, Any]], response: dict[str, Any] | None = None) -> None:
    response = response or st.session_state.last_result
    if not response:
        page_header("Results", [("No active result", "warn")])
        empty_state("Run an analysis or reopen a history snapshot to populate this workspace.")
        if st.button("Open Query Studio", type="primary"):
            navigate("Query Studio")
        return
    dataset_name = _result_dataset_name(response, datasets)
    frame = result_dataframe(response.get("columns") or response.get("result_columns"), response.get("result") or response.get("rows"))
    page_header(
        "Results",
        [
            (dataset_name, "blue"),
            (f"{len(frame):,} rows displayed", ""),
            ("Read-only validated", "good"),
        ],
    )
    st.markdown(f"**Question:** {response.get('question') or 'Not recorded'}")
    st.caption(f"Completed {friendly_datetime(response.get('generated_at') or response.get('created_at') or response.get('timestamp'), include_time=True)}")
    tabs = st.tabs(["Summary", "Visualization", "Data", "SQL", "Quality", "Report"])
    with tabs[0]:
        render_result_summary(response, frame, dataset_name)
    with tabs[1]:
        render_result_visualization(response, frame)
    with tabs[2]:
        render_result_data(response, frame)
    with tabs[3]:
        render_result_sql(response, dataset_name)
    with tabs[4]:
        render_result_quality(response)
    with tabs[5]:
        render_result_report(response, dataset_name)


def _history_to_result(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **item,
        "history_id": item.get("id"),
        "_ui_dataset_name": item.get("dataset_name") or "Ecommerce demo",
        "_ui_mode": "Ecommerce Demo" if item.get("dataset_id") is None else "My Uploaded Dataset",
        "timestamp": item.get("created_at"),
        "quality_eval": item.get("quality_eval") or ({"score": item.get("quality_score")} if item.get("quality_score") is not None else None),
    }


def _prepare_history_rerun(item: dict[str, Any]) -> None:
    st.session_state.query_text = item.get("question") or ""
    if item.get("dataset_id") is None:
        st.session_state.analysis_mode = "Ecommerce Demo"
        st.session_state.query_mode_widget = "Ecommerce Demo"
    else:
        st.session_state.analysis_mode = "My Uploaded Dataset"
        st.session_state.query_mode_widget = "My Uploaded Dataset"
        st.session_state.selected_dataset_id = item.get("dataset_id")
        st.session_state.query_dataset_widget = item.get("dataset_id")
    navigate("Query Studio")


def render_history(datasets: list[dict[str, Any]]) -> None:
    page_header("Query History", [("Private audit trail", "good"), ("Up to 500 recent runs", "")])
    response = history_api(st.session_state.token, limit=500)
    if api_error(response):
        return
    history = response.get("history", [])
    if not history:
        empty_state("No saved analysis history yet. Successful demo and uploaded-data queries will appear here.")
        if st.button("Start an analysis", type="primary"):
            navigate("Query Studio")
        return

    dataset_choices: list[tuple[str, int | str | None]] = [("All data contexts", "all"), ("Ecommerce Demo", None)]
    dataset_choices.extend((item.get("dataset_name", f"Dataset {item['id']}"), item["id"]) for item in datasets)
    filter_columns = st.columns([1.3, 0.75, 0.7, 0.65])
    with filter_columns[0]:
        search = st.text_input("Search questions", placeholder="Search question or insight", key="history_search").strip().lower()
    with filter_columns[1]:
        selected_context = st.selectbox("Dataset", dataset_choices, format_func=lambda choice: choice[0], key="history_dataset_filter")
    parsed_dates = [pd.to_datetime(item.get("created_at"), errors="coerce", utc=True) for item in history]
    valid_dates = [timestamp.date() for timestamp in parsed_dates if not pd.isna(timestamp)]
    earliest = min(valid_dates) if valid_dates else date.today() - timedelta(days=90)
    latest = max(valid_dates) if valid_dates else date.today()
    with filter_columns[2]:
        selected_range = st.date_input("Date range", value=(earliest, latest), min_value=earliest, max_value=max(latest, date.today()), key="history_date_range")
    with filter_columns[3]:
        sort_order = st.selectbox("Sort", ["Newest first", "Oldest first"], key="history_sort")

    filtered = history
    context_id = selected_context[1]
    if context_id != "all":
        filtered = [item for item in filtered if item.get("dataset_id") == context_id]
    if search:
        filtered = [item for item in filtered if search in f"{item.get('question', '')} {item.get('insight', '')}".lower()]
    if isinstance(selected_range, (tuple, list)) and len(selected_range) == 2:
        start_date, end_date = selected_range
        filtered = [
            item for item in filtered
            if not pd.isna(timestamp := pd.to_datetime(item.get("created_at"), errors="coerce", utc=True))
            and start_date <= timestamp.date() <= end_date
        ]
    filtered.sort(key=lambda item: str(item.get("created_at") or ""), reverse=sort_order == "Newest first")

    summary_left, summary_middle, summary_right = st.columns([0.8, 0.8, 1.4])
    with summary_left:
        st.metric("Matching analyses", f"{len(filtered):,}")
    with summary_middle:
        export_frame = pd.DataFrame(
            [
                {
                    "dataset": item.get("dataset_name"),
                    "question": item.get("question"),
                    "sql": item.get("sql"),
                    "insight": item.get("insight"),
                    "quality_score": item.get("quality_score"),
                    "rag_used": item.get("rag_used"),
                    "correction_used": item.get("correction_used"),
                    "created_at": item.get("created_at"),
                }
                for item in filtered
            ]
        )
        st.download_button("Export filtered history", export_frame.to_csv(index=False).encode("utf-8"), "query_history.csv", "text/csv", width="stretch", disabled=export_frame.empty)
    with summary_right:
        with st.expander("Clear history"):
            if context_id is None:
                st.info("For safety, demo-only bulk deletion is not performed. Delete individual demo records below.")
            else:
                scope = "all history" if context_id == "all" else selected_context[0]
                confirmed = st.checkbox(f"Permanently delete {scope}", key="clear_history_confirm")
                if st.button("Clear selected history", disabled=not confirmed, key="clear_history_button"):
                    deletion = clear_history_api(st.session_state.token, None if context_id == "all" else int(context_id))
                    if not api_error(deletion):
                        st.success(f"Deleted {int(deletion.get('deleted_count') or 0):,} history records.")
                        st.rerun()

    if not filtered:
        empty_state("No history records match the selected filters.")
        return

    for item in filtered:
        history_id = int(item["id"])
        title = item.get("question") or "Untitled analysis"
        with st.expander(f"{title} · {friendly_datetime(item.get('created_at'), include_time=True)}"):
            metadata = st.columns(5)
            metadata[0].metric("Dataset", item.get("dataset_name") or "Ecommerce demo")
            metadata[1].metric("Rows", compact_number(item.get("row_count")))
            metadata[2].metric("Quality", f"{float(item['quality_score']):.0f}/100" if item.get("quality_score") is not None else "Unavailable")
            metadata[3].metric("RAG", "Used" if item.get("rag_used") else "No")
            metadata[4].metric("Execution", f"{int(item['execution_ms']):,} ms" if item.get("execution_ms") is not None else "—")
            st.markdown(f'<div class="insight-card">{safe_html(item.get("insight") or "No insight was saved for this run.")}</div>', unsafe_allow_html=True)
            with st.expander("Generated SQL"):
                st.code(item.get("sql") or "-- SQL unavailable", language="sql")
            actions = st.columns(4)
            with actions[0]:
                can_reopen = bool(item.get("columns") is not None and item.get("result") is not None)
                if st.button("Reopen result", key=f"reopen_history_{history_id}", disabled=not can_reopen, width="stretch"):
                    st.session_state.last_result = _history_to_result(item)
                    navigate("Results")
            with actions[1]:
                if st.button("Rerun question", key=f"rerun_history_{history_id}", width="stretch"):
                    _prepare_history_rerun(item)
            with actions[2]:
                if item.get("report_available"):
                    if st.button("Prepare report", key=f"history_report_{history_id}", width="stretch"):
                        download = download_report_api(st.session_state.token, history_id)
                        if not api_error(download):
                            st.session_state.report_downloads[history_id] = download
                    prepared = st.session_state.report_downloads.get(history_id)
                    if prepared:
                        st.download_button("Download report", prepared["content"], prepared.get("filename") or f"report_{history_id}.txt", prepared.get("content_type") or "text/plain", key=f"history_report_download_{history_id}", width="stretch")
                else:
                    local_report = report_markdown(_history_to_result(item), item.get("dataset_name") or "Ecommerce demo")
                    st.download_button("Markdown report", local_report.encode("utf-8"), f"analysis_{history_id}.md", "text/markdown", key=f"history_local_report_{history_id}", width="stretch")
            with actions[3]:
                confirm_delete = st.checkbox("Confirm delete", key=f"history_delete_confirm_{history_id}")
                if st.button("Delete record", key=f"history_delete_{history_id}", disabled=not confirm_delete, width="stretch"):
                    deletion = delete_history_api(st.session_state.token, history_id)
                    if not api_error(deletion):
                        st.rerun()


def render_reports(datasets: list[dict[str, Any]]) -> None:
    page_header("Reports", [("Authenticated downloads", "good"), ("No filesystem paths", "blue")])
    history = load_history(show_error=True)
    if not history:
        empty_state("No completed analyses are available for reporting.")
        return
    report_ready = sum(bool(item.get("report_available")) for item in history)
    report_metrics = st.columns(3)
    with report_metrics[0]:
        metric_card("Completed analyses", compact_number(len(history)), "Potential decision records")
    with report_metrics[1]:
        metric_card("Generated artifacts", compact_number(report_ready), "Stored behind owner checks")
    with report_metrics[2]:
        metric_card("Portable fallback", "Always available", "Client-generated Markdown")
    st.write("")
    section_heading("Report library", "Download a protected backend artifact when available, or generate a portable record from the saved snapshot.")
    report_search = st.text_input("Find a report", placeholder="Search question or dataset", key="report_search").strip().lower()
    visible = [
        item for item in history
        if not report_search or report_search in f"{item.get('question', '')} {item.get('dataset_name', '')}".lower()
    ]
    for item in visible:
        history_id = int(item["id"])
        with st.container(border=True):
            text_column, status_column, action_column = st.columns([1.35, 0.35, 0.5])
            with text_column:
                st.markdown(f"**{item.get('question') or 'Untitled analysis'}**")
                st.caption(f"{item.get('dataset_name') or 'Ecommerce demo'} · {friendly_datetime(item.get('created_at'), include_time=True)}")
            with status_column:
                st.markdown(f'<span class="pill {"good" if item.get("report_available") else "warn"}">{"Generated" if item.get("report_available") else "Portable"}</span>', unsafe_allow_html=True)
            with action_column:
                if item.get("report_available"):
                    if st.button("Prepare", key=f"library_prepare_{history_id}", width="stretch"):
                        response = download_report_api(st.session_state.token, history_id)
                        if not api_error(response):
                            st.session_state.report_downloads[history_id] = response
                    download = st.session_state.report_downloads.get(history_id)
                    if download:
                        st.download_button("Download", download["content"], download.get("filename") or f"report_{history_id}.txt", download.get("content_type") or "text/plain", key=f"library_download_{history_id}", width="stretch")
                else:
                    portable = report_markdown(_history_to_result(item), item.get("dataset_name") or "Ecommerce demo")
                    st.download_button("Download .md", portable.encode("utf-8"), f"analysis_{history_id}.md", "text/markdown", key=f"library_markdown_{history_id}", width="stretch")


def render_profile() -> None:
    user = st.session_state.user or {}
    page_header("Profile & Security", [(str(user.get("role") or "user").title(), "blue"), ("Session active", "good")])
    profile_column, password_column = st.columns([0.85, 1.15], gap="large")
    with profile_column:
        with st.container(border=True):
            section_heading("Account profile", "Identity values are sourced from the authenticated /auth/me endpoint.")
            st.text_input("Full name", value=user.get("full_name") or "", disabled=True)
            st.text_input("Email", value=user.get("email") or "", disabled=True)
            st.text_input("Role", value=str(user.get("role") or "user").title(), disabled=True, help="Roles cannot be changed from the frontend.")
            st.text_input("Account created", value=friendly_datetime(user.get("created_at"), include_time=True), disabled=True)
            st.caption("Profile editing is not exposed until a dedicated audited backend endpoint is available.")
        with st.container(border=True):
            section_heading("Current session", "The bearer token is kept in Streamlit session state and is never rendered or logged.")
            st.markdown('<span class="pill good">Authenticated</span>', unsafe_allow_html=True)
            st.write("Access automatically ends when the short-lived JWT expires or the password changes.")
            if st.button("Sign out this session", key="profile_signout", width="stretch"):
                end_session("You have been signed out securely.")
    with password_column:
        with st.container(border=True):
            section_heading("Change password", "Changing your password revokes existing access tokens across devices.")
            show_passwords = st.checkbox("Show passwords", key="profile_show_passwords")
            current_password = st.text_input("Current password", type="default" if show_passwords else "password", key="profile_current_password", autocomplete="current-password")
            new_password = st.text_input("New password", type="default" if show_passwords else "password", key="profile_new_password", autocomplete="new-password")
            confirm_password = st.text_input("Confirm new password", type="default" if show_passwords else "password", key="profile_confirm_password", autocomplete="new-password")
            score, label, improvements = password_strength(new_password)
            st.progress(score / 5 if new_password else 0, text=f"Password strength: {label if new_password else 'not entered'}")
            if new_password and improvements and score < 4:
                st.caption("Suggested: " + "; ".join(improvements[:2]) + ".")
            if st.button("Update password", type="primary", key="change_password", width="stretch"):
                if not current_password:
                    st.warning("Enter your current password.")
                elif score < 4:
                    st.warning("Choose a stronger new password.")
                elif new_password != confirm_password:
                    st.warning("New passwords do not match.")
                elif new_password == current_password:
                    st.warning("The new password must be different from the current password.")
                else:
                    with st.spinner("Updating password and revoking sessions…"):
                        response = change_password_api(st.session_state.token, current_password, new_password)
                    if not api_error(response):
                        end_session(response.get("message") or "Password updated. Sign in again.")
        st.info("Forgotten passwords use short-lived, single-use reset tokens. Account-existence details are never revealed by the reset request.")


def render_project_info() -> None:
    health = health_api()
    api_healthy = not health.get("error") and health.get("status") == "healthy"
    page_header(
        "Project Info",
        [("API online" if api_healthy else "API degraded", "good" if api_healthy else "warn"), ("PostgreSQL", "blue"), ("Gemini + RAG", "")],
    )
    with st.container(border=True):
        section_heading("Governed agent pipeline", "Each stage has a narrow responsibility and a graceful secondary-feature fallback.")
        stages = [
            ("01", "Identity & ownership", "JWT identity establishes which datasets, history records, and reports may be accessed."),
            ("02", "Schema context", "The selected demo model or private dataset schema becomes the only authorized generation context."),
            ("03", "RAG-assisted generation", "Gemini receives safe project knowledge and schema metadata, not credentials or another user's data."),
            ("04", "SQL policy gate", "Only one SELECT or WITH…SELECT statement may continue; blocked operations, tables, schemas, and unsafe functions fail closed."),
            ("05", "Read-only execution", "PostgreSQL executes with a timeout, result bound, and selected-table allowlist."),
            ("06", "Evaluation & delivery", "Quality checks, grounded insight, interactive charts, history, and authenticated reports complete the analysis."),
        ]
        for offset in range(0, len(stages), 3):
            columns = st.columns(3)
            for column, stage in zip(columns, stages[offset : offset + 3]):
                with column:
                    feature_card(*stage)

    capability_column, boundary_column = st.columns(2, gap="large")
    with capability_column:
        with st.container(border=True):
            section_heading("Product capabilities", "A complete analyst experience, not just SQL generation.")
            for item in [
                "Preloaded ecommerce executive dashboard",
                "CSV/XLSX upload and bounded profiling",
                "Dual-mode natural-language Query Studio",
                "Automatic and manually configurable Plotly charts",
                "Transparent RAG and SQL-quality metadata",
                "Private searchable history and report center",
                "Forgot/reset/change-password security flows",
            ]:
                st.markdown(f"- {item}")
    with boundary_column:
        with st.container(border=True):
            section_heading("Security boundaries", "Controls enforced by the API, not trusted to browser state.")
            for item in [
                "User identity is derived from the verified token",
                "Dataset IDs are rechecked against the authenticated owner",
                "Uploaded queries allow exactly one physical dataset table",
                "Demo queries allow only four ecommerce tables",
                "Mutation and PostgreSQL system access are rejected",
                "Downloads require owner-checked endpoints",
                "Raw prompts, secrets, and filesystem paths stay hidden",
            ]:
                st.markdown(f"- {item}")

    st.write("")
    with st.container(border=True):
        section_heading("Runtime status", "A concise operational view without raw infrastructure errors.")
        runtime = st.columns(4)
        runtime[0].metric("Frontend", "Ready")
        runtime[1].metric("API", "Healthy" if api_healthy else "Degraded")
        runtime[2].metric("Database", "Connected" if health.get("database") == "connected" else "Unavailable")
        runtime[3].metric("SQL mode", "Read only")
        if not api_healthy:
            st.warning("The backend or database is not fully available. Start the FastAPI service and verify PostgreSQL configuration.")


def run_application() -> None:
    if not st.session_state.token:
        render_authentication()
        return

    if not st.session_state.user:
        identity = me_api(st.session_state.token)
        if api_error(identity):
            return
        st.session_state.user = identity

    dataset_response = datasets_api(st.session_state.token)
    if api_error(dataset_response, show=False):
        if dataset_response.get("status_code") != 401:
            st.warning("Your dataset catalog could not be loaded. Demo analytics and account controls may still be available.")
        datasets: list[dict[str, Any]] = []
    else:
        datasets = dataset_response.get("datasets", [])

    valid_dataset_ids = [item.get("id") for item in datasets]
    if st.session_state.selected_dataset_id not in valid_dataset_ids:
        st.session_state.selected_dataset_id = valid_dataset_ids[0] if valid_dataset_ids else None

    render_sidebar(st.session_state.user, datasets)
    page = st.session_state.page
    if page == "Home":
        render_home(datasets)
    elif page == "Demo Dashboard":
        render_demo_dashboard()
    elif page == "My Datasets":
        render_datasets(datasets)
    elif page == "Upload Dataset":
        render_upload_dataset()
    elif page == "Query Studio":
        render_query_studio(datasets)
    elif page == "Results":
        render_results(datasets)
    elif page == "Query History":
        render_history(datasets)
    elif page == "Reports":
        render_reports(datasets)
    elif page == "Profile & Security":
        render_profile()
    else:
        render_project_info()


run_application()
