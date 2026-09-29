# GETTING THE DATA:
# 1. Go to https://azsos.gov/elections/election-information/voter-registration-counts
# 2. Click the CSV links to download from July 2026 (Primary Election) back to January 2015
# 3. Copy downloaded files to the input directory for this script ([basedir]/registration/getdata/input/AZ/reg/)
# 4. Run this program
import os
import pandas as pd
#import numpy as np
from pathlib import Path
#import glob

#INPUT_DIR = Path("input") if Path("input").exists() else Path("registration/input")
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

filedefs = pd.DataFrame(
    [
        [4, "2015-01-01.csv"],                              #JAN 2014   G.E. 2014   JAN 2015    2015 January Voter Registration - January 1, 2015
        #[4, "2015-04-01.csv"],                             #G.E. 2014  JAN 2015    APR 2015    2015 April Voter Registration - April 1, 2015
        [4, "2015-07-01.csv"],                              #JAN 2015   APR 2015    JUL 2015    2015 July Voter Registration - July 1, 2015
        #[4, "2015-10-01.csv"],                             #APR 2015   JUL 2015    OCT 2015    2015 October Voter Registration - October 1, 2015
        #[4. "2016-01-01.xlsx"],                            #Jul-15     Oct-15      Jan-15      2016 January Voter Registration - January 1, 2016
        [4, "2016-03-01.csv"],                              #OCT 2015   JAN 2016    MAR 2016    2016 March Voter Registration - March 1, 2016
        #[4, "2016-05-17.csv"],                             #PPE 2016   Mar-16      May-16      2016 May Special Voter Registration - May 17, 2016
        #[4, "2016-08-01.csv"],                             #MAR 2016   MAY 2016    P.E. 2016   2016 Primary Election - August 30, 2016
        [4, "2016-11-08.csv"],                              #MAY 2016   P.E. 2016   G.E. 2016   2016 General Election Voter Registration - November 8, 2016
        #[4, "2017-01-01.csv"],                             #P.E. 2016  G.E. 2016   JAN 2017    2017 January Voter Registration - January 1, 2017
        #[4, "2017-04-01.csv"],                             #G.E. 2016  JAN 2017    APR 2017    2017 April Voter Registration - April 1, 2017
        [4, "2017-07-01.csv"],                              #JAN 2017   APR 2017    JULY 2017   2017 July Voter Registration - July 1, 2017
        #[4, "2017-10-01.csv"],                             #APR 2017   JULY 2017   OCT 2017    2017 October Voter Registration - October 1, 2017
        #[4, "2018-01-01.csv"],                             #JULY 2017  OCT 2017    JAN 2018    2018 January Voter Registration - January 1, 2018
        [5, "2018-03-01.csv"],                              #OCT 2017   JAN 2018    MAR 2018    2018 March Voter Registration - March 01, 2018
        #[5, "2018-08-01.csv"],                             #JAN 2018   MAR 2018    P.E. 2018   2018 Primary Election - August 28, 2018
        [5, "2018-10-01.csv"],                              #MAR 2018   P.E. 2018   G.E. 2018   2018 General Election - November 06, 2018
        #[5, "2019-01-01.csv"],                             #P.E. 2018  G.E. 2018   JAN 2019    2019 January Voter Registration - January 01, 2019
        #[5, "2019-04-01.csv"],                             #G.E. 2018  JAN 2019    APR 2019    2019 April Voter Registration - April 01, 2019
        [5, "2019-07-01.csv"],                              #JAN 2019   APR 2019    JUL 2019    2019 July Voter Registration - July 01, 2019
        #[5, "2019_october_state_voter_registration_report.csv"],#APR 2019  JUL 2019  OCT 2019   2019 October Voter Registration - October 01, 2019
        #[5, "2020_0121_january_state_voter_registration.csv"],#JUL 2019  OCT 2019  JAN 2020    2020 January Voter Registration - January 02, 2020
        [5, "2020_0218_voter_registration_statistics.csv"], #OCT 2019   JAN 2020    PPE 2020    2020 Presidential Preference Election, Voter Registration  - March 17, 2020
        #[5, "state_voter_registration_april_1_2020.csv"],  #JAN 2020   PPE 2020    APR 2020    2020 April Voter Registration - April 01, 2020
        #[5, "state_voter_registration_2020_primary.csv"],  #PPE 2020   APR 2020    P.E. 2020   2020 Primary Election - August 04, 2020
        [5, "state_voter_reigstration_2020_general.csv"],   #APR 2020   P.E. 2020   G.E. 2020   2020 General Election - November 03, 2020
        #[5, "State_Voter_Registration_January_2021.csv"],  #P.E. 2020  G.E. 2020   Jan-21      2021 January Voter Registration - January 02, 2021
        #[5, "State_Voter_Registration_April_2021.csv"],    #G.E. 2020  JAN 2021    APR 2021    2021 April Voter Registration - April 01, 2021
        [5, "State_Voter_Registration_July_2021.csv"],      #JAN 2021   APR 2021    JUL 2021    2021 July Voter Registration - July 01, 2021
        #[5, "State_Voter_Registration_October_2021.csv"],  #APR 2021   JUL 2021    OCT 2021    2021 October Voter Registration - October 01, 2021
        #[5, "State_Voter_Registration_January_2022.csv"],  #JUL 2021   OCT 2021    JAN 2022    2022 January Voter Registration - January 02, 2022
        [5, "State_Voter_Registration_April_2022.csv"],     #OCT 2021   JAN 2022    APR 2022    2022 April Voter Registration - April 01, 2022
        #[5, "State_Voter_Reigstration_2022_Primary.csv"],  #JAN 2022   APR 2022    P.E. 2022   2022 Primary Election - August 02, 2022
        #[5, "State_Voter_Registration_2022_General.csv"],  #APR 2022   P.E. 2022   G.E. 2022   2022 General Election - November 08, 2022
        [5, "state_voter_registration_january_2023.xlsx"],  #P.E. 2022  G.E. 2022   Jan-23      2023 January Voter Registration - January 02, 2023
        [5, "state_voter_registration_2023_july.xlsx"],     #Jan-23     Apr-23      Jul-23      2023 July Voter Registration - July 01, 2023
        #[5, "state_voter_registration_october_2023.xlsx"], #Apr-23     Jul-23      Oct-23      2023 Oct Voter Registration - October 01, 2023
        #[5, "state_voter_registration_jan2024.xlsx"],      #23-Jul     23-Oct      24-Jan      2024 Jan Voter Registration - January 02, 2024
        [5, "State_Voter_Reigstration_2024_PPE.xlsx"],      #Oct-23     Jan-24      PPE 2024    2024 Presidential Preference Election, Voter Registration  - March 19, 2024
        #[5, "State_Voter_Registration_April_2024.xlsx"],   #24-Jan     PPE 2024    24-Apr      2024 April Voter Registration - April 01, 2024
        #[5, "State_Voter_Registration_July_2024.csv"],     #PPE 2024   Apr-24      P.E. 2024   2024 Primary Election - July 30, 2024
        [5, "State_Voter_Registration_October_2024.csv"],   #Apr-24     P.E. 2024   G.E. 2024   2024 General Election - November 05, 2024
        #[5, "State_Voter_Registration_January_2025.csv"],  #P.E. 2024  G.E. 2024   Jan-25      2025 January Voter Registration - January 02, 2025
        #[5, "State-Voter-Registration-April-2025.csv"],    #G.E. 2024  Jan-25      Apr-25      2025 April Voter Registration - April 01, 2025
        [5, "State-Voter-Registration-July-2025.csv"],      #25-Jan     25-Apr      25-Jul      2025 July Voter Registration - July 01, 2025
        #[5, "State-Voter-Registration-October-2025.csv"],  #Apr-25     Jul-25      Oct-25      2025 October Voter Registration - October 01, 2025
        #[5, "State-Voter-Registration-January-2026.csv"],  #Jul-25     Oct-25      Jan-26      2026 January Voter Registration - January 02, 2026
        [5, "State-Voter-Registration-April-2026.csv"],     #Oct-25     Jan-26      Apr-26      2026 April Voter Registration - April 01, 2026
        [5, "State-Voter-Registration_July_2026.csv"]       #26-Jan     26-Apr      PE 2026     2026 Primary Election - July 21, 2026
    ],
    columns=["skip", "filename"]
)

mapping = {
    "JAN 2014": "2014-01-02",
    "G.E. 2014": "2014-11-04",
    "JAN 2015": "2015-01-02",
    "APR 2015": "2015-04-01",
    "JUL 2015": "2015-07-01",
    "OCT 2015": "2015-10-01",
    "JAN 2016": "2016-01-02",
    "MAR 2016": "2016-03-01",
    "MAY 2016": "2016-05-01",
    "P.E. 2016": "2016-08-30",
    "G.E. 2016": "2016-11-08",
    "JAN 2017": "2017-01-02",
    "APR 2017": "2017-04-01",
    "JUL 2018": "2017-07-01",
    "JULY 2017": "2017-07-01",
    "OCT 2017": "2017-10-01",
    "JAN 2018": "2018-01-02",
    "MAR 2018": "2018-03-01",
    "P.E. 2018": "2018-08-28",
    "G.E. 2018": "2018-11-06",
    "JAN 2019": "2019-01-02",
    "APR 2019": "2019-04-01",
    "JUL 2019": "2019-07-01",
    "OCT 2019": "2019-10-01",
    "JAN 2020": "2020-01-02",
    "PPE 2020": "2020-03-17",
    "APR 2020": "2020-04-01",
    "P.E. 2020": "2020-08-04",
    "G.E. 2020": "2020-11-03",
    "JAN 2021": "2021-01-02",
    "APR 2021": "2021-04-01",
    "JUL 2021": "2021-07-01",
    "OCT 2021": "2021-10-01",
    "JAN 2022": "2022-01-02",
    "APR 2022": "2022-04-01",
    "P.E. 2022": "2022-08-02",
    "G.E. 2022": "2022-11-08",
    "Jan-23": "2023-01-02",
    "Apr-23": "2023-04-01",
    "Jul-23": "2023-07-01",
    "Oct-23": "2023-10-01",
    "Jan-24": "2024-01-02",
    "PPE 2024": "2024-03-19",
    "Apr-24": "2024-04-01",
    "P.E. 2024": "2024-07-30",
    "G.E. 2024": "2024-11-05",
    "25-Jan": "2025-01-02",
    "25-Apr": "2025-04-01",
    "25-Jul": "2025-07-01",
    "Oct-25": "2025-10-01",
    "Jan-26": "2026-01-01",
    "Apr-26": "2026-04-01",
    "26-Jan": "2026-01-01",
    "26-Apr": "2026-04-01",
    "PE 2026": "2026-07-21"
}

def find_percentages_line(filename):
    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            if "PERCENTAGES:" in line or "Percentages:" in line:
                return lineno
    return None  # Not found

PARTIES = ["REP", "DEM", "Minor", "None"]
PARTY_CHOICES = ["DEM", "REP", "Minor", "None"]
DEFAULT_COLORS = "red3,blue3,green3,gray60"
DEFAULT_SHAPES = "15,16,17,2"

basepath =    str(Path(__file__).resolve().parent.parent) + "/"
getdatapath = str(Path(__file__).resolve().parent) + "/"
bdatapath  = basepath + "data/"
gdatapath  = getdatapath + "data/"
#precpath  = getdatapath + "precinct/"
inputpath = getdatapath + "input/"
os.makedirs(bdatapath, exist_ok=True) # create data directory in bdatapath if it doesn't exist
os.makedirs(gdatapath, exist_ok=True) # create data directory in gdatapath if it doesn't exist
#os.makedirs(precpath, exist_ok=True) # create precinct directory if it doesn't exist

ee = None
for row in filedefs.itertuples(index=False):
    print(row.skip)
    print(row.filename)
    filepath = inputpath + "AZ/reg/" + row.filename
    filetype = Path(row.filename).suffix
    if (filetype == ".csv"):
        lineno = find_percentages_line(filepath)
        if (lineno == None):
            print("====> lineno=None")
            dd = pd.read_csv(filepath, skiprows=row.skip, index_col=False, dtype=str)
        else:
            print("====> lineno="+str(lineno))
            dd = pd.read_csv(filepath, skiprows=row.skip, index_col=False, dtype=str, nrows=lineno, engine="python")
    else:
        dd = pd.read_excel(filepath, header=row.skip, index_col=False, dtype=str)
    if "County" not in dd.columns and "Precincts" in dd.columns:
        i = dd.columns.get_loc("Precincts")
        if i > 0:
            cols = list(dd.columns)
            cols[i - 1] = "County"
            dd.columns = cols
    dd = dd.loc[:, ~dd.columns.str.startswith("Unnamed")]
    dd["County"] = dd["County"].ffill()
    dd.loc[
        dd["County"].str.strip().str.upper() == "TOTALS:",
        "County"
    ] = "TOTALS"
    print(dd) #DEBUG_TMP
    dd.rename(columns={"Date/Period": "Date"}, inplace=True)
    dd.rename(columns={"TOTAL": "Total"}, inplace=True)
    dd.rename(columns={"Democratic": "DEM"}, inplace=True)
    dd.rename(columns={"Republican": "REP"}, inplace=True)
    dd.drop(columns=["Precincts"], errors="ignore", inplace=True)
    dd = dd[dd["Date"].notna()]
    dd = dd[dd["Date"] != "Date/Period"]
    dd["Date"] = dd["Date"].str.replace(" 00:00:00", "", regex=False)
    #dd = dd[dd["County"] != "Percentages:"]
    #mask = dd["County"].eq("Percentages:")
    mask = dd["County"].str.lower().eq("percentages:") #DEBUG - fix for 2018-01-01
    if mask.any():
        idx = mask.idxmax()
        dd = dd.loc[:idx-1].reset_index(drop=True)
    #dd["Date"] = pd.to_datetime(dd["Date"], format="%b-%y")
    print(dd["Date"]) #DEBUG_TMP
    dd["Date"] = dd["Date"].replace(mapping)
    dd["Year"] = dd["Date"].str[:4].astype(int)

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

    # dd["Date"] = (
    #     pd.to_datetime(dd["Date"], format="%b-%y")
    #     .dt.strftime("%Y-%m-%d")
    # )
    #dd['Date'] = pd.to_datetime(dd['Date'], format='%b-%y').dt.strftime('%Y-%m-%d')
    print(dd)
    ee = pd.concat([ee, dd], ignore_index=True)
# Remove duplicates (these 4 lines change order of data)
ee = (
    ee.drop_duplicates()
      .sort_values(["County", "Date"])
      .reset_index(drop=True)
)

cols = ee.loc[:, "Total":].columns

ee[cols] = (
    ee[cols]
    .replace({",": "", r"^\*$": "0"}, regex=True)
    .apply(pd.to_numeric)
)
outpath = gdatapath + "az_reg.csv"
ee.to_csv(outpath, index=False)
poutpath = bdatapath + "az_reg.csv"
ee.to_csv(poutpath, index=False)
