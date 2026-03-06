# ---- build stage ----
FROM python:3.11-slim AS build

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- runtime stage ----
FROM python:3.11-slim

# aria2c for fast multi-connection downloads
RUN apt-get update && apt-get install -y --no-install-recommends \
        aria2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from build stage
COPY --from=build /install /usr/local

# Copy application source
COPY game_scraper/ game_scraper/
COPY setup.py .

RUN pip install --no-cache-dir --no-deps -e .

# Use keyrings.alt (file-based) as the keyring backend — no desktop daemon needed.
ENV PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring

# Config and data live in a named volume mounted here
ENV XDG_CONFIG_HOME=/data/config
ENV XDG_DATA_HOME=/data/local

# Downloaded games go here — users should bind-mount a host directory
VOLUME ["/downloads"]
ENV GAME_SCRAPER_DOWNLOAD_DIR=/downloads

# Non-root user for safety
RUN useradd -m scraper
RUN mkdir -p /data && chown -R scraper:scraper /data /downloads
USER scraper

ENTRYPOINT ["game-scraper"]
CMD ["--help"]
