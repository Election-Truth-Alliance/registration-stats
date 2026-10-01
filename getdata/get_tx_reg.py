# GETTING THE DATA:
# 1) Create input directory for this script ([basepath]/getdata/input/TX/reg/)
# 2) Run get_tx_reg_files.py to create files in this directory.
# 3) Run this program (get_tx_reg.py).

# THIS PROGRAM WAS CREATED BY CODEX WITH THE FOLLOWING PROMPT (between dashed lines)
#-----------------------------------------------------------------------------------
# In the following, take [basepath] to be C:\Users\bdavi\OneDrive\Documents\a.python\registration-stats but write the program so that it would work for any value of [basepath].
# Create a python program named get_tx_reg.py at [basepath]/getdata/ that will do the following:
# 1) Read the files at [basepath]/getdata/input/TX/reg/ one by one.
# 2. Each of these files should contain a table. Convert the table into a dataframe. The names of the columns in the table should be similar to 'County Name', Precincts, 'Voter Registration', 'Suspense Voters', and 'Non-Suspense Voters'.
# 3) For each dataframe, create a pandas dataframe with the following columns, in order:
#    a) Year - set equal to the year of the date specified by the YYMMDD at the beginning of the file's name.
#    b) Date - set equal to the year of the date specified by the YYMMDD at the beginning of the file's name in MM/DD/YYYY format.
#    c) County - set equal to column 'County Name'.
#    d) Total - set equal to column 'Voter Registration'
#    e) Active - set equal to column 'Non-Suspense Voters'.
#    f) Inactive - set equal to column 'Suspense Voters'.
#    g) If there is a column not covered above, add it via a column of the same name at the far right, making all prior values for that column missing
#    h) If there is a column named Precincts, delete it
#    i) If there is a row with the County equal to "STATEWIDE TOTAL" (without the quotes), change it to TOTALS.
# 4) Do step 3 for all of the files and concatenate all the the pandas dataframe to create one long pandas dataframe.
# 5) Write the one long pandas dataframe to [basepath]/getdata/data/tx_reg.csv and [basepath]/data/tx_reg.csv
#-----------------------------------------------------------------------------------

"""Combine downloaded Texas voter-registration report tables into one CSV.

This program must be stored at ``[basepath]/getdata/get_tx_reg.py``. All input
and output paths are derived from the program's own location, so ``basepath``
may be any directory.
"""

from __future__ import annotations

import re
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd


CORE_COLUMNS = ["Year", "Date", "County", "Total", "Active", "Inactive"]
STANDARD_NAMES = {
    "countyname": "County Name",
    "county": "County Name",
    "precincts": "Precincts",
    "voterregistration": "Voter Registration",
    "registeredvoters": "Voter Registration",
    "suspensevoters": "Suspense Voters",
    "suspense": "Suspense Voters",
    "nonsuspensevoters": "Non-Suspense Voters",
    "nonsuspense": "Non-Suspense Voters",
}


def clean_text(value: object) -> str:
    """Collapse whitespace and non-breaking spaces in a label."""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def column_key(value: object) -> str:
    """Create a case- and punctuation-insensitive column key."""
    return re.sub(r"[^a-z0-9]", "", clean_text(value).lower())


def flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Flatten multi-row HTML headings and standardize known column names."""
    frame = frame.copy()
    labels: list[str] = []
    for column in frame.columns:
        parts = column if isinstance(column, tuple) else (column,)
        useful = [
            clean_text(part)
            for part in parts
            if clean_text(part) and not clean_text(part).startswith("Unnamed")
        ]
        label = useful[-1] if useful else clean_text(parts[-1])
        labels.append(STANDARD_NAMES.get(column_key(label), label))

    # Retain repeated unknown columns instead of silently discarding them.
    seen: dict[str, int] = {}
    unique_labels: list[str] = []
    for label in labels:
        seen[label] = seen.get(label, 0) + 1
        unique_labels.append(label if seen[label] == 1 else f"{label}_{seen[label]}")
    frame.columns = unique_labels
    return frame


def date_from_filename(path: Path) -> datetime:
    """Read the leading YYMMDD date from a downloaded report filename."""
    match = re.match(r"^(\d{6})_", path.name)
    if not match:
        raise ValueError(f"Filename does not begin with YYMMDD_: {path.name}")
    try:
        return datetime.strptime(match.group(1), "%y%m%d")
    except ValueError as exc:
        raise ValueError(f"Invalid YYMMDD date in filename: {path.name}") from exc


def read_tables(path: Path) -> list[pd.DataFrame]:
    """Read table candidates from a downloaded HTML page or CSV file."""
    if path.suffix.lower() == ".csv":
        return [pd.read_csv(path)]
    html = path.read_text(encoding="utf-8", errors="replace")
    return pd.read_html(StringIO(html))


def registration_table(path: Path) -> pd.DataFrame:
    """Select and normalize the county registration table in one file."""
    for raw_table in read_tables(path):
        table = flatten_columns(raw_table)
        keys = {column_key(column) for column in table.columns}
        required_keys = {
            "countyname", "voterregistration", "suspensevoters",
            "nonsuspensevoters",
        }
        if required_keys.issubset(keys):
            return table
    raise ValueError(f"No voter-registration table found in {path}")


def reshape(frame: pd.DataFrame, report_date: datetime) -> pd.DataFrame:
    """Map one source table to the required long-data schema."""
    required = [
        "County Name", "Voter Registration", "Non-Suspense Voters",
        "Suspense Voters",
    ]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Source table is missing required columns: {missing}")

    data = pd.DataFrame({
        "Year": report_date.year,
        "Date": report_date.strftime("%m/%d/%Y"),
        "County": frame["County Name"],
        "Total": frame["Voter Registration"],
        "Active": frame["Non-Suspense Voters"],
        "Inactive": frame["Suspense Voters"],
    })

    counties = data["County"].astype("string").str.strip()
    data["County"] = counties.mask(
        counties.str.upper() == "STATEWIDE TOTAL", "TOTALS"
    )

    # Precincts is explicitly excluded rather than treated as an extra column.
    covered = set(required) | {"Precincts"}
    for column in frame.columns:
        if column not in covered and column not in data.columns:
            data[column] = frame[column]

    for column in ["Total", "Active", "Inactive"]:
        if column in data.columns:
            cleaned = (
                data[column].astype("string").str.replace(",", "", regex=False)
            )
            numeric = pd.to_numeric(cleaned, errors="coerce")
            if numeric.notna().any():
                data[column] = numeric.astype("Int64")
    return data


def main() -> None:
    getdata_dir = Path(__file__).resolve().parent
    basepath = getdata_dir.parent
    if getdata_dir != basepath / "getdata":
        raise RuntimeError(
            "This program must be located directly in [basepath]/getdata"
        )

    input_dir = getdata_dir / "input" / "TX" / "reg"
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    files = sorted(path for path in input_dir.iterdir() if path.is_file())
    if not files:
        raise RuntimeError(f"No input files found in {input_dir}")

    frames: list[pd.DataFrame] = []
    for path in files:
        print(f"Reading {path.name}")
        try:
            report_date = date_from_filename(path)
            frames.append(reshape(registration_table(path), report_date))
        except Exception as exc:
            raise RuntimeError(f"Failed to process {path}: {exc}") from exc

    result = pd.concat(frames, ignore_index=True, sort=False)
    extras = [column for column in result.columns if column not in CORE_COLUMNS]
    result = result[CORE_COLUMNS + extras]

    output_paths = [
        getdata_dir / "data" / "tx_reg.csv",
        basepath / "data" / "tx_reg.csv",
    ]
    for output_path in output_paths:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)
        print(f"Wrote {len(result):,} rows to {output_path}")


if __name__ == "__main__":
    main()
