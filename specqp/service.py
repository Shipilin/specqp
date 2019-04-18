import os
import logging

# Service folders and files
LOG_FILE_NAME = "../data/log/app.log"
INIT_FILE_NAME = "../data/specqp.init"

SERVICE_CONSTANTS = (
    "DEFAULT_DATA_FOLDER",
)


def prepare_service_files():
    # Create the log directory if doesn't exist
    directory = os.path.dirname(LOG_FILE_NAME)
    if not os.path.exists(directory):
        os.makedirs(directory)
    # Create the init file if doesn't exist
    if not os.path.isfile(INIT_FILE_NAME):
        with open(INIT_FILE_NAME, 'w') as init_file:
            init_file.write(f"{SERVICE_CONSTANTS[0]}={os.getcwd()}")


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