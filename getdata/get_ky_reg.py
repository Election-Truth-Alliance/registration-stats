# GETTING THE DATA:
# 1. Go to https://elect.ky.gov/Resources/Pages/Registration-Statistics.aspx
# 2. Click the link to the xls file for every month (this should be from the current year back to 2017). Ignore the 1978-2016 zip file. This should download the files to the Dowload folder.
# 3. Note for update: Only the new files
# 4. Copy the downloaded files to [basepath]/getdata/input/KY/reg/
# 5. Note for update: Only the new files need to be downloaded and copied to [basepath]/getdata/input/KY/reg/ 
# 6. Run this program

import os
import pandas as pd
#import numpy as np
from pathlib import Path
import glob

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

def proc_file(filepath, imonth, iday):
    print(f"Reading {filepath}")
    dd = pd.read_excel(filepath, sheet_name="By County", header=0)
    dd.rename(columns={"COUNTY": "County"}, inplace=True)
    dd.rename(columns={"Dem": "DEM"}, inplace=True)
    dd.rename(columns={"Rep": "REP"}, inplace=True)
    dd.rename(columns={"Registered": "Total"}, inplace=True)
    dd.drop(columns=["Precinct count"], errors="ignore", inplace=True)
    dd.drop(columns=["Male"], errors="ignore", inplace=True)
    dd.drop(columns=["Female"], errors="ignore", inplace=True)
    dd = dd[dd['County'].fillna('').str.strip() != '']
    dd.loc[dd['County'] == 'Statewide totals', 'County'] = '999 TOTALS'
    dd['County'] = dd['County'].str[4:]
    dd['Year'] = year
    dd['Date'] = str(imonth + 1)+"/"+str(iday)+"/"+str(year)
    dd['Date'] = pd.to_datetime(dd['Date'], format="%m/%d/%Y")
    #dd = dd.sort_values("Date")

    # Columns that should appear first
    first_cols = ["Year", "Date", "County", "Total", "REP", "DEM"]
    # Add any missing required columns
    for col in first_cols:
        if col not in dd.columns:
            dd[col] = pd.NA
    # Keep all other columns in their current order
    other_cols = [col for col in dd.columns if col not in first_cols]
    # Reorder the DataFrame
    dd = dd[first_cols + other_cols]
    return dd

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
first_month = 0
last_month = 12
first_year = 2017
last_year  = 2026
for year in range(first_year, 2023):
    pattern = os.path.join(inputpath, f"KY/reg/voterstats-{year}[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9].xls")
    filelist = glob.glob(pattern)
    ii = len(inputpath) + 22
    for filename in filelist:
        imonth = int(filename[ii]) * 10 + int(filename[ii+1]) - 1
        iday   = int(filename[ii+2]) * 10 + int(filename[ii+3])
        dd = proc_file(filename, imonth, iday)
        ee = pd.concat([ee, dd], ignore_index=True)
for year in range(2023, last_year+1):
    if year == 2026:
        last_month = 6
    for imonth in range(first_month, last_month):
        filepath = inputpath + "KY/reg/voterstats-"+MONTHS[imonth]+" "+str(year)+".xls"
        if not Path(filepath).exists():
            filepath = inputpath + "KY/reg/voterstats- "+MONTHS[imonth]+" "+str(year)+".xls" # handle extra space in some files
        dd = proc_file(filepath, imonth, 1)
        ee = pd.concat([ee, dd], ignore_index=True)
        # if year == 2026 and imonth == 4:
        #     break
        #ee = ee[ee["County"] != "TOTALS"]
        # Process the dataframe here``
        #print(dd.head())
outpath = datapath + "ky_reg.csv"
ee.to_csv(outpath, index=False)
poutpath = basepath + "data/ky_reg.csv"
ee.to_csv(poutpath, index=False)
