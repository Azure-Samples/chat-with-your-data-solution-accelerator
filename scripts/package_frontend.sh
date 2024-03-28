#!/usr/bin/env bash
set -eou pipefail

mkdir -p dist
poetry export -o dist/requirements.txt
cp app.py dist
cp -r backend dist

cd frontend
npm install
npm run build
