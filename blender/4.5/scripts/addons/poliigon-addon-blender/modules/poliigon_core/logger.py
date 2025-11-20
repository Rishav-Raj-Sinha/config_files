import logging
import os
from io import StringIO
from typing import Optional, List

from .env import PoliigonEnvironment


# Numerical comment -> values for .ini
NOT_SET = logging.NOTSET  # 0
DEBUG = logging.DEBUG  # 10
INFO = logging.INFO  # 20
WARNING = logging.WARNING  # 30
ERROR = logging.ERROR  # 40
CRITICAL = logging.CRITICAL  # 50


# Import and use get_addon_logger() to get hold of the logger manager
addon_logger = None


class MockLogger:
    """Placeholder logger which accepts any arguments and does nothing"""

    def __getattr__(self, method_name):
        # Names matching the built in logging class methods
        log_methods = ['critical', 'error', 'exception', 'fatal',
                       'debug', 'info', 'log',
                       'warn', 'warning']
        if method_name not in log_methods:
            raise RuntimeError("Invalid logger method")

        def method(*args, **kwargs):
            return None
        return method


class AddonLogger:
    """Class to store all the data (created loggers, formatting information
    and handlers) and functionality related to the Addon Logs.

    loggers: Stores all created loggers;
    dcc_handlers: Stores all handlers created on DCC side.
                  For adding new Handlers, use the method set_dcc_handlers;
    write_to_file: Defines if the new loggers write the output into a .log file;
    log_file_path: The output path to create the .log file;

    """

    loggers = []
    dcc_handlers = []

    write_to_file: bool = False

    str_format = ("%(name)s, %(levelname)s, %(threadName)s, %(asctime)s, "
                  "%(filename)s/%(funcName)s:%(lineno)d: %(message)s")

    date_format = "%I:%M:%S"

    def __init__(
            self,
            env: Optional[PoliigonEnvironment] = None,
            file_path: Optional[str] = None):

        self.addon_env = env
        self.file_handler = None
        self.stream_handler = None

        addon_core_path = os.path.split(os.path.split(os.path.realpath(__file__))[0])[0]
        self.log_file_path = os.path.join(addon_core_path, "logs.log")

        if file_path is not None:
            self.log_file_path = file_path
            self.write_to_file = True
        else:
            try:
                self.write_to_file = self.addon_env.config.getboolean(
                    "DEFAULT", "log_to_file", fallback=False)
            except AttributeError:
                pass  # no .ini

    def _init_filehandler(self, have_filehandler: bool) -> None:
        """Optionally initializes the default file handler."""

        if not have_filehandler:
            self.file_handler = None
            return

        log_file_exists = os.path.isfile(self.log_file_path)
        if log_file_exists:
            log_file_write_access = os.access(self.log_file_path, os.W_OK)
        else:
            log_file_write_access = True

        log_dir = os.path.dirname(self.log_file_path)
        log_dir_exists = os.path.isdir(log_dir)
        if log_dir_exists:
            log_dir_write_access = os.access(log_dir, os.W_OK)
        else:
            log_dir_write_access = False

        log_file_overwrite = log_file_exists and log_file_write_access
        log_file_create_allowed = log_dir_exists and log_dir_write_access and not log_file_exists
        if log_file_overwrite or log_file_create_allowed:
            if self.file_handler is None:
                self.file_handler = AddonFileHandler(self.log_file_path, self)

    def initialize_logger(self, module_name: Optional[str] = None,
                          *,
                          log_lvl: Optional[int] = None,
                          log_stream: Optional[StringIO] = None,
                          base_name: str = "Addon",
                          append_dcc_handlers: bool = True,
                          have_filehandler: bool = True
                          ) -> logging.Logger:
        """Set format, log level and returns a logger instance

        Args:
           module_name: The name of the module a required argument
                        Env log_lvl variable name is derived as follows:
                        Logger name: Addon => log_lvl
                        Logger name: Addon.DL => log_lvl_dl
                        Logger name: Addon.P4C.UI => log_lvl_p4c_ui
                        But also:
                        Logger name: bonnie => log_lvl
                        Logger name: clyde.whatever => log_lvl_whatever
           log_lvl: Integer specifying which logs to be printed, one of:
                https://docs.python.org/3/library/logging.html#levels
           log_stream: Output to StringIO stream instead of the console if not None
           base_name: By default all loggers get derived from logger "Addon".
           append_dcc_handlers: Defines if the handlers cached in self.dcc_handlers
                                should be added for the new logger.
           have_filehandler: Set to fault too disable logging to a file.

        Returns:
            Returns a reference to the initialized logger instance

        Raises:
            AttributeError: If log_lvl and env are both None.
        """

        if module_name is None:
            logger_name = f"{base_name}"
            name_hierarchy = []
        else:
            logger_name = f"{base_name}.{module_name}"
            name_hierarchy = module_name.split(".")

        if log_lvl is None:
            log_lvl_name = "log_lvl"
            for name in name_hierarchy:
                log_lvl_name += f"_{name.lower()}"

            try:
                log_lvl = self.addon_env.config.getint(
                    "DEFAULT", log_lvl_name, fallback=NOT_SET)
            except AttributeError:
                log_lvl = NOT_SET  # no .ini

        logger = logging.getLogger(logger_name)
        logger.propagate = False
        logger.setLevel(log_lvl)

        if self.stream_handler is None:
            self.stream_handler = logging.StreamHandler(log_stream)
        self.set_dcc_handlers(handlers=[self.stream_handler])

        self._init_filehandler(have_filehandler)
        if self.file_handler is not None:
            self.set_dcc_handlers(handlers=[self.file_handler])

        if append_dcc_handlers and len(self.dcc_handlers) > 1:
            self.set_dcc_handlers(loggers=[logger])

        self.loggers.append(logger)

        return logger

    def set_write_to_file_handler(
            self, enabled: bool, path: Optional[str] = None) -> None:
        self.write_to_file = enabled
        if path is not None:
            self.log_file_path = path

    def set_dcc_handlers(
            self,
            loggers: Optional[List[logging.Logger]] = None,
            handlers: Optional[List[logging.Handler]] = None) -> None:

        loggers_to_add = loggers if loggers is not None else self.loggers
        handlers_to_add = handlers if handlers is not None else self.dcc_handlers
        for _logger in loggers_to_add:
            for _handler in handlers_to_add:
                self.set_handlers_formatter([_handler])
                _logger.addHandler(_handler)
                if _handler not in self.dcc_handlers:
                    self.dcc_handlers.append(_handler)

    def set_handlers_formatter(
            self,
            handlers: Optional[List[logging.Handler]] = None) -> None:
        handlers_to_format = handlers if handlers is not None else self.dcc_handlers
        formatter = logging.Formatter(
            fmt=self.str_format, datefmt=self.date_format)
        for _handler in handlers_to_format:
            _handler.setFormatter(formatter)


class AddonFileHandler(logging.FileHandler):
    def __init__(self, filepath: str, log_manager: AddonLogger):
        super(AddonFileHandler, self).__init__(filepath)

        self.log_manager = log_manager
        self.original_emit_event = self.emit
        self.emit = self.custom_emit

    def change_log_filename(self, filename: str):
        if os.path.isfile(filename):
            self.baseFilename = filename

    def custom_emit(self, record: logging.LogRecord) -> None:
        if not self.log_manager.write_to_file:
            return

        if self.log_manager.log_file_path != self.baseFilename:
            self.baseFilename = self.log_manager.log_file_path
            self.close()
            self.stream = None

        # Ensure original emit event runs
        self.original_emit_event(record)


def get_addon_logger(env: Optional[PoliigonEnvironment] = None) -> AddonLogger:
    global addon_logger
    if addon_logger is None:
        addon_logger = AddonLogger(env)
    return addon_logger
