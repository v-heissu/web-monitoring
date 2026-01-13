"""
Celery Worker
Handles async scraping tasks and scheduling
"""

from celery import Celery
from celery.schedules import crontab
from services.dataforseo import DataForSEOClient
from services.gemini import GeminiAnalyzer
from services.alerts import AlertEngine
from utils.db import get_db_connection
from datetime import datetime
import os
import json

# Initialize Celery
celery_app = Celery(
    'web_monitor',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0')
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Rome',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # 50 minutes soft limit
)

# Schedule configuration
celery_app.conf.beat_schedule = {
    'scrape-all-projects-6h': {
        'task': 'worker.scrape_all_active_projects',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def scrape_project(self, project_id: int):
    """
    Scrape single project

    Args:
        project_id: Project ID to scrape

    Returns:
        {'success': bool, 'new_articles': int, 'total_found': int}
    """
    db = get_db_connection()
    cursor = db.cursor()
    job_id = None

    try:
        # Create job record
        cursor.execute("""
            INSERT INTO scraping_jobs (
                project_id, status, started_at, celery_task_id
            ) VALUES (%s, 'running', NOW(), %s)
            RETURNING id
        """, (project_id, self.request.id))

        job_id = cursor.fetchone()['id']
        db.commit()

        # Get project config
        cursor.execute("""
            SELECT * FROM projects WHERE id = %s AND status = 'active'
        """, (project_id,))

        project = cursor.fetchone()
        if not project:
            raise ValueError(f"Project {project_id} not found or inactive")

        # Get keywords
        cursor.execute("""
            SELECT keyword FROM keywords WHERE project_id = %s
        """, (project_id,))
        keywords = [row['keyword'] for row in cursor.fetchall()]

        # Get competitors
        cursor.execute("""
            SELECT name FROM competitors WHERE project_id = %s
        """, (project_id,))
        competitors = [row['name'] for row in cursor.fetchall()]

        # Combine all search terms
        all_terms = [project['brand']] + keywords + competitors

        if not all_terms:
            raise ValueError("No search terms configured for project")

        # Initialize services
        dataforseo = DataForSEOClient()
        gemini = GeminiAnalyzer()

        # Scrape news
        print(f"[{project_id}] Scraping {len(all_terms)} terms...")
        scrape_result = dataforseo.search_news(
            keywords=all_terms,
            market=project['market'],
            days_back=7,
            max_results=100
        )

        if not scrape_result['success']:
            raise Exception(f"DataForSEO error: {scrape_result.get('error')}")

        articles = scrape_result['articles']
        print(f"[{project_id}] Found {len(articles)} articles")

        if not articles:
            # No new articles, mark as completed
            cursor.execute("""
                UPDATE scraping_jobs
                SET status = 'completed',
                    completed_at = NOW(),
                    articles_found = 0,
                    new_articles = 0,
                    api_calls = %s
                WHERE id = %s
            """, (scrape_result['api_calls'], job_id))
            db.commit()

            return {
                'success': True,
                'new_articles': 0,
                'total_found': 0
            }

        # AI Analysis (batch)
        print(f"[{project_id}] Analyzing with Gemini...")
        analyzed = gemini.batch_analyze_articles(
            articles,
            project['brand']
        )

        # Save articles
        new_articles = 0
        for article in analyzed:
            try:
                cursor.execute("""
                    INSERT INTO articles (
                        project_id, url, title, source, published_at,
                        snippet, summary, sentiment, sentiment_score,
                        topics, entities, relevance_score, query_source
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (url) DO NOTHING
                """, (
                    project_id,
                    article['url'],
                    article.get('title'),
                    article.get('source'),
                    article.get('published_at'),
                    article.get('snippet'),
                    article.get('summary'),
                    article.get('sentiment'),
                    article.get('sentiment_score'),
                    json.dumps(article.get('topics', [])),
                    json.dumps(article.get('entities', {})),
                    article.get('relevance_score'),
                    article.get('query_source')
                ))

                if cursor.rowcount > 0:
                    new_articles += 1

            except Exception as e:
                print(f"Error saving article: {e}")
                continue

        db.commit()
        print(f"[{project_id}] Saved {new_articles} new articles")

        # Log API usage
        cursor.execute("""
            INSERT INTO api_logs (
                project_id, api_name, endpoint, status_code,
                cost_usd
            ) VALUES (%s, 'dataforseo', 'news', 200, %s)
        """, (project_id, scrape_result['cost_usd']))

        # Update job
        cursor.execute("""
            UPDATE scraping_jobs
            SET status = 'completed',
                completed_at = NOW(),
                articles_found = %s,
                new_articles = %s,
                api_calls = %s
            WHERE id = %s
        """, (len(articles), new_articles, scrape_result['api_calls'], job_id))

        # Update schedule
        cursor.execute("""
            UPDATE schedules
            SET last_run = NOW(),
                next_run = NOW() + INTERVAL '6 hours'
            WHERE project_id = %s
        """, (project_id,))

        db.commit()

        # Check alerts
        if new_articles > 0:
            print(f"[{project_id}] Checking alerts...")
            alert_engine = AlertEngine(db)
            alert_engine.check_all_alerts(project_id, new_articles)

        return {
            'success': True,
            'new_articles': new_articles,
            'total_found': len(articles)
        }

    except Exception as exc:
        # Log error
        if job_id:
            try:
                cursor.execute("""
                    UPDATE scraping_jobs
                    SET status = 'failed',
                        completed_at = NOW(),
                        error_message = %s
                    WHERE id = %s
                """, (str(exc), job_id))
                db.commit()
            except Exception:
                pass

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=300)

    finally:
        cursor.close()
        db.close()


@celery_app.task
def scrape_all_active_projects():
    """
    Scheduled task: scrape all active projects
    Triggered by Celery Beat every 6 hours
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT id, name FROM projects
            WHERE status = 'active'
        """)

        projects = cursor.fetchall()

        print(f"Scheduling scraping for {len(projects)} projects...")

        for project in projects:
            project_id = project['id']
            name = project['name']
            scrape_project.delay(project_id)
            print(f"Queued: {name} (ID: {project_id})")

        return {
            'success': True,
            'projects_scheduled': len(projects),
            'timestamp': datetime.now().isoformat()
        }

    finally:
        cursor.close()
        db.close()


@celery_app.task
def test_task():
    """Test task for debugging"""
    return {
        'status': 'ok',
        'message': 'Celery is working!',
        'timestamp': datetime.now().isoformat()
    }
