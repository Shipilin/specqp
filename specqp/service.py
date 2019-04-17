import os
import logging
from logging.handlers import RotatingFileHandler

# Default font for the GUI
LARGE_FONT = ("Verdana", "12")

# Preparing service folders and files
LOGFILE_NAME = "../data/log/app.log"
INITFILE_NAME = "../data/specqp.init"


def initialize_logging():
    # Create the log directory if doesn't exist
    directory = os.path.dirname(LOGFILE_NAME)
    if not os.path.exists(directory):
        os.makedirs(directory)
    # Create the init file if doesn't exist
    if not os.path.isfile(INITFILE_NAME):
        with open(INITFILE_NAME, 'w') as init_file:
            init_file.write(f"LASTDATAFOLDER={os.getcwd()}")

    # Setting up the main logger for the app
    specqp_app_logger = logging.getLogger("specqp")
    specqp_app_logger.setLevel(logging.INFO)

    # Setting up console output with more information to be logged
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    # Setting up logfile output with only errors and critical errors to be logged
    # Set rotating handlers so that the logfile doesn't grow forever
    file_handler = RotatingFileHandler(LOGFILE_NAME, maxBytes=1000000, backupCount=3)
    file_handler.setLevel(logging.ERROR)

    formatter = logging.Formatter("%(asctime)s (%(levelname)s in %(name)s): %(message)s", "%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    specqp_app_logger.addHandler(console_handler)
    specqp_app_logger.addHandler(file_handler)