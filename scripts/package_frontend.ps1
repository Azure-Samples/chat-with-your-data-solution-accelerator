mkdir dist -Force
rm dist/* -r -Force

# Python
poetry install
cp *.py dist -Force
cp backend dist -r -Force
cp ../pyproject.toml dist -Force
cp ../poetry.lock dist -Force

# Node
cd frontend
npm install
npm run build
