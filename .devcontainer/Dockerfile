FROM --platform=linux/amd64 mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

# install git
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends git