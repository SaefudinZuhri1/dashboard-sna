"""CSS global dan komponen UI helper untuk dashboard."""

import streamlit as st

PRIMARY = "#E53935"
ACCENT = "#B71C1C"
POSITIVE = "#4CAF50"
NEGATIVE = "#F44336"
NEUTRAL = "#FF9800"
CARD_RADIUS = "12px"
HEADER_GRAD = "linear-gradient(135deg, #B71C1C, #E53935, #F05A56)"


def load_css(dark_mode: bool = False, hide_sidebar: bool = False) -> None:
    """Terapkan tema global, sidebar, komponen, dan mode gelap dashboard."""
    try:
        if dark_mode:
            app_bg = "#0B0F17"
            sidebar_bg = "#111827"
            card_bg = "#151B26"
            secondary_bg = "#1E293B"
            input_bg = "#111827"
            text = "#F8FAFC"
            muted = "#A7B0BF"
            border = "#2A3648"
            header_bg = "rgba(11, 15, 23, 0.88)"
            shadow = "0 10px 30px rgba(0, 0, 0, 0.28)"
            table_header = "#1E293B"
        else:
            app_bg = "#F7F8FA"
            sidebar_bg = "#FFFFFF"
            card_bg = "#FFFFFF"
            secondary_bg = "#F4F5F7"
            input_bg = "#F4F5F7"
            text = "#1F1F1F"
            muted = "#5F6368"
            border = "#E5E7EB"
            header_bg = "rgba(255, 255, 255, 0.90)"
            shadow = "0 10px 28px rgba(15, 23, 42, 0.08)"
            table_header = "#FFF1F1"

        sidebar_visibility = (
            """
            section[data-testid="stSidebar"] {
                display: none !important;
            }
            [data-testid="collapsedControl"] {
                display: none !important;
            }
            """
            if hide_sidebar
            else ""
        )

        st.markdown(
            f"""
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

                :root {{
                    --app-primary: {PRIMARY};
                    --app-accent: {ACCENT};
                    --app-positive: {POSITIVE};
                    --app-neutral: {NEUTRAL};
                    --app-negative: {NEGATIVE};
                    --app-bg: {app_bg};
                    --app-sidebar: {sidebar_bg};
                    --app-card: {card_bg};
                    --app-secondary: {secondary_bg};
                    --app-input: {input_bg};
                    --app-text: {text};
                    --app-muted: {muted};
                    --app-border: {border};
                    --card-radius: {CARD_RADIUS};
                }}

                html,
                body,
                [class*="css"],
                .stApp {{
                    font-family: 'Plus Jakarta Sans', sans-serif;
                }}

                html,
                body,
                .stApp,
                [data-testid="stAppViewContainer"],
                [data-testid="stAppViewContainer"] > .main {{
                    background: {app_bg} !important;
                    color: {text} !important;
                }}

                [data-testid="stHeader"] {{
                    background: {header_bg} !important;
                    border-bottom: 1px solid {border};
                    backdrop-filter: blur(12px);
                }}

                [data-testid="stToolbar"] {{
                    color: {text} !important;
                }}

                footer {{
                    visibility: hidden;
                }}

                .block-container {{
                    max-width: 100%;
                    padding-top: 1.5rem;
                    padding-right: 2rem;
                    padding-bottom: 1.25rem;
                    padding-left: 2rem;
                }}

                [data-testid="stSidebarNav"] {{
                    display: none !important;
                }}

                section[data-testid="stSidebar"],
                section[data-testid="stSidebar"] > div {{
                    background: {sidebar_bg} !important;
                }}

                section[data-testid="stSidebar"] {{
                    border-right: 1px solid {border};
                }}

                section[data-testid="stSidebar"] > div:first-child {{
                    padding-top: 1rem;
                }}

                section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
                section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
                section[data-testid="stSidebar"] label,
                section[data-testid="stSidebar"] label p,
                section[data-testid="stSidebar"] span {{
                    color: {text};
                }}

                section[data-testid="stSidebar"] hr {{
                    border-color: {border} !important;
                    margin: 0.85rem 0;
                }}

                .sidebar-profile-card {{
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 0.45rem;
                    padding: 1rem 0.8rem;
                    margin: 0 0 0.8rem 0;
                    background: {card_bg};
                    border: 1px solid {border};
                    border-radius: 14px;
                    box-shadow: {shadow};
                }}

                .sidebar-avatar {{
                    width: 72px;
                    height: 72px;
                    display: block;
                    object-fit: cover;
                    border-radius: 50%;
                    border: 3px solid {PRIMARY};
                    background: {secondary_bg};
                }}

                .sidebar-avatar-fallback {{
                    width: 72px;
                    height: 72px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 50%;
                    border: 3px solid {PRIMARY};
                    background: {secondary_bg};
                    font-size: 2rem;
                }}

                .sidebar-profile-name {{
                    color: {text};
                    font-size: 0.98rem;
                    font-weight: 700;
                    line-height: 1.3;
                    text-align: center;
                    overflow-wrap: anywhere;
                }}

                .sidebar-role-badge {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 24px;
                    padding: 3px 10px;
                    border-radius: 999px;
                    color: #FFFFFF !important;
                    font-size: 0.75rem;
                    font-weight: 700;
                }}

                .sidebar-role-admin {{
                    background: {ACCENT};
                }}

                .sidebar-role-user {{
                    background: {PRIMARY};
                }}

                [data-testid="stMarkdownContainer"],
                [data-testid="stMarkdownContainer"] p,
                [data-testid="stMarkdownContainer"] li,
                [data-testid="stMarkdownContainer"] span,
                .stApp label,
                .stApp h1,
                .stApp h2,
                .stApp h3,
                .stApp h4,
                .stApp h5,
                .stApp h6 {{
                    color: {text};
                }}

                [data-testid="stCaptionContainer"],
                [data-testid="stCaptionContainer"] p,
                small {{
                    color: {muted} !important;
                }}

                [data-testid="stMetric"],
                [data-testid="metric-container"] {{
                    background: {card_bg};
                    border: 1px solid {border};
                    border-radius: {CARD_RADIUS};
                    padding: 1rem;
                    box-shadow: {shadow};
                }}

                [data-testid="stMetricLabel"] p {{
                    color: {muted} !important;
                }}

                [data-testid="stMetricValue"] {{
                    color: {text} !important;
                }}

                .metric-card {{
                    background: {card_bg};
                    border: 1px solid {border};
                    border-radius: {CARD_RADIUS};
                    color: {text};
                    padding: 1.2rem;
                    margin-bottom: 0.5rem;
                    box-shadow: {shadow};
                    transition: transform 0.2s ease, box-shadow 0.2s ease;
                }}

                .metric-card:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 12px 30px rgba(229, 57, 53, 0.14);
                }}

                .banner-header,
                .page-header {{
                    background: {HEADER_GRAD};
                    color: #FFFFFF !important;
                    padding: 2rem;
                    border-radius: {CARD_RADIUS};
                    margin-bottom: 1.5rem;
                    box-shadow: 0 12px 30px rgba(183, 28, 28, 0.18);
                    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
                }}

                .banner-header h1,
                .banner-header p,
                .banner-header span,
                .page-header h1,
                .page-header p,
                .page-header span {{
                    color: #FFFFFF !important;
                }}

                .banner-header h1,
                .page-header h1 {{
                    margin: 0;
                    font-size: 1.55rem;
                }}

                .banner-header p,
                .page-header p {{
                    margin: 0.45rem 0 0 0;
                    opacity: 0.94;
                }}

                .badge {{
                    display: inline-block;
                    border-radius: 20px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 700;
                    color: #FFFFFF !important;
                    white-space: nowrap;
                }}

                .badge-admin {{ background: {ACCENT}; }}
                .badge-user {{ background: {PRIMARY}; }}
                .badge-positive {{ background: {POSITIVE}; }}
                .badge-neutral {{ background: {NEUTRAL}; }}
                .badge-negative {{ background: {NEGATIVE}; }}
                .badge-ready {{ background: {POSITIVE}; }}
                .badge-soon,
                .badge-coming-soon,
                .badge-unknown {{ background: #64748B; }}
                .badge-real {{ background: {POSITIVE}; }}
                .badge-dummy {{ background: {NEUTRAL}; }}

                .chip {{
                    display: inline-block;
                    border-radius: 12px;
                    padding: 2px 10px;
                    font-size: 11px;
                    font-weight: 700;
                    color: #FFFFFF !important;
                    white-space: nowrap;
                }}

                .chip-twitter {{ background: #1DA1F2; }}
                .chip-instagram {{ background: #833AB4; }}
                .chip-tiktok {{ background: #111111; }}

                div[data-baseweb="input"] > div,
                div[data-baseweb="select"] > div,
                div[data-baseweb="base-input"],
                [data-testid="stTextInput"] input,
                [data-testid="stNumberInput"] input,
                [data-testid="stDateInput"] input,
                [data-testid="stTextArea"] textarea {{
                    background: {input_bg} !important;
                    color: {text} !important;
                    border-color: {border} !important;
                }}

                [data-testid="stTextInput"] input::placeholder,
                [data-testid="stTextArea"] textarea::placeholder {{
                    color: {muted} !important;
                    opacity: 1;
                }}

                div[data-baseweb="popover"],
                div[data-baseweb="menu"],
                ul[role="listbox"] {{
                    background: {card_bg} !important;
                    color: {text} !important;
                    border-color: {border} !important;
                }}

                li[role="option"] {{
                    color: {text} !important;
                }}

                li[role="option"]:hover {{
                    background: {secondary_bg} !important;
                }}

                [data-testid="stExpander"] {{
                    background: {card_bg};
                    border: 1px solid {border};
                    border-radius: {CARD_RADIUS};
                    overflow: hidden;
                }}

                [data-testid="stExpander"] summary,
                [data-testid="stExpander"] summary p {{
                    color: {text} !important;
                }}

                button[data-baseweb="tab"] {{
                    color: {muted} !important;
                }}

                button[data-baseweb="tab"][aria-selected="true"] {{
                    color: {PRIMARY} !important;
                    font-weight: 700;
                }}

                [data-baseweb="tab-list"] {{
                    gap: 0.3rem;
                    border-bottom: 1px solid {border};
                }}

                .stButton > button,
                .stDownloadButton > button {{
                    border-radius: 10px;
                    border-color: {border};
                    font-weight: 600;
                }}

                .stButton > button[kind="secondary"],
                .stDownloadButton > button[kind="secondary"] {{
                    background: {card_bg};
                    color: {text};
                }}

                .stButton > button[kind="secondary"]:hover,
                .stDownloadButton > button[kind="secondary"]:hover {{
                    border-color: {PRIMARY};
                    color: {PRIMARY};
                }}

                [data-testid="stFileUploader"] {{
                    background: {card_bg};
                    border-radius: {CARD_RADIUS};
                }}

                [data-testid="stDataFrame"],
                [data-testid="stTable"] {{
                    background: {card_bg};
                    border: 1px solid {border};
                    border-radius: {CARD_RADIUS};
                    overflow: hidden;
                }}

                [data-testid="stTable"] thead tr th {{
                    background: {table_header} !important;
                    color: {text} !important;
                }}

                [data-testid="stPlotlyChart"] {{
                    background: {card_bg};
                    border: 1px solid {border};
                    border-radius: {CARD_RADIUS};
                    padding: 0.25rem;
                    overflow: hidden;
                }}

                [data-testid="stPlotlyChart"] .main-svg {{
                    background: transparent !important;
                }}

                [data-testid="stPlotlyChart"] .main-svg .bg {{
                    fill: {card_bg} !important;
                }}

                [data-testid="stPlotlyChart"] .main-svg text {{
                    fill: {text} !important;
                }}

                [data-testid="stPlotlyChart"] .gridlayer path,
                [data-testid="stPlotlyChart"] .zerolinelayer path {{
                    stroke: {border} !important;
                }}

                [data-testid="stAlert"] {{
                    border-radius: {CARD_RADIUS};
                }}

                [data-testid="stToggle"] label p {{
                    color: {text} !important;
                    font-weight: 600;
                }}

                hr {{
                    border-color: {border} !important;
                }}

                ::-webkit-scrollbar {{
                    width: 7px;
                    height: 7px;
                }}

                ::-webkit-scrollbar-track {{
                    background: transparent;
                }}

                ::-webkit-scrollbar-thumb {{
                    background: {PRIMARY};
                    border-radius: 8px;
                }}

                ::-webkit-scrollbar-thumb:hover {{
                    background: #B71C1C;
                }}

                @keyframes fadeIn {{
                    from {{
                        opacity: 0;
                        transform: translateY(8px);
                    }}
                    to {{
                        opacity: 1;
                        transform: translateY(0);
                    }}
                }}

                [data-testid="stMainBlockContainer"] {{
                    animation: fadeIn 0.28s ease;
                }}

                @media (max-width: 900px) {{
                    .block-container {{
                        padding-right: 1rem;
                        padding-left: 1rem;
                    }}

                    .banner-header,
                    .page-header {{
                        padding: 1.35rem;
                    }}
                }}


                /* ===== UI PATCH 1.1: Sidebar ringkas, kontras, dan responsif ===== */
                section[data-testid="stSidebar"][aria-expanded="true"] {{
                    width: 320px !important;
                    min-width: 320px !important;
                    max-width: 320px !important;
                    box-shadow: 8px 0 28px rgba(15, 23, 42, 0.08);
                }}

                section[data-testid="stSidebar"] > div:first-child {{
                    width: 320px !important;
                    padding: 0.8rem 1rem 1rem 1rem !important;
                    overflow-x: hidden;
                }}

                /* HOTFIX FASE 15: hilangkan seluruh panel ketika sidebar ditutup.
                   Tombol pembuka bawaan Streamlit berada di luar section sidebar,
                   sehingga tetap dapat digunakan untuk membuka sidebar kembali. */
                section[data-testid="stSidebar"][aria-expanded="false"] {{
                    display: none !important;
                    width: 0 !important;
                    min-width: 0 !important;
                    max-width: 0 !important;
                    overflow: hidden !important;
                    border-right: 0 !important;
                    box-shadow: none !important;
                }}

                section[data-testid="stSidebar"][aria-expanded="false"] > div,
                section[data-testid="stSidebar"][aria-expanded="false"] > div:first-child {{
                    display: none !important;
                    width: 0 !important;
                    min-width: 0 !important;
                    max-width: 0 !important;
                    padding: 0 !important;
                    margin: 0 !important;
                    overflow: hidden !important;
                    opacity: 0 !important;
                    pointer-events: none !important;
                }}

                /* Kontrol buka/tutup sidebar ditangani khusus di app.py.
                   Hindari override warna berdasarkan mode terang/gelap. */

                .sidebar-brand {{
                    display: flex;
                    align-items: center;
                    gap: 0.7rem;
                    min-height: 54px;
                    padding: 0.55rem 0.65rem;
                    margin: 0 0 0.65rem 0;
                    background: linear-gradient(135deg, rgba(29,161,242,0.13), rgba(13,71,161,0.07));
                    border: 1px solid rgba(29,161,242,0.24);
                    border-radius: 13px;
                }}

                .sidebar-brand-logo,
                .sidebar-brand-fallback {{
                    width: 38px;
                    height: 38px;
                    min-width: 38px;
                    border-radius: 10px;
                    object-fit: contain;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: rgba(255,255,255,0.95);
                    padding: 4px;
                    font-size: 1.25rem;
                }}

                .sidebar-brand-copy {{
                    min-width: 0;
                    display: flex;
                    flex-direction: column;
                    line-height: 1.18;
                }}

                .sidebar-brand-title {{
                    color: {text} !important;
                    font-size: 0.94rem;
                    font-weight: 750;
                    letter-spacing: -0.01em;
                    white-space: nowrap;
                }}

                .sidebar-brand-subtitle {{
                    color: {muted} !important;
                    margin-top: 0.18rem;
                    font-size: 0.68rem;
                    font-weight: 600;
                    letter-spacing: 0.07em;
                    text-transform: uppercase;
                }}

                .sidebar-profile-card {{
                    display: flex !important;
                    flex-direction: row !important;
                    align-items: center !important;
                    justify-content: flex-start !important;
                    gap: 0.72rem !important;
                    min-height: 72px;
                    padding: 0.72rem !important;
                    margin: 0 0 0.75rem 0 !important;
                    background: {card_bg} !important;
                    border: 1px solid {border} !important;
                    border-radius: 13px !important;
                    box-shadow: none !important;
                }}

                .sidebar-avatar,
                .sidebar-avatar-fallback {{
                    width: 50px !important;
                    height: 50px !important;
                    min-width: 50px !important;
                    border-width: 2px !important;
                    font-size: 1.35rem !important;
                    box-shadow: 0 0 0 4px rgba(29,161,242,0.10);
                }}

                .sidebar-profile-copy {{
                    min-width: 0;
                    display: flex;
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 0.36rem;
                }}

                .sidebar-profile-name {{
                    max-width: 190px;
                    color: {text} !important;
                    font-size: 0.92rem !important;
                    font-weight: 750 !important;
                    text-align: left !important;
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}

                .sidebar-role-badge {{
                    min-height: 20px !important;
                    padding: 2px 8px !important;
                    font-size: 0.66rem !important;
                    letter-spacing: 0.03em;
                    text-transform: uppercase;
                }}

                .sidebar-role-admin {{
                    background: rgba(229,57,53,0.14) !important;
                    color: #FF6B68 !important;
                    border: 1px solid rgba(229,57,53,0.24);
                }}

                .sidebar-role-user {{
                    background: rgba(29,161,242,0.14) !important;
                    color: {PRIMARY} !important;
                    border: 1px solid rgba(29,161,242,0.24);
                }}

                .sidebar-section-label {{
                    color: {muted} !important;
                    margin: 0.2rem 0 0.35rem 0.2rem;
                    font-size: 0.62rem;
                    font-weight: 750;
                    letter-spacing: 0.10em;
                }}

                .sidebar-menu-label {{
                    margin-top: 0.85rem;
                }}

                section[data-testid="stSidebar"] [data-testid="stToggle"] {{
                    margin: 0 0.1rem;
                    padding: 0.1rem 0;
                }}

                section[data-testid="stSidebar"] [data-testid="stToggle"] label {{
                    min-height: 32px;
                }}

                section[data-testid="stSidebar"] [data-testid="stToggle"] label p {{
                    color: {text} !important;
                    font-size: 0.82rem !important;
                    font-weight: 600 !important;
                }}

                [data-testid="stToggle"] button[role="switch"][aria-checked="true"] {{
                    background: {PRIMARY} !important;
                    border-color: {PRIMARY} !important;
                }}

                [data-testid="stToggle"] button[role="switch"][aria-checked="false"] {{
                    background: {secondary_bg} !important;
                    border-color: {border} !important;
                }}

                section[data-testid="stSidebar"] [data-testid="stButton"] {{
                    margin: 0.12rem 0 !important;
                }}

                section[data-testid="stSidebar"] [data-testid="stButton"] button {{
                    width: 100% !important;
                    min-height: 43px !important;
                    display: flex !important;
                    align-items: center !important;
                    justify-content: flex-start !important;
                    padding: 0.55rem 0.78rem !important;
                    border-radius: 10px !important;
                    font-size: 0.82rem !important;
                    font-weight: 600 !important;
                    letter-spacing: -0.005em;
                    box-shadow: none !important;
                    transition: background 0.16s ease, border-color 0.16s ease,
                        color 0.16s ease, transform 0.16s ease !important;
                }}

                section[data-testid="stSidebar"] [data-testid="stButton"] button p {{
                    width: 100%;
                    margin: 0 !important;
                    color: inherit !important;
                    text-align: left !important;
                    white-space: normal !important;
                    line-height: 1.25 !important;
                }}

                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"] {{
                    background: transparent !important;
                    border: 1px solid transparent !important;
                    color: {text} !important;
                }}

                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover {{
                    background: {secondary_bg} !important;
                    border-color: {border} !important;
                    color: {PRIMARY} !important;
                    transform: translateX(2px);
                }}

                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {{
                    background: linear-gradient(135deg, {PRIMARY}, #1685D1) !important;
                    border: 1px solid rgba(29,161,242,0.88) !important;
                    color: #FFFFFF !important;
                    font-weight: 750 !important;
                    box-shadow: 0 7px 18px rgba(29,161,242,0.18) !important;
                }}

                section[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]:hover {{
                    background: linear-gradient(135deg, #168FDC, #0D71B8) !important;
                    border-color: #168FDC !important;
                    transform: none !important;
                }}

                .sidebar-account-divider {{
                    height: 1px;
                    margin: 0.85rem 0 0.55rem 0;
                    background: {border};
                }}

                .sidebar-version {{
                    display: flex;
                    flex-direction: column;
                    gap: 0.2rem;
                    margin-top: 0.65rem;
                    padding: 0.55rem 0.65rem;
                    color: {muted} !important;
                    font-size: 0.61rem;
                    line-height: 1.35;
                    text-align: center;
                    border-radius: 9px;
                    background: rgba(29,161,242,0.045);
                }}

                .sidebar-version span {{
                    color: {muted} !important;
                }}

                /* Form autentikasi dan tombol utama */
                [data-testid="stForm"] {{
                    background: {card_bg} !important;
                    border: 1px solid {border} !important;
                    border-radius: 13px !important;
                    padding: 0.9rem !important;
                    box-shadow: {shadow};
                }}

                .stFormSubmitButton > button,
                .stButton > button[kind="primary"] {{
                    background: linear-gradient(135deg, {PRIMARY}, #1685D1) !important;
                    border-color: {PRIMARY} !important;
                    color: #FFFFFF !important;
                }}

                .stFormSubmitButton > button p,
                .stButton > button[kind="primary"] p {{
                    color: #FFFFFF !important;
                }}

                .stFormSubmitButton > button:hover,
                .stButton > button[kind="primary"]:hover {{
                    background: linear-gradient(135deg, #168FDC, #0D71B8) !important;
                    border-color: #168FDC !important;
                }}

                .stFormSubmitButton > button:disabled,
                .stButton > button:disabled {{
                    background: {secondary_bg} !important;
                    border-color: {border} !important;
                    color: {muted} !important;
                    opacity: 0.78;
                }}

                .stFormSubmitButton > button:disabled p,
                .stButton > button:disabled p {{
                    color: {muted} !important;
                }}

                /* Plotly: fallback kontras bila chart belum membaca tema Python */
                [data-testid="stPlotlyChart"] .main-svg .gtitle,
                [data-testid="stPlotlyChart"] .main-svg .legendtext,
                [data-testid="stPlotlyChart"] .main-svg .xtick text,
                [data-testid="stPlotlyChart"] .main-svg .ytick text,
                [data-testid="stPlotlyChart"] .main-svg .xtitle,
                [data-testid="stPlotlyChart"] .main-svg .ytitle {{
                    fill: {text} !important;
                    color: {text} !important;
                }}

                @media (max-width: 720px) {{
                    section[data-testid="stSidebar"][aria-expanded="true"],
                    section[data-testid="stSidebar"] > div:first-child {{
                        width: min(88vw, 320px) !important;
                        min-width: min(88vw, 320px) !important;
                        max-width: min(88vw, 320px) !important;
                    }}
                }}

                {sidebar_visibility}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Tema tampilan belum dapat dimuat.")


def inject_platform_badge(platform: str) -> str:
    """Kembalikan HTML badge untuk platform media sosial."""
    try:
        key = (platform or "").strip().lower()
        aliases = {
            "twitter": ("chip-twitter", "Twitter/X"),
            "x": ("chip-twitter", "Twitter/X"),
            "twitter/x": ("chip-twitter", "Twitter/X"),
            "instagram": ("chip-instagram", "Instagram"),
            "ig": ("chip-instagram", "Instagram"),
            "tiktok": ("chip-tiktok", "TikTok"),
        }
        if key in aliases:
            css_class, label = aliases[key]
            return f'<span class="chip {css_class}">{label}</span>'
        safe_name = (platform or "Unknown").strip() or "Unknown"
        return f'<span class="badge badge-unknown">{safe_name}</span>'
    except Exception:
        return f'<span class="badge badge-unknown">{platform}</span>'


def render_metric_card(
    title: str,
    value: str,
    delta: str = None,
    icon: str = "📊",
) -> None:
    """Render kartu metrik KPI dengan style global."""
    try:
        delta_html = (
            f'<div style="font-size:0.85rem;color:var(--app-muted);">{delta}</div>'
            if delta
            else ""
        )
        st.markdown(
            f"""
            <div class="metric-card">
                <div style="font-size:1.5rem;">{icon}</div>
                <div style="font-size:0.85rem;color:var(--app-muted);">{title}</div>
                <div style="font-size:1.6rem;font-weight:700;">{value}</div>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Kartu metrik belum dapat ditampilkan.")


def render_data_badge(is_real: bool) -> None:
    """Render badge status data asli atau dummy."""
    try:
        if is_real:
            st.markdown(
                '<span class="badge badge-real">✅ Data Asli</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span class="badge badge-dummy">⚠️ Data Dummy</span>',
                unsafe_allow_html=True,
            )
    except Exception:
        st.error("Status sumber data belum dapat ditampilkan.")


def render_coming_soon_card(layanan: str, fitur: str) -> None:
    """Render kartu status pengembangan untuk layanan yang belum tersedia."""
    try:
        st.markdown(
            f"""
            <div class="metric-card" style="border-left:4px solid #9E9E9E;">
                <span class="badge badge-soon">Dalam Pengembangan</span><br><br>
                <strong>⏳ {layanan}</strong><br>
                <span style="color:var(--app-muted);">
                    {fitur} belum tersedia untuk layanan ini.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Informasi pengembangan belum dapat ditampilkan.")


def render_page_header(title: str, subtitle: str = None) -> None:
    """Render header halaman dengan banner gradient."""
    try:
        sub = f"<p>{subtitle}</p>" if subtitle else ""
        st.markdown(
            f'<div class="banner-header"><h1>{title}</h1>{sub}</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        st.error("Header halaman belum dapat ditampilkan.")
