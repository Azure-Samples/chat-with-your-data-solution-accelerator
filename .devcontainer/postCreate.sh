#!/bin/bash

pip install --upgrade pip

pip install poetry

poetry install --with dev

poetry run pre-commit install

npm install ./code/frontend

npm install ./tests/integration/ui/
