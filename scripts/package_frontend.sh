#!/usr/bin/env bash
set -eou pipefail

mkdir -p dist
rm -rf dist/*
poetry install
cp *.py dist
cp -r backend dist
cp ../pyproject.toml dist
cp ../poetry.lock dist

cd frontend
npm install
npm run build
