# Reference base image for DotSci runners (Python).
#
# BASE_IMAGE is required and should be pinned by digest, for example:
#   python:3.11-slim@sha256:<digest>
# Get the digest with: docker buildx imagetools inspect python:3.11-slim
#
# This image installs nothing. Per-claim images extend it and install pinned
# dependencies at build time, because the sandbox has no network at run time.
# See claim.Dockerfile.example.

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# A real passwd entry for the runtime user avoids surprises in libraries that look it up.
RUN groupadd --gid 10001 runner \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

WORKDIR /work
USER 10001:10001
