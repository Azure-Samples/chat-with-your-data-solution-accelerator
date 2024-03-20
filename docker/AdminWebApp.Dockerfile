FROM python:3.11.7-bookworm
RUN apt-get update && apt-get install python3-tk tk-dev -y
COPY pyproject.toml /usr/local/cwyd/pyproject.toml
COPY poetry.lock /usr/local/cwyd/poetry.lock
WORKDIR /usr/local/cwyd
RUN pip install --upgrade pip && pip install poetry && poetry install
COPY ./code/backend /usr/local/cwyd/admin
COPY ./code/backend/batch/utilities /usr/local/cwyd/utilities
WORKDIR /usr/local/src/cwyd/admin
ENV PYTHONPATH "${PYTHONPATH}:/usr/local/cwyd"
EXPOSE 80
CMD ["streamlit", "run", "Admin.py", "--server.port", "80", "--server.enableXsrfProtection", "false"]