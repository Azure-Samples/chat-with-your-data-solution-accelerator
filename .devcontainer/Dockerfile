FROM --platform=linux/amd64 mcr.microsoft.com/devcontainers/python:1-3.11-bullseye
# We need to force the container to be amd so that it works on a Mac. Without this the functions extension doesn't install.

# install git
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends git