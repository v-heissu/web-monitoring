"""
SQLAlchemy ORM Models
Database models for Web Monitor v2
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, ARRAY, JSON, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import os

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255))
    role = Column(String(50), default='user')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    projects = relationship("Project", back_populates="creator")


class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=False)
    industry = Column(String(255))
    market = Column(String(10), default='IT')
    status = Column(String(50), default='active')
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    creator = relationship("User", back_populates="projects")
    keywords = relationship("Keyword", back_populates="project", cascade="all, delete-orphan")
    competitors = relationship("Competitor", back_populates="project", cascade="all, delete-orphan")
    articles = relationship("Article", back_populates="project", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="project", cascade="all, delete-orphan")
    schedule = relationship("Schedule", back_populates="project", uselist=False, cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = 'keywords'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    keyword = Column(String(255), nullable=False)
    is_ai_suggested = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="keywords")


class Competitor(Base):
    __tablename__ = 'competitors'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    domain = Column(String(255))
    is_ai_suggested = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="competitors")


class Article(Base):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    url = Column(Text, unique=True, nullable=False)
    title = Column(Text)
    source = Column(String(255))
    published_at = Column(DateTime(timezone=True))
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    # Content
    snippet = Column(Text)
    content = Column(Text)
    summary = Column(Text)

    # AI Analysis
    sentiment = Column(String(50))
    sentiment_score = Column(Float)
    topics = Column(JSON)
    entities = Column(JSON)

    # Metadata
    query_source = Column(String(255))
    relevance_score = Column(Float, default=0)

    # Relationships
    project = relationship("Project", back_populates="articles")


class Alert(Base):
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    type = Column(String(100), nullable=False)

    # Configuration
    threshold = Column(Float, nullable=False)
    window_hours = Column(Integer, default=24)
    email_recipients = Column(ARRAY(Text), nullable=False)

    # Status
    is_active = Column(Boolean, default=True)
    last_triggered = Column(DateTime(timezone=True))
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="alerts")


class ScrapingJob(Base):
    __tablename__ = 'scraping_jobs'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='SET NULL'))
    status = Column(String(50), nullable=False)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Metrics
    articles_found = Column(Integer, default=0)
    new_articles = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text)
    celery_task_id = Column(String(255))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Schedule(Base):
    __tablename__ = 'schedules'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, unique=True)
    frequency = Column(String(50), default='daily')
    last_run = Column(DateTime(timezone=True))
    next_run = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    # Relationships
    project = relationship("Project", back_populates="schedule")


class APILog(Base):
    __tablename__ = 'api_logs'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='SET NULL'))
    api_name = Column(String(100))
    endpoint = Column(String(255))
    status_code = Column(Integer)
    response_time = Column(Float)
    cost_usd = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


def get_engine():
    """Get SQLAlchemy engine from DATABASE_URL"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not configured")

    # Handle Railway's postgres:// vs postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    return create_engine(database_url)


def get_session():
    """Get SQLAlchemy session"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def create_tables():
    """Create all tables"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("Tables created successfully")


if __name__ == '__main__':
    create_tables()
