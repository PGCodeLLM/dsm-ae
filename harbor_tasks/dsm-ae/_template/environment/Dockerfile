# template Dockerfile
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive         PYTHONUNBUFFERED=1

WORKDIR /app

# Install dsm-ae from repo source (export script prepares pyproject + src in build context)
COPY pyproject.toml README.md /src/dsm-ae/
COPY src /src/dsm-ae/src
RUN pip install --no-cache-dir -e /src/dsm-ae

# Pack fixtures (CONTRACT_FILES) prepared by export script into the build context.
# These land in /app so that agent phase (per instruction.md) can read them via tools.
# Verifier also uses /app as work_root for score_workspace.
# ... fixtures added by exporter
