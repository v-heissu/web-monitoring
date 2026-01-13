"""
Web Monitor v2 - Streamlit Frontend
Main dashboard application
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from utils.db import get_db_connection
from utils.auth import check_password
from services.pdf_export import PDFExporter
from services.gemini import GeminiAnalyzer
from worker import scrape_project
import time

# Configuration
st.set_page_config(
    page_title="Web Monitor v2",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auth check
if not check_password():
    st.stop()

# Custom CSS
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)


# Database connection
@st.cache_resource
def get_db():
    return get_db_connection()


db = get_db()
cursor = db.cursor()

# Sidebar
st.sidebar.title("Web Monitor")
st.sidebar.caption(f"Logged as: {st.session_state.get('current_user', 'User')}")

# Logout button
if st.sidebar.button("Logout"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

st.sidebar.divider()

# Project selector
cursor.execute("SELECT id, name FROM projects ORDER BY name")
projects = cursor.fetchall()

project_options = ["+ Nuovo Progetto"] + [p['name'] for p in projects]
selected = st.sidebar.selectbox("Seleziona Progetto", project_options)

# Main content
if selected == "+ Nuovo Progetto":
    # NEW PROJECT CREATION
    st.title("Crea Nuovo Progetto")

    with st.form("create_project"):
        col1, col2 = st.columns(2)

        with col1:
            brand = st.text_input("Brand *", help="Nome del brand da monitorare")
            industry = st.text_input("Settore *", help="Es: Tech, Fashion, Food")

        with col2:
            market = st.selectbox(
                "Mercato",
                ["IT", "US", "UK", "DE", "FR", "ES"],
                help="Mercato di riferimento"
            )
            use_ai = st.checkbox(
                "Usa AI per suggerimenti",
                value=True,
                help="Gemini suggerira competitor e keywords"
            )

        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            submitted = st.form_submit_button("Crea Progetto", type="primary")
        with col2:
            cancelled = st.form_submit_button("Annulla")

        if cancelled:
            st.rerun()

        if submitted and brand and industry:
            with st.spinner("Generando suggerimenti AI..."):
                # AI Suggestions
                suggestions = {'competitors': [], 'keywords': [], 'portals': []}

                if use_ai:
                    try:
                        gemini = GeminiAnalyzer()
                        suggestions = gemini.suggest_competitors_keywords(
                            brand, industry, market
                        )
                    except Exception as e:
                        st.warning(f"AI suggestions failed: {e}")

            # Store in session for next step
            st.session_state['new_project'] = {
                'brand': brand,
                'industry': industry,
                'market': market,
                'suggestions': suggestions,
                'use_ai': use_ai
            }

    # Show suggestions if we have them
    if 'new_project' in st.session_state:
        np = st.session_state['new_project']
        suggestions = np['suggestions']

        if np['use_ai'] and (suggestions.get('competitors') or suggestions.get('keywords')):
            st.success("Suggerimenti generati!")

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Competitor")
                selected_competitors = st.multiselect(
                    "Seleziona",
                    suggestions.get('competitors', []),
                    default=suggestions.get('competitors', [])[:3]
                )
                manual_competitors = st.text_area(
                    "Aggiungi manualmente (uno per riga)",
                    ""
                )

            with col2:
                st.subheader("Keywords")
                selected_keywords = st.multiselect(
                    "Seleziona",
                    suggestions.get('keywords', []),
                    default=suggestions.get('keywords', [])[:5]
                )
                manual_keywords = st.text_area(
                    "Aggiungi manualmente (uno per riga)",
                    ""
                )

            # Merge selections
            all_competitors = selected_competitors + [
                c.strip() for c in manual_competitors.split('\n') if c.strip()
            ]
            all_keywords = selected_keywords + [
                k.strip() for k in manual_keywords.split('\n') if k.strip()
            ]

            # Save button
            if st.button("Salva Progetto", type="primary"):
                try:
                    # Insert project
                    cursor.execute("""
                        INSERT INTO projects (name, brand, industry, market, created_by)
                        VALUES (%s, %s, %s, %s, 1)
                        RETURNING id
                    """, (f"{np['brand']} Monitor", np['brand'], np['industry'], np['market']))

                    project_id = cursor.fetchone()['id']

                    # Insert competitors
                    for comp in all_competitors:
                        cursor.execute("""
                            INSERT INTO competitors (project_id, name, is_ai_suggested)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (project_id, comp, np['use_ai']))

                    # Insert keywords
                    for kw in all_keywords:
                        cursor.execute("""
                            INSERT INTO keywords (project_id, keyword, is_ai_suggested)
                            VALUES (%s, %s, %s)
                            ON CONFLICT DO NOTHING
                        """, (project_id, kw, np['use_ai']))

                    # Create schedule
                    cursor.execute("""
                        INSERT INTO schedules (project_id, frequency, next_run)
                        VALUES (%s, 'daily', NOW() + INTERVAL '6 hours')
                    """, (project_id,))

                    db.commit()

                    st.success("Progetto creato con successo!")
                    st.balloons()

                    # Trigger first scraping
                    task = scrape_project.delay(project_id)
                    st.info(f"Primo scraping avviato (Task: {task.id})")

                    # Clear session and reload
                    del st.session_state['new_project']
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"Errore: {e}")
                    db.rollback()

else:
    # EXISTING PROJECT DASHBOARD
    project = next(p for p in projects if p['name'] == selected)
    project_id = project['id']

    # Load full project data
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project_data = cursor.fetchone()

    # Header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.title(f"{project_data['name']}")
        st.caption(f"Brand: {project_data['brand']} | {project_data['industry']} | {project_data['market']}")

    with col2:
        if st.button("Scraping Manuale", use_container_width=True):
            task = scrape_project.delay(project_id)
            st.success(f"Task avviato: {task.id}")

    with col3:
        if st.button("Impostazioni", use_container_width=True):
            st.session_state.show_settings = True

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Dashboard",
        "Articoli",
        "Configurazione",
        "Alert"
    ])

    with tab1:
        # DASHBOARD TAB
        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        # Today's articles
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM articles
            WHERE project_id = %s
            AND DATE(scraped_at) = CURRENT_DATE
        """, (project_id,))
        today_count = cursor.fetchone()['count']

        # Yesterday's articles
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM articles
            WHERE project_id = %s
            AND DATE(scraped_at) = CURRENT_DATE - 1
        """, (project_id,))
        yesterday_count = cursor.fetchone()['count'] or 1

        delta = ((today_count - yesterday_count) / yesterday_count * 100) if yesterday_count else 0

        with col1:
            st.metric("Articoli Oggi", today_count, f"{delta:+.0f}%")

        # Average sentiment
        cursor.execute("""
            SELECT AVG(sentiment_score) as avg
            FROM articles
            WHERE project_id = %s
            AND scraped_at >= NOW() - INTERVAL '7 days'
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

        # Top source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM articles
            WHERE project_id = %s
            GROUP BY source
            ORDER BY count DESC
            LIMIT 1
        """, (project_id,))

        top_source_row = cursor.fetchone()
        top_source = top_source_row['source'] if top_source_row else "N/A"

        with col3:
            st.metric("Top Fonte", top_source)

        # Active alerts
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM alerts
            WHERE project_id = %s
            AND is_active = TRUE
        """, (project_id,))
        alert_count = cursor.fetchone()['count']

        with col4:
            st.metric("Alert Attivi", alert_count)

        st.divider()

        # Timeline chart
        cursor.execute("""
            SELECT DATE(scraped_at) as date, COUNT(*) as count
            FROM articles
            WHERE project_id = %s
            AND scraped_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(scraped_at)
            ORDER BY date
        """, (project_id,))

        timeline_data = cursor.fetchall()

        if timeline_data:
            df_timeline = pd.DataFrame(timeline_data)
            fig_timeline = px.line(
                df_timeline,
                x='date',
                y='count',
                title='Menzioni Giornaliere (30 giorni)',
                labels={'count': 'Articoli', 'date': 'Data'}
            )
            fig_timeline.update_traces(line_color='#667eea', line_width=3)
            fig_timeline.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12)
            )
            st.plotly_chart(fig_timeline, use_container_width=True)

        # Charts row
        col1, col2 = st.columns(2)

        with col1:
            # Sentiment distribution
            cursor.execute("""
                SELECT sentiment, COUNT(*) as count
                FROM articles
                WHERE project_id = %s
                AND sentiment IS NOT NULL
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
                        'positive': '#27ae60',
                        'neutral': '#f39c12',
                        'negative': '#e74c3c'
                    }
                )
                fig_sentiment.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_sentiment, use_container_width=True)

        with col2:
            # Top sources
            cursor.execute("""
                SELECT source, COUNT(*) as count
                FROM articles
                WHERE project_id = %s
                GROUP BY source
                ORDER BY count DESC
                LIMIT 10
            """, (project_id,))

            source_data = cursor.fetchall()

            if source_data:
                df_sources = pd.DataFrame(source_data)
                fig_sources = px.bar(
                    df_sources,
                    y='source',
                    x='count',
                    orientation='h',
                    title='Top 10 Fonti',
                    labels={'count': 'Articoli', 'source': ''}
                )
                fig_sources.update_traces(marker_color='#667eea')
                fig_sources.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_sources, use_container_width=True)

    with tab2:
        # ARTICLES TAB
        st.subheader("Articoli")

        # Filters
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

        with col1:
            filter_sentiment = st.multiselect(
                "Sentiment",
                ["positive", "neutral", "negative"]
            )

        with col2:
            filter_days = st.selectbox(
                "Periodo",
                [7, 14, 30, 60, 90],
                index=2
            )

        with col3:
            filter_source = st.text_input("Filtra fonte")

        with col4:
            sort_by = st.selectbox(
                "Ordina per",
                ["Data (recenti)", "Rilevanza", "Sentiment"]
            )

        # Build query
        query = """
            SELECT id, title, source, published_at, sentiment,
                   sentiment_score, relevance_score, url, summary
            FROM articles
            WHERE project_id = %s
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
            "Data (recenti)": "published_at DESC",
            "Rilevanza": "relevance_score DESC",
            "Sentiment": "sentiment_score DESC"
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
                    "CSV",
                    csv,
                    f"articles_{project_data['name']}_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )

        with col2:
            if articles and st.button("PDF", use_container_width=True):
                with st.spinner("Generando PDF..."):
                    pdf_exporter = PDFExporter()
                    pdf_bytes = pdf_exporter.generate_report(
                        project_data,
                        articles,
                        filter_days
                    )
                    st.download_button(
                        "Download PDF",
                        pdf_bytes,
                        f"report_{project_data['name']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        "application/pdf"
                    )

        st.caption(f"Trovati {len(articles)} articoli")

        # Display articles
        for article in articles:
            sentiment_emoji = {
                'positive': '+',
                'neutral': '=',
                'negative': '-'
            }

            sentiment_color = {
                'positive': '#27ae60',
                'neutral': '#f39c12',
                'negative': '#e74c3c'
            }

            with st.container():
                col1, col2 = st.columns([5, 1])

                with col1:
                    emoji = sentiment_emoji.get(article['sentiment'], '')
                    st.markdown(f"### [{emoji}] {article['title']}")
                    st.caption(f"**{article['source']}** | {article['published_at']} | Rilevanza: {article['relevance_score']:.0f}/100")
                    st.write(article['summary'] or "Nessun summary disponibile")
                    st.markdown(f"[Leggi articolo]({article['url']})")

                with col2:
                    color = sentiment_color.get(article['sentiment'], '#f39c12')
                    st.markdown(
                        f"<div style='background: {color}; color: white; padding: 10px; "
                        f"border-radius: 5px; text-align: center;'>"
                        f"<b>{article['sentiment'].upper() if article['sentiment'] else 'N/A'}</b><br/>"
                        f"{article['sentiment_score']:+.2f}</div>",
                        unsafe_allow_html=True
                    )

                st.divider()

    with tab3:
        # CONFIGURATION TAB
        st.subheader("Configurazione")

        # Keywords
        st.markdown("### Keywords")
        cursor.execute("""
            SELECT id, keyword, is_ai_suggested
            FROM keywords
            WHERE project_id = %s
            ORDER BY keyword
        """, (project_id,))
        keywords = cursor.fetchall()

        for kw in keywords:
            col1, col2 = st.columns([5, 1])
            with col1:
                prefix = "[AI]" if kw['is_ai_suggested'] else "[M]"
                st.text(f"{prefix} {kw['keyword']}")
            with col2:
                if st.button("X", key=f"del_kw_{kw['id']}", use_container_width=True):
                    cursor.execute("DELETE FROM keywords WHERE id = %s", (kw['id'],))
                    db.commit()
                    st.rerun()

        # Add keyword
        with st.form("add_keyword"):
            new_kw = st.text_input("Nuova keyword")
            if st.form_submit_button("Aggiungi"):
                if new_kw:
                    cursor.execute("""
                        INSERT INTO keywords (project_id, keyword)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (project_id, new_kw))
                    db.commit()
                    st.rerun()

        st.divider()

        # Competitors
        st.markdown("### Competitor")
        cursor.execute("""
            SELECT id, name, is_ai_suggested
            FROM competitors
            WHERE project_id = %s
            ORDER BY name
        """, (project_id,))
        competitors = cursor.fetchall()

        for comp in competitors:
            col1, col2 = st.columns([5, 1])
            with col1:
                prefix = "[AI]" if comp['is_ai_suggested'] else "[M]"
                st.text(f"{prefix} {comp['name']}")
            with col2:
                if st.button("X", key=f"del_comp_{comp['id']}", use_container_width=True):
                    cursor.execute("DELETE FROM competitors WHERE id = %s", (comp['id'],))
                    db.commit()
                    st.rerun()

        # Add competitor
        with st.form("add_competitor"):
            new_comp = st.text_input("Nuovo competitor")
            if st.form_submit_button("Aggiungi"):
                if new_comp:
                    cursor.execute("""
                        INSERT INTO competitors (project_id, name)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (project_id, new_comp))
                    db.commit()
                    st.rerun()

        st.divider()

        # Schedule
        st.markdown("### Scheduling")
        cursor.execute("""
            SELECT * FROM schedules WHERE project_id = %s
        """, (project_id,))
        schedule = cursor.fetchone()

        frequency = st.selectbox(
            "Frequenza scraping",
            ["hourly", "daily", "weekly"],
            index=["hourly", "daily", "weekly"].index(schedule['frequency'] if schedule else 'daily')
        )

        if st.button("Salva"):
            cursor.execute("""
                UPDATE schedules
                SET frequency = %s
                WHERE project_id = %s
            """, (frequency, project_id))
            db.commit()
            st.success("Salvato!")

    with tab4:
        # ALERTS TAB
        st.subheader("Alert")

        # Existing alerts
        cursor.execute("""
            SELECT * FROM alerts WHERE project_id = %s
            ORDER BY created_at DESC
        """, (project_id,))
        alerts = cursor.fetchall()

        for alert in alerts:
            status_icon = "[ON]" if alert['is_active'] else "[OFF]"

            with st.expander(f"{status_icon} {alert['type']} - Threshold: {alert['threshold']}"):
                st.write(f"**Destinatari:** {', '.join(alert['email_recipients'])}")
                st.write(f"**Ultimo trigger:** {alert['last_triggered'] or 'Mai'}")
                st.write(f"**Trigger totali:** {alert['trigger_count']}")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Elimina", key=f"del_alert_{alert['id']}"):
                        cursor.execute("DELETE FROM alerts WHERE id = %s", (alert['id'],))
                        db.commit()
                        st.rerun()

                with col2:
                    new_status = not alert['is_active']
                    btn_label = "Disattiva" if alert['is_active'] else "Attiva"
                    if st.button(btn_label, key=f"toggle_alert_{alert['id']}"):
                        cursor.execute("""
                            UPDATE alerts
                            SET is_active = %s
                            WHERE id = %s
                        """, (new_status, alert['id']))
                        db.commit()
                        st.rerun()

        st.divider()

        # Create new alert
        st.markdown("### Nuovo Alert")

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
                "Email destinatari (uno per riga)",
                placeholder="email1@example.com\nemail2@example.com"
            )

            if st.form_submit_button("Crea Alert"):
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

# Sidebar footer
st.sidebar.divider()
st.sidebar.caption(f"""
**Ultimo aggiornamento:** {datetime.now().strftime('%H:%M')}
**Versione:** 2.0.0

[Docs](https://github.com) | [Bug Report](https://github.com)
""")
