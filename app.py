"""
Web Monitor v2 - Streamlit Frontend
Main dashboard application - Pro Web Consulting Branding
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from utils.db import get_db_connection
from utils.auth import check_password
from services.pdf_export import PDFExporter
from services.gemini import GeminiAnalyzer
from worker import scrape_project
import time

# Configuration
st.set_page_config(
    page_title="Web Monitor | Pro Web Consulting",
    page_icon="https://ai-landscape.prowebconsulting.net/assets/pwc-logo.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CUSTOM CSS - Pro Web Consulting Branding
# =============================================================================
st.markdown("""
<style>
    /* ===== HIDE STREAMLIT DEFAULT ELEMENTS ===== */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    div[data-testid="stToolbar"] {display: none;}
    div[data-testid="stDecoration"] {display: none;}
    div[data-testid="stStatusWidget"] {display: none;}

    /* Hide "Made with Streamlit" */
    .viewerBadge_container__r5tak {display: none;}
    .styles_viewerBadge__CvC9N {display: none;}

    /* ===== ROOT VARIABLES ===== */
    :root {
        --pwc-blue: #002856;
        --pwc-purple: #6B1AC7;
        --pwc-orange: #E8732A;
        --pwc-green: #27AE60;
        --pwc-red: #E74C3C;
        --pwc-yellow: #F39C12;
        --bg-dark: #0a1628;
        --bg-card: rgba(255,255,255,0.03);
        --bg-card-hover: rgba(255,255,255,0.06);
        --text-primary: #FFFFFF;
        --text-secondary: rgba(255,255,255,0.7);
        --border-color: rgba(255,255,255,0.1);
    }

    /* ===== MAIN BACKGROUND ===== */
    .stApp {
        background: linear-gradient(135deg, #0a1628 0%, #1a1a3e 50%, #0f2744 100%);
    }

    /* ===== SIDEBAR ===== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1f3c 0%, #162447 100%);
        border-right: 1px solid var(--border-color);
    }

    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text-primary);
    }

    /* Sidebar selectbox */
    [data-testid="stSidebar"] [data-testid="stSelectbox"] label {
        color: var(--text-secondary) !important;
    }

    /* ===== TYPOGRAPHY ===== */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    h1 {
        font-weight: 700 !important;
        font-size: 2rem !important;
    }

    p, span, label, .stMarkdown {
        color: var(--text-secondary);
    }

    /* ===== CARDS ===== */
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        transition: all 0.3s ease;
    }

    .metric-card:hover {
        background: var(--bg-card-hover);
        border-color: var(--pwc-purple);
        transform: translateY(-2px);
    }

    /* ===== METRICS ===== */
    [data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1rem 1.25rem;
    }

    [data-testid="stMetric"] label {
        color: var(--text-secondary) !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
    }

    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-size: 1.75rem !important;
        font-weight: 700 !important;
    }

    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-size: 0.875rem !important;
    }

    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: var(--bg-card);
        border-radius: 12px;
        padding: 0.5rem;
        border: 1px solid var(--border-color);
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        color: var(--text-secondary);
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: var(--pwc-purple) !important;
        color: white !important;
    }

    /* ===== BUTTONS ===== */
    .stButton > button {
        background: linear-gradient(135deg, var(--pwc-orange) 0%, #d35d1e 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(232, 115, 42, 0.4);
    }

    .stButton > button[kind="secondary"] {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
    }

    /* Primary button variant */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--pwc-purple) 0%, #5a15a8 100%);
    }

    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 15px rgba(107, 26, 199, 0.4);
    }

    /* ===== INPUTS ===== */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--pwc-purple) !important;
        box-shadow: 0 0 0 2px rgba(107, 26, 199, 0.2) !important;
    }

    /* ===== MULTISELECT ===== */
    .stMultiSelect > div > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
    }

    .stMultiSelect span[data-baseweb="tag"] {
        background: var(--pwc-purple) !important;
        border-radius: 6px !important;
    }

    /* ===== EXPANDER ===== */
    .streamlit-expanderHeader {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
    }

    .streamlit-expanderContent {
        background: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px !important;
    }

    /* ===== DIVIDER ===== */
    hr {
        border-color: var(--border-color) !important;
        margin: 1.5rem 0 !important;
    }

    /* ===== DATAFRAME ===== */
    .stDataFrame {
        border: 1px solid var(--border-color);
        border-radius: 12px;
        overflow: hidden;
    }

    /* ===== ALERTS/MESSAGES ===== */
    .stSuccess {
        background: rgba(39, 174, 96, 0.1) !important;
        border: 1px solid var(--pwc-green) !important;
        border-radius: 8px !important;
    }

    .stWarning {
        background: rgba(243, 156, 18, 0.1) !important;
        border: 1px solid var(--pwc-yellow) !important;
        border-radius: 8px !important;
    }

    .stError {
        background: rgba(231, 76, 60, 0.1) !important;
        border: 1px solid var(--pwc-red) !important;
        border-radius: 8px !important;
    }

    .stInfo {
        background: rgba(107, 26, 199, 0.1) !important;
        border: 1px solid var(--pwc-purple) !important;
        border-radius: 8px !important;
    }

    /* ===== CUSTOM CLASSES ===== */
    .logo-container {
        text-align: center;
        padding: 1rem 0 1.5rem 0;
    }

    .logo-container img {
        max-width: 180px;
    }

    .article-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }

    .article-card:hover {
        border-color: var(--pwc-purple);
        background: var(--bg-card-hover);
    }

    .sentiment-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.875rem;
        text-align: center;
    }

    .sentiment-positive {
        background: rgba(39, 174, 96, 0.2);
        color: #27AE60;
        border: 1px solid #27AE60;
    }

    .sentiment-neutral {
        background: rgba(243, 156, 18, 0.2);
        color: #F39C12;
        border: 1px solid #F39C12;
    }

    .sentiment-negative {
        background: rgba(231, 76, 60, 0.2);
        color: #E74C3C;
        border: 1px solid #E74C3C;
    }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
    }

    .section-header {
        color: var(--text-primary);
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--pwc-purple);
        display: inline-block;
    }

    /* Link styling */
    a {
        color: var(--pwc-orange) !important;
        text-decoration: none !important;
    }

    a:hover {
        color: var(--pwc-purple) !important;
        text-decoration: underline !important;
    }

    /* Form styling */
    [data-testid="stForm"] {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
    }

    /* Checkbox */
    .stCheckbox label span {
        color: var(--text-secondary) !important;
    }

    /* Slider */
    .stSlider > div > div > div {
        background: var(--pwc-purple) !important;
    }

    /* Caption */
    .stCaption {
        color: var(--text-secondary) !important;
    }

    /* Download button */
    .stDownloadButton > button {
        background: var(--bg-card) !important;
        border: 1px solid var(--pwc-purple) !important;
        color: var(--pwc-purple) !important;
    }

    .stDownloadButton > button:hover {
        background: var(--pwc-purple) !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# AUTH CHECK
# =============================================================================
if not check_password():
    st.stop()

# =============================================================================
# DATABASE CONNECTION
# =============================================================================
@st.cache_resource
def get_db():
    return get_db_connection()

db = get_db()
cursor = db.cursor()

# =============================================================================
# SIDEBAR
# =============================================================================
# Logo
st.sidebar.markdown("""
<div class="logo-container">
    <img src="https://ai-landscape.prowebconsulting.net/assets/pwc-logo.svg" alt="Pro Web Consulting">
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### Web Monitor")
st.sidebar.caption(f"Utente: **{st.session_state.get('current_user', 'Admin')}**")

# Logout button
if st.sidebar.button("Logout", use_container_width=True):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.divider()

# Project selector
cursor.execute("SELECT id, name FROM projects ORDER BY name")
projects = cursor.fetchall()

project_options = ["+ Nuovo Progetto"] + [p['name'] for p in projects]
selected = st.sidebar.selectbox("Seleziona Progetto", project_options, label_visibility="collapsed")

# =============================================================================
# PLOTLY THEME
# =============================================================================
PLOTLY_LAYOUT = {
    'plot_bgcolor': 'rgba(0,0,0,0)',
    'paper_bgcolor': 'rgba(0,0,0,0)',
    'font': {'color': 'rgba(255,255,255,0.8)', 'family': 'Inter, sans-serif'},
    'title': {'font': {'color': 'white', 'size': 16}},
    'xaxis': {
        'gridcolor': 'rgba(255,255,255,0.1)',
        'linecolor': 'rgba(255,255,255,0.2)',
        'tickcolor': 'rgba(255,255,255,0.5)'
    },
    'yaxis': {
        'gridcolor': 'rgba(255,255,255,0.1)',
        'linecolor': 'rgba(255,255,255,0.2)',
        'tickcolor': 'rgba(255,255,255,0.5)'
    },
    'legend': {'font': {'color': 'rgba(255,255,255,0.8)'}}
}

# =============================================================================
# MAIN CONTENT
# =============================================================================
if selected == "+ Nuovo Progetto":
    # NEW PROJECT CREATION
    st.markdown("## Crea Nuovo Progetto")
    st.caption("Configura un nuovo progetto di monitoraggio brand")

    st.markdown("<br>", unsafe_allow_html=True)

    with st.form("create_project"):
        col1, col2 = st.columns(2)

        with col1:
            brand = st.text_input("Brand *", help="Nome del brand da monitorare", placeholder="Es: Nike, Apple, Ferrari")
            industry = st.text_input("Settore *", help="Es: Tech, Fashion, Food", placeholder="Es: Automotive, Fashion")

        with col2:
            market = st.selectbox(
                "Mercato di riferimento",
                ["IT", "US", "UK", "DE", "FR", "ES"],
                help="Paese principale per il monitoraggio"
            )
            use_ai = st.checkbox(
                "Usa AI per suggerimenti automatici",
                value=True,
                help="Gemini suggerira competitor e keywords rilevanti"
            )

        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            submitted = st.form_submit_button("Crea Progetto", type="primary", use_container_width=True)
        with col2:
            cancelled = st.form_submit_button("Annulla", use_container_width=True)

        if cancelled:
            st.rerun()

        if submitted and brand and industry:
            with st.spinner("Generando suggerimenti AI..."):
                suggestions = {'competitors': [], 'keywords': [], 'portals': []}

                if use_ai:
                    try:
                        gemini = GeminiAnalyzer()
                        suggestions = gemini.suggest_competitors_keywords(brand, industry, market)
                    except Exception as e:
                        st.warning(f"AI suggestions failed: {e}")

            st.session_state['new_project'] = {
                'brand': brand,
                'industry': industry,
                'market': market,
                'suggestions': suggestions,
                'use_ai': use_ai
            }

    # Show suggestions
    if 'new_project' in st.session_state:
        np = st.session_state['new_project']
        suggestions = np['suggestions']

        if np['use_ai'] and (suggestions.get('competitors') or suggestions.get('keywords')):
            st.success("Suggerimenti AI generati con successo!")

            st.markdown("<br>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<p class="section-header">Competitor</p>', unsafe_allow_html=True)
                selected_competitors = st.multiselect(
                    "Seleziona i competitor da monitorare",
                    suggestions.get('competitors', []),
                    default=suggestions.get('competitors', [])[:3],
                    label_visibility="collapsed"
                )
                manual_competitors = st.text_area(
                    "Aggiungi competitor manualmente (uno per riga)",
                    "",
                    height=100,
                    placeholder="Competitor 1\nCompetitor 2"
                )

            with col2:
                st.markdown('<p class="section-header">Keywords</p>', unsafe_allow_html=True)
                selected_keywords = st.multiselect(
                    "Seleziona le keywords da monitorare",
                    suggestions.get('keywords', []),
                    default=suggestions.get('keywords', [])[:5],
                    label_visibility="collapsed"
                )
                manual_keywords = st.text_area(
                    "Aggiungi keywords manualmente (uno per riga)",
                    "",
                    height=100,
                    placeholder="keyword 1\nkeyword 2"
                )

            all_competitors = selected_competitors + [c.strip() for c in manual_competitors.split('\n') if c.strip()]
            all_keywords = selected_keywords + [k.strip() for k in manual_keywords.split('\n') if k.strip()]

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("Salva e Avvia Monitoraggio", type="primary", use_container_width=False):
                try:
                    cursor.execute("""
                        INSERT INTO projects (name, brand, industry, market, created_by)
                        VALUES (%s, %s, %s, %s, 1)
                        RETURNING id
                    """, (f"{np['brand']} Monitor", np['brand'], np['industry'], np['market']))

                    project_id = cursor.fetchone()['id']

                    for comp in all_competitors:
                        cursor.execute("""
                            INSERT INTO competitors (project_id, name, is_ai_suggested)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (project_id, comp, np['use_ai']))

                    for kw in all_keywords:
                        cursor.execute("""
                            INSERT INTO keywords (project_id, keyword, is_ai_suggested)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (project_id, kw, np['use_ai']))

                    cursor.execute("""
                        INSERT INTO schedules (project_id, frequency, next_run)
                        VALUES (%s, 'daily', NOW() + INTERVAL '6 hours')
                    """, (project_id,))

                    db.commit()

                    st.success("Progetto creato con successo!")
                    st.balloons()

                    task = scrape_project.delay(project_id)
                    st.info(f"Primo scraping avviato - Task ID: `{task.id}`")

                    del st.session_state['new_project']
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"Errore durante la creazione: {e}")
                    db.rollback()

else:
    # =============================================================================
    # EXISTING PROJECT DASHBOARD
    # =============================================================================
    project = next(p for p in projects if p['name'] == selected)
    project_id = project['id']

    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project_data = cursor.fetchone()

    # Header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"## {project_data['name']}")
        st.caption(f"**Brand:** {project_data['brand']} | **Settore:** {project_data['industry']} | **Mercato:** {project_data['market']}")

    with col2:
        if st.button("Scraping Manuale", use_container_width=True):
            task = scrape_project.delay(project_id)
            st.success(f"Task avviato!")

    with col3:
        if st.button("Elimina Progetto", use_container_width=True):
            st.session_state.confirm_delete = True

    if st.session_state.get('confirm_delete'):
        st.warning("Sei sicuro di voler eliminare questo progetto? Questa azione e irreversibile.")
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("Conferma", type="primary"):
                cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
                db.commit()
                del st.session_state['confirm_delete']
                st.rerun()
        with col2:
            if st.button("Annulla"):
                del st.session_state['confirm_delete']
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard",
        "Articoli",
        "Configurazione",
        "Alert",
        "Scraping Jobs"
    ])

    # =============================================================================
    # TAB 1: DASHBOARD
    # =============================================================================
    with tab1:
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        cursor.execute("""
            SELECT COUNT(*) as count FROM articles
            WHERE project_id = %s AND DATE(scraped_at) = CURRENT_DATE
        """, (project_id,))
        today_count = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM articles
            WHERE project_id = %s AND DATE(scraped_at) = CURRENT_DATE - 1
        """, (project_id,))
        yesterday_count = cursor.fetchone()['count'] or 1
        delta = ((today_count - yesterday_count) / yesterday_count * 100) if yesterday_count else 0

        with col1:
            st.metric("Articoli Oggi", today_count, f"{delta:+.0f}%")

        cursor.execute("""
            SELECT AVG(sentiment_score) as avg FROM articles
            WHERE project_id = %s AND scraped_at >= NOW() - INTERVAL '7 days'
            AND sentiment_score IS NOT NULL
        """, (project_id,))
        avg_sentiment = cursor.fetchone()['avg'] or 0

        with col2:
            sentiment_color = "normal"
            if avg_sentiment > 0.3:
                sentiment_color = "off"
            elif avg_sentiment < -0.3:
                sentiment_color = "inverse"
            st.metric("Sentiment 7gg", f"{avg_sentiment:+.2f}", delta_color=sentiment_color)

        cursor.execute("""
            SELECT source, COUNT(*) as count FROM articles
            WHERE project_id = %s GROUP BY source
            ORDER BY count DESC LIMIT 1
        """, (project_id,))
        top_source_row = cursor.fetchone()
        top_source = (top_source_row['source'] if top_source_row and top_source_row['source'] else "N/A") or "N/A"

        with col3:
            display_source = top_source[:20] + "..." if top_source and len(top_source) > 20 else (top_source or "N/A")
            st.metric("Top Fonte", display_source)

        cursor.execute("""
            SELECT COUNT(*) as count FROM alerts
            WHERE project_id = %s AND is_active = TRUE
        """, (project_id,))
        alert_count = cursor.fetchone()['count']

        with col4:
            st.metric("Alert Attivi", alert_count)

        st.markdown("<br>", unsafe_allow_html=True)

        # Timeline chart
        cursor.execute("""
            SELECT DATE(scraped_at) as date, COUNT(*) as count
            FROM articles WHERE project_id = %s
            AND scraped_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(scraped_at) ORDER BY date
        """, (project_id,))
        timeline_data = cursor.fetchall()

        if timeline_data:
            df_timeline = pd.DataFrame(timeline_data)
            fig_timeline = go.Figure()
            fig_timeline.add_trace(go.Scatter(
                x=df_timeline['date'],
                y=df_timeline['count'],
                mode='lines+markers',
                line=dict(color='#6B1AC7', width=3),
                marker=dict(size=8, color='#6B1AC7'),
                fill='tozeroy',
                fillcolor='rgba(107, 26, 199, 0.1)'
            ))
            fig_timeline.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font={'color': 'rgba(255,255,255,0.8)', 'family': 'Inter, sans-serif'},
                title={'text': 'Menzioni Giornaliere (30 giorni)', 'font': {'color': 'white', 'size': 16}},
                xaxis={
                    'gridcolor': 'rgba(255,255,255,0.1)',
                    'linecolor': 'rgba(255,255,255,0.2)',
                    'tickcolor': 'rgba(255,255,255,0.5)'
                },
                yaxis={
                    'gridcolor': 'rgba(255,255,255,0.1)',
                    'linecolor': 'rgba(255,255,255,0.2)',
                    'tickcolor': 'rgba(255,255,255,0.5)'
                },
                height=350,
                showlegend=False
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.info("Nessun dato disponibile per il grafico timeline. Avvia uno scraping per raccogliere dati.")

        # Charts row
        col1, col2 = st.columns(2)

        with col1:
            cursor.execute("""
                SELECT sentiment, COUNT(*) as count FROM articles
                WHERE project_id = %s AND sentiment IS NOT NULL
                GROUP BY sentiment
            """, (project_id,))
            sentiment_data = cursor.fetchall()

            if sentiment_data:
                df_sentiment = pd.DataFrame(sentiment_data)
                fig_sentiment = px.pie(
                    df_sentiment,
                    values='count',
                    names='sentiment',
                    title='Distribuzione Sentiment',
                    color='sentiment',
                    color_discrete_map={
                        'positive': '#27AE60',
                        'neutral': '#F39C12',
                        'negative': '#E74C3C'
                    },
                    hole=0.4
                )
                fig_sentiment.update_traces(textposition='inside', textinfo='percent+label')
                fig_sentiment.update_layout(**PLOTLY_LAYOUT, height=350)
                st.plotly_chart(fig_sentiment, use_container_width=True)

        with col2:
            cursor.execute("""
                SELECT source, COUNT(*) as count FROM articles
                WHERE project_id = %s GROUP BY source
                ORDER BY count DESC LIMIT 8
            """, (project_id,))
            source_data = cursor.fetchall()

            if source_data:
                df_sources = pd.DataFrame(source_data)
                fig_sources = px.bar(
                    df_sources,
                    y='source',
                    x='count',
                    orientation='h',
                    color_discrete_sequence=['#6B1AC7']
                )
                fig_sources.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font={'color': 'rgba(255,255,255,0.8)', 'family': 'Inter, sans-serif'},
                    title={'text': 'Top 8 Fonti', 'font': {'color': 'white', 'size': 16}},
                    xaxis={
                        'gridcolor': 'rgba(255,255,255,0.1)',
                        'linecolor': 'rgba(255,255,255,0.2)',
                        'tickcolor': 'rgba(255,255,255,0.5)'
                    },
                    yaxis={
                        'categoryorder': 'total ascending',
                        'gridcolor': 'rgba(255,255,255,0.1)',
                        'linecolor': 'rgba(255,255,255,0.2)',
                        'tickcolor': 'rgba(255,255,255,0.5)'
                    },
                    height=350,
                    showlegend=False
                )
                st.plotly_chart(fig_sources, use_container_width=True)

    # =============================================================================
    # TAB 2: ARTICLES
    # =============================================================================
    with tab2:
        st.markdown('<p class="section-header">Articoli Raccolti</p>', unsafe_allow_html=True)

        # Filters
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

        with col1:
            filter_sentiment = st.multiselect("Sentiment", ["positive", "neutral", "negative"])

        with col2:
            filter_days = st.selectbox("Periodo", [7, 14, 30, 60, 90], index=2)

        with col3:
            filter_source = st.text_input("Filtra fonte", placeholder="Es: Repubblica")

        with col4:
            sort_by = st.selectbox("Ordina per", ["Data (recenti)", "Rilevanza", "Sentiment"])

        # Build query
        query = """
            SELECT id, title, source, published_at, sentiment,
                   sentiment_score, relevance_score, url, summary
            FROM articles WHERE project_id = %s
            AND scraped_at >= NOW() - INTERVAL '%s days'
        """
        params = [project_id, filter_days]

        if filter_sentiment:
            placeholders = ','.join(['%s'] * len(filter_sentiment))
            query += f" AND sentiment IN ({placeholders})"
            params.extend(filter_sentiment)

        if filter_source:
            query += " AND source ILIKE %s"
            params.append(f"%{filter_source}%")

        sort_map = {
            "Data (recenti)": "published_at DESC NULLS LAST",
            "Rilevanza": "relevance_score DESC NULLS LAST",
            "Sentiment": "sentiment_score DESC NULLS LAST"
        }
        query += f" ORDER BY {sort_map[sort_by]} LIMIT 100"

        cursor.execute(query, params)
        articles = cursor.fetchall()

        # Export buttons
        col1, col2, col3 = st.columns([1, 1, 6])

        with col1:
            if articles:
                df_export = pd.DataFrame(articles)
                csv = df_export.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Esporta CSV",
                    csv,
                    f"articles_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )

        with col2:
            if articles and st.button("Genera PDF", use_container_width=True):
                with st.spinner("Generando PDF..."):
                    pdf_exporter = PDFExporter()
                    pdf_bytes = pdf_exporter.generate_report(project_data, articles, filter_days)
                    st.download_button(
                        "Download PDF",
                        pdf_bytes,
                        f"report_{datetime.now().strftime('%Y%m%d')}.pdf",
                        "application/pdf"
                    )

        st.caption(f"Trovati **{len(articles)}** articoli")

        st.markdown("<br>", unsafe_allow_html=True)

        # Display articles
        for article in articles:
            sentiment_class = f"sentiment-{article['sentiment']}" if article['sentiment'] else "sentiment-neutral"

            st.markdown(f"""
            <div class="article-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="flex: 1;">
                        <h4 style="color: white; margin: 0 0 0.5rem 0;">{article['title'] or 'Titolo non disponibile'}</h4>
                        <p style="color: rgba(255,255,255,0.6); font-size: 0.875rem; margin: 0 0 0.75rem 0;">
                            <strong>{article['source'] or 'Fonte sconosciuta'}</strong> |
                            {article['published_at'] or 'Data N/A'} |
                            Rilevanza: {article['relevance_score']:.0f if article['relevance_score'] else 0}/100
                        </p>
                        <p style="color: rgba(255,255,255,0.8); margin: 0 0 0.75rem 0;">
                            {article['summary'][:300] + '...' if article['summary'] and len(article['summary']) > 300 else article['summary'] or 'Nessun summary disponibile'}
                        </p>
                        <a href="{article['url']}" target="_blank" style="color: #E8732A;">Leggi articolo completo →</a>
                    </div>
                    <div style="margin-left: 1rem;">
                        <span class="sentiment-badge {sentiment_class}">
                            {article['sentiment'].upper() if article['sentiment'] else 'N/A'}<br/>
                            {article['sentiment_score']:+.2f if article['sentiment_score'] else '0.00'}
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # =============================================================================
    # TAB 3: CONFIGURATION
    # =============================================================================
    with tab3:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<p class="section-header">Keywords</p>', unsafe_allow_html=True)

            cursor.execute("""
                SELECT id, keyword, is_ai_suggested FROM keywords
                WHERE project_id = %s ORDER BY keyword
            """, (project_id,))
            keywords = cursor.fetchall()

            for kw in keywords:
                c1, c2 = st.columns([5, 1])
                with c1:
                    badge = "AI" if kw['is_ai_suggested'] else "M"
                    st.markdown(f"**[{badge}]** {kw['keyword']}")
                with c2:
                    if st.button("X", key=f"del_kw_{kw['id']}"):
                        cursor.execute("DELETE FROM keywords WHERE id = %s", (kw['id'],))
                        db.commit()
                        st.rerun()

            with st.form("add_keyword"):
                new_kw = st.text_input("Aggiungi keyword", placeholder="Nuova keyword")
                if st.form_submit_button("Aggiungi", use_container_width=True):
                    if new_kw:
                        cursor.execute("""
                            INSERT INTO keywords (project_id, keyword)
                            VALUES (%s, %s) ON CONFLICT DO NOTHING
                        """, (project_id, new_kw))
                        db.commit()
                        st.rerun()

        with col2:
            st.markdown('<p class="section-header">Competitor</p>', unsafe_allow_html=True)

            cursor.execute("""
                SELECT id, name, is_ai_suggested FROM competitors
                WHERE project_id = %s ORDER BY name
            """, (project_id,))
            competitors = cursor.fetchall()

            for comp in competitors:
                c1, c2 = st.columns([5, 1])
                with c1:
                    badge = "AI" if comp['is_ai_suggested'] else "M"
                    st.markdown(f"**[{badge}]** {comp['name']}")
                with c2:
                    if st.button("X", key=f"del_comp_{comp['id']}"):
                        cursor.execute("DELETE FROM competitors WHERE id = %s", (comp['id'],))
                        db.commit()
                        st.rerun()

            with st.form("add_competitor"):
                new_comp = st.text_input("Aggiungi competitor", placeholder="Nuovo competitor")
                if st.form_submit_button("Aggiungi", use_container_width=True):
                    if new_comp:
                        cursor.execute("""
                            INSERT INTO competitors (project_id, name)
                            VALUES (%s, %s) ON CONFLICT DO NOTHING
                        """, (project_id, new_comp))
                        db.commit()
                        st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<p class="section-header">Scheduling</p>', unsafe_allow_html=True)

        cursor.execute("SELECT * FROM schedules WHERE project_id = %s", (project_id,))
        schedule = cursor.fetchone()

        col1, col2 = st.columns([2, 4])
        with col1:
            frequency = st.selectbox(
                "Frequenza scraping",
                ["hourly", "daily", "weekly"],
                index=["hourly", "daily", "weekly"].index(schedule['frequency'] if schedule else 'daily'),
                format_func=lambda x: {"hourly": "Ogni ora", "daily": "Giornaliero", "weekly": "Settimanale"}[x]
            )

            if st.button("Salva Configurazione", type="primary"):
                cursor.execute("""
                    UPDATE schedules SET frequency = %s WHERE project_id = %s
                """, (frequency, project_id))
                db.commit()
                st.success("Configurazione salvata!")

    # =============================================================================
    # TAB 4: ALERTS
    # =============================================================================
    with tab4:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown('<p class="section-header">Alert Configurati</p>', unsafe_allow_html=True)

            cursor.execute("""
                SELECT * FROM alerts WHERE project_id = %s ORDER BY created_at DESC
            """, (project_id,))
            alerts = cursor.fetchall()

            if not alerts:
                st.info("Nessun alert configurato. Crea il tuo primo alert per ricevere notifiche.")

            for alert in alerts:
                status = "Attivo" if alert['is_active'] else "Disattivato"
                status_color = "#27AE60" if alert['is_active'] else "#E74C3C"
                alert_name = "Spike Menzioni" if alert['type'] == 'spike_detection' else "Cambio Sentiment"

                with st.expander(f"{alert_name} - Soglia: {alert['threshold']}"):
                    st.markdown(f"**Stato:** <span style='color: {status_color}'>{status}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Destinatari:** {', '.join(alert['email_recipients'])}")
                    st.markdown(f"**Ultimo trigger:** {alert['last_triggered'] or 'Mai'}")
                    st.markdown(f"**Trigger totali:** {alert['trigger_count']}")

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Elimina", key=f"del_alert_{alert['id']}", use_container_width=True):
                            cursor.execute("DELETE FROM alerts WHERE id = %s", (alert['id'],))
                            db.commit()
                            st.rerun()
                    with c2:
                        btn_label = "Disattiva" if alert['is_active'] else "Attiva"
                        if st.button(btn_label, key=f"toggle_{alert['id']}", use_container_width=True):
                            cursor.execute("""
                                UPDATE alerts SET is_active = NOT is_active WHERE id = %s
                            """, (alert['id'],))
                            db.commit()
                            st.rerun()

        with col2:
            st.markdown('<p class="section-header">Nuovo Alert</p>', unsafe_allow_html=True)

            with st.form("new_alert"):
                alert_type = st.selectbox(
                    "Tipo Alert",
                    ["spike_detection", "sentiment_shift"],
                    format_func=lambda x: {
                        'spike_detection': 'Spike Menzioni',
                        'sentiment_shift': 'Cambio Sentiment'
                    }[x]
                )

                if alert_type == "spike_detection":
                    st.caption("Notifica quando le menzioni superano la media storica")
                    threshold = st.slider("Moltiplicatore soglia", 1.0, 3.0, 1.5, 0.1)
                else:
                    st.caption("Notifica quando il sentiment cambia significativamente")
                    threshold = st.slider("Delta sentiment", 0.1, 1.0, 0.3, 0.05)

                emails = st.text_area(
                    "Email destinatari",
                    placeholder="email1@example.com\nemail2@example.com",
                    height=100
                )

                if st.form_submit_button("Crea Alert", type="primary", use_container_width=True):
                    email_list = [e.strip() for e in emails.split('\n') if e.strip()]

                    if not email_list:
                        st.error("Inserisci almeno un'email")
                    else:
                        cursor.execute("""
                            INSERT INTO alerts (project_id, type, threshold, email_recipients)
                            VALUES (%s, %s, %s, %s)
                        """, (project_id, alert_type, threshold, email_list))
                        db.commit()
                        st.success("Alert creato!")
                        st.rerun()

    # =============================================================================
    # TAB 5: SCRAPING JOBS
    # =============================================================================
    with tab5:
        st.markdown('<p class="section-header">Scraping Jobs</p>', unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 4])

        with col1:
            if st.button("Avvia Scraping", type="primary", use_container_width=True):
                try:
                    task = scrape_project.delay(project_id)
                    st.success(f"Task avviato: {task.id}")
                except Exception as e:
                    st.error(f"Errore avvio task: {e}")

        with col2:
            if st.button("Test Celery", use_container_width=True):
                try:
                    from worker import test_task
                    result = test_task.delay()
                    st.info(f"Test task inviato: {result.id}")
                    # Wait a bit for result
                    import time
                    time.sleep(2)
                    if result.ready():
                        st.success(f"Celery OK! {result.result}")
                    else:
                        st.warning("Task in attesa... controlla i log del worker")
                except Exception as e:
                    st.error(f"Errore connessione Celery/Redis: {e}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Recent jobs table
        cursor.execute("""
            SELECT
                id,
                status,
                started_at,
                completed_at,
                articles_found,
                new_articles,
                error_message,
                celery_task_id
            FROM scraping_jobs
            WHERE project_id = %s
            ORDER BY created_at DESC
            LIMIT 20
        """, (project_id,))
        jobs = cursor.fetchall()

        if not jobs:
            st.info("Nessun job di scraping eseguito. Clicca 'Avvia Scraping' per iniziare.")
        else:
            for job in jobs:
                status_color = {
                    'running': '#F39C12',
                    'completed': '#27AE60',
                    'failed': '#E74C3C'
                }.get(job['status'], '#888')

                status_icon = {
                    'running': '...',
                    'completed': 'OK',
                    'failed': 'ERR'
                }.get(job['status'], '?')

                with st.expander(
                    f"[{status_icon}] Job #{job['id']} - {job['started_at'].strftime('%d/%m %H:%M') if job['started_at'] else 'N/A'}",
                    expanded=(job['status'] == 'running')
                ):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f"**Status:** <span style='color: {status_color}'>{job['status'].upper()}</span>", unsafe_allow_html=True)
                        st.markdown(f"**Avviato:** {job['started_at']}")
                        st.markdown(f"**Completato:** {job['completed_at'] or 'In corso...'}")

                    with col2:
                        st.markdown(f"**Articoli trovati:** {job['articles_found'] or 0}")
                        st.markdown(f"**Nuovi articoli:** {job['new_articles'] or 0}")
                        if job['celery_task_id']:
                            st.markdown(f"**Task ID:** `{job['celery_task_id'][:16]}...`")

                    if job['error_message']:
                        st.error(f"**Errore:** {job['error_message']}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Environment check
        st.markdown('<p class="section-header">Diagnostica</p>', unsafe_allow_html=True)

        import os
        env_vars = {
            'DATABASE_URL': bool(os.getenv('DATABASE_URL')),
            'REDIS_URL': bool(os.getenv('REDIS_URL')),
            'DATAFORSEO_LOGIN': bool(os.getenv('DATAFORSEO_LOGIN')),
            'DATAFORSEO_PASSWORD': bool(os.getenv('DATAFORSEO_PASSWORD')),
            'GEMINI_API_KEY': bool(os.getenv('GEMINI_API_KEY')),
        }

        for var, configured in env_vars.items():
            icon = "OK" if configured else "MANCA"
            color = "#27AE60" if configured else "#E74C3C"
            st.markdown(f"<span style='color: {color}'>**[{icon}]**</span> {var}", unsafe_allow_html=True)

        if not all(env_vars.values()):
            st.warning("Alcune variabili d'ambiente non sono configurate. Lo scraping potrebbe fallire.")

# =============================================================================
# SIDEBAR FOOTER
# =============================================================================
st.sidebar.divider()
st.sidebar.caption(f"""
**Versione:** 2.0.0
**Ultimo refresh:** {datetime.now().strftime('%H:%M')}

[Pro Web Consulting](https://www.prowebconsulting.it)
""")
