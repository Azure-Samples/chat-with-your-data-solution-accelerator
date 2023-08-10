import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler
from ..helpers.EnvHelper import EnvHelper

class TokenLogger:
    def __init__(self, name: str = __name__):
        env_helper : EnvHelper = EnvHelper()
        self.logger = logging.getLogger(name)
        self.logger.addHandler(AzureLogHandler(connection_string=env_helper.APPINSIGHTS_CONNECTION_STRING))
        self.logger.setLevel(logging.INFO)
    
    def get_logger(self):
        return self.logger
    
    def log(self, message: str, custom_dimensions: dict):
        # Setting log properties
        log_properties = {
            "custom_dimensions": custom_dimensions
        }
        self.logger.info(message, extra=log_properties)
    