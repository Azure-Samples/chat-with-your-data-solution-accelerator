FROM node:20-alpine AS frontend  
RUN mkdir -p /home/node/app/node_modules && chown -R node:node /home/node/app
WORKDIR /home/node/app 
COPY ./code/frontend/package*.json ./  
USER node
RUN npm ci  
COPY --chown=node:node ./code/frontend ./frontend 
WORKDIR /home/node/app/frontend
RUN npm run build
  
FROM python:3.11.7-bookworm
RUN apt-get update && apt-get install python3-tk tk-dev -y

COPY pyproject.toml /usr/local/cwyd/pyproject.toml
COPY poetry.lock /usr/local/cwyd/poetry.lock
WORKDIR /usr/local/cwyd
RUN pip install --upgrade pip && pip install poetry uwsgi && poetry export -o requirements.txt && pip install -r requirements.txt
 
COPY ./code/app.py /usr/local/cwyd/
COPY ./code/backend/batch/utilities /usr/local/cwyd/utilities
COPY --from=frontend /home/node/app/static  /usr/local/cwyd/static/
WORKDIR /usr/local/cwyd
EXPOSE 80  
CMD ["uwsgi", "--http", ":80", "--wsgi-file", "app.py", "--callable", "app", "-b","32768"]  