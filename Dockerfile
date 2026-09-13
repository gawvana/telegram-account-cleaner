# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root user for security
RUN groupadd -g 1000 cleaner && \
    useradd -u 1000 -g cleaner -s /bin/bash -m cleaner && \
    mkdir -p /app/sessions /app/webapp/static && \
    chown -R cleaner:cleaner /app

COPY --from=builder /root/.local /home/cleaner/.local
COPY --chown=cleaner:cleaner . .

ENV PATH=/home/cleaner/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER cleaner

EXPOSE 8080

CMD ["python", "main.py"]
