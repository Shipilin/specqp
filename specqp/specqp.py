import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from service import prepare_service_files
from service import LOG_FILE_NAME
from gui import main as call_gui


prepare_service_files()

# Setting up the main logger for the app
specqp_logger = logging.getLogger("specqp")
specqp_logger.setLevel(logging.DEBUG)  # Main level filter for log messages (with DEBUG all messages are evaluated)

# Setting up console output with more information to be logged
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Secondary level filter for log messages in console

# Setting up logfile output with only errors and critical errors to be logged
# Set rotating handlers so that the logfile doesn't grow forever
file_handler = RotatingFileHandler(LOG_FILE_NAME, maxBytes=1000000, backupCount=3)
file_handler.setLevel(logging.ERROR)  # Secondary level filter for log messages in file

formatter = logging.Formatter("%(asctime)s (%(levelname)s in %(name)s): %(message)s", "%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

specqp_logger.addHandler(console_handler)
specqp_logger.addHandler(file_handler)


def main(*args, **kwargs):  # TODO: think and write the logics for the batch mode
    """Defines the behavior of the app if run in batch mode
    """
    print("Running in batch mode")
    if args is not None:
        for arg in args:
            print(arg)
    if kwargs is not None:
        for key, value in kwargs.items():
            print(f"{key}={value}")


if __name__ == "__main__":
    specqp_logger.info(f"App started as: {sys.argv}")
    # Enable the case below to force the user to provide arguments
    # if len(sys.argv) < 2:
    #     raise SyntaxError("Insufficient arguments.")

    if len(sys.argv) == 1:
        # If only script name is specified call GUI for interactive work
        call_gui()
    if len(sys.argv) > 1:
        # If there are additional arguments run in batch mode
        args = []
        kwargs = []
        for arg in sys.argv[1:]:
            if "=" in arg:
                # If key word arguments are provided
                kwargs.append(arg)
            else:
                args.append(arg)
        main(*args, *kwargs)
