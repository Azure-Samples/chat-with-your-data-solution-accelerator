FROM node:20-alpine AS frontend
RUN mkdir -p /home/node/app/node_modules && chown -R node:node /home/node/app
WORKDIR /home/node/app
COPY ./src/frontend/package*.json ./
USER node
RUN npm ci
COPY --chown=node:node ./src/frontend ./frontend
WORKDIR /home/node/app/frontend
RUN npm install --save-dev @types/node @types/jest
RUN npm run build

FROM python:3.11.7-bookworm
RUN apt-get update && apt-get install python3-tk tk-dev -y

COPY pyproject.toml /usr/src/app/pyproject.toml
COPY uv.lock /usr/src/app/uv.lock
WORKDIR /usr/src/app
RUN pip install --upgrade pip && pip install uv && uv export --no-hashes -o requirements.txt && pip install -r requirements.txt

COPY ./src/frontend/frontend_app.py /usr/src/app/src/frontend/frontend_app.py
COPY --from=frontend /home/node/app/dist/static /usr/src/app/dist/static/
ENV PYTHONPATH="${PYTHONPATH}:/usr/src/app"
ENV BACKEND_URL="http://backend:8000"
EXPOSE 80
CMD ["uvicorn", "src.frontend.frontend_app:app", "--host", "0.0.0.0", "--port", "80"]
