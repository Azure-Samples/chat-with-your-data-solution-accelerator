import logging


# TODO: We probably don't need a separate class for this
class TokenLogger:
    def __init__(self, name: str = __name__):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

    def get_logger(self):
        return self.logger

    def log(self, message: str, custom_dimensions: dict):
        # Setting log properties
        self.logger.info(message, extra=custom_dimensions)
