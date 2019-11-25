import os
import logging
# from helpers import is_iterable
from specqp.helpers import is_iterable

service_logger = logging.getLogger("specqp.service")  # Configuring child logger

service_vars = {
    "DEFAULT_DATA_FOLDER": os.path.expanduser("~") + "/Documents",
    "LOG_FILE_NAME": os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/data/log/app.log",
    "INIT_FILE_NAME": os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/data/specqp.init",
    "DEFAULT_OUTPUT_FOLDER": os.path.expanduser("~") + "/Documents/specqp_output",
    "FFMPEG_PATH": "",
    "ROUND_PRECISION": "5",
    "PLOT_ASPECT_RATIO": "0.75",
    "FONT_SIZE": "12",
    "PHOTON_ENERGY": "",
    "ENERGY_SHIFT": "",
    "FERMI_FIT_PARAMETERS": "1.00;0.00;0.10;0.00",
    "NORMALIZATION_CONSTANT": "1",
    "NORMALIZE_BY_CONSTANT": "",
    "CROP": ";",
    "DO_CROP": "",
    "NORMALIZE_SWEEPS": "True",
    "NORMALIZE_DWELL": "True",
    "SUBTRACT_CONSTANT": "",
    "SUBTRACT_SHIRLEY": "",
    "LEGEND": ";True;True"
}


def prepare_startup():
    # Read the last used data folder from .init file if exists. Create the .init file if doesn't exist
    if os.path.isfile(service_vars["INIT_FILE_NAME"]):
        _read_service_vars()
    else:
        try:
            with open(service_vars["INIT_FILE_NAME"], 'w') as init_file:
                for key, val in service_vars.items():
                    init_file.write(f"{key}={val}\n")
        except IOError:
            service_logger.error(f"Can't create init file {service_vars['INIT_FILE_NAME']}", exc_info=True)


def get_service_parameter(parameter):
    return service_vars[parameter]


# def read_from_init(parameter):
#     try:
#         with open(service_vars["INIT_FILE_NAME"], 'r') as init_file:
#             lines = init_file.readlines()
#             for i, line in enumerate(lines):
#                 if parameter in line:
#                     # Return the part of the line after the constant name and '=' sign
#                     return line[(len(parameter) + 1):]
#         return False
#     except IOError:
#         service_logger.error(f"Can't access the file {service_vars['INIT_FILE_NAME']}", exc_info=True)


def _read_service_vars():
    try:
        with open(service_vars["INIT_FILE_NAME"], 'r') as init_file:
            lines = init_file.readlines()
            for line in lines:
                key, val = line.split("=")
                service_vars[key] = val.rstrip() # rstrip in case new lines were added
    except IOError:
        service_logger.error(f"Can't access the file {service_vars['INIT_FILE_NAME']}", exc_info=True)


def set_init_parameters(parameters, values):
    """Writing new parameters or new values for existing parameters to init file
    :param parameters: str or sequence of strings (name(s) of parameter(s))
    :param values: str or number or sequence of strings or numbers to be recorded
    :return: None
    """
    if type(parameters) == str:
        parameters = [parameters]
    elif not is_iterable(parameters):
        return
    if type(values) == str or not is_iterable(values):
        values = [values]
    assert len(parameters) == len(values)
    # Make sure that all values and parameters are strings for future comparison
    parameters = [str(p) for p in parameters]
    values = [str(v) for v in values]

    change_counter = 0
    for i, par in enumerate(parameters):
        if (not service_vars[par] == values[i]) or (par not in service_vars):
            service_vars[par] = values[i]
            change_counter += 1
    # If nothing new appeared or same values are already stored do nothing
    if change_counter == 0:
        return


def write_init_file():
    # Otherwise, write the file anew
    new_lines = []
    for key, val in service_vars.items():
        new_lines.append(f"{key}={val}")
    try:
        with open(service_vars["INIT_FILE_NAME"], 'w') as init_file:
            new_lines = map(lambda x: x + '\n', new_lines)
            init_file.writelines(new_lines)
    except IOError:
        service_logger.error(f"Can't access the file {service_vars['INIT_FILE_NAME']}", exc_info=True)