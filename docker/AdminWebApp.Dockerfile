FROM python:3.9.10-slim-buster
RUN apt-get update && apt-get install python-tk python3-tk tk-dev -y
COPY ./admin/requirements.txt /usr/local/src/myscripts/requirements.txt
WORKDIR /usr/local/src/myscripts
RUN pip install -r requirements.txt
COPY ./admin/ /usr/local/src/myscripts
EXPOSE 80
CMD ["streamlit", "run", "Admin.py", "--server.port", "80", "--server.enableXsrfProtection", "false"]