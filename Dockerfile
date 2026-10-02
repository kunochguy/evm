# Use a lightweight Python base image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer issues
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy ONLY the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Bind Gunicorn to the dynamic port assigned by the hosting provider
CMD gunicorn --workers 1 --bind 0.0.0.0:$PORT evm_app:app
