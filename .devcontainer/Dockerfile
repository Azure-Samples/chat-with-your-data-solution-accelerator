FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

# Remove Yarn repository to avoid GPG key expiration issue
RUN rm -f /etc/apt/sources.list.d/yarn.list

# install git
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends git libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libnss3 libxss1 libasound2 libxtst6 xauth xvfb
