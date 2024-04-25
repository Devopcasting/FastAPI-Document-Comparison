import logging
import os

class DOCCOMLogging:
    def __init__(self, log_file='doccom.log', log_level=logging.INFO):
        LOG_PATH = os.path.abspath(os.path.join("app", "log"))
        self.log_file = os.path.join(LOG_PATH, log_file)
        self.log_level = log_level

    def configure_logger(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(self.log_level)

        if not self._file_handler_exists(logger):
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(self.log_level)
            formatter = logging.Formatter('%(process)d %(asctime)s %(levelname)s %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        return logger

    def _file_handler_exists(self, logger):
        if not os.path.isfile(self.log_file):
            # Create the log file if it doesn't exist
            open(self.log_file, 'a').close()
            return False
        return any(isinstance(handler, logging.FileHandler) and handler.baseFilename == self.log_file for handler in logger.handlers)