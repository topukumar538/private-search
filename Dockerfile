FROM python:3.12-slim

# Don't write .pyc files, print logs immediately, keep the image small.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Install dependencies first, so this layer is reused when only code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy only the application code (never .env or tests).
COPY app ./app

# Run the app as a normal user, not root.
RUN useradd --create-home appuser
USER appuser

# Render sets $PORT; 7860 is the default for local runs.
# --no-access-log: uvicorn would otherwise log every visitor's IP address.
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860} --no-access-log"]