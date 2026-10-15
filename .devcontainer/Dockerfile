FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

# pip + npm resolve from the Microsoft mirrors so the default registries
# (which can be blocked) are never contacted.
ENV PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple \
    NPM_CONFIG_REGISTRY=https://pkgs.dev.azure.com/ms-feed-12/1es-public/_packaging/npm-public/npm/registry/

# Remove Yarn repository to avoid GPG key expiration issue
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Install git
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install uv (v2 replaces Poetry with uv for Python dependency management)
RUN pip install --no-cache-dir --upgrade pip uv
