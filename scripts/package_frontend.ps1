mkdir dist -Force
poetry export -o dist/requirements.txt
cp app.py dist -Force
cp backend dist -r -Force

cd frontend
npm install
npm run build