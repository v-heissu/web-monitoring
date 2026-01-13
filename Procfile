web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
worker: celery -A worker worker --loglevel=info --concurrency=4
beat: celery -A worker beat --loglevel=info
