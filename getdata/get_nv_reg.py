# GETTING THE DATA:Total
# 1. Go to https://www.nvsos.gov/elections/voters/2017-statistics
# 2. Click the 'Active Voters' link for each month in the 'Voter Registration by COUNTY & PARTY' section to open the corresponding file.
# 3. Download the file to [basepath]/getdata/input/NV/reg/ but append YYMMDD_ to the filename with YY being the last 2 digits of the year, MM being the month (01-12) and DD being "01".
# 4. Click on the years in the left panel and repeat the above steps for every year from 2018 to the current year. Note that 'Active Voter' link may be an 'Active' link.
# 5. Note when updating: The above steps need only be done for new months.
# 5. Run this program.

# The following program was created with the following prompt:
# -----------------------------------------------------------
# Place the following python program at C:\Users\bdavi\OneDrive\Documents\a.python\registration-stats\getdata\ but it should work for any value of [basepath\getdata\ 
# Create a python program at [basepath]\getdata\get_nv_reg.py that does the following:
# 1. Load each of the pdf files at [basepath]\getdata\input\NV\reg, loading them one at a time.
# 1a. Interpret the first 6 characters of each filename as YYMMDD where YY is the last two digits of the year and MM is the month (from 01 to 12) associated with the file.  DD is 01 for the first day of the month.
# 2. Convert the table in each file into a pandas dataframe.  It seems like many, if not all PDF files containing the original data, can have their data extracted without using OCR.  Try to do the same task while extracting the data without using OCR.
# 3. Change column 'County Name' to County, Democratic to DEM, Republican to REP, and Libertarian as LIB.
# 4. Delete column '% of Total'.
# 5. Add column Year containing the year and column Date containing the date in yyyy-mm-dd format.
# 6. Order the columns as Year, Date, County, Total, REP, DEM, LIB, and all other parties.
# 7. Change the last County (which will likely be Statewide or Total) to TOTALS.
# 8. Go through all years 2017 to 2026 and all available months, appending the panda dataframes from each to form one long pandas dataframe.
# 9. Output the pandas dataframe to a csv file at [basepath]\getdata\data\nv_reg0.csv
# 10. Sort the party columns after Total in alphabetical order and output to a csv file at [basepath]\getdata\data\nv_reg.csv and at [basepath]\data\nv_reg.csv 
# -----------------------------------------------------------
"""Extract Nevada registration PDFs beneath this script's getdata directory.

Install pandas and pdfplumber. No OCR or companion Python module is required.
Move the entire getdata directory beneath any base path; input and output
paths are resolved from this file's location.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pdfplumber


GETDATA = Path(__file__).resolve().parent
DEFAULT_PDF_DIR = GETDATA / "input" / "NV" / "reg"
DEFAULT_CSV0 = GETDATA / "data" / "nv_reg0.csv"
DEFAULT_CSV = GETDATA / "data" / "nv_reg.csv"
DEFAULT_BASE_CSV = GETDATA.parent / "data" / "nv_reg.csv"
FIRST_COLUMNS = ("Year", "Date", "County", "Total", "REP", "DEM", "LIB")
COUNTIES = (
    "Carson City", "Churchill", "Clark", "Douglas", "Elko", "Esmeralda",
    "Eureka", "Humboldt", "Lander", "Lincoln", "Lyon", "Mineral", "Nye",
    "Pershing", "Storey", "Washoe", "White Pine", "TOTALS",
)
FILENAME = re.compile(r"^(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})_.+\.pdf$", re.I)


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def header_name(value: object) -> str | None:
    original = clean(value)
    key = re.sub(r"[^a-z]", "", original.lower())
    if not key or "%" in original or key in {"oftotal", "percentoftotal", "percentageoftotal"}:
        return None
    names = {
        "county": "County", "countyname": "County",
        "total": "Total", "totals": "Total",
        "democrat": "DEM", "democratic": "DEM",
        "republican": "REP", "libertarian": "LIB", "libertarianparty": "LIB",
        "independentamerican": "Independent American",
        "independentamericanparty": "Independent American",
        "indepamerican": "Independent American",
        "green": "Green Party", "greenparty": "Green Party",
        "naturallaw": "Natural Law Party", "naturallawparty": "Natural Law Party",
        "nonpartisan": "Nonpartisan", "other": "Other", "otherallothers": "Other",
    }
    return names.get(key, original)


def integer(value: object) -> int:
    number = clean(value).replace(",", "").replace("\u00a0", "")
    if not re.fullmatch(r"\d+", number):
        raise ValueError(f"Expected an integer, got {value!r}")
    return int(number)


def find_reports(pdf_dir: Path) -> list[tuple[int, int, Path]]:
    reports: dict[tuple[int, int], Path] = {}
    for path in pdf_dir.glob("*.pdf"):
        match = FILENAME.fullmatch(path.name)
        if match is None:
            raise ValueError(f"PDF filename does not begin YYMMDD_: {path.name}")
        year, month, day = 2000 + int(match["yy"]), int(match["mm"]), int(match["dd"])
        if not 2017 <= year <= 2026 or not 1 <= month <= 12 or day != 1:
            raise ValueError(f"Invalid report date in PDF filename: {path.name}")
        key = (year, month)
        if key in reports:
            raise ValueError(f"Duplicate PDFs for {year}-{month:02d}: {reports[key]} and {path}")
        reports[key] = path
    if not reports:
        raise FileNotFoundError(f"No PDFs found in {pdf_dir}")
    return [(year, month, reports[year, month]) for year, month in sorted(reports)]


def extract_report(path: Path, year: int, month: int) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for index, raw_headers in enumerate(table):
                    if not raw_headers or header_name(raw_headers[0]) != "County":
                        continue
                    headers = [header_name(value) for value in raw_headers]
                    if not {"County", "Total", "REP", "DEM", "LIB"}.issubset(headers):
                        continue
                    records = []
                    for cells in table[index + 1:]:
                        if not cells:
                            continue
                        county = clean(cells[0])
                        if county.lower() in {"statewide", "total", "totals"}:
                            county = "TOTALS"
                        if county not in COUNTIES:
                            continue
                        if len(cells) < len(headers):
                            raise ValueError(f"Short row for {county} in {path.name}")
                        record = {"County": county}
                        for column, value in zip(headers[1:], cells[1:]):
                            if column is not None:
                                record[column] = integer(value)
                        records.append(record)
                    if [record["County"] for record in records] != list(COUNTIES):
                        continue
                    frame = pd.DataFrame(records)
                    columns = list(FIRST_COLUMNS[2:]) + [
                        column for column in frame if column not in FIRST_COLUMNS
                    ]
                    frame = frame[columns]
                    frame.insert(0, "Date", f"{year:04d}-{month:02d}-01")
                    frame.insert(0, "Year", year)
                    parties = [column for column in frame if column not in FIRST_COLUMNS[:4]]
                    if not frame[parties].sum(axis=1).eq(frame["Total"]).all():
                        raise ValueError(f"Party counts do not sum to Total in {path.name}")
                    numeric = [column for column in frame if column not in {"Year", "Date", "County"}]
                    if not frame.iloc[:-1][numeric].sum().eq(frame.iloc[-1][numeric]).all():
                        raise ValueError(f"County sums differ from TOTALS in {path.name}")
                    return frame
    raise ValueError(f"No complete 18-row county table found in {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--csv0-output", type=Path, default=DEFAULT_CSV0)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--base-csv-output", type=Path, default=DEFAULT_BASE_CSV)
    args = parser.parse_args()

    reports = find_reports(args.pdf_dir)
    frames = []
    for year, month, path in reports:
        frame = extract_report(path, year, month)
        frames.append(frame)
        print(f"{path.name}: {len(frame)} rows", flush=True)

    combined = pd.concat(frames, ignore_index=True, sort=False)
    other = [column for column in combined if column not in FIRST_COLUMNS]
    combined = combined[list(FIRST_COLUMNS) + other]
    if len(combined) != 18 * len(reports) or combined["Date"].nunique() != len(reports):
        raise ValueError("Combined data contains missing or duplicate months")

    args.csv0_output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(args.csv0_output, index=False)
    parties = sorted((column for column in combined if column not in FIRST_COLUMNS[:4]),
                     key=str.casefold)
    alphabetized = combined[list(FIRST_COLUMNS[:4]) + parties]
    for output in (args.csv_output, args.base_csv_output):
        output.parent.mkdir(parents=True, exist_ok=True)
        alphabetized.to_csv(output, index=False)
    print(f"Wrote {len(combined):,} rows from {len(reports)} PDFs")


if __name__ == "__main__":
    main()
