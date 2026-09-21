# THIS PROGRAM WAS CREATED BY CODEX WITH THE FOLLOWING PROMPT (between dashed lines)
#-----------------------------------------------------------------------------------
# Create a python program named get_pa_reg_files.py that will do the following:
# 1) Go to https://web.archive.org/
# 2) Search for all instances of www.dos.pa.gov/VotingElections/OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls
# 3) Download the last daily instance of this file from every available date since 2016 into the directory [basepath]/getdata/input/PA/reg where [basepath]/getdata/ is where this program is located
# 4) After downloading each file, prepare to rename it by adding YYMMDD_ to the beginning of the existing name where YYMMDD is the date listed at the end of the first line in the file in YYMMDD format where YY is the last two digits of the year, MM is the number of the month from from 01 to 12, and DD is the number of the day from 01 to 31.
# 5) If that file already exists, rename the existing copy by prepending the current name with dupN_ where N is the smallest integer above 0 for which the file doesn't currently exist.
# 6) Now, rename the downloaded file to the name prepared in step 4.
# 7) Repeat steps 1 to 6 but use https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/voting-and-elections/voting-and-election-statistics/currentvotestats.xls as the URL to search for in step 2 and start from 2024.
# 8) Append all messages to the console to a file called get_pa_reg_files.log at [basepath]/getdata/
# 9) Save the final python program at [basepath]/getdata/
#-----------------------------------------------------------------------------------

#!/usr/bin/env python3
"""Download the last daily PA voter-registration workbook from Wayback.

Requires Python 3.9+ and xlrd (``python -m pip install xlrd``).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from typing import TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

basepath =    str(Path(__file__).resolve().parent.parent) + "/"
getdatapath = str(Path(__file__).resolve().parent) + "/"

SEARCHES = (
    (
        "http://www.dos.pa.gov/VotingElections/OtherServicesEvents/"
        "VotingElectionStatistics/Documents/currentvotestats.xls",
        2016,
    ),
    (
        "https://www.pa.gov/content/dam/copapwp-pagov/en/dos/resources/"
        "voting-and-elections/voting-and-election-statistics/currentvotestats.xls",
        2024,
    ),
)
CDX_URL = "https://web.archive.org/cdx/search/cdx"
REPLAY_ROOT = "https://web.archive.org/web"
PROGRAM_DIR = getdatapath
DEFAULT_OUTPUT_DIR = Path(
    getdatapath + "input/PA/reg"
)
LOG_FILE = PROGRAM_DIR + "get_pa_reg_files.log"
USER_AGENT = "PA-registration-archive-downloader/1.0 (personal research)"
TIMEOUT = 90
MAX_ATTEMPTS = 5


def request_bytes(url: str) -> bytes:
    """Fetch a URL with a descriptive user agent and bounded retries."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return response.read()
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt == MAX_ATTEMPTS:
                raise
        except (URLError, TimeoutError):
            if attempt == MAX_ATTEMPTS:
                raise
        delay = min(30, 2 ** attempt)
        print(f"  Request failed; retrying in {delay} seconds...", file=sys.stderr)
        time.sleep(delay)
    raise RuntimeError("unreachable")


class Tee:
    """Write text to both the original console stream and the append-only log."""

    def __init__(self, console: TextIO, log: TextIO) -> None:
        self.console = console
        self.log = log

    def write(self, text: str) -> int:
        self.console.write(text)
        self.log.write(text)
        self.log.flush()
        return len(text)

    def flush(self) -> None:
        self.console.flush()
        self.log.flush()

    def isatty(self) -> bool:
        return self.console.isatty()


def get_last_capture_per_day(target_url: str, start_year: int) -> list[dict[str, str]]:
    """Return the chronologically last successful capture for every UTC day."""
    params = {
        "url": target_url,
        "from": str(start_year),
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
    }
    payload = json.loads(request_bytes(f"{CDX_URL}?{urlencode(params)}"))
    if not payload or len(payload) == 1:
        return []

    headings = payload[0]
    captures = [dict(zip(headings, row)) for row in payload[1:]]
    latest: dict[str, dict[str, str]] = {}
    for capture in captures:
        timestamp = capture.get("timestamp", "")
        if re.fullmatch(r"\d{14}", timestamp):
            day = timestamp[:8]
            if day not in latest or timestamp > latest[day]["timestamp"]:
                latest[day] = capture
    return [latest[day] for day in sorted(latest)]


def first_excel_line(workbook_bytes: bytes) -> tuple[str, date | None]:
    """Read the first worksheet row and preserve an Excel date cell if present."""
    try:
        import xlrd  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "This program needs xlrd to read .xls files. Install it with: "
            f"{sys.executable} -m pip install xlrd"
        ) from exc

    book = xlrd.open_workbook(file_contents=workbook_bytes, on_demand=True)
    try:
        sheet = book.sheet_by_index(0)
        if sheet.nrows == 0:
            raise ValueError("the first worksheet is empty")

        values: list[str] = []
        excel_date: date | None = None
        for cell in sheet.row(0):
            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                continue
            if cell.ctype == xlrd.XL_CELL_DATE:
                dt = xlrd.xldate.xldate_as_datetime(cell.value, book.datemode)
                excel_date = dt.date()
                values.append(dt.strftime("%m/%d/%Y"))
            else:
                value = str(cell.value).strip()
                if value:
                    values.append(value)
        return " ".join(values).strip(), excel_date
    finally:
        book.release_resources()


DATE_PATTERNS = (
    (re.compile(r"(?P<m>\d{1,2})[/-](?P<d>\d{1,2})[/-](?P<y>\d{4})\s*$"), "%m/%d/%Y"),
    (re.compile(r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\s*$"), "%Y-%m-%d"),
    (re.compile(r"(?P<month>[A-Za-z]+)\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{4})\s*$"), "%B %d %Y"),
    (re.compile(r"(?P<month>[A-Za-z]{3})\.?\s+(?P<d>\d{1,2}),?\s+(?P<y>\d{4})\s*$"), "%b %d %Y"),
)


def date_at_end_of_line(line: str, excel_date: date | None) -> date:
    """Parse a date occurring at the end of the workbook's first line."""
    cleaned = re.sub(r"\s+", " ", line).strip()
    for pattern, fmt in DATE_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        text = match.group(0).strip().replace(",", "").replace(".", "")
        if fmt == "%m/%d/%Y":
            text = text.replace("-", "/")
        return datetime.strptime(text, fmt).date()
    if excel_date is not None:
        return excel_date
    raise ValueError(f"could not find a date at the end of the first line: {line!r}")


def next_duplicate_path(destination: Path) -> Path:
    """Return the first available dupN_ name, where N starts at 1."""
    number = 1
    while True:
        candidate = destination.with_name(f"dup{number}_{destination.name}")
        if not candidate.exists():
            return candidate
        number += 1


def download_capture(capture: dict[str, str], output_dir: Path) -> tuple[Path, Path | None]:
    timestamp = capture["timestamp"]
    original = capture["original"]
    replay_url = f"{REPLAY_ROOT}/{timestamp}id_/{original}"
    workbook = request_bytes(replay_url)
    first_line, excel_date = first_excel_line(workbook)
    report_date = date_at_end_of_line(first_line, excel_date)
    destination = output_dir / f"{report_date:%y%m%d}_currentvotestats.xls"

    # Put the validated download in the destination directory, then perform the
    # two requested renames. os.replace is atomic when source/destination share
    # a filesystem.
    temporary_path: Path | None = None
    preserved_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".currentvotestats_", suffix=".xls", dir=output_dir, delete=False
        ) as temporary:
            temporary.write(workbook)
            temporary_path = Path(temporary.name)

        if destination.exists():
            preserved_path = next_duplicate_path(destination)
            os.replace(destination, preserved_path)
        try:
            os.replace(temporary_path, destination)
            temporary_path = None
        except Exception:
            if preserved_path is not None and not destination.exists():
                os.replace(preserved_path, destination)
            raise
        return destination, preserved_path
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"download directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="seconds to wait between downloads (default: 1.0)",
    )
    return parser.parse_args()


def main() -> int:
    Path(PROGRAM_DIR).mkdir(parents=True, exist_ok=True)
    with Path(LOG_FILE).open("a", encoding="utf-8") as log:
        original_stdout, original_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = Tee(original_stdout, log), Tee(original_stderr, log)
        try:
            args = parse_args()
            print(f"\n=== Run started {datetime.now().astimezone().isoformat(timespec='seconds')} ===")
            print(f"Log file: {LOG_FILE}")
            if args.delay < 0:
                print("Error: --delay cannot be negative.", file=sys.stderr)
                return 2

            args.output_dir.mkdir(parents=True, exist_ok=True)
            failures: list[str] = []
            for target_url, start_year in SEARCHES:
                print(f"\nQuerying captures from {start_year} onward for:\n  {target_url}")
                try:
                    captures = get_last_capture_per_day(target_url, start_year)
                except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                    message = f"Index query failed for {target_url}: {exc}"
                    failures.append(message)
                    print(message, file=sys.stderr)
                    continue

                print(f"Found {len(captures)} daily captures.")
                for number, capture in enumerate(captures, start=1):
                    timestamp = capture["timestamp"]
                    print(f"[{number}/{len(captures)}] {timestamp}: downloading...")
                    try:
                        destination, preserved = download_capture(capture, args.output_dir)
                        if preserved is not None:
                            print(f"  Existing file preserved as {preserved.name}")
                        print(f"  Saved {destination}")
                    except Exception as exc:
                        message = f"{target_url} at {timestamp}: {exc}"
                        failures.append(message)
                        print(f"  FAILED: {message}", file=sys.stderr)
                    if number < len(captures) and args.delay:
                        time.sleep(args.delay)

            if failures:
                print(f"\nCompleted with {len(failures)} failure(s):", file=sys.stderr)
                for failure in failures:
                    print(f"  {failure}", file=sys.stderr)
                return 1
            print("\nAll available daily files were downloaded successfully.")
            return 0
        finally:
            sys.stdout, sys.stderr = original_stdout, original_stderr


if __name__ == "__main__":
    raise SystemExit(main())
