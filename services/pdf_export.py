"""
PDF Report Generator
Creates formatted PDF reports
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
from typing import List, Dict
import io


class PDFExporter:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#34495e'),
            spaceBefore=20,
            spaceAfter=12,
            borderPadding=5,
            borderColor=colors.HexColor('#3498db'),
            borderWidth=1
        ))

    def generate_report(
        self,
        project: Dict,
        articles: List[Dict],
        period_days: int = 30
    ) -> bytes:
        """
        Generate PDF report

        Args:
            project: Project dict
            articles: List of articles
            period_days: Report period

        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        story = []

        # Title page
        story.append(Paragraph(
            "Report di Monitoraggio",
            self.styles['CustomTitle']
        ))
        story.append(Paragraph(
            f"{project['name']}",
            self.styles['Heading2']
        ))
        story.append(Spacer(1, 1*cm))

        # Project info
        info_data = [
            ['Brand:', project['brand']],
            ['Settore:', project.get('industry', 'N/A')],
            ['Mercato:', project.get('market', 'IT')],
            ['Periodo:', f"Ultimi {period_days} giorni"],
            ['Data Report:', datetime.now().strftime('%d/%m/%Y')],
            ['Articoli Totali:', str(len(articles))]
        ]

        info_table = Table(info_data, colWidths=[4*cm, 10*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#34495e')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#ecf0f1')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(info_table)
        story.append(Spacer(1, 1*cm))

        # Sentiment distribution
        story.append(Paragraph("Distribuzione Sentiment", self.styles['SectionHeader']))

        sentiment_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        for a in articles:
            sentiment = a.get('sentiment', 'neutral')
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

        total = len(articles)
        sentiment_data = [
            ['Sentiment', 'Conteggio', 'Percentuale']
        ]

        for sentiment, count in sentiment_counts.items():
            pct = (count / total * 100) if total > 0 else 0
            sentiment_data.append([
                sentiment.capitalize(),
                str(count),
                f"{pct:.1f}%"
            ])

        sentiment_table = Table(sentiment_data, colWidths=[5*cm, 4*cm, 4*cm])
        sentiment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')])
        ]))

        story.append(sentiment_table)
        story.append(Spacer(1, 1*cm))

        # Top articles
        story.append(PageBreak())
        story.append(Paragraph("Top Articoli per Rilevanza", self.styles['SectionHeader']))
        story.append(Spacer(1, 0.5*cm))

        # Sort by relevance
        sorted_articles = sorted(
            articles,
            key=lambda x: x.get('relevance_score', 0),
            reverse=True
        )[:15]

        for i, article in enumerate(sorted_articles, 1):
            # Article header
            title_text = f"<b>{i}. {article.get('title', 'No title')}</b>"
            story.append(Paragraph(title_text, self.styles['Normal']))

            # Metadata
            meta_text = f"""
            <i>Fonte: {article.get('source', 'N/A')} |
            Data: {article.get('published_at', 'N/A')}</i><br/>
            <b>Sentiment:</b> {article.get('sentiment', 'N/A').capitalize()} ({article.get('sentiment_score', 0):+.2f}) |
            <b>Rilevanza:</b> {article.get('relevance_score', 0):.0f}/100
            """
            story.append(Paragraph(meta_text, self.styles['Normal']))

            # Summary
            summary = article.get('summary', article.get('snippet', 'No summary'))[:300]
            story.append(Paragraph(summary, self.styles['Normal']))

            # URL
            url = article.get("url", "#")
            url_text = f'<a href="{url}" color="blue">{url}</a>'
            story.append(Paragraph(url_text, self.styles['Normal']))

            story.append(Spacer(1, 0.7*cm))

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
