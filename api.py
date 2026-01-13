"""
FastAPI REST API
Backend API for Web Monitor v2
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
import os

from utils.db import get_db_connection
from services.gemini import GeminiAnalyzer
from worker import scrape_project

# Initialize FastAPI
app = FastAPI(
    title="Web Monitor v2 API",
    description="Brand/Media Listening System API",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Models
class ProjectCreate(BaseModel):
    name: str
    brand: str
    industry: Optional[str] = None
    market: str = "IT"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    industry: Optional[str] = None
    market: Optional[str] = None
    status: Optional[str] = None


class KeywordCreate(BaseModel):
    keyword: str
    is_ai_suggested: bool = False


class CompetitorCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    is_ai_suggested: bool = False


class AlertCreate(BaseModel):
    type: str
    threshold: float
    window_hours: int = 24
    email_recipients: List[str]


class SuggestionsRequest(BaseModel):
    brand: str
    industry: str
    market: str = "IT"


# Database dependency
def get_db():
    db = get_db_connection()
    try:
        yield db
    finally:
        db.close()


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Projects endpoints
@app.get("/api/projects")
async def list_projects(db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        SELECT p.*,
               (SELECT COUNT(*) FROM articles WHERE project_id = p.id) as article_count,
               (SELECT COUNT(*) FROM keywords WHERE project_id = p.id) as keyword_count
        FROM projects p
        ORDER BY p.created_at DESC
    """)
    projects = cursor.fetchall()
    return {"projects": projects}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/api/projects")
async def create_project(project: ProjectCreate, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO projects (name, brand, industry, market, created_by)
        VALUES (%s, %s, %s, %s, 1)
        RETURNING *
    """, (project.name, project.brand, project.industry, project.market))
    new_project = cursor.fetchone()

    # Create default schedule
    cursor.execute("""
        INSERT INTO schedules (project_id, frequency, next_run)
        VALUES (%s, 'daily', NOW() + INTERVAL '6 hours')
    """, (new_project['id'],))

    db.commit()
    return new_project


@app.put("/api/projects/{project_id}")
async def update_project(project_id: int, project: ProjectUpdate, db=Depends(get_db)):
    cursor = db.cursor()

    # Build update query dynamically
    updates = []
    values = []
    for field, value in project.dict(exclude_unset=True).items():
        if value is not None:
            updates.append(f"{field} = %s")
            values.append(value)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(project_id)
    cursor.execute(f"""
        UPDATE projects SET {', '.join(updates)}, updated_at = NOW()
        WHERE id = %s RETURNING *
    """, values)

    updated = cursor.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")

    db.commit()
    return updated


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM projects WHERE id = %s RETURNING id", (project_id,))
    deleted = cursor.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    db.commit()
    return {"message": "Project deleted", "id": project_id}


# Keywords endpoints
@app.get("/api/projects/{project_id}/keywords")
async def list_keywords(project_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM keywords WHERE project_id = %s ORDER BY keyword
    """, (project_id,))
    return {"keywords": cursor.fetchall()}


@app.post("/api/projects/{project_id}/keywords")
async def add_keyword(project_id: int, keyword: KeywordCreate, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO keywords (project_id, keyword, is_ai_suggested)
        VALUES (%s, %s, %s)
        ON CONFLICT (project_id, keyword) DO NOTHING
        RETURNING *
    """, (project_id, keyword.keyword, keyword.is_ai_suggested))
    new_keyword = cursor.fetchone()
    db.commit()
    return new_keyword


@app.delete("/api/keywords/{keyword_id}")
async def delete_keyword(keyword_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM keywords WHERE id = %s RETURNING id", (keyword_id,))
    deleted = cursor.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Keyword not found")
    db.commit()
    return {"message": "Keyword deleted", "id": keyword_id}


# Competitors endpoints
@app.get("/api/projects/{project_id}/competitors")
async def list_competitors(project_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM competitors WHERE project_id = %s ORDER BY name
    """, (project_id,))
    return {"competitors": cursor.fetchall()}


@app.post("/api/projects/{project_id}/competitors")
async def add_competitor(project_id: int, competitor: CompetitorCreate, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO competitors (project_id, name, domain, is_ai_suggested)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (project_id, name) DO NOTHING
        RETURNING *
    """, (project_id, competitor.name, competitor.domain, competitor.is_ai_suggested))
    new_competitor = cursor.fetchone()
    db.commit()
    return new_competitor


@app.delete("/api/competitors/{competitor_id}")
async def delete_competitor(competitor_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM competitors WHERE id = %s RETURNING id", (competitor_id,))
    deleted = cursor.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Competitor not found")
    db.commit()
    return {"message": "Competitor deleted", "id": competitor_id}


# Articles endpoints
@app.get("/api/projects/{project_id}/articles")
async def list_articles(
    project_id: int,
    sentiment: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db)
):
    cursor = db.cursor()

    query = """
        SELECT id, title, source, published_at, sentiment, sentiment_score,
               relevance_score, url, summary
        FROM articles
        WHERE project_id = %s
        AND scraped_at >= NOW() - INTERVAL '%s days'
    """
    params = [project_id, days]

    if sentiment:
        query += " AND sentiment = %s"
        params.append(sentiment)

    query += " ORDER BY published_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cursor.execute(query, params)
    articles = cursor.fetchall()

    # Get total count
    cursor.execute("""
        SELECT COUNT(*) as total FROM articles
        WHERE project_id = %s
        AND scraped_at >= NOW() - INTERVAL '%s days'
    """, (project_id, days))
    total = cursor.fetchone()['total']

    return {
        "articles": articles,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/projects/{project_id}/stats")
async def get_project_stats(project_id: int, days: int = 30, db=Depends(get_db)):
    cursor = db.cursor()

    # Article count by sentiment
    cursor.execute("""
        SELECT sentiment, COUNT(*) as count
        FROM articles
        WHERE project_id = %s
        AND scraped_at >= NOW() - INTERVAL '%s days'
        GROUP BY sentiment
    """, (project_id, days))
    sentiment_stats = cursor.fetchall()

    # Average sentiment score
    cursor.execute("""
        SELECT AVG(sentiment_score) as avg_sentiment
        FROM articles
        WHERE project_id = %s
        AND scraped_at >= NOW() - INTERVAL '%s days'
        AND sentiment_score IS NOT NULL
    """, (project_id, days))
    avg_sentiment = cursor.fetchone()['avg_sentiment'] or 0

    # Top sources
    cursor.execute("""
        SELECT source, COUNT(*) as count
        FROM articles
        WHERE project_id = %s
        AND scraped_at >= NOW() - INTERVAL '%s days'
        GROUP BY source
        ORDER BY count DESC
        LIMIT 10
    """, (project_id, days))
    top_sources = cursor.fetchall()

    # Daily counts
    cursor.execute("""
        SELECT DATE(scraped_at) as date, COUNT(*) as count
        FROM articles
        WHERE project_id = %s
        AND scraped_at >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(scraped_at)
        ORDER BY date
    """, (project_id, days))
    daily_counts = cursor.fetchall()

    return {
        "sentiment_distribution": sentiment_stats,
        "average_sentiment": avg_sentiment,
        "top_sources": top_sources,
        "daily_counts": daily_counts
    }


# Alerts endpoints
@app.get("/api/projects/{project_id}/alerts")
async def list_alerts(project_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM alerts WHERE project_id = %s ORDER BY created_at DESC
    """, (project_id,))
    return {"alerts": cursor.fetchall()}


@app.post("/api/projects/{project_id}/alerts")
async def create_alert(project_id: int, alert: AlertCreate, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO alerts (project_id, type, threshold, window_hours, email_recipients)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
    """, (project_id, alert.type, alert.threshold, alert.window_hours, alert.email_recipients))
    new_alert = cursor.fetchone()
    db.commit()
    return new_alert


@app.put("/api/alerts/{alert_id}/toggle")
async def toggle_alert(alert_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        UPDATE alerts SET is_active = NOT is_active WHERE id = %s RETURNING *
    """, (alert_id,))
    updated = cursor.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.commit()
    return updated


@app.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM alerts WHERE id = %s RETURNING id", (alert_id,))
    deleted = cursor.fetchone()
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.commit()
    return {"message": "Alert deleted", "id": alert_id}


# Scraping endpoints
@app.post("/api/projects/{project_id}/scrape")
async def trigger_scraping(project_id: int, db=Depends(get_db)):
    # Verify project exists
    cursor = db.cursor()
    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Project not found")

    # Trigger Celery task
    task = scrape_project.delay(project_id)

    return {
        "message": "Scraping task queued",
        "task_id": task.id,
        "project_id": project_id
    }


@app.get("/api/projects/{project_id}/jobs")
async def list_scraping_jobs(project_id: int, limit: int = 10, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
        SELECT * FROM scraping_jobs
        WHERE project_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (project_id, limit))
    return {"jobs": cursor.fetchall()}


# AI Suggestions endpoint
@app.post("/api/suggestions")
async def get_suggestions(request: SuggestionsRequest):
    try:
        gemini = GeminiAnalyzer()
        suggestions = gemini.suggest_competitors_keywords(
            request.brand,
            request.industry,
            request.market
        )
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
