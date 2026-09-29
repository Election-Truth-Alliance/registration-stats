# GETTING THE DATA:
# 1. Go to https://dos.fl.gov/elections/data-statistics/voter-registration-statistics/voter-registration-reports/
# 2. Click on the 'County and Party - Excel link in the 'Current Voter Registration Data section' to download file
# 3. Copy file (party-affiliation-by-county-2026-post.xlsx) to input directory for this script ([basedir]/registration/getdata/input/FL/reg/)
# 4. Click the links under Archived Monthly Reports from 2025 back to 2017 to download those zip files
# 5. Copy downloaded zip files to the input directory for this script ([basedir]/registration/getdata/input/FL/reg/)
# 6. Unzip all of the zip files into the same directory, creating subdirectories with the same name as the zip files
# 7. Run the program
import os
import pandas as pd
#import numpy as np
from pathlib import Path

#INPUT_DIR = Path("input") if Path("input").exists() else Path("reg1/input")
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

REG_FILES = {
    2017: "voter-registration-report-archive-2017/Party Affilation Reports - 2017.xlsx",
    2018: "voter-registration-report-archive-2018/Party-Affilation-by-County-2018.xlsx",
    2019: "voter-registration-report-archive-2019/party-affilation-by-county-2019.xlsx",
    2020: "voter-registration-report-archive-2020/Party Affilation by County 2020.xlsx",
    2021: "voter-registration-report-archive-2021/party-affiliation-by-county-2021.xlsx",
    2022: "2022-archived/party-affiliation-by-county-2022.xlsx",
    2023: "voter-registration-report-archive-2023/party-affiliation-by-county-2023.xlsx",
    2024: "voter-registration-report-archive-2024/party-affiliation-by-county-2024.xlsx",
    2025: "2025-archived/party-affiliation-by-county-2025 POST.xlsx",
    2026: "party-affiliation-by-county-2026-post.xlsx"
}

PARTIES = ["REP", "DEM", "Minor", "None"]
PARTY_CHOICES = ["DEM", "REP", "Minor", "None"]
DEFAULT_COLORS = "red3,blue3,green3,gray60"
DEFAULT_SHAPES = "15,16,17,2"

basepath =    str(Path(__file__).resolve().parent.parent) + "/"
getdatapath = str(Path(__file__).resolve().parent) + "/"
datapath  = getdatapath + "data/"
#precpath  = getdatapath + "precinct/"
inputpath = getdatapath + "input/"
os.makedirs(datapath, exist_ok=True) # create data directory if it doesn't exist
#os.makedirs(precpath, exist_ok=True) # create precinct directory if it doesn't exist

ee = None
for year, filename in REG_FILES.items():
    #filepath = inputpath + "FL/reg/voter-registration-report-archive-" + str(year) + "/" + filename
    filepath = inputpath + "FL/reg/" + filename
    print(f"Reading {filepath}")
    max_month = 12
    if year == 2026:
        max_month = 8 #DEBUG UPDATE
    for i in range(0, max_month):
        mdate = pd.read_excel(filepath, sheet_name=MONTHS[i], header=0)
        sdate = str(mdate.iloc[0, 0])
        dd = pd.read_excel(filepath, sheet_name=MONTHS[i], header=3)
        dd.columns = ["COUNTY", "REP", "DEM", "Minor", "None", "Total"]
        dd['YEAR'] = year
        dd['MO'] = i + 1
        dd['Date'] = sdate
        dd['Date'] = dd['Date'].str.replace(r"^Data as of ", "", regex=True)
        ee = pd.concat([ee, dd], ignore_index=True)
        #ee = ee[ee["COUNTY"] != "TOTALS"]
        # Process the dataframe here
        #print(dd.head())
outpath = datapath + "fl_reg.csv"
ee.to_csv(outpath, index=False)
outpath = basepath + "data/fl_reg.csv"
ee.to_csv(outpath, index=False)
