mkdir dist -Force
rm dist/* -r -Force

# Python
poetry export -o dist/requirements.txt
cp *.py dist -Force
cp backend dist -r -Force

# Node
cd frontend
npm install
npm run build
