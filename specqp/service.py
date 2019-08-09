import os
import logging


service_logger = logging.getLogger("specqp.service")  # Configuring child logger

service_vars = {
    "DEFAULT_DATA_FOLDER": "../",
    "LOG_FILE_NAME": "../data/log/app.log",
    "INIT_FILE_NAME": "../data/specqp.init",
    "DEFAULT_OUTPUT_FOLDER": "",
}


def prepare_startup():
    # Read the last used data folder from .init file if exists. Create the .init file if doesn't exist
    if os.path.isfile(service_vars["INIT_FILE_NAME"]):
        service_vars["DEFAULT_DATA_FOLDER"] = read_default_data_folder_from_file()
    else:
        with open(service_vars["INIT_FILE_NAME"], 'w') as init_file:
            service_vars["DEFAULT_DATA_FOLDER"] = os.getcwd()
            init_file.write(f"DEFAULT_DATA_FOLDER={service_vars['DEFAULT_DATA_FOLDER']}")

    service_vars["DEFAULT_OUTPUT_FOLDER"] = service_vars["DEFAULT_DATA_FOLDER"] + "/output"


def read_default_data_folder_from_file():
    try:
        with open(service_vars["INIT_FILE_NAME"], 'r') as init_file:
            lines = init_file.readlines()
            for i, line in enumerate(lines):
                if "DEFAULT_DATA_FOLDER" in line:
                    # Return the part of the line after the constant name and '=' sign
                    return line[(len("DEFAULT_DATA_FOLDER") + 1):]
    except IOError:
        service_logger.error(f"Can't access the file {service_vars['INIT_FILE_NAME']}", exc_info=True)


def set_default_data_folder(new_dir):
    # If the new folder is actually the same as before do nothing
    if new_dir == service_vars["DEFAULT_DATA_FOLDER"]:
        return
    service_vars["DEFAULT_DATA_FOLDER"] = new_dir
    service_vars["DEFAULT_OUTPUT_FOLDER"] = service_vars["DEFAULT_DATA_FOLDER"] + "/output"
    new_line = f"DEFAULT_DATA_FOLDER={new_dir}"
    try:
        with open(service_vars["INIT_FILE_NAME"], 'r') as init_file:
            lines = init_file.readlines()
            for i, line in enumerate(lines):
                if "DEFAULT_DATA_FOLDER" in line:
                    lines[i] = new_line
                    break
            # If not found in .init file add at the end of the file
            if new_line not in lines:
                lines.append(new_line)
        with open(service_vars["INIT_FILE_NAME"], 'w') as init_file:
            init_file.writelines(lines)
    except IOError:
        service_logger.error(f"Can't access the file {service_vars['INIT_FILE_NAME']}", exc_info=True)