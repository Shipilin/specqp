from .region import Region 

def importScientaFile(filename, energy_correction=0, fermi_level=False, regions_number_line=1):
    """Opens and parses provided scienta file returning the data and info for all regions 
    as a list of Region objects. 'energy_correction' variable provides the possibility
    to change the retrieved energy values by constant value of energy shift derived
    from e.g. Fermi level measurement. 'fermi_level' defines whether the scan represents
    the Fermi level. Optional variable 'regions_number_line' gives the
    number of the line in the scienta file where the number of regions is given
    (the line numbering starts with 0 and by default it is the line number 1 that
    contains the needed information)
    """
    with open(filename) as f:
        lines = f.read().splitlines()
    
    # Dictionary that contains the map of the file, where the name of the section is
    # the key and the list of first and last indices of Info and Data sections is the value
    # Example: {"Region 1": [[3, 78], [81, 180]]}
    #                         Info      Data
    file_map = {}
        
    # The number of regions is given in the second line of the file
    regions_number = int(lines[regions_number_line].split("=")[1])
    # If number of regions higher than one, we'll need to make a list of scan objects
    regions = []
    
    # Temporary counter to know the currently treated region number in the 
    # for-loop below
    cnt = 1
    # Temporary list variables to store the first and the last indices of the 
    # info and the data file blocks for every region
    info_indices = []
    data_indices = []
    
    # Parsing algorithm below assumes that the file structure is constant and 
    # the blocks follow the sequence:
    # [Region N] - not important info
    # [Info N] - important info
    # [Data N] - data
    for i, line in enumerate(lines):
        if ("[Region %d]" % cnt) in line:
            # If it is not the first region, than the data section of the previous region
            # ends on the previous line
            if cnt > 1:
                data_indices.append(i-1) 
            continue
        if ("[Info %d]" % cnt) in line:
            info_indices.append(i+1)  
            continue
        if ("[Data %d]" % cnt) in line:
            info_indices.append(i-1)
            data_indices.append(i+1)
            if cnt == regions_number:
                data_indices.append(len(lines)-1)
                break
            else:
                cnt += 1    
    
    # Reseting region number counter to 1 to start again from the first region
    cnt = 1
    for j in range(1, len(info_indices), 2):
        file_map[f"Region {cnt}"] = [[info_indices[j-1], info_indices[j]], [data_indices[j-1], data_indices[j]]]
        cnt += 1
    
    # Iterating through regions            
    for val in file_map.values():
        energy, counts = [], []
        # Parsing Data block of the current region 
        data_block = lines[val[1][0]:val[1][1]+1]
        for line in data_block:
            if not line.strip():
                continue # Scip empty lines
            else:
                xy = line.split()
                x = float(xy[0].strip())
                y = float(xy[1].strip())
                if y > 0:
                    energy.append(x)
                    counts.append(y)

        # Info block of the current region 
        info_lines = parseScientaFileInfo(lines[val[0][0]:val[0][1]+1])
        
        # In case the original energy value should be corrected for 
        # a constant energy shift do the correction. Set the corresponding flag
        if energy_correction != 0:
            energy = [(value + energy_correction) for value in energy]
            energy_corrected_flag = True
        else:
            energy_corrected_flag = False
        
        # Check which energy scale is used: 
        if info_lines["Energy Scale"] == "Kinetic":
            binding_energy_flag_value = False
        else:
            binding_energy_flag_value = True
        
        # Create a Region object for the current region with corresponding values
        # of flags
        regions.append(Region(energy, counts, energy_shift_corrected=energy_corrected_flag, binding_energy_flag=binding_energy_flag_value, 
                 fermi_level_flag=fermi_level, info=info_lines))
        
    return regions

def parseScientaFileInfo(lines):
    """Parses the Scienta file and returnes 'info' dictionary
    """
    info = {} 
    for line in lines:
        line = line.strip()
        if '=' in line:
            line_content = line.split('=', 1)
            info[line_content[0].strip()] = line_content[1].strip()   
                                 
    return info
