"""Styles CSS dark finance avec accents or/dore."""

import streamlit as st

# Palette de couleurs
BG_DARK = "#0D1117"
BG_CARD = "#161B22"
BG_SURFACE = "#1C2333"
GOLD = "#D4A843"
GOLD_MUTED = "#C0A062"
GOLD_DIM = "#8B7332"
TEXT_PRIMARY = "#E6EDF3"
TEXT_SECONDARY = "#8B949E"
BORDER = "#30363D"
SUCCESS = "#3FB950"
DANGER = "#F85149"


def get_plotly_dark_theme() -> dict:
    """Retourne un template Plotly pour le theme dark finance."""
    return dict(
        paper_bgcolor=BG_DARK,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT_PRIMARY, family="Inter, system-ui, sans-serif"),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER),
        colorway=[GOLD, GOLD_MUTED, GOLD_DIM, SUCCESS, "#58A6FF", DANGER],
    )


def inject_global_css():
    """Injecte les styles CSS globaux (dark finance)."""
    st.markdown(
        f"""
    <style>
    /* ===== GLOBAL ===== */
    .stApp {{ background-color: {BG_DARK}; color: {TEXT_PRIMARY}; }}
    [data-testid="stAppViewContainer"] {{ background-color: {BG_DARK}; }}
    [data-testid="stHeader"] {{ background-color: {BG_DARK}; }}
    .main .block-container {{ max-width: 960px; padding-top: 1.5rem; }}

    /* ===== SIDEBAR ===== */
    [data-testid="stSidebar"] {{
        background-color: {BG_CARD}; border-right: 1px solid {BORDER};
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdown"] {{ color: {TEXT_PRIMARY}; }}

    /* ===== INPUTS ===== */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {{
        background-color: {BG_CARD} !important; color: {TEXT_PRIMARY} !important;
        border: 1px solid {BORDER} !important;
    }}
    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus {{
        border-color: {GOLD} !important;
        box-shadow: 0 0 0 2px rgba(212,168,67,0.2) !important;
    }}
    [data-testid="stTextInput"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stRadio"] label,
    [data-testid="stCheckbox"] label {{
        color: {TEXT_SECONDARY} !important;
    }}
    [data-testid="stSelectbox"] > div > div {{
        background-color: {BG_CARD} !important; border-color: {BORDER} !important;
        color: {TEXT_PRIMARY} !important;
    }}

    /* ===== BOUTONS ===== */
    button[data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, {GOLD} 0%, {GOLD_MUTED} 100%) !important;
        color: {BG_DARK} !important; font-weight: 700 !important; border: none !important;
        box-shadow: 0 4px 12px rgba(212,168,67,0.3) !important;
    }}
    button[data-testid="baseButton-primary"]:hover {{
        box-shadow: 0 6px 20px rgba(212,168,67,0.5) !important;
    }}
    button[data-testid="baseButton-secondary"] {{
        background-color: {BG_CARD} !important; color: {TEXT_PRIMARY} !important;
        border: 1px solid {BORDER} !important;
    }}
    button[data-testid="baseButton-secondary"]:hover {{
        border-color: {GOLD_MUTED} !important;
    }}

    /* ===== EXPANDERS ===== */
    [data-testid="stExpander"] {{
        background-color: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    }}
    [data-testid="stExpander"] summary {{ color: {TEXT_PRIMARY} !important; }}

    /* ===== TABS ===== */
    [data-testid="stTabs"] button {{ color: {TEXT_SECONDARY} !important; }}
    [data-testid="stTabs"] button[aria-selected="true"] {{
        color: {GOLD} !important; border-bottom-color: {GOLD} !important;
    }}

    /* ===== METRICS ===== */
    [data-testid="stMetricValue"] {{ color: {TEXT_PRIMARY} !important; }}
    [data-testid="stMetricLabel"] {{ color: {TEXT_SECONDARY} !important; }}

    /* ===== CARTES TYPE DE BIEN ===== */
    .type-card {{
        border: 2px solid {BORDER}; border-radius: 12px; padding: 1rem 0.5rem;
        text-align: center; background: {BG_CARD}; transition: all 0.2s ease;
        min-height: 100px; display: flex; flex-direction: column;
        align-items: center; justify-content: center; margin-bottom: 0.3rem;
    }}
    .type-card:hover {{
        border-color: {GOLD_MUTED}; box-shadow: 0 4px 12px rgba(212,168,67,0.15);
    }}
    .type-card.selected {{
        border-color: {GOLD}; background: {BG_SURFACE};
        box-shadow: 0 4px 16px rgba(212,168,67,0.25);
    }}
    .type-card .card-icon {{ font-size: 2.2rem; margin-bottom: 0.3rem; }}
    .type-card .card-label {{
        font-weight: 600; font-size: 0.8rem; color: {TEXT_PRIMARY};
        text-transform: uppercase; letter-spacing: 0.5px;
    }}

    /* ===== CARTE RESULTAT ===== */
    .result-card {{
        background: linear-gradient(135deg, {BG_CARD} 0%, {BG_SURFACE} 100%);
        border: 1px solid {BORDER}; border-radius: 16px; padding: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3); text-align: center; margin: 1rem 0;
    }}
    .result-price {{
        font-size: 2.8rem; font-weight: 800; color: {GOLD};
        text-shadow: 0 2px 8px rgba(212,168,67,0.3);
    }}
    .result-price-m2 {{ font-size: 1.1rem; color: {TEXT_SECONDARY}; margin-top: 0.3rem; }}
    .result-confidence {{
        display: inline-block; margin-top: 0.6rem; padding: 0.25rem 1rem;
        border-radius: 20px; font-weight: 600; font-size: 0.85rem;
        letter-spacing: 0.3px;
    }}
    .result-range {{
        text-align: center; color: {TEXT_SECONDARY}; font-size: 0.95rem;
        margin: 0.3rem 0 1rem 0;
    }}
    .result-range b {{ color: {TEXT_PRIMARY}; }}

    /* ===== RESUME SYNTHESE ===== */
    .result-summary {{
        background: {BG_SURFACE}; border-left: 3px solid {GOLD};
        border-radius: 0 8px 8px 0; padding: 1rem 1.2rem; margin: 1rem 0;
    }}
    .result-summary .summary-title {{
        color: {GOLD}; font-weight: 700; font-size: 0.95rem;
        margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.5px;
    }}
    .result-summary .summary-row {{
        display: flex; justify-content: space-between; padding: 0.3rem 0;
        border-bottom: 1px solid rgba(48,54,61,0.5); font-size: 0.88rem;
    }}
    .result-summary .summary-row:last-child {{ border-bottom: none; }}
    .result-summary .summary-label {{ color: {TEXT_SECONDARY}; }}
    .result-summary .summary-value {{ color: {TEXT_PRIMARY}; font-weight: 600; }}

    /* ===== PILULES AJUSTEMENT ===== */
    .adjustment-pill {{
        display: inline-block; padding: 0.2rem 0.7rem; border-radius: 12px;
        font-size: 0.78rem; font-weight: 600; margin: 0.15rem 0.2rem;
        background: rgba(212,168,67,0.12); color: {GOLD_MUTED};
        border: 1px solid rgba(212,168,67,0.25);
    }}
    .adjustment-pill.positive {{ color: {SUCCESS}; background: rgba(63,185,80,0.1); border-color: rgba(63,185,80,0.25); }}
    .adjustment-pill.negative {{ color: {DANGER}; background: rgba(248,81,73,0.1); border-color: rgba(248,81,73,0.25); }}

    /* ===== CHART HEADER ===== */
    .chart-title {{
        color: {TEXT_SECONDARY}; font-size: 0.85rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.3rem;
    }}

    /* ===== HEADERS ===== */
    .form-header {{ color: {GOLD}; font-size: 1.2rem; font-weight: 700; margin-bottom: 0.3rem; }}
    .form-subtitle {{ color: {TEXT_SECONDARY}; font-size: 0.85rem; margin-bottom: 1rem; }}
    .section-divider {{ border-top: 1px solid {BORDER}; margin: 1.5rem 0; }}

    /* ===== NOTE AJUSTEMENT ===== */
    .adjustment-note {{
        background: rgba(212,168,67,0.1); border: 1px solid rgba(212,168,67,0.3);
        border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: {GOLD_MUTED};
        margin-top: 1rem;
    }}

    /* ===== ZONES ===== */
    .zone-badge {{
        display: inline-block; padding: 0.15rem 0.5rem; border-radius: 10px;
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.3px;
    }}
    .zone-badge.zone-1 {{ background: rgba(212,168,67,0.2); color: {GOLD}; border: 1px solid rgba(212,168,67,0.4); }}
    .zone-badge.zone-2 {{ background: rgba(88,166,255,0.15); color: #58A6FF; border: 1px solid rgba(88,166,255,0.3); }}
    .zone-badge.zone-3 {{ background: rgba(139,148,158,0.15); color: {TEXT_SECONDARY}; border: 1px solid rgba(139,148,158,0.3); }}

    .zone-breakdown {{
        display: flex; gap: 1rem; margin: 1rem 0;
    }}
    .zone-breakdown-card {{
        flex: 1; background: {BG_CARD}; border: 1px solid {BORDER};
        border-radius: 12px; padding: 1rem 0.8rem; text-align: center;
    }}
    .zone-breakdown-card .zb-title {{
        font-size: 0.82rem; font-weight: 700;
        letter-spacing: 0.3px; margin-bottom: 0.5rem;
    }}
    .zone-breakdown-card .zb-value {{
        font-size: 1.25rem; font-weight: 800; color: {TEXT_PRIMARY};
        margin: 0.3rem 0;
    }}
    .zone-breakdown-card .zb-detail {{
        font-size: 0.78rem; color: {TEXT_SECONDARY}; margin-top: 0.3rem;
        line-height: 1.5;
    }}

    /* ===== RADIO / CHECKBOX ===== */
    [data-testid="stRadio"] > div {{ color: {TEXT_PRIMARY}; }}
    [data-testid="stCheckbox"] span {{ color: {TEXT_PRIMARY} !important; }}

    /* ===== MASQUER CHROME ===== */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}
    </style>
    """,
        unsafe_allow_html=True,
    )
