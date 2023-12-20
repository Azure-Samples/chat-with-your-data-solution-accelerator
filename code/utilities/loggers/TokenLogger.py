import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler
from ..helpers.EnvHelper import EnvHelper


class TokenLogger:
    """
    A class for logging messages with custom dimensions using Azure Application Insights.
    """

    def __init__(self, name: str = __name__):
        """
        Initializes a new instance of the TokenLogger class.

        Args:
            name (str, optional): The name of the logger. Defaults to __name__.
        """
        env_helper: EnvHelper = EnvHelper()
        self.logger = logging.getLogger(name)
        self.logger.addHandler(AzureLogHandler(
            connection_string=env_helper.APPINSIGHTS_CONNECTION_STRING))
        self.logger.setLevel(logging.INFO)

    def get_logger(self):
        """
        Gets the logger instance.

        Returns:
            logging.Logger: The logger instance.
        """
        return self.logger

    def log(self, message: str, custom_dimensions: dict):
        """
        Logs a message with custom dimensions.

        Args:
            message (str): The message to be logged.
            custom_dimensions (dict): The custom dimensions to be included in the log.

        """
        # Setting log properties
        log_properties = {
            "custom_dimensions": custom_dimensions
        }
        self.logger.info(message, extra=log_properties)
