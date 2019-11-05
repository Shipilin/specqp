import sys
import os
import logging
from logging.handlers import RotatingFileHandler

# import service
# from gui import main as call_gui
from specqp import service
from specqp.gui import main as call_gui


specqp_logger = logging.getLogger("specqp")


def initialize_logging():
    """Setting up the main logger for the app
    """
    specqp_logger.setLevel(logging.ERROR)  # Main level filter for log messages (with DEBUG all messages are evaluated)

    # Setting up console output with more information to be logged
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)  # Secondary level filter for log messages in console

    # Create the log directory if doesn't exist
    directory = os.path.dirname(service.service_vars["LOG_FILE_NAME"])
    if not os.path.exists(directory):
        os.makedirs(directory)
    # Setting up logfile output with only errors and critical errors to be logged
    # Set rotating handlers so that the logfile doesn't grow forever
    file_handler = RotatingFileHandler(service.service_vars["LOG_FILE_NAME"], maxBytes=1000000, backupCount=3)
    file_handler.setLevel(logging.ERROR)  # Secondary level filter for log messages in file

    formatter = logging.Formatter("%(asctime)s (%(levelname)s in %(name)s): %(message)s", "%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    specqp_logger.addHandler(console_handler)
    specqp_logger.addHandler(file_handler)


def parse_batch_file(filename, sections=None):
    guidelines = []
    fl = filename
    if not os.path.isfile(filename):
        filename = os.getcwd() + '/' + filename
        if not os.path.isfile(filename):
            specqp_logger.error(f"Can't find the source text file {fl}. The file was not loaded.")
            return [None]
    with open(filename, 'r') as f:
        lines = f.readlines()
        if sections is None:
            guidelines = [line for line in lines if line[0] == 'F']
            return guidelines
        else:
            for section in sections:
                section_start = [i + 1 for i, line in enumerate(lines) if f"[{section}]" in line]
                section_end = [i for i, line in enumerate(lines) if f"[/{section}]" in line]
                if len(section_start) != len(section_end):
                    specqp_logger.error(f"Every section of the instruction file should begin with"
                                        "'[sectionname]' label and end with [/sectionname] label. "
                                        "The file {fl} was not loaded.")
                    return [None]
                for i in range(len(section_start)):
                    guidelines += [line for line in lines[section_start[i]:section_end[i]] if line[0] == 'F']
            return guidelines


# TODO: write the logics for the batch mode
def main(*args, **kwargs):
    """Defines the behavior of the app if run with flags and/or other parameters
    """
    # If no command line arguments or only '-gui' flag provided, run blank GUI
    if (len(args) == 0 and len(kwargs) == 0) or \
       (len(args) == 1 and args[0] == "-gui" and len(kwargs) == 0):
        call_gui()

    # To load a bunch of regions from files listed in a text file provide flag '-gui' and the filename(s)
    elif "-gui" in args and "filenames" in kwargs:
        instruction_lines = []
        loader_instructions = {
            "FP": [],
            "FT": [],
            "PE": [],
            "ES": [],
            "NC": [],
            "CO": [],
            "CROP": [],
            "CBG": [],
            "SBG": []
        }

        if "sections" in kwargs:
            sections_to_load = []
            sections_to_load += [sec.strip() for sec in kwargs["sections"].split(";")]
            if "filenames" in kwargs:
                for filename in kwargs["filenames"].split(';'):
                    instruction_lines += parse_batch_file(filename.strip(), sections_to_load)
        else:
            for filename in kwargs["filenames"].split(';'):
                instruction_lines += parse_batch_file(filename.strip())

        loaded_files = []
        if len(instruction_lines) > 0:
            for line in instruction_lines:
                if line is not None:
                    parts = [l.strip().split('=') for l in line.split(';')]
                    fname = parts[0][1].strip() # The name of the file to load is the first parameter in the line
                    # In case the file has already been put in the loading que, skip it
                    if fname in loaded_files:
                        continue
                    else:
                        loaded_files.append(fname)
                    for part in parts:
                        name, value = part[0].strip(), part[1].strip()
                        if name in loader_instructions:
                            if name == "NC" and value == '':
                                value = "1"
                            if name == "CROP" and value != '':
                                value = [v.strip() for v in value.split(':')]
                            if name == "CROP" and value == '':
                                value = [0, 0]  # To emphasize  that no cropping shall be done
                            loader_instructions[name].append(value)
        if len(loader_instructions["FP"]) > 0:
            call_gui("-batchload", **loader_instructions)
        else:
            print("No source files were loaded. Specqp process is terminated.")
            sys.exit()


if __name__ == "__main__":
    initialize_logging()
    # Setting up service variables, folders, log files path, etc.
    service.prepare_startup()
    specqp_logger.info(f"App started as: {sys.argv}")
    # Enable the case below to force the user to provide arguments
    # if len(sys.argv) < 2:
    #     raise SyntaxError("Insufficient arguments.")

    if len(sys.argv) == 1:
        # If only script name is specified call GUI for interactive work
        specqp_logger.info("Running the app in GUI mode")
        main()
    if len(sys.argv) > 1:
        # If there are additional arguments run in batch mode
        specqp_logger.info("Running the app in BATCH mode")
        args = []
        kwargs = {}
        for arg in sys.argv[1:]:
            if "=" in arg:
                key, val = arg.split('=')
                # If keyword arguments are provided
                kwargs[key.strip()] = val.strip()
            else:
                args.append(arg)
        main(*args, **kwargs)
