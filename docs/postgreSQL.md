### PostgreSQL Integration in CWYD

The CWYD has been enhanced with PostgreSQL as a core feature, enabling flexible, robust, and scalable database capabilities. This document outlines the features, configurations, and functionality introduced with PostgreSQL support.

---

## Features and Enhancements

### 1. **Default Database Configuration**
PostgreSQL is now the default database for CWYD deployments. If no database preference is specified (`DATABASE_TYPE` is unset or empty), the platform defaults to PostgreSQL. This ensures a streamlined deployment process while utilizing PostgreSQL’s advanced capabilities.

---

### 2. **Unified Environment Configuration**
To simplify environment setup, PostgreSQL configurations are now grouped under a unified JSON environment variable:

Example:
```json
{
  "type": "PostgreSQL",
  "user": "DBUSER",
  "database": "DBNAME",
  "host": "DBHOST"
}
```
This structure ensures easier management of environment variables and dynamic database selection during runtime.

---

### 3. **PostgreSQL as the Search Index Provider**
The PostgreSQL `search_indexes` table is used for managing search-related indexing. It supports vector-based similarity searches, replacing Azure Search indexing in specific configurations.

**Table Schema**:
```sql
CREATE TABLE IF NOT EXISTS search_indexes(
    id TEXT,
    title TEXT,
    chunk INTEGER,
    chunk_id TEXT,
    offset INTEGER,
    page_number INTEGER,
    content TEXT,
    source TEXT,
    metadata TEXT,
    content_vector VECTOR(1536)
);
```

**Similarity Query Example**:
```sql
SELECT content
FROM search_indexes
ORDER BY content_vector <=> $1
LIMIT $2;
```


---

### 4. **Automated Table Creation**
The PostgreSQL deployment process automatically creates the necessary tables for chat history and search indexes. The script `create_postgres_tables.py` is executed as part of the infrastructure deployment, ensuring the database is ready for use immediately after setup.

---

### 8. **Secure PostgreSQL Connections**
All PostgreSQL connections use secure configurations:
- SSL is enabled with parameters such as `sslmode=verify-full`.
- Credentials are securely managed via environment variables and Key Vault integrations.

---

### 9. **Backend Enhancements**
- PostgreSQL integration is limited to the Semantic Kernel orchestrator to ensure focused functionality.
- Database operations, including indexing and similarity searches, align with the CWYD workflow.

---

## Benefits of PostgreSQL Integration
1. **Scalability**: PostgreSQL offers robust indexing capabilities suitable for large-scale deployments.
2. **Flexibility**: Dynamic database switching allows users to choose between PostgreSQL and CosmosDB based on their requirements.
3. **Ease of Use**: Automated table creation and environment configuration simplify deployment and management.
4. **Security**: SSL-enabled connections and secure credential handling ensure data protection.


---

## Conclusion
PostgreSQL integration transforms CWYD into a versatile, scalable platform capable of handling complex indexing and search scenarios. By leveraging PostgreSQL’s advanced features, CWYD ensures a seamless user experience, robust performance, and future-ready architecture.
