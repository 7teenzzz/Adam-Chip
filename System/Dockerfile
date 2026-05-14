FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADAM_CONFIG=/app/System/Config.json \
    PYTHONPATH=/app/System

WORKDIR /app

COPY System/requirements.txt /app/System/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/System/requirements.txt

COPY System /app/System
COPY ["Agent Adam Chip", "/app/Agent Adam Chip/"]
COPY README.md /app/README.md

EXPOSE 8080
CMD ["python", "System/Orchestrator.py"]
