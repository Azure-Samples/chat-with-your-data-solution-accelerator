#!/bin/bash

pip install --upgrade pip

pip install poetry

# https://pypi.org/project/poetry-plugin-export/
pip install poetry-plugin-export
poetry config warnings.export false

poetry install --with dev

poetry run pre-commit install

(cd ./code/frontend; npm install)

(cd ./tests/integration/ui; npm install)
