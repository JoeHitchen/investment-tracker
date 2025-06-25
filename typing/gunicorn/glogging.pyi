import logging

from .config import ErrorLog, Config


class Logger():

    error_log: logging.Logger

    def setup(self, cfg: Config) -> None:
        ...

    def _set_handler(
        self,
        logger: logging.Logger,
        output: ErrorLog,  # Probably?
        formatter: logging.Formatter,
    ) -> None:
        ...

