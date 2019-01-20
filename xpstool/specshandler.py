from .region import Region 

def parseSpecFileInfo(lines):
    """Parses the SPEC.xy file and returns 'info' dictionary
    """
    info = {} 
    for line in lines:
        line = line.strip().lstrip('#').strip()
        if ':' in line:
            line_content = line.split(':', 1)
            info[line_content[0].strip()] = line_content[1].strip()   
                                 
    return info
