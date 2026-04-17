FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY telegram_bot/ ./telegram_bot/

# Set environment variables
ENV PYTHONPATH=/app
ENV BOT_TOKEN=""
ENV ADMIN_IDS=""

# Run bot
CMD ["python", "-m", "telegram_bot.main"]