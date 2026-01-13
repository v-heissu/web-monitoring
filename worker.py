"""
Celery Worker
Handles async scraping tasks and scheduling
With proper logging for Railway
"""

from celery import Celery
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from datetime import datetime
import os
import json
import logging
import sys

# Configure logging to stdout for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('worker')

# Get Redis URL
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
logger.info(f"Celery broker: {REDIS_URL[:30]}...")

# Initialize Celery with explicit task naming
celery_app = Celery(
    'worker',
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Rome',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_log_format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    worker_task_log_format='%(asctime)s [%(levelname)s] %(task_name)s[%(task_id)s]: %(message)s',
)

# Schedule configuration
celery_app.conf.beat_schedule = {
    'scrape-all-projects-6h': {
        'task': 'worker.scrape_all_active_projects',
        'schedule': crontab(minute=0, hour='*/6'),
    },
}

# Task logger
task_logger = get_task_logger(__name__)


def log(msg, level='info'):
    """Helper to log to both logger and print (for Railway)"""
    getattr(logger, level)(msg)
    print(f"[{level.upper()}] {msg}", flush=True)


@celery_app.task(bind=True, name='worker.scrape_project', max_retries=3, default_retry_delay=300)
def scrape_project(self, project_id: int):
    """
    Scrape single project with full logging
    """
    log(f"=== SCRAPE START === Project ID: {project_id}, Task ID: {self.request.id}")

    # Late imports to avoid issues at module load
    from utils.db import get_db_connection

    db = None
    cursor = None
    job_id = None

    try:
        # Connect to database
        db = get_db_connection()
        cursor = db.cursor()
        log(f"[{project_id}] Database connected")

        # Create job record
        cursor.execute("""
            INSERT INTO scraping_jobs (
                project_id, status, started_at, celery_task_id
            ) VALUES (%s, 'running', NOW(), %s)
            RETURNING id
        """, (project_id, self.request.id))

        job_id = cursor.fetchone()['id']
        db.commit()
        log(f"[{project_id}] Job record created: {job_id}")

        # Get project config
        cursor.execute("""
            SELECT * FROM projects WHERE id = %s AND status = 'active'
        """, (project_id,))

        project = cursor.fetchone()
        if not project:
            raise ValueError(f"Project {project_id} not found or inactive")

        log(f"[{project_id}] Project: {project['name']} | Brand: {project['brand']} | Market: {project['market']}")

        # Get keywords
        cursor.execute("SELECT keyword FROM keywords WHERE project_id = %s", (project_id,))
        keywords = [row['keyword'] for row in cursor.fetchall()]
        log(f"[{project_id}] Keywords: {keywords}")

        # Get competitors
        cursor.execute("SELECT name FROM competitors WHERE project_id = %s", (project_id,))
        competitors = [row['name'] for row in cursor.fetchall()]
        log(f"[{project_id}] Competitors: {competitors}")

        # Combine all search terms
        all_terms = [project['brand']] + keywords + competitors
        log(f"[{project_id}] Total search terms: {len(all_terms)}")

        if not all_terms:
            raise ValueError("No search terms configured for project")

        # Check DataForSEO credentials BEFORE initializing
        dataforseo_login = os.getenv("DATAFORSEO_LOGIN")
        dataforseo_pass = os.getenv("DATAFORSEO_PASSWORD")

        if not dataforseo_login or not dataforseo_pass:
            log(f"[{project_id}] ERROR: DataForSEO credentials not configured!", 'error')
            log(f"[{project_id}] Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables", 'error')
            raise ValueError("DataForSEO credentials not configured")

        log(f"[{project_id}] DataForSEO credentials found: {dataforseo_login[:3]}***")

        # Initialize DataForSEO (late import)
        from services.dataforseo import DataForSEOClient
        dataforseo = DataForSEOClient()
        log(f"[{project_id}] DataForSEO client initialized")

        # Scrape news
        log(f"[{project_id}] Calling DataForSEO API...")
        scrape_result = dataforseo.search_news(
            keywords=all_terms,
            market=project['market'],
            days_back=7,
            max_results=100
        )

        if not scrape_result['success']:
            error_msg = scrape_result.get('error', 'Unknown error')
            log(f"[{project_id}] DataForSEO API error: {error_msg}", 'error')
            raise Exception(f"DataForSEO error: {error_msg}")

        articles = scrape_result['articles']
        log(f"[{project_id}] DataForSEO returned {len(articles)} articles")

        if not articles:
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
            log(f"[{project_id}] No articles found - job completed")

            return {
                'success': True,
                'new_articles': 0,
                'total_found': 0,
                'job_id': job_id
            }

        # Check Gemini credentials
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            log(f"[{project_id}] WARNING: GEMINI_API_KEY not set - skipping AI analysis", 'warning')
            # Provide default analysis
            analyzed = []
            for a in articles:
                analyzed.append({
                    **a,
                    'sentiment': 'neutral',
                    'sentiment_score': 0.0,
                    'topics': [],
                    'entities': {},
                    'summary': (a.get('snippet') or '')[:200],
                    'relevance_score': 50.0
                })
        else:
            log(f"[{project_id}] Gemini API key found, starting AI analysis...")
            from services.gemini import GeminiAnalyzer
            gemini = GeminiAnalyzer()
            analyzed = gemini.batch_analyze_articles(articles, project['brand'])
            log(f"[{project_id}] Gemini analysis completed for {len(analyzed)} articles")

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
                log(f"[{project_id}] Error saving article: {e}", 'error')
                continue

        db.commit()
        log(f"[{project_id}] Saved {new_articles} NEW articles (duplicates skipped)")

        # Log API usage
        cursor.execute("""
            INSERT INTO api_logs (
                project_id, api_name, endpoint, status_code, cost_usd
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
            try:
                from services.alerts import AlertEngine
                log(f"[{project_id}] Checking alerts...")
                alert_engine = AlertEngine(db)
                alert_engine.check_all_alerts(project_id, new_articles)
            except Exception as e:
                log(f"[{project_id}] Alert check error (non-fatal): {e}", 'warning')

        log(f"=== SCRAPE COMPLETE === Project {project_id}: {new_articles} new / {len(articles)} total")

        return {
            'success': True,
            'new_articles': new_articles,
            'total_found': len(articles),
            'job_id': job_id
        }

    except Exception as exc:
        log(f"=== SCRAPE FAILED === Project {project_id}: {str(exc)}", 'error')

        # Log error to DB
        if job_id and cursor:
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
        if cursor:
            cursor.close()
        if db:
            db.close()


@celery_app.task(name='worker.scrape_all_active_projects')
def scrape_all_active_projects():
    """
    Scheduled task: scrape all active projects
    """
    log("=== SCHEDULED SCRAPE START === Scraping all active projects")

    from utils.db import get_db_connection

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT id, name FROM projects WHERE status = 'active'
        """)

        projects = cursor.fetchall()
        log(f"Found {len(projects)} active projects to scrape")

        for project in projects:
            project_id = project['id']
            name = project['name']
            scrape_project.delay(project_id)
            log(f"Queued: {name} (ID: {project_id})")

        log(f"=== SCHEDULED SCRAPE QUEUED === {len(projects)} projects")

        return {
            'success': True,
            'projects_scheduled': len(projects),
            'timestamp': datetime.now().isoformat()
        }

    finally:
        cursor.close()
        db.close()


@celery_app.task(name='worker.test_task')
def test_task():
    """Test task for debugging - verifies Celery is working"""
    log("=== TEST TASK EXECUTED ===")

    # Check environment
    env_check = {
        'REDIS_URL': bool(os.getenv('REDIS_URL')),
        'DATABASE_URL': bool(os.getenv('DATABASE_URL')),
        'DATAFORSEO_LOGIN': bool(os.getenv('DATAFORSEO_LOGIN')),
        'DATAFORSEO_PASSWORD': bool(os.getenv('DATAFORSEO_PASSWORD')),
        'GEMINI_API_KEY': bool(os.getenv('GEMINI_API_KEY')),
    }

    log(f"Environment check: {env_check}")

    return {
        'status': 'ok',
        'message': 'Celery is working!',
        'timestamp': datetime.now().isoformat(),
        'environment': env_check
    }


# Startup log
log("Worker module loaded successfully")
