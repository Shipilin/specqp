#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov  2 10:03:50 2018
@author: Shipilin
"""

from datetime import datetime
import csv
import os
from tkinter import *
from tkinter.scrolledtext import ScrolledText
from tkinter import filedialog
from tkinter import messagebox
from shutil import copyfile

## Change to the full path to logbook folder in quotation marks.
## For example:
## /Users/Shipilin/Documents/Beamtimes/November2018/P22/logbook
log_files_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logbook")
## Name of the Logbook
## IMPORTANT: Don't change unless a new logbook is supposed to be created
log_file_name = "e-logbook"










## This folders and files are created automatically for each new logging folder specified above
auxilary_folder = os.path.join(log_files_folder, "auxilary")
individual_csvs_folder = os.path.join(auxilary_folder, "individual_entries")
figures_folder = os.path.join(auxilary_folder, "figures")

## This class handles the entries and provides methods for saving them as lines of .csv files
class CSV_File_Handler:
    def __init__(self, filepath):
        self.Filepath = filepath
    def ReadFile(self):
        with open(self.Filepath,"r") as f:
            Data = f.readlines()
            f.close()
            return Data
    def ApendEntry(self, string):
        with open(self.Filepath, 'a+') as f:
            f.write("\n" + string)
            f.close()
    def GetLastEntry(self):
        with open(self.Filepath,"r") as f:
            Data = f.readlines()
            f.close()
            return Data[len(Data)-1]
    def GetLastEntryNumber(self):
        lastEntry = self.GetLastEntry().split(', ')
        return int(lastEntry[1])

## This class provides methods for making the .html version of logbook
class HTML_File_Handler:
    def __init__(self, filepath):
        self.Filepath = filepath
    def AddEntry(self, string):
        f = open(self.Filepath, "r")
        contents = f.readlines()
        f.close()
        contents.insert(7, string)
        f = open(self.Filepath, "w")
        f.writelines(contents)
        f.close()
    def CreateNew(self):
        if not os.path.exists(self.Filepath):
            f=open(self.Filepath,"w")
            f.write("""
<!DOCTYPE html>
<html>
<head>
<title>Logbook</title>
</head>
<body>
</body>
</html>
                    """)
            f.close()

## This class stores and manages information related to each log entry
class LogEntry():
    def __init__(self, logParameters):
       self.EntryNumber = logParameters[0]
       self.Author = logParameters[1]
       self.Title = logParameters[2]
       self.Body = logParameters[3]
       self.Attachment = logParameters[4]
       self.CopiedAttachment = logParameters[5].rstrip(" ")
       self.TimeStamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def __str__(self):
        return ("{0} Entry #{1}\n\n{2} ({3})\n\n{4}\n\nAttachments: {5}\n\nCopied Attachments: {6}".format(self.TimeStamp, self.EntryNumber, self.Title, self.Author, self.Body, self.Attachment, self.CopiedAttachments))

    def get_number(self):
        return self.EntryNumber

    def get_html_str(self):
        Output = "<h3><font color=""blue"">{0} Entry #{1} ({3})</font></h3>\n<b>{2}</b>\n<p>{4}</p>\n<p>Attacments: ".format(self.TimeStamp, self.EntryNumber, self.Title, self.Author, self.Body)
        for attachment in self.Attachment.split(" "):
            Output += os.path.basename(attachment) + " "
        Output = Output.rstrip(" ")
        Output += "</p>\n"
        if not (self.CopiedAttachment == ""):
            attached_files = self.CopiedAttachment.rstrip(" ").split(" ")
            for file in attached_files:
                if os.path.exists(file):
                    Output += "<img src=""{0}"" alt=""Image"">\n".format(file)
        return Output

    def get_csv_str(self):
        Output = "{0}, {1}, {2}, {3}, {4}, {5}, {6}".format(self.TimeStamp, self.EntryNumber, self.Title, self.Author, self.Body, self.Attachment, self.CopiedAttachment)
        return(Output)

    def selfcheck(self):
        if self.EntryNumber == None:
            return False
        if self.Author == None:
            return False
        if self.Title == None:
            return False
        if self.Body == None:
            return False
        if self.Attachment == None:
            return False
        if self.CopiedAttachment == None:
            return False
        return True

## This method manages Entry dialog and copying of the ttacments files
def LogEntryDialog(lastEntryParameters):
    def add_entry():
        parameters[1] = entAuthor.get()
        parameters[2] = entTitle.get()
        parameters[3] = st.get(1.0, END).replace("\n", " ").rstrip(" ")
        if not parameters[5] == "":
            parameters[4] = attachments_field.get(1.0, END).replace("\n", " ").rstrip(" ")
        else:
            parameters[4] = "No attachments"
        logWindow.quit()
    def add_attachments():
        filenames = filedialog.askopenfilenames(parent=logWindow)
        if filenames:
            output = ""
            for filename in filenames:
                for i in range(1, 100):
                    copied_figure = os.path.join(figures_folder, "Entry_{0}_Figure_{1}.png".format(parameters[0],i))
                    if os.path.exists(copied_figure):
                        continue
                    else:
                        copyfile(filename, copied_figure)
                        parameters[5] += copied_figure + " "
                        break

                output += filename + "\n"
            attachments_field.delete(1.0,END)
            attachments_field.insert(INSERT, output)
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            parameters[1] = None
            parameters[2] = None
            parameters[3] = None
            parameters[4] = None
            logWindow.destroy()

    lastEntryNumber = int(lastEntryParameters[0])
    lastEntryTitle = lastEntryParameters[1]
    lastEntryAuthor = lastEntryParameters[2]

    ## Initial parameters: Entry nubmer, lastEntryAuthor, lastEntryTitle, Body content, Attachments field, Copied figures field (initially empty)
    parameters = [str(lastEntryNumber + 1), lastEntryAuthor, lastEntryTitle, "No notes", "Only PNG files accepted", ""]

    logWindow = Tk()
    logWindow.title("Entry #{0}".format(lastEntryNumber + 1))
    Label(logWindow, text="Author:").grid(row=0, column=0)
    entAuthor = Entry(logWindow, width=70); entAuthor.grid(row=0, column=1); entAuthor.insert(0,parameters[1])
    Label(logWindow, text="Title:").grid(row=1, column=0)
    entTitle = Entry(logWindow, width=70); entTitle.grid(row=1, column=1); entTitle.insert(0,parameters[2])
    Label(logWindow, text="Body:").grid(row=2, column=0)
    st = ScrolledText(logWindow, width=70, height=7, borderwidth=2, relief="groove"); st.grid(row=2, column=1)
    Label(logWindow, text="Attachments:").grid(row=3, column=0)
    attachments_field = ScrolledText(logWindow, width=70, height=3, borderwidth=2, relief="groove"); attachments_field.grid(row=3, column=1); attachments_field.insert(INSERT, parameters[4])

    Button(logWindow, text="Add Attachments", command=(lambda: add_attachments())).grid(row=4, column=0, sticky="EW")
    Button(logWindow, text="Save Entry", command=(lambda: add_entry())).grid(row=5, column=0, sticky="EW")
    logWindow.protocol("WM_DELETE_WINDOW", on_closing)

    logWindow.mainloop()

    return parameters

def main():
    ## Creating all necessary folders
    if not os.path.exists(log_files_folder):
        os.makedirs(log_files_folder)
    if not os.path.exists(auxilary_folder):
        os.makedirs(auxilary_folder)
    if not os.path.exists(individual_csvs_folder):
        os.makedirs(individual_csvs_folder)
    if not os.path.exists(figures_folder):
        os.makedirs(figures_folder)

    ## Creating necessray files
    csv_file_path = os.path.join(auxilary_folder, log_file_name + ".csv")
    csv_file = CSV_File_Handler(csv_file_path)

    if not os.path.exists(csv_file.Filepath):
        logParameters = LogEntryDialog(["0", "Title", "Author"])
        logentry = LogEntry(logParameters)
    else:
        lastEntry = csv_file.GetLastEntry().split(', ')
        logParameters = LogEntryDialog([lastEntry[1], lastEntry[2], lastEntry[3]])
        logentry = LogEntry(logParameters)

    if logentry.selfcheck():
        csv_file.ApendEntry(logentry.get_csv_str())
        for i in range(1, 1000000):
            individual_csv_name = os.path.join(individual_csvs_folder, "Entry_{0}.csv".format(i))
            if os.path.exists(individual_csv_name):
                continue
            else:
                individual_csv_file = CSV_File_Handler(individual_csv_name)
                individual_csv_file.ApendEntry(logentry.get_csv_str())
                break

        html_file = HTML_File_Handler(os.path.join(log_files_folder, log_file_name + ".html"))
        if not os.path.exists(html_file.Filepath):
            html_file.CreateNew()
            html_file.AddEntry(logentry.get_html_str())
        else:
            html_file.AddEntry(logentry.get_html_str())
        print("Entry {0} was recorded".format(logentry.get_number()))
    else:
        print("Entry {0} was not recorded!!!".format(logentry.get_number()))

if __name__ == "__main__":
    main()
