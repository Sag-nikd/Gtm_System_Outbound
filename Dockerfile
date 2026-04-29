FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cached separately from source)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Runtime defaults — override via docker run -e or docker-compose env
ENV PYTHONUNBUFFERED=1 \
    MOCK_MODE=true \
    STORAGE_ENABLED=false \
    LOG_LEVEL=INFO

CMD ["python", "src/main.py"]
