FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the Halifax Transit GTFS feed into the image at build time, so the image works
# without any local data. Docker caches this step: rebuild with --no-cache (or a different
# FEED_URL) to fetch a newer feed. The build fails if the download isn't a valid zip.
ARG FEED_URL=http://gtfs.halifax.ca/static/google_transit.zip
RUN mkdir -p data/raw && python -c "\
import sys, urllib.request, zipfile; \
urllib.request.urlretrieve(sys.argv[1], 'data/raw/halifax.zip'); \
assert zipfile.ZipFile('data/raw/halifax.zip').testzip() is None" "$FEED_URL"

COPY main.py .
COPY src/ src/
COPY config/ config/

# Create an unprivileged user and run the app as that user instead of root.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# Every 30s, call /health; mark the container unhealthy after 3 failures.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
