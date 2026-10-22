FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY src/ src/
COPY config/ config/
COPY static/ static/

# Pre-computed block distances and durations, built locally with scripts/build_summaries.py
# and committed to git. The image holds no raw GTFS feed: every tool answers from this file,
# and its stamp records exactly which feed and code produced it.
COPY data/summaries/ data/summaries/

# Public-sources index (built locally with scripts/build_source_index.py, committed), and the
# small embedding model it needs to embed questions, downloaded once here at build time. At
# run time the app works offline: HF_HUB_OFFLINE stops any attempt to fetch the model again.
COPY data/index/ data/index/
ENV MODEL_DIR=data/models HF_HUB_DISABLE_TELEMETRY=1
RUN python -c "from src.sources import embedder; embedder()" && chmod -R a+rX data/models
ENV HF_HUB_OFFLINE=1

# Create an unprivileged user and run the app as that user instead of root.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Every 30s, call /health; mark the container unhealthy after 3 failures.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
