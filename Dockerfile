FROM python:3.12-slim

# Don't write .pyc files, and print logs immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Run as a normal user, not root (Hugging Face uses UID 1000).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

# Install dependencies first, so this layer is reused when only code changes.
COPY --chown=user requirements.txt .
RUN pip install --user -r requirements.txt

# Copy only the application code.
COPY --chown=user app ./app

# Hosts like Render choose the port through $PORT; 7860 is the default
# that Hugging Face Spaces and local runs use.
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]