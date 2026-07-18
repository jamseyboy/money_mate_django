# Use official Python runtime as base image
FROM python:3.11-slim

# Set environment variables
# PYTHONUNBUFFERED: ensures Python output is logged to container logs
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install system dependencies (including PostgreSQL client)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Copy project code
COPY . .

# Create a non-root user for running the app (security best practice)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Collect static files (if using Django static files)
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 8000

# Run Gunicorn server
CMD ["gunicorn", "money_mate_django.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60"]
