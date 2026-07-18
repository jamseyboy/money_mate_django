import logging
import os
from pathlib import Path


class DynamicFileHandler(logging.Handler):
    """
    A custom handler that reads the log's 'name' and dynamically
    routes it to a file named <name>.log
    """

    def __init__(self, log_dir):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._handlers = {}

    def emit(self, record):
        # record.name is the [{name}] part (e.g., 'django.db', 'loginModule')
        logger_name = record.name

        # If we haven't created a file for this logger yet, make one
        if logger_name not in self._handlers:
            file_path = self.log_dir / f"{logger_name}.log"

            # Create a standard FileHandler for this specific file
            fh = logging.FileHandler(file_path)
            fh.setFormatter(self.formatter)
            self._handlers[logger_name] = fh

        # Pass the log record to the specific file handler
        self._handlers[logger_name].emit(record)

    def close(self):
        # Ensure all dynamically created files are safely closed on shutdown
        for handler in self._handlers.values():
            handler.close()
        super().close()