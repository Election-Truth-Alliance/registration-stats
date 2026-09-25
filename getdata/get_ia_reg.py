# GETTING THE DATA:
#------------------
# 1. Run get_ia_reg_files.py
# 2. Run this program (get_ia_reg.py)

# The following program was created with codex and the following prompt:
# ----------------------------------------------------------------------
# Note: For the following [basepath] refers to the path containing subdirectory getdata (referred to as [basepath]/getdata which contains the python program being created. Currently [basepath] is C:\Users\bdavi\OneDrive\Documents\a.python\registration-stats\ but the program should work for any value of [basepath]
# Create python file [basepath]/getdata/get_ia_reg.py which will do the following:
# 1) Read each of the pdf files in [basepath]/getdata/input/IA/reg/ and extract the dataframe contained in each.
# 2) Do not use OCR and, if there is a problem extracting the dataframes without OCR, notify me.
# 3) For each file, create a pandas dataframe with the following columns, in order:
# a) Year - set equal to the year of the date in the upper right corner of the first page
# b) Date - set equal to the date in the upper right corner of the first page in MM/DD/YYYY format
# c) County - set equal to County
# d) Total - set equal to Total Active or the equivalent
# e) REP - set equal to Rep Active or Republican Active or the equivalent
# f) DEM - set equal to Dem Active or Democratic Active or the equivalent
# g) No_Party - set equal to No Party Active or the equivalent
# h) Other - set equal to No Other Active or the equivalent
# 4) Do step 3 for all of the files and concatenate all the the pandas dataframe to create one long pandas dataframe.
# 5) Write the one long pandas dataframe to a file at [basepath]/data/ia_reg.csv and [basepath]/getdata/data/ia_reg.csv

"""Extract Iowa county voter-registration totals from downloaded PDFs.

This script uses the embedded PDF text only; it does not perform OCR.
Input and output paths are derived from the location of this file, making the
script independent of the current working directory and project location.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pandas as pd
import pdfplumber


OUTPUT_COLUMNS = ["Year", "Date", "County", "Total", "REP", "DEM", "No_Party", "Other"]
DATE_PATTERN = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
# A few older PDFs omit the space between a county and its first value, and
# one omits the label on the statewide Grand row. Restricting the label to
# name characters lets embedded text still be parsed safely without OCR.
ROW_PATTERN = re.compile(
    r"^([A-Za-z][A-Za-z .'-]*?)?\s*((?:[\d,]+\s+){8,12}[\d,]+)$"
)


class ExtractionError(RuntimeError):
    """Raised when a PDF table cannot be extracted safely without OCR."""


def read_pdf_text(pdf_path: Path) -> tuple[str, list[str]]:
    """Return first-page text and the text from every page."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                raise ExtractionError("the PDF has no pages")
            page_texts = [page.extract_text() or "" for page in pdf.pages]
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"could not read the PDF: {exc}") from exc

    if not page_texts[0].strip():
        raise ExtractionError(
            "the first page has no extractable text; OCR may be required"
        )
    return page_texts[0], page_texts


def get_report_date(first_page_text: str) -> datetime:
    """Extract and validate the report date printed on the first page."""
    match = DATE_PATTERN.search(first_page_text)
    if not match:
        raise ExtractionError(
            "the report date could not be extracted from the first page without OCR"
        )
    try:
        return datetime.strptime(match.group(1), "%m/%d/%Y")
    except ValueError as exc:
        raise ExtractionError(f"invalid report date {match.group(1)!r}") from exc


def active_schema(first_page_text: str) -> list[str]:
    """Determine the order of active-registration columns from the header."""
    header_lines: list[str] = []
    for line in first_page_text.splitlines():
        if ROW_PATTERN.fullmatch(line.strip()):
            break
        header_lines.append(line)
    header = " ".join(header_lines).lower()

    if "county" not in header or "total" not in header:
        raise ExtractionError("the active-registration table header was not recognized")

    # The 2012-2014 reports use abbreviated headings and put REP before DEM:
    #     REP DEM NP OTH TOTAL REP DEM NP OTH TOTAL TOTAL
    if re.search(r"\brep\s+dem\s+np\s+oth\s+total\b", header):
        return ["REP", "DEM", "No_Party", "Other", "Total"]

    if "active" not in header:
        raise ExtractionError("the active-registration table header was not recognized")

    # Reports in part of the archive have a distinct Libertarian column. It is
    # retained in Total but is not requested as a separate output column.
    if "libertarian" in header:
        return ["DEM", "REP", "Libertarian", "No_Party", "Other", "Total"]
    return ["DEM", "REP", "No_Party", "Other", "Total"]


def parse_number(value: str) -> int:
    return int(value.replace(",", ""))


def repair_old_active_values(tokens: list[str]) -> list[int] | None:
    """Split joined 2012 active values using their printed Total as a check."""
    # The six columns after Total Active are intact in the affected PDF. The
    # active section must expand to REP, DEM, NP, OTH, TOTAL.
    active_tokens = [token.replace(",", "") for token in tokens[:-6]]
    inactive = [parse_number(token) for token in tokens[-6:]]
    missing = 5 - len(active_tokens)
    if missing <= 0:
        return None

    candidates: list[list[int]] = []
    for token_index, token in enumerate(active_tokens):
        pieces_needed = missing + 1
        if len(token) < pieces_needed:
            continue
        for cuts in combinations(range(1, len(token)), pieces_needed - 1):
            boundaries = (0, *cuts, len(token))
            pieces = [token[boundaries[i] : boundaries[i + 1]] for i in range(pieces_needed)]
            if any(len(piece) > 1 and piece.startswith("0") for piece in pieces):
                continue
            expanded = active_tokens[:token_index] + pieces + active_tokens[token_index + 1 :]
            values = [int(value) for value in expanded]
            if len(values) == 5 and sum(values[:4]) == values[4]:
                candidates.append(values + inactive)

    return candidates[0] if len(candidates) == 1 else None


def extract_rows(page_texts: list[str], schema: list[str]) -> list[dict[str, int | str]]:
    """Extract county rows and validate the active totals."""
    rows: list[dict[str, int | str]] = []
    seen_counties: set[str] = set()
    expected_values = 13 if "Libertarian" in schema else 11

    for page_text in page_texts:
        for raw_line in page_text.splitlines():
            match = ROW_PATTERN.fullmatch(raw_line.strip())
            if not match:
                continue

            county = " ".join(match.group(1).split()) if match.group(1) else "Grand"
            value_tokens = match.group(2).split()
            values = [parse_number(value) for value in value_tokens]
            if len(values) != expected_values and schema == ["REP", "DEM", "No_Party", "Other", "Total"]:
                repaired = repair_old_active_values(value_tokens)
                if repaired is not None:
                    values = repaired
            if len(values) != expected_values:
                continue
            if county in seen_counties:
                raise ExtractionError(f"duplicate row for county {county!r}")

            active = dict(zip(schema, values[: len(schema)]))
            component_names = [name for name in schema if name != "Total"]
            component_total = sum(active[name] for name in component_names)
            if component_total != active["Total"]:
                raise ExtractionError(
                    f"active total does not match party columns for {county!r}: "
                    f"{component_total} != {active['Total']}"
                )

            seen_counties.add(county)
            rows.append(
                {
                    "County": county,
                    "Total": active["Total"],
                    "REP": active["REP"],
                    "DEM": active["DEM"],
                    "No_Party": active["No_Party"],
                    "Other": active["Other"],
                }
            )

    # Iowa has 99 counties, and each report also contains one statewide Totals
    # row. This check prevents a partially extracted PDF from entering the CSV.
    if len(rows) != 100:
        raise ExtractionError(
            f"expected 100 table rows (99 counties plus Totals), extracted {len(rows)}; "
            "the layout may have changed or OCR may be required"
        )
    total_labels = {"grand", "grand total", "total", "totals"}
    if not any(row["County"].lower() in total_labels for row in rows):
        raise ExtractionError("the statewide Totals row was not extracted")
    return rows


def extract_pdf(pdf_path: Path) -> pd.DataFrame:
    """Extract one Iowa registration PDF into the requested columns."""
    first_page_text, page_texts = read_pdf_text(pdf_path)
    report_date = get_report_date(first_page_text)
    schema = active_schema(first_page_text)
    rows = extract_rows(page_texts, schema)

    frame = pd.DataFrame(rows)
    frame.insert(0, "Date", report_date.strftime("%m/%d/%Y"))
    frame.insert(0, "Year", report_date.year)
    return frame[OUTPUT_COLUMNS]


def main() -> None:
    getdata_dir = Path(__file__).resolve().parent
    base_dir = getdata_dir.parent
    input_dir = getdata_dir / "input" / "IA" / "reg"
    output_paths = [base_dir / "data" / "ia_reg.csv", getdata_dir / "data" / "ia_reg.csv"]

    pdf_paths = sorted(input_dir.glob("*.pdf"), key=lambda path: path.name.lower())
    if not pdf_paths:
        raise SystemExit(f"No PDF files found in {input_dir}")

    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    for number, pdf_path in enumerate(pdf_paths, start=1):
        print(f"[{number}/{len(pdf_paths)}] Extracting {pdf_path.name}")
        try:
            frames.append(extract_pdf(pdf_path))
        except ExtractionError as exc:
            errors.append(f"{pdf_path.name}: {exc}")

    if errors:
        details = "\n".join(f"  - {error}" for error in errors)
        raise SystemExit(
            "Data extraction failed without OCR for the following PDFs:\n" + details
        )

    combined = pd.concat(frames, ignore_index=True)
    combined.sort_values(["Date", "County"], key=lambda values: (
        pd.to_datetime(values, format="%m/%d/%Y") if values.name == "Date" else values
    ), inplace=True)
    combined.reset_index(drop=True, inplace=True)

    for output_path in output_paths:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(output_path, index=False)
        print(f"Wrote {len(combined):,} rows to {output_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
