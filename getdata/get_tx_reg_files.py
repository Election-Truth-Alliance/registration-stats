# THIS PROGRAM WAS CREATED BY CODEX WITH THE FOLLOWING PROMPT (between dashed lines)
#-----------------------------------------------------------------------------------
# In the following, take [basepath] to be C:\Users\bdavi\OneDrive\Documents\a.python\registration-stats but write the program so that it would work for any value of [basepath].
# Create a python program named get_tx_reg_files.py at [basepath]/getdata/ that will do the following:
# 1) Navigate to all of the pages pointed to by links at https://www.sos.texas.gov/elections/historical/vrfig.shtml from the page of the link labelled "January" for 2015 to the page of the link at the top for the most recent year and month.
# 2) Download each of these pages into the directory [basepath]/getdata/input/TX/reg where [basepath]/getdata/ is where this program is located, creating any necessary directories. 
# 3) To each filename prepend YYMMDD_ where YYMMDD is the date of the election in YYMMDD format where YY is the last two digits of the year, MM is the number of the month from from 01 to 12, and DD is 01.
# 4) While downloading each file, maintain a dataframe where the first column is filename and the second column is url. For each file downloaded, add a row with this information.
# 5) When all files have been downloaded, write the dataframe with the filename and url column to [basepath]/getdata/input/TX/file_urls.csv
#-----------------------------------------------------------------------------------

"""Download Texas historical voter-registration report pages.

The program is location-independent: it treats the parent of the directory
containing this file as ``basepath``.  For example, when this file is stored at
``[basepath]/getdata/get_tx_reg_files.py``, downloaded pages are written below
``[basepath]/getdata/input``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


INDEX_URL = "https://www.sos.texas.gov/elections/historical/vrfig.shtml"
START_YEAR_MONTH = (2015, 1)
MONTH_NUMBERS = {
    month.lower(): number
    for number, month in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        start=1,
    )
}


def clean_text(value: object) -> str:
    """Collapse whitespace and non-breaking spaces."""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def discover_reports(session: requests.Session) -> list[tuple[int, int, str]]:
    """Return all report links from January 2015 through the newest report."""
    response = session.get(INDEX_URL, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    reports: dict[tuple[int, int], str] = {}

    for anchor in soup.select("a[href]"):
        month_name = clean_text(anchor.get_text(" ", strip=True)).lower()
        if month_name not in MONTH_NUMBERS:
            continue

        parent_text = clean_text(anchor.parent.get_text(" ", strip=True))
        year_match = re.search(r"\b(20\d{2})\b", parent_text)
        if not year_match:
            continue

        year = int(year_match.group(1))
        month = MONTH_NUMBERS[month_name]
        if (year, month) >= START_YEAR_MONTH:
            reports[(year, month)] = urljoin(INDEX_URL, anchor["href"])

    if START_YEAR_MONTH not in reports:
        raise RuntimeError("The January 2015 starting report was not found")
    if not reports:
        raise RuntimeError("No Texas registration reports were discovered")

    return [
        (year, month, url)
        for (year, month), url in sorted(reports.items())
    ]


def source_filename(url: str) -> str:
    """Return a safe filename from a report URL."""
    filename = Path(unquote(urlparse(url).path)).name
    if not filename or filename in {".", ".."}:
        raise ValueError(f"The report URL has no usable filename: {url}")
    return filename


def main() -> None:
    getdata_dir = Path(__file__).resolve().parent
    basepath = getdata_dir.parent
    if getdata_dir != basepath / "getdata":
        raise RuntimeError(
            "This program must be located directly in [basepath]/getdata"
        )

    report_dir = getdata_dir / "input" / "TX" / "reg"
    manifest_path = getdata_dir / "input" / "TX" / "file_urls.csv"
    report_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = (
        "tx-registration-file-downloader/1.0 (public-data scraper)"
    )

    manifest_rows: list[dict[str, str]] = []
    reports = discover_reports(session)
    for year, month, url in reports:
        filename = f"{year % 100:02d}{month:02d}01_{source_filename(url)}"
        destination = report_dir / filename
        print(f"Downloading {year:04d}-{month:02d}: {url}")
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            destination.write_bytes(response.content)
            manifest_rows.append({"filename": filename, "url": url})
        except Exception as exc:
            print(
                f"ERROR: Could not process {url}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    if not manifest_rows:
        raise RuntimeError("No registration report pages were downloaded")

    manifest = pd.DataFrame(manifest_rows, columns=["filename", "url"])
    manifest.to_csv(manifest_path, index=False)
    print(
        f"Wrote {len(manifest):,} registration report pages to {report_dir}\n"
        f"Wrote URL manifest to {manifest_path}"
    )


if __name__ == "__main__":
    main()
