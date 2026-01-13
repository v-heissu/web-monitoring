"""
Database connection utilities
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from urllib.parse import urlparse


def get_db_connection():
    """
    Get PostgreSQL connection

    Returns:
        psycopg2 connection with RealDictCursor
    """
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        raise ValueError("DATABASE_URL not configured")

    # Parse Railway's DATABASE_URL format
    url = urlparse(database_url)

    conn = psycopg2.connect(
        host=url.hostname,
        port=url.port,
        user=url.username,
        password=url.password,
        database=url.path[1:],  # Remove leading /
        cursor_factory=RealDictCursor
    )

    return conn


def init_database():
    """
    Initialize database schema
    Run this once after deployment
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Read schema file
    with open('migrations/init_db.sql', 'r') as f:
        schema_sql = f.read()

    cursor.execute(schema_sql)
    conn.commit()

    cursor.close()
    conn.close()

    print("Database initialized successfully")


if __name__ == '__main__':
    init_database()
