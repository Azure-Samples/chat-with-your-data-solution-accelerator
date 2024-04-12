#!/usr/bin/env bash
set -eou pipefail

mkdir -p dist
rm -rf dist/*
poetry install
poetry export -o dist/requirements.txt
cp *.py dist
cp -r backend dist


cd frontend
npm install
VITE_ENV_DIR=$(dirname $(azd env list --output json | jq -r '.[] | select(.IsDefault == true) | .DotEnvPath')) npm run build
