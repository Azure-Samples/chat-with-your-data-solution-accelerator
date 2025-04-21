FROM python:3.11-slim

WORKDIR /app

# Copy only the migration script
COPY create_postgres_tables.py .

# Install the bits it needs
RUN pip install psycopg2-binary azure-identity

# When this container starts, run the migration
CMD ["python", "create_postgres_tables.py"]
