mkdir dist -Force
rm dist/* -r -Force

# Python
poetry install
poetry export -o dist/requirements.txt
cp *.py dist -Force
cp backend dist -r -Force

# Node
cd frontend
npm install
VITE_ENV_DIR=$(dirname $(azd env list --output json | jq -r '.[] | select(.IsDefault == true) | .DotEnvPath')) npm run build
