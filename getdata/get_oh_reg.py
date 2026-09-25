# GETTING THE DATA:
# 1. Go to https://data.ohiosos.gov/portal/past-election-results
# 2. In the 'Select Year' select list, select 2026
# 3. In the 'Select Election" select list, select 'Primary/Special Election - May ...'
# 4. Click on the blue 'Voter Turnout by County' button to download turnoutbycountybyparty.xlsx into the Download folder.
# 5. Append YYMMDD_ to the filename with YY being the last 2 digits of the year, MM being the month (01-12) and DD being the day (01-31) of the date of the election.
# 6. Repeat steps 4 and 5 for every year back through 2016 and every election for which there is a button for voter turnout by county for all of the counties, skipping special elections for a subset of counties.
# 7. Click on the years in the left panel and repeat the above steps for every year from 2018 to the current year. Note that 'Active Voter' link may be an 'Active' link.
# 8. Note when updating: The above steps need only be done for new months.
# 9. Run this program.

# The following program was created with codex and the following prompt:
# ----------------------------------------------------------------------
# In the following, [basepath] is the directory that contains subdirectory getdata (designated by [basepath]/getdata/ ).
# In this case, take [basepath] to be C:\a.python\registration-stats (set to actual current path).  However, the program should work for any [basepath].
# Create a python program located at [basepath]/getdata/get_oh_reg.py that will do the following:
# 1. Read each of the files at [basepath]/getdata/input/OH/reg/ which begin with 6 integers and have an extension .xlsx
# 2. For all of the files except for the one that starts with "180508" read the file with read_excel and option skip=1 into dataframe dd.  For the file that starts with "180508" read the file with read_excel and option skip=0 into dataframe dd.
# 3. Rename the column named 'County Name' to 'County' (if it exists).
# 4. Rename the column named 'CountyNumber' to 'County' (if it exists).
# 5. Rename the column named 'Registered Voters' to 'Total'.
# 6. Delete any rows where County equals 'Percentage'
# 7. If dd contains a row with County equals 'Total', change that County to 'TOTALS'.
# 8. If dd does not contain a row with County equals 'TOTALS', add such a row with column 'Total' equal to it sum in the other rows.
# 9. Interpret the first 6 characters of the file as YYMMDD where YY is the last two digits of the year with the 1st two digits being 20. MM is the number of the month from from 01 to 12, and DD is the number of the day from 01 to 31.
# 10. Create a column named Year that contains the 4-digit year represented by YY.
# 11. Create a column named Date which equals the date represented by YYMMDD in MM/DD/YYYY format.
# 12. Create a column named All that is equal to column Total.
# 13. Create a new dataframe ee by taking the columns Year, Date, County, Total, and All of dataframe dd, in that order.
# 14. Starting with an empty dataframe, append each of these new dataframes to create one dataframe ff with columns Year, Date, County, Total, and All.
# 15. Store the final long appended dataframe into [basepath]/data/oh_reg.csv and [basepath]/getdata/data/oh_reg.csv , creating any directories necessary.

"""Combine dated Ohio voter-registration workbooks into long CSV files."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd


FILENAME_PATTERN = re.compile(r"^(\d{6}).*\.xlsx$", re.IGNORECASE)
OUTPUT_COLUMNS = ["Year", "Date", "County", "Total", "All"]


def combine_registration_files(basepath: Path) -> pd.DataFrame:
    """Read all matching workbooks and write the two requested CSV outputs."""
    input_dir = basepath / "getdata" / "input" / "OH" / "reg"
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    dated_files: list[tuple[Path, str]] = []
    for source in input_dir.iterdir():
        match = FILENAME_PATTERN.match(source.name) if source.is_file() else None
        if match:
            dated_files.append((source, match.group(1)))

    if not dated_files:
        raise FileNotFoundError(
            f"No .xlsx files beginning with six digits were found in {input_dir}"
        )

    frames: list[pd.DataFrame] = []
    for source, date_code in sorted(dated_files):
        # The specification fixes the century at 20, rather than using
        # strptime's platform-independent two-digit-year pivot.
        file_date = datetime(
            2000 + int(date_code[:2]),
            int(date_code[2:4]),
            int(date_code[4:6]),
        )
        skiprows = 0 if date_code == "180508" else 1
        dd = pd.read_excel(source, skiprows=skiprows)

        # One source workbook has an extra title row after the requested skip.
        # Promote its first data row when that row contains the real headings.
        first_row = set(dd.iloc[0].dropna().astype(str)) if not dd.empty else set()
        if {"County Name", "Registered Voters"}.issubset(first_row):
            dd.columns = dd.iloc[0]
            dd = dd.iloc[1:].reset_index(drop=True)

        dd = dd.rename(
            columns={
                "County Name": "County",
                "CountyNumber": "County",
                "Registered Voters": "Total",
            }
        )

        missing = {"County", "Total"}.difference(dd.columns)
        if missing:
            raise ValueError(
                f"{source}: required column(s) not found after renaming: "
                f"{', '.join(sorted(missing))}"
            )

        dd = dd.loc[dd["County"] != "Percentage"].copy()
        dd.loc[dd["County"] == "Total", "County"] = "TOTALS"

        if not dd["County"].eq("TOTALS").any():
            totals = pd.to_numeric(dd["Total"], errors="raise")
            total_row = pd.DataFrame(
                [{"County": "TOTALS", "Total": totals.sum()}]
            )
            dd = pd.concat([dd, total_row], ignore_index=True)

        dd["Year"] = file_date.year
        dd["Date"] = file_date.strftime("%m/%d/%Y")
        dd["All"] = dd["Total"]
        ee = dd.loc[:, OUTPUT_COLUMNS].copy()
        frames.append(ee)

    ff = pd.concat(frames, ignore_index=True)

    output_paths = (
        basepath / "data" / "oh_reg.csv",
        basepath / "getdata" / "data" / "oh_reg.csv",
    )
    for output_path in output_paths:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ff.to_csv(output_path, index=False)

    return ff


def main() -> None:
    basepath = Path(__file__).resolve().parent.parent
    combine_registration_files(basepath)


if __name__ == "__main__":
    main()
