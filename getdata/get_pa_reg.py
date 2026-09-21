# GETTING THE DATA:
# 1. Create input directory for this script ([basepath]/getdata/input/PA/reg/)
# 2. Run get_pa_reg_files.py to create files in this directory.
# 3. Run get_pa_reg_single_files.py to create 4 more files in this directory.
# 4. Run this program to create pa_reg.csv in [basepath]/getdata/data
# 5. If necessary, copy this file to [basepath]/data

import os
import pandas as pd
#import numpy as np
from datetime import datetime
from pathlib import Path

#INPUT_DIR = Path("input") if Path("input").exists() else Path("reg1/input")
# MONTHS = [
#     "January",
#     "February",
#     "March",
#     "April",
#     "May",
#     "June",
#     "July",
#     "August",
#     "September",
#     "October",
#     "November",
#     "December",
# ]

# REG_FILES = {
#     2017: "voter-registration-report-archive-2017/Party Affilation Reports - 2017.xlsx",
#     2018: "voter-registration-report-archive-2018/Party-Affilation-by-County-2018.xlsx",
#     2019: "voter-registration-report-archive-2019/party-affilation-by-county-2019.xlsx",
#     2020: "voter-registration-report-archive-2020/Party Affilation by County 2020.xlsx",
#     2021: "voter-registration-report-archive-2021/party-affiliation-by-county-2021.xlsx",
#     2022: "2022-archived/party-affiliation-by-county-2022.xlsx",
#     2023: "voter-registration-report-archive-2023/party-affiliation-by-county-2023.xlsx",
#     2024: "voter-registration-report-archive-2024/party-affiliation-by-county-2024.xlsx",
#     2025: "2025-archived/party-affiliation-by-county-2025 POST.xlsx",
#     2026: "party-affiliation-by-county-2026-post.xlsx"
# }

# PARTIES = ["REP", "DEM", "Minor", "None"]
# PARTY_CHOICES = ["DEM", "REP", "Minor", "None"]
# DEFAULT_COLORS = "red3,blue3,green3,gray60"
# DEFAULT_SHAPES = "15,16,17,2"

basepath =    str(Path(__file__).resolve().parent.parent) + "/"
getdatapath = str(Path(__file__).resolve().parent) + "/"
datapath  = getdatapath + "data/"
#precpath  = getdatapath + "precinct/"
inputpath = getdatapath + "input/"
os.makedirs(datapath, exist_ok=True) # create data directory if it doesn't exist
#os.makedirs(precpath, exist_ok=True) # create precinct directory if it doesn't exist

ee = None
inputpath_pa = inputpath + "PA/reg/"
filenames = os.listdir(inputpath_pa)
filenames = [f for f in filenames if not f.startswith("dup")]
filenames = [f for f in filenames if not f.lower().endswith(".pdf")]
for filename in filenames:
    filepath = inputpath + "PA/reg/" + filename
    print(f"Reading {filepath}")
    if filepath.lower().endswith(".csv"):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath, sheet_name=0, skiprows=1)

    #df = df.rename(columns={"County": "COUNTY"})
    df = df.rename(columns={"Count of Democratic Voters": "DEM"})
    df = df.rename(columns={"Count of Republican Voters": "REP"})
    df = df.rename(columns={"Count of No Affiliation Voters": "None"})
    df = df.rename(columns={"Count of all Other Voters": "Other"})
    df = df.rename(columns={"Total Count of All Voters": "Total"})

    df = df.rename(columns={"CountyName": "County"})
    df = df.rename(columns={"Dem": "DEM"})
    df = df.rename(columns={"Rep": "REP"})
    df = df.rename(columns={"No Aff": "None"})
    #df = df.rename(columns={"Other": "Other"})
    #df = df.rename(columns={"Total Count of All Voters": "Total"})

    #df = df.rename(columns={"County": "COUNTY"})
    df = df.rename(columns={"Democratic": "DEM"})
    df = df.rename(columns={"Republican": "REP"})
    #df = df.rename(columns={"Count of No Affiliation Voters": "None"})
    #df = df.rename(columns={"Other Parties": "Other"})
    df = df.rename(columns={"All Parties": "Total"})
    if 'None' not in df.columns:
        df['None'] = None
    if 'Other' not in df.columns:
        df['Other'] = None

    dd = df[['County', 'Total', 'REP', 'DEM', 'None', 'Other']].copy()
    date1 = datetime.strptime(filename[:6], "%y%m%d").date()
    dd.insert(0, 'Date', date1)
    dd.insert(0, 'Year', date1.year)
    dd.loc[dd['County'] == 'Totals:', 'County'] = 'TOTALS'
    dd.loc[dd['County'] == 'Total', 'County'] = 'TOTALS'
    ee = pd.concat([ee, dd], ignore_index=True)
outpath = datapath + "pa_reg.csv"
ee.to_csv(outpath, index=False)
outpath = basepath + "data/pa_reg.csv"
ee.to_csv(outpath, index=False)
