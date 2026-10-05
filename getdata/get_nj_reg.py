# GETTING THE DATA:
# 1. Create input directory for this script ([basepath]/getdata/input/NJ/reg/)
# 2. Run get_nj_reg_files.py to create files in this directory.
# 3. Run this program (get_nj_reg.py)

# THIS PROGRAM WAS CREATED BY CODEX WITH THE FOLLOWING PROMPT (between dashed lines)
#-----------------------------------------------------------------------------------
# Note: For the following [basepath] refers to the path containing subdirectory getdata (referred to as [basepath]/getdata which contains the python program being created. Currently [basepath] is C:\Users\bdavi\OneDrive\Documents\a.python\registration-stats\ but the program should work for any value of [basepath]
# Create python file [basepath]/getdata/get_nj_reg.py which will do the following:
# 1) Read the files in [basepath]/getdata/input/NJ/reg/
# 2) On each of these files, convert the table that each contains into a dataframe. The names of the columns in the table should be similar to COUNTY, UNA, DEM, REP, GRE, LIB, RFP, CON, NAT, CNV, SSP, and Total.  If one of the columns is named total, change it to Total.  If one of the columns is named County, change it to COUNTY.
# 3) For each dataframe, create a pandas dataframe with the following columns, in order:
# a) Year - set equal to the year of the date shown at the top of the PDF file. If no date is found, use the date indicated by the first characters of the file in one of the following formats:
#    1) YYYY-MM format where YYYY is year, MM the month between 1 and 12, and day the day shown in the PDF. If no day is shown, make it 1.
#    2) YYYY-MMDD format where YYYY is year, MM is the month between 1 and 12, and DD is the day between 1 and 31. 
#    3) YYYY-MM-DD format where YYYY is year, MM is the month between 1 and 12, and DD is the day between 1 and 31.
# b) Date - set equal to the date described in the description of Year above. Store it in M/D/YYYY format where MM is the month from 1 to 31, DD is the day from 1 to 31, and YYYY is the year (with no leading zeroes).
# c) County - set equal to column COUNTY set to uppercase
# d) Total - set equal to column Total
# e) REP - set equal to column REP
# f) DEM - set equal to column DEM
# g) LIB - set equal to column LIB
# h) GRE - set equal to column GRE
# i) CNV - set equal to column CNV
# j) CON - set equal to column CON
# k) NAT - set equal to column NAT
# l) RFP - set equal to column RFP
# m) SSP - set equal to column SSP
# n) UNA - set equal to column UNA
# o) If there is a column not covered above, add it via a column of the same name at the far right, making all prior values for that column missing
# p) Add a row with Year and Date the same as above, County equal to TOTALS, and he other columns equal to their sums.
# 4) Do step 2 and 3 for all of the files and concatenate all the the pandas dataframe to create one long pandas dataframe.
# 5) Write the one long pandas dataframe to a file named nj_reg.csv in directory [basepath]\getdata\data and [basepath]\data
#-----------------------------------------------------------------------------------

"""Convert New Jersey county voter-registration PDFs to one CSV dataset."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import pdfplumber


STANDARD_COLUMNS = [
    "Year",
    "Date",
    "County",
    "Total",
    "REP",
    "DEM",
    "LIB",
    "GRE",
    "CNV",
    "CON",
    "NAT",
    "RFP",
    "SSP",
    "UNA",
]
NJ_COUNTIES = {
    "atlantic", "bergen", "burlington", "camden", "cape may", "cumberland",
    "essex", "gloucester", "hudson", "hunterdon", "mercer", "middlesex",
    "monmouth", "morris", "ocean", "passaic", "salem", "somerset", "sussex",
    "union", "warren",
}
NUMBER = re.compile(r"\d[\d,]*")
CID_DIGIT = re.compile(r"\(cid:(\d+)\)")
DATE_IN_TEXT = re.compile(r"\b(\d{1,2}/\d{1,2}/(?:\d{2}|\d{4}))\b")


def normalize_header(name: str) -> str:
    """Normalize the two known case variants while preserving other names."""
    cleaned = name.strip().rstrip(":")
    if cleaned.lower() in {"county", "counties"}:
        return "COUNTY"
    if cleaned.lower() == "total":
        return "Total"
    return cleaned


def find_header(lines: list[str], source: Path) -> tuple[int, list[str]]:
    """Find the registration table header and return its line and columns."""
    for index, line in enumerate(lines):
        tokens = [normalize_header(token) for token in line.split()]
        if {"UNA", "DEM", "REP"}.issubset(tokens) and any(
            token.lower() == "total" for token in tokens
        ):
            if not tokens or tokens[0] != "COUNTY":
                tokens.insert(0, "COUNTY")
            return index, tokens
    raise ValueError(f"Could not find the county table header in {source.name}")


def report_date(filename: str, pdf_text: str) -> pd.Timestamp:
    """Use the date at the top of the PDF, falling back to its filename."""
    displayed = DATE_IN_TEXT.search(pdf_text)
    if displayed:
        value = displayed.group(1)
        year_format = "%Y" if len(value.rsplit("/", 1)[1]) == 4 else "%y"
        parsed = datetime.strptime(value, f"%m/%d/{year_format}")
        return pd.Timestamp(parsed.date())

    filename_formats = (
        (r"^(\d{4}-\d{2}-\d{2})(?!\d)", "%Y-%m-%d"),
        (r"^(\d{4}-\d{4})(?!\d)", "%Y-%m%d"),
        (r"^(\d{4}-\d{2})(?!\d)", "%Y-%m"),
    )
    for pattern, date_format in filename_formats:
        match = re.match(pattern, filename)
        if match:
            parsed = datetime.strptime(match.group(1), date_format)
            return pd.Timestamp(parsed.date())

    raise ValueError(
        f"Filename does not start with YYYY-MM, YYYY-MMDD, or YYYY-MM-DD: {filename}"
    )


def read_registration_pdf(source: Path) -> pd.DataFrame:
    """Extract and standardize the county table from one NJ PDF."""
    with pdfplumber.open(source) as pdf:
        page_texts = [page.extract_text(layout=True) or "" for page in pdf.pages]

    text = "\n".join(page_texts)
    # The report date is printed in the header at the top of page 1.
    top_of_first_page = "\n".join(page_texts[0].splitlines()[:20])

    # Two 2017 PDFs encode a final digit with a broken embedded font map.
    # In that font, digit glyphs 0-9 use CIDs 17-26.
    text = CID_DIGIT.sub(lambda match: str(int(match.group(1)) - 17), text)

    lines = text.splitlines()
    header_index, headers = find_header(lines, source)
    value_columns = headers[1:]
    records: list[dict[str, object]] = []

    for line in lines[header_index + 1 :]:
        matches = list(NUMBER.finditer(line))
        if len(matches) != len(value_columns):
            continue

        county = line[: matches[0].start()].strip()
        if county.casefold() not in NJ_COUNTIES:
            continue

        values = [match.group().replace(",", "") for match in matches]
        record: dict[str, object] = {"COUNTY": county}
        record.update(zip(value_columns, values))
        records.append(record)

    if not records:
        raise ValueError(f"No county rows were extracted from {source.name}")
    if len(records) != len(NJ_COUNTIES):
        found = {str(record["COUNTY"]).casefold() for record in records}
        missing_counties = sorted(NJ_COUNTIES - found)
        raise ValueError(
            f"Expected {len(NJ_COUNTIES)} counties in {source.name}, found "
            f"{len(records)}; missing: {missing_counties}"
        )

    frame = pd.DataFrame.from_records(records)
    frame.columns = [normalize_header(str(column)) for column in frame.columns]
    required = {"COUNTY", "Total", "REP", "DEM", "LIB", "GRE", "CNV", "CON", "NAT", "RFP", "SSP", "UNA"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source.name} is missing required columns: {missing}")

    for column in frame.columns:
        if column != "COUNTY":
            frame[column] = pd.to_numeric(frame[column], errors="raise")

    date = report_date(source.name, top_of_first_page)
    date_text = f"{date.month}/{date.day}/{date.year}"
    frame.insert(0, "Year", date.year)
    frame.insert(1, "Date", date_text)
    frame = frame.rename(columns={"COUNTY": "County"})
    frame["County"] = frame["County"].str.upper()

    extras = [column for column in frame.columns if column not in STANDARD_COLUMNS]
    frame = frame[STANDARD_COLUMNS + extras]

    totals: dict[str, object] = {
        "Year": date.year,
        "Date": date_text,
        "County": "TOTALS",
    }
    for column in frame.columns[3:]:
        totals[column] = frame[column].sum(min_count=1)
    return pd.concat([frame, pd.DataFrame([totals])], ignore_index=True)


def main() -> None:
    getdata_dir = Path(__file__).resolve().parent
    input_dir = getdata_dir / "input" / "NJ" / "reg"
    sources = sorted(input_dir.glob("*.pdf"), key=lambda path: path.name.casefold())
    if not sources:
        raise FileNotFoundError(f"No PDF files found in {input_dir}")

    frames: list[pd.DataFrame] = []
    for number, source in enumerate(sources, start=1):
        print(f"[{number}/{len(sources)}] {source.name}", flush=True)
        frames.append(read_registration_pdf(source))

    combined = pd.concat(frames, ignore_index=True, sort=False)
    extras = [column for column in combined.columns if column not in STANDARD_COLUMNS]
    combined = combined[STANDARD_COLUMNS + extras]

    destinations = [getdata_dir / "data" / "nj_reg.csv", getdata_dir.parent / "data" / "nj_reg.csv"]
    for destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(destination, index=False)
        print(f"Wrote {len(combined):,} rows to {destination}")


if __name__ == "__main__":
    main()
