web: gunicorn --chdir ./server app:app --bind 0.0.0.0:$PORT --timeout 120
postdeploy: alembic upgrade head
