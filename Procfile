web: gunicorn run:app --workers 2 --bind 0.0.0.0:$PORT --timeout 30
worker: celery -A celery_worker.celery worker --loglevel=info
beat: celery -A celery_worker.celery beat --loglevel=info
