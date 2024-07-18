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
npm run build
