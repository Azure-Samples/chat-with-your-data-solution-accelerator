#!/bin/bash

pip install --upgrade pip

pip install poetry

poetry install --with dev

poetry run pre-commit install

(cd ./code/frontend; npm install)

(cd ./tests/integration/ui; npm install)
