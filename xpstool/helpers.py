import datetime

# Default info fields for every region 
# (defined by the version of Scienta software)
info_fields = (
    "Region Name",
    "Lens Mode",
    "Pass Energy",
    "Number of Sweeps",
    "Excitation Energy",
    "Energy Scale",
    "Acquisition Mode",
    "Energy Unit",
    "Center Energy",
    "Low Energy",
    "High Energy",
    "Energy Step",
    "Step Time",
    "Detector First X-Channel",
    "Detector Last X-Channel",
    "Detector First Y-Channel",
    "Detector Last Y-Channel",
    "Number of Slices",
    "File",
    "Sequence",
    "Spectrum Name",
    "Instrument",
    "Location",
    "User",
    "Sample",
    "Comments",
    "Date",
    "Time",
    "Time per Spectrum Channel",
    "DetectorMode"            
)

class Scan:
    """Contains and handles a single recorded region together with all information
    about the scan and experimental conditions provided in data file
    """
    
    def __init__(self):
        print(f"Scan class instance was created at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def parse():
    """Parses the info and the data input
    """
    pass
     