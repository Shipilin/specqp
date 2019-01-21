from .region import Region 

def importSpecsFile(filename, energy_correction=0, fermi_level=False):
    """Opens and parses provided specs.xy file returning the data and info for all
    region as a list of Region objects. 'energy_correction' variable provides the possibility
    to change the retrieved energy values by constant value of energy shift derived
    from e.g. Fermi level measurement. 'fermi_level' defines whether the scan represents
    the Fermi level.
    """
    with open(filename) as f:
        lines = f.read().splitlines()
    
    # Basic parsing based on the appearance of SPECS files
    energy, counts = [], []
    info_lines = []
    for line in lines:
        if not line.strip():
            continue # Scip empty lines
        elif line.strip().startswith('#'):
            info_lines.append(line) # Save info lines
        else:
            xy = line.split()
            x = float(xy[0].strip())
            y = float(xy[1].strip())
            if y > 0:
                energy.append(x)
                counts.append(y)

    # Switch from list to dictionary
    info_lines = parseSpecFileInfo(info_lines)

    # In case the original energy value should be corrected for 
    # a constant energy shift do the correction. Set the corresponding flag
    if energy_correction != 0:
        energy = [(value + energy_correction) for value in energy]
        energy_corrected_flag = True
        # We also need to change info entries accordingly to the shift correction
        info_lines["Kinetic Energy"] = str(float(info_lines["Kinetic Energy"]) + energy_correction)
        
    else:
        energy_corrected_flag = False
    
    # Check which energy scale is used: 
    if info_lines["Energy Axis"] == "Kinetic Energy":
        binding_energy_flag_value = False
    else:
        binding_energy_flag_value = True
    
    # Create a Region object for the current region with corresponding values
    # of flags
    regions = []
    regions.append(Region(energy, counts, energy_shift_corrected=energy_corrected_flag, binding_energy_flag=binding_energy_flag_value, 
             fermi_level_flag=fermi_level, info=info_lines))
    
    return regions

def parseSpecFileInfo(lines):
    """Parses the list of lines read from SPEC.xy file info block
    and returns 'info' dictionary
    """
    info = {} 
    for line in lines:
        line = line.strip().lstrip('#').strip()
        if ':' in line:
            line_content = line.split(':', 1)
            info[line_content[0].strip()] = line_content[1].strip()   
                                 
    return info
