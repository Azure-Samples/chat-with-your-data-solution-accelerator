#!/bin/bash

pip install --upgrade pip

pip install poetry

poetry install --with dev

poetry run pre-commit install

sudo apt-get update

sudo apt-get install libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libnss3 libxss1 libasound2 libxtst6 xauth xvfb