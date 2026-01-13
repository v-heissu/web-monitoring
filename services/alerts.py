"""
Alert Engine
Checks conditions and sends notifications
"""

from datetime import datetime
from typing import Dict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


class AlertEngine:
    def __init__(self, db_connection):
        self.db = db_connection
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.app_url = os.getenv("APP_URL", "http://localhost:8501")

    def check_all_alerts(self, project_id: int, new_articles_count: int):
        """
        Check all alert conditions for a project

        Args:
            project_id: Project ID
            new_articles_count: Number of new articles just scraped
        """
        self.check_spike_alerts(project_id, new_articles_count)
        self.check_sentiment_alerts(project_id)

    def check_spike_alerts(self, project_id: int, new_articles: int):
        """Check mention spike alerts"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT COUNT(*)::float / 7 as avg_daily
            FROM articles
            WHERE project_id = %s
            AND scraped_at >= NOW() - INTERVAL '7 days'
        """, (project_id,))

        result = cursor.fetchone()
        avg_daily = result['avg_daily'] if result else 0

        # Get active spike alerts
        cursor.execute("""
            SELECT * FROM alerts
            WHERE project_id = %s
            AND type = 'spike_detection'
            AND is_active = TRUE
        """, (project_id,))

        alerts = cursor.fetchall()

        for alert in alerts:
            threshold = alert['threshold']

            if new_articles > avg_daily * threshold:
                self._trigger_alert(
                    alert,
                    "Spike Menzioni Rilevato",
                    f"{new_articles} nuovi articoli (media storica: {avg_daily:.1f})",
                    project_id
                )

    def check_sentiment_alerts(self, project_id: int):
        """Check sentiment shift alerts"""
        cursor = self.db.cursor()

        # Recent sentiment (24h)
        cursor.execute("""
            SELECT AVG(sentiment_score) as avg_sentiment
            FROM articles
            WHERE project_id = %s
            AND scraped_at >= NOW() - INTERVAL '24 hours'
            AND sentiment_score IS NOT NULL
        """, (project_id,))

        recent = cursor.fetchone()
        recent_score = recent['avg_sentiment'] if recent and recent['avg_sentiment'] else None

        if recent_score is None:
            return

        # Historical sentiment (30 days)
        cursor.execute("""
            SELECT AVG(sentiment_score) as avg_sentiment
            FROM articles
            WHERE project_id = %s
            AND scraped_at >= NOW() - INTERVAL '30 days'
            AND scraped_at < NOW() - INTERVAL '24 hours'
            AND sentiment_score IS NOT NULL
        """, (project_id,))

        historical = cursor.fetchone()
        historical_score = historical['avg_sentiment'] if historical and historical['avg_sentiment'] else 0

        # Get active sentiment alerts
        cursor.execute("""
            SELECT * FROM alerts
            WHERE project_id = %s
            AND type = 'sentiment_shift'
            AND is_active = TRUE
        """, (project_id,))

        alerts = cursor.fetchall()

        for alert in alerts:
            threshold = alert['threshold']
            delta = abs(recent_score - historical_score)

            if delta > threshold:
                trend = "positivo" if recent_score > historical_score else "negativo"
                self._trigger_alert(
                    alert,
                    "Cambio Sentiment Rilevato",
                    f"Sentiment attuale: {recent_score:+.2f} (storico: {historical_score:+.2f})\nTrend: {trend}",
                    project_id
                )

    def _trigger_alert(self, alert: Dict, subject: str, message: str, project_id: int):
        """Send alert notification"""
        cursor = self.db.cursor()

        # Get project info
        cursor.execute("""
            SELECT name, brand FROM projects WHERE id = %s
        """, (project_id,))

        project = cursor.fetchone()

        # Build email
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
                <h2 style="color: #2c3e50; margin-top: 0;">{subject}</h2>

                <div style="background: white; padding: 20px; border-radius: 4px; margin: 20px 0;">
                    <p style="font-size: 16px; line-height: 1.6;">
                        <strong>Progetto:</strong> {project['name']}<br>
                        <strong>Brand:</strong> {project['brand']}<br>
                        <strong>Timestamp:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}
                    </p>

                    <div style="background: #e3f2fd; padding: 15px; border-left: 4px solid #2196f3; margin: 15px 0;">
                        <pre style="margin: 0; white-space: pre-wrap; font-family: Arial;">{message}</pre>
                    </div>
                </div>

                <div style="text-align: center; margin-top: 20px;">
                    <a href="{self.app_url}"
                       style="background: #2196f3; color: white; padding: 12px 30px;
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Vai alla Dashboard
                    </a>
                </div>

                <p style="color: #7f8c8d; font-size: 12px; margin-top: 20px;">
                    Questo e un alert automatico da Web Monitor.
                    <br>Puoi gestire gli alert dalla dashboard del progetto.
                </p>
            </div>
        </body>
        </html>
        """

        # Send to all recipients
        for email in alert['email_recipients']:
            self._send_email(
                email,
                f"[Web Monitor] {subject}",
                html
            )

        # Update alert record
        cursor.execute("""
            UPDATE alerts
            SET last_triggered = NOW(),
                trigger_count = trigger_count + 1
            WHERE id = %s
        """, (alert['id'],))

        self.db.commit()

    def _send_email(self, to: str, subject: str, html: str):
        """Send HTML email via SMTP"""
        if not self.smtp_user or not self.smtp_pass:
            print(f"SMTP not configured, skipping email to {to}")
            return

        msg = MIMEMultipart('alternative')
        msg['From'] = self.smtp_user
        msg['To'] = to
        msg['Subject'] = subject

        msg.attach(MIMEText(html, 'html', 'utf-8'))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            print(f"Email sent to {to}")

        except Exception as e:
            print(f"Email send failed to {to}: {e}")
