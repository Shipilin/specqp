## Quick plot of a single file
from contextlib import contextmanager
from matplotlib.pyplot import figure
import os
import matplotlib.pyplot as plt
import numpy as np

## Change to the fool path to data files in quotation marks.
data_files_folder = os.path.dirname(os.path.abspath(__file__))

def main():

    ## Set 'True' for plotting Binding Energy axis, change to 'False' for Kinetic Energy
    ## If you choose 'True' for Binding Energy, enter the photon energy value below
    binding_energy_flag = True

    ## Specify the incoming photon energy in eV
    photon_energy = 3700

    ## Energy axis reverse. Set 'True' to reverse and 'False' otherwise
    energy_axis_reverse_flag = True

    ## Specify the offset in eV (Fermi level position or correction based on known peak position)
    ## Work function goes in here as well
    ## positive value for addition, negtive - for subtraction
    ## NOTE: Make sure that the sign is correct with regard to kinetic/binding trasformation
    data_offset = 0

    ## Plotting figures in separate windows if the file contains several regions
    ## 'True' for separate plotting, 'False for non-separate plotting'
    separate_plotting_flag = False


    ## Plot information from a single file (can contain several regions)
    ## the file name should include the full path if the file is not in the same
    ## folder with the script
    # plotsinglefile('Rh1O1.txt',
    #                [binding_energy_flag, photon_energy, energy_axis_reverse_flag,
    #                data_offset, separate_plotting_flag])

    ## Same as above but plots several files using the same parameters set
    plotmultiplefiles(['O1.txt',
                      'O2.txt',
                      'O3.txt',
                      [binding_energy_flag, photon_energy, energy_axis_reverse_flag,
                      data_offset, separate_plotting_flag]])

    ## Same as above but plots several files using different parameters sets
    ## NOTE: this function doesn't properly handle the case when the values of
    ## energy_axis_reverse_flag and separate_plotting_flag
    ## are different for different files
    # plotmultiplefileswithparameters(['Rh1O1.txt',
    #                                 [binding_energy_flag, photon_energy, energy_axis_reverse_flag,
    #                                 data_offset, separate_plotting_flag],
    #                                 'Rh2O2.txt',
    #                                 [binding_energy_flag, photon_energy, energy_axis_reverse_flag,
    #                                 data_offset, separate_plotting_flag]])













## Changing the working directory
@contextmanager
def working_directory(path):
    current_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current_dir)

## Parsing list of lines belonging to region N
## Parsing three separate sections:
## '[Region N]' (typically has no use)
## '[Info N]' and '[Data N]' (important information and the actual data)
## Returns region name, info string, lists of energy and counts values "as recorded",
## and "True/False" if the data has Kinetic/Binding scale
def parseregion(regionlines):
    infostring = ""
    region_name = ""

    ## Parsing the info section and finding the line where data entries begin
    region_name_flag = False # Region name can appear several times, we want to add it only once
    kinetic_flag = True # By default, the energy scale is kinetic in the data file
    data_begin_position = 0

    cnt = -1
    for line in regionlines:
        cnt += 1
        if ('Region Name=' in line) and not region_name_flag:
            infostring += line
            region_name = line
            region_name_flag = True
            continue
        if ('Pass Energy=' in line):
            infostring += line
            continue
        if ('Number of Sweeps=' in line):
            infostring += line
            continue
        if ('Date=' in line):
            infostring += line
            continue
        if ('Time=' in line):
            if ('Step Time=' in line):
                continue
            infostring += line
            continue

        ## Check for Binding energy scale
        if ('Energy Scale=Binding' in line):
                kinetic_flag = False
                continue

        if ('[Data' in line):
            data_begin_position = cnt+1 ## Skip the '[Data] header'
            break

    ## Parsing the data entries
    energy = []
    counts = []
    for i in range(data_begin_position, len(regionlines)):
        if (regionlines[i] == "") or (regionlines[i] == "\n") or (not regionlines[i]):
            continue
        data_point = regionlines[i].strip("\n").strip().split("  ")
        try:
            energy.append(float(data_point[0]))
            counts.append(float(data_point[1]))
        except:
            if not any(char.isdigit() for char in regionlines[i]):
                continue

    return (region_name, infostring, energy, counts, kinetic_flag)

def plotsinglefile(xps_file_name, plotting_parameters, multiple_files_flag=False):
    binding_energy_flag = bool(plotting_parameters[0])
    photon_energy = float(plotting_parameters[1])
    energy_axis_reverse_flag = bool(plotting_parameters[2])
    data_offset = float(plotting_parameters[3])
    separate_plotting_flag = bool(plotting_parameters[4])

    ## Reading a single file

    with working_directory(data_files_folder):
        try:
            txt_file_handle = open(xps_file_name, 'r')
            ## Save the file name
            file_name = txt_file_handle.name
            ## Transfer all lines in the file to a list
            file_lines = txt_file_handle.readlines()
            txt_file_handle.close()
        except IOError:
            print("File not found or path is incorrect")
            quit()

    ## The second line (index 1) in the file contains the number of scanned regions in the file
    number_of_regions = int(file_lines[1][(file_lines[1].find("=")+1):].lstrip("0"))
    ## Array holding first and last lines of each region
    region_boundaries = np.zeros([number_of_regions, 2], dtype = int)

    cnt = 0 ## Counter for writing in region_boundaries array
    line_cnt = -1 ## Line counter
    region_cnt = 1 ## Region counter
    for line in file_lines:
        line_cnt += 1 ## Starting with 0 and incrementing every time
        ## Finding lines relative to the Region N
        if (("[Region %d]" % region_cnt) in line):
            ## If it is not the first region in a multi region file, we need to
            ## complete the previous region iteration by filling the second value
            ## in the previous array entry
            if region_cnt > 1:
                region_boundaries[cnt-1][1] = line_cnt - 1
            region_boundaries[cnt][0] = line_cnt
            ## In case it is the last region in the file, we don't need to look further
            if number_of_regions == region_cnt:
                region_boundaries[cnt][1] = len(file_lines)
                break
            else:
                region_cnt += 1
                cnt += 1
                continue

    ## If the function was called for a single file
    if not multiple_files_flag:
        ## Plotting the data with the required energy scale and corrections
        for i in range(0, number_of_regions):
            if separate_plotting_flag:
                plt.figure(i+1)
            region_parser = parseregion(file_lines[region_boundaries[i][0]:region_boundaries[i][1]+1])
            ## In the case the data has kinetic scale and the user wants binding scale (default)
            ## adding offset if exists
            if binding_energy_flag and region_parser[4]:
                plt.plot([photon_energy - x + data_offset for x in region_parser[2]],region_parser[3], label=file_name + '\n' + region_parser[1].rstrip("\n"))
                plt.xlabel('Binding Energy (eV)')
            ## In the case the data has binding scale and the user wants binding scale
            ## adding offset if exists
            if binding_energy_flag and not region_parser[4]:
                plt.plot([x+data_offset for x in region_parser[2]],region_parser[3], label=file_name + '\n' + region_parser[1].rstrip("\n"))
                plt.xlabel('Binding Energy (eV)')
            ## In the case the data has kinetic scale and the user wants kinetic scale
            ## adding offset if exists
            if not binding_energy_flag and region_parser[4]:
                plt.plot([x + data_offset for x in region_parser[2]],region_parser[3], label=file_name + '\n' + region_parser[1].rstrip("\n"))
                plt.xlabel('Kinetic Energy (eV)')
            ## In the case the data has binding scale and the user wants kinetic scale
            ## adding offset if exists
            if not binding_energy_flag and not region_parser[4]:
                plt.plot([photon_energy + x + data_offset for x in region_parser[2]],region_parser[3], label=file_name + '\n' + region_parser[1].rstrip("\n"))
                plt.xlabel('Kinetic Energy (eV)')

            ## Revert axis if necessary
            if energy_axis_reverse_flag:
                plt.gca().invert_xaxis()
            plt.ylabel('Counts')
            plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
            plt.title('File plotted: ' + file_name)
            plt.tight_layout()

        plt.title('File plotted: ' + file_name)
        plt.tight_layout()
        plt.show()
    ## If the function was called from another function working with multiple files
    else:
        region_parser = []
        for i in range(0, number_of_regions):
            region_parser.append(parseregion(file_lines[region_boundaries[i][0]:region_boundaries[i][1]+1]))

        return region_parser

## Just rearranges the arguments in a way digestible for the plotmultiplefileswithparameters()
## and calls it
def plotmultiplefiles(args):
    parameters_argument = args[len(args)-1]
    overloaded_arguments = []
    for i in range(0, len(args)-1):
        overloaded_arguments.append(args[i])
        overloaded_arguments.append(parameters_argument)

    plotmultiplefileswithparameters(overloaded_arguments)

def plotmultiplefileswithparameters(args):
    cnt = 0
    i = 0
    plot_title = 'Files plotted:\n'
    while cnt < len(args) - 1:
        regions = plotsinglefile(args[cnt], args[cnt+1], True)
        for region_parser in regions:
            if args[cnt+1][4]:
                plt.figure(i+1)
                plot_title = 'Files plotted: ' + args[cnt]
            ## In the case the data has kinetic scale and the user wants binding scale (default)
            ## adding offset if exists
            if args[cnt+1][0] and region_parser[4]:
                plt.plot([args[cnt+1][1] - x + args[cnt+1][3] for x in region_parser[2]],region_parser[3], label=args[cnt] + '\n'+ region_parser[1].rstrip("\n"))
                plt.xlabel('Binding Energy (eV)')
            ## In the case the data has binding scale and the user wants binding scale
            ## adding offset if exists
            if args[cnt+1][0] and not region_parser[4]:
                plt.plot([x+args[cnt+1][3] for x in region_parser[2]],region_parser[3], label=args[cnt] + '\n'+ region_parser[1].rstrip("\n"))
                plt.xlabel('Binding Energy (eV)')
            ## In the case the data has kinetic scale and the user wants kinetic scale
            ## adding offset if exists
            if not args[cnt+1][0] and region_parser[4]:
                plt.plot([x+args[cnt+1][3] for x in region_parser[2]],region_parser[3], label=args[cnt] + '\n'+ region_parser[1].rstrip("\n"))
                plt.xlabel('Kinetic Energy (eV)')
            ## In the case the data has binding scale and the user wants kinetic scale
            ## adding offset if exists
            if not args[cnt+1][0] and not region_parser[4]:
                plt.plot([args[cnt+1][1] + x + args[cnt+1][3] for x in region_parser[2]],region_parser[3], label=args[cnt] + '\n'+ region_parser[1].rstrip("\n"))
                plt.xlabel('Kinetic Energy (eV)')

            ## Revert axis if necessary
            if args[cnt+1][2]:
                plt.gca().invert_xaxis()
            plt.ylabel('Counts')
            plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
            plt.title(plot_title)
            plt.tight_layout()

        if args[cnt+1][4]:
            plot_title = 'Files plotted: ' + args[cnt]
        else:
            plot_title += args[cnt] + '\n'

        cnt +=2
        i += 1
    plt.title(plot_title)
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    main()
