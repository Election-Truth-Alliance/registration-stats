# GETTING THE DATA:
# 1. Run get_nc_reg_files.py.
# 2. This will download PA files from 2017 to 2026 to the input directory for this script([getdata_dir]/input/2024/NC/)
# 3. Run this program (get_nc_reg.py).

import os
import pandas as pd
#import numpy as np
from pathlib import Path
import glob
import re

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

basepath =    str(Path(__file__).resolve().parent.parent) + "/"
getdatapath = str(Path(__file__).resolve().parent) + "/"
datapath  = getdatapath + "data/"
#precpath  = getdatapath + "precinct/"
inputpath = getdatapath + "input/"
os.makedirs(datapath, exist_ok=True) # create data directory if it doesn't exist
#os.makedirs(precpath, exist_ok=True) # create precinct directory if it doesn't exist

filepath = os.path.join(inputpath, "NC/reg/get_nc_reg1.csv")
print(f"Reading {filepath}")
#dd = pd.read_excel(filepath, sheet_name="By County", header=0)
dd = pd.read_csv(filepath)
dd["YEAR"] = 2000 + dd["edate"].str[-2:].astype(int)
dd["MO"] = dd["edate"].str[3:5].astype(int)
#ee = dd[["County", "Republican", "Democratic", "Libertarian", "Green", "Unaffiliated","Total"]].copy()
#dd = dd[["County", "Rep", "Dem", "Other", "Ind", "Libert", "Green", "Const", "Reform", "Soc Wk", "Registered"]]
#dd.columns = ["COUNTY", "REP", "DEM", "Other", "Ind", "Libert", "Green", "Const", "Reform", "Soc Wk", "Total"]
dd.rename(columns={"County": "COUNTY"}, inplace=True)
dd.rename(columns={"Democratic": "DEM"}, inplace=True)
dd.rename(columns={"Green": "GRN"}, inplace=True)
dd.rename(columns={"Libertarian": "LIB"}, inplace=True)
dd.rename(columns={"Republican": "REP"}, inplace=True)
dd.rename(columns={"Unaffiliated": "NONE"}, inplace=True)

#dd.rename(columns={"White": "White"}, inplace=True)
#dd.rename(columns={"Black": "Black"}, inplace=True)
dd.rename(columns={"American Indian/Alaska Native": "AmerIndian"}, inplace=True)
#dd.rename(columns={"Asian": "Asian"}, inplace=True)
dd.rename(columns={"Native Hawaiian/Other Pacific": "Pacific"}, inplace=True)
#dd.rename(columns={"Multiracial": "Multiracial"}, inplace=True)
#dd.rename(columns={"Other": "Other"}, inplace=True)
#dd.rename(columns={"Undesignated": "Undesignated"}, inplace=True)
#dd.rename(columns={"Hispanic": "Hispanic"}, inplace=True)

#dd.rename(columns={"Male": "Male"}, inplace=True)
#dd.rename(columns={"Female": "Female"}, inplace=True)
#ee.rename(columns={"Total": "Total"}, inplace=True)

#ee.drop(columns=["All_Parties"], inplace=True)
#ee = dd[dd['COUNTY'].fillna('').str.strip() != '']
dd.rename(columns={"edate": "Date"}, inplace=True)
dd['Date'] = pd.to_datetime(dd['Date'], format="%m/%d/%Y")
dd.sort_values(
    by=["Date", "COUNTY"],
    key=lambda s: pd.to_datetime(s, format="%m/%d/%Y") if s.name == "edate" else s,
    inplace=True
)
ee = dd[["COUNTY", "REP", "DEM", "GRN", "LIB", "NONE", "Total", "YEAR", "MO", "Date"]]
outpath = datapath + "nc_reg.csv"
ee.to_csv(outpath, index=False)
poutpath = basepath + "data/nc_reg.csv"
ee.to_csv(poutpath, index=False)

ee = dd[["COUNTY", "White", "Black", "Asian", "Hispanic", "AmerIndian", "Pacific", "Multiracial", "Other", "Undesignated", "Total", "YEAR", "MO", "Date"]]
outpath = datapath + "nc_race_reg.csv"
ee.to_csv(outpath, index=False)
# poutpath = basepath + "data/nc_race_reg.csv"
# ee.to_csv(poutpath, index=False)

ee = dd[["COUNTY", "Male", "Female", "Total", "YEAR", "MO", "Date"]]
outpath = datapath + "nc_gender_reg.csv"
ee.to_csv(outpath, index=False)
# poutpath = basepath + "data/nc_gender_reg.csv"
# ee.to_csv(poutpath, index=False)

# def proc_file(filepath, imonth, iday):
#     print(f"Reading {filepath}")
#     #dd = pd.read_excel(filepath, sheet_name="By County", header=0)
#     dd = pd.read_csv(filepath)
#     #dd = dd[["County", "Rep", "Dem", "Other", "Ind", "Libert", "Green", "Const", "Reform", "Soc Wk", "Registered"]]
#     #dd.columns = ["COUNTY", "REP", "DEM", "Other", "Ind", "Libert", "Green", "Const", "Reform", "Soc Wk", "Total"]
#     dd.rename(columns={"County": "COUNTY"}, inplace=True)
#     dd.rename(columns={"Democratic": "DEM"}, inplace=True)
#     dd.rename(columns={"Republican": "REP"}, inplace=True)
#     dd.rename(columns={"Libertarian": "LIB"}, inplace=True)
#     dd.rename(columns={"Other_Parties": "OTHER"}, inplace=True)
#     dd.rename(columns={"All_Parties": "Total"}, inplace=True)
#     #dd.drop(columns=["All_Parties"], inplace=True)
#     #dd = dd[dd['COUNTY'].fillna('').str.strip() != '']
#     dd.loc[dd['COUNTY'] == 'Total', 'COUNTY'] = 'TOTALS'
#     dd['YEAR'] = year
#     dd['MO'] = imonth
#     dd['Date'] = str(imonth)+"/"+str(iday)+"/"+str(year)
#     dd['Date'] = pd.to_datetime(dd['Date'], format="%m/%d/%Y")
#     #dd = dd.sort_values("Date")
#     return dd

# PARTIES = ["REP", "DEM", "Minor", "None"]
# PARTY_CHOICES = ["DEM", "REP", "Minor", "None"]
# DEFAULT_COLORS = "red3,blue3,green3,gray60"
# DEFAULT_SHAPES = "15,16,17,2"

# datapath  = getdatapath + "data/"
# #precpath  = getdatapath + "precinct/"
# inputpath = getdatapath + "input/"
# os.makedirs(datapath, exist_ok=True) # create data directory if it doesn't exist
# #os.makedirs(precpath, exist_ok=True) # create precinct directory if it doesn't exist

# ee = None
# first_year = 2017
# last_year  = 2026
# for year in range(first_year, last_year+1):
#     pattern = os.path.join(inputpath, f"PA/reg/vs-{year}[0-9][0-9][0-9][0-9].csv")
#     #filelist = glob.glob(pattern)
#     for filepath in glob.glob(pattern):
#         filename = os.path.basename(filepath)
#         m = re.fullmatch(
#             rf"vs-{year}([0-9][0-9])([0-9][0-9])\.csv",
#             filename
#         )
#         if m:
#             imonth = int(m.group(1))
#             iday =   int(m.group(2))

#         dd = proc_file(os.path.join(inputpath, "PA/reg/", filename), imonth, iday)
#         ee = pd.concat([ee, dd], ignore_index=True)
# cols = list(ee.columns)
# i_dem = cols.index("DEM")
# i_rep = cols.index("REP")
# cols[i_dem], cols[i_rep] = cols[i_rep], cols[i_dem]
# ee = ee[cols]

# outpath = datapath + "pa_reg_26_26.csv"
# ee.to_csv(outpath, index=False)
# poutpath = basepath + "data/pa_reg.csv"
# ee.to_csv(poutpath, index=False)
