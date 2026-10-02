FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Updated to 1 worker to prevent duplicate logs/race conditions
CMD gunicorn --workers 1 --bind 0.0.0.0:$PORT evm_app:app
