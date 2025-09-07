# Multi-stage build for Golden Plate Recorder
FROM node:18-alpine AS frontend-build

# Set working directory for frontend
WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy frontend source
COPY frontend/ ./

# Build frontend
RUN npm run build

# Python backend stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy backend source
COPY src/ ./src/

# Copy built frontend from previous stage
COPY --from=frontend-build /app/frontend/dist ./src/static

# Create data directory for SQLite database
RUN mkdir -p /app/data

# Set environment variables
ENV FLASK_ENV=production
ENV DATABASE_URL=sqlite:///data/golden_plate_recorder.db
ENV PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Run application with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "src.main:app"]

