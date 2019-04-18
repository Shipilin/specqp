import sys

from service import initialize_app
from gui import main as call_gui


initialize_app()


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
