FROM python:3.12-slim

# Avoid bytecode files in the image and flush structured logs directly to container output.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
# Install pinned major-version ranges before copying source for better layer caching.
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py constants.py ./
COPY e2e ./e2e
COPY docs ./docs

EXPOSE 8000
# Use the root-level FastAPI instance; Uvicorn access logs are replaced by correlation logs.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
