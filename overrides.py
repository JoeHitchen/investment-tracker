import logging

from gunicorn import config, glogging


class GunicornLogger(glogging.Logger):
    """Custom logger for Gunicorn log messages."""

    def setup(self, cfg: config.Config) -> None:
        """Configure Gunicorn application logging configuration."""
        super().setup(cfg)

        # Override Gunicorn's `error_log` configuration.
        self._set_handler(
            self.error_log,
            cfg.errorlog,
            logging.Formatter(fmt = 'PID-%(process)d  %(levelname)s  %(message)s'),
        )

