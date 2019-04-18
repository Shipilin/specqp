import os
import logging
from logging.handlers import RotatingFileHandler

# Preparing service folders and files
LOG_FILE_NAME = "../data/log/app.log"
INIT_FILE_NAME = "../data/specqp.init"

SERVICE_CONSTANTS = (
    "DEFAULT_DATA_FOLDER",
)


def initialize_app():
    """The function that is called from specqp upon start
    to initialize logging and create specqp.init file if doesn't exist
    """
    # Create the log directory if doesn't exist
    directory = os.path.dirname(LOG_FILE_NAME)
    if not os.path.exists(directory):
        os.makedirs(directory)
    # Create the init file if doesn't exist
    if not os.path.isfile(INIT_FILE_NAME):
        with open(INIT_FILE_NAME, 'w') as init_file:
            init_file.write(f"{SERVICE_CONSTANTS[0]}={os.getcwd()}")

    # Setting up the main logger for the app
    specqp_app_logger = logging.getLogger("specqp")
    specqp_app_logger.setLevel(logging.INFO)

    # Setting up console output with more information to be logged
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    # Setting up logfile output with only errors and critical errors to be logged
    # Set rotating handlers so that the logfile doesn't grow forever
    file_handler = RotatingFileHandler(LOG_FILE_NAME, maxBytes=1000000, backupCount=3)
    file_handler.setLevel(logging.ERROR)

    formatter = logging.Formatter("%(asctime)s (%(levelname)s in %(name)s): %(message)s", "%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    specqp_app_logger.addHandler(console_handler)
    specqp_app_logger.addHandler(file_handler)


def set_default_data_folder(new_dir):
    new_line = f"{SERVICE_CONSTANTS[0]}={new_dir}"
    try:
        with open(INIT_FILE_NAME, 'r') as init_file:
            lines = init_file.readlines()
            for i, line in enumerate(lines):
                if SERVICE_CONSTANTS[0] in line:
                    lines[i] = new_line
                    break
            # If not found in .init file add at the end of the file
            if new_line not in lines:
                lines.append(new_line)
        with open(INIT_FILE_NAME, 'w') as init_file:
            init_file.writelines(lines)
    except IOError:
        logger = logging.getLogger("specqp.service")  # Configuring child logger
        logger.error(f"Can't access the file {INIT_FILE_NAME}", exc_info=True)


def get_default_data_folder():
    try:
        with open(INIT_FILE_NAME, 'r') as init_file:
            lines = init_file.readlines()
            for i, line in enumerate(lines):
                if SERVICE_CONSTANTS[0] in line:
                    # Return the part of the line after the constant name and '=' sign
                    return line[(len(SERVICE_CONSTANTS[0]) + 1):]
    except IOError:
        logger = logging.getLogger("specqp.service")  # Configuring child logger
        logger.error(f"Can't access the file {INIT_FILE_NAME}", exc_info=True)