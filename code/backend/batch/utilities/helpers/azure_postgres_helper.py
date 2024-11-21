import logging
import psycopg2
from .llm_helper import LLMHelper
from .env_helper import EnvHelper
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class AzurePostgresHelper:

    def __init__(self):
        self.llm_helper = LLMHelper()
        self.env_helper = EnvHelper()

    def connect(self):
        user = self.env_helper.POSTGRESQL_USER
        host = self.env_helper.POSTGRESQL_HOST
        dbname = self.env_helper.POSTGRESQL_DATABASE
        cred = DefaultAzureCredential()
        # Acquire the access token
        accessToken = cred.get_token(
            "https://ossrdbms-aad.database.windows.net/.default"
        )

        # Combine the token with the connection string to establish the connection.
        conn_string = "host={0} user={1} dbname={2} password={3}".format(
            host, user, dbname, accessToken.token
        )
        conn = psycopg2.connect(conn_string)
        return conn
