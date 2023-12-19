FROM python:3.11.7-bookworm
RUN apt-get update && apt-get install python3-tk tk-dev -y
COPY ./code/requirements.txt /usr/local/src/myscripts/requirements.txt
WORKDIR /usr/local/src/myscripts
RUN pip install -r requirements.txt
COPY ./code/admin /usr/local/src/myscripts/admin
COPY ./code/utilities /usr/local/src/myscripts/utilities
WORKDIR /usr/local/src/myscripts/admin
ENV PYTHONPATH "${PYTHONPATH}:/usr/local/src/myscripts"
EXPOSE 80
CMD ["streamlit", "run", "Admin.py", "--server.port", "80", "--server.enableXsrfProtection", "false"]