FROM python:3.12-slim AS base

WORKDIR /app

# Install deps first (better layer caching) via the pinned requirements
# file - identical dependency set to pyproject.toml's [project.dependencies].
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY pyproject.toml ./
COPY start.sh /start.sh
RUN chmod +x /start.sh

RUN useradd --create-home --uid 1000 pgplanadvisor \
    && mkdir -p /var/log/pgplanadvisor/backend /app/data \
    && chown -R pgplanadvisor:pgplanadvisor /var/log/pgplanadvisor /app
USER pgplanadvisor

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["/start.sh"]
