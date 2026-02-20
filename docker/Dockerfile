# TCG Automation Docker Image
FROM python:3.11-slim

LABEL maintainer="joshleyva816@gmail.com"
LABEL description="Pokemon TCG automation for Odoo ERP"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install package
RUN pip install --no-cache-dir -e .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default command (can be overridden)
ENTRYPOINT ["tcg"]
CMD ["--help"]

# Expose port for web server
EXPOSE 5000
