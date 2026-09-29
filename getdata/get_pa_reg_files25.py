#!/usr/bin/env python3
"""Download daily PA voter-registration files from the Wayback Machine.

The program queries every successful capture of the PA voting-statistics page
from 2025 onward, keeps the last capture on each UTC calendar day, follows the
"Voter registration statistics by county" link in each saved page, and saves
the linked file under ``input/PA/reg`` below this script's directory.

Legacy ``.xls`` files require the optional ``xlrd`` package::

    python -m pip install xlrd

Modern ``.xlsx`` files require ``openpyxl``::

    python -m pip install openpyxl
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
import tempfile
import time
import zipfile
from datetime import date, datetime
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from typing import BinaryIO, TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


PAGE_URL = (
    "https://www.pa.gov/agencies/dos/resources/voting-and-elections-resources/"
    "voting-and-election-statistics"
)
LINK_TEXT = "Voter registration statistics by county"
CDX_URL = "https://web.archive.org/cdx/search/cdx"
REPLAY_ROOT = "https://web.archive.org/web"
PROGRAM_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROGRAM_DIR / "input" / "PA" / "reg"
LOG_FILE = PROGRAM_DIR / "get_pa_reg_files25.log"
USER_AGENT = "PA-registration-archive-downloader/2.0 (personal research)"
TIMEOUT_SECONDS = 90
MAX_ATTEMPTS = 5


class Tee:
    """Write output to both a console stream and an append-only log."""

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


def request(url: str) -> tuple[bytes, Message, str]:
    """Return a URL's bytes, response headers, and final URL with retries."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
                body = response.read()
                # Raw (``id_``) Wayback replays can retain the origin's gzip
                # content encoding. urllib deliberately does not decode it.
                if body.startswith(b"\x1f\x8b"):
                    body = gzip.decompress(body)
                return body, response.headers, response.geturl()
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt == MAX_ATTEMPTS:
                raise
        except (URLError, TimeoutError):
            if attempt == MAX_ATTEMPTS:
                raise
        delay = min(30, 2**attempt)
        print(f"  Request failed; retrying in {delay} seconds...", file=sys.stderr)
        time.sleep(delay)
    raise RuntimeError("unreachable")


def last_capture_each_day(start_year: int) -> list[dict[str, str]]:
    """Query CDX and return the last successful HTML capture on each UTC day."""
    params = {
        "url": PAGE_URL,
        "matchType": "exact",
        "from": str(start_year),
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype",
        "filter": ["statuscode:200", "mimetype:text/html"],
    }
    # doseq is needed because CDX accepts more than one filter parameter.
    query_url = f"{CDX_URL}?{urlencode(params, doseq=True)}"
    body, _, _ = request(query_url)
    payload = json.loads(body.decode("utf-8"))
    if not payload or len(payload) == 1:
        return []

    headings = payload[0]
    latest: dict[str, dict[str, str]] = {}
    for row in payload[1:]:
        capture = dict(zip(headings, row))
        timestamp = capture.get("timestamp", "")
        if re.fullmatch(r"\d{14}", timestamp):
            day = timestamp[:8]
            if day not in latest or timestamp > latest[day]["timestamp"]:
                latest[day] = capture
    return [latest[day] for day in sorted(latest)]


class LinkFinder(HTMLParser):
    """Find anchors whose normalized visible text equals the requested label."""

    def __init__(self, wanted_text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.wanted = " ".join(wanted_text.casefold().split())
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.matches: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "a":
            self.current_href = dict(attrs).get("href")
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self.current_href is None:
            return
        text = " ".join("".join(self.current_text).casefold().split())
        if text == self.wanted or self.wanted in text:
            self.matches.append(self.current_href)
        self.current_href = None
        self.current_text = []


def source_url_from_archive_href(href: str, page_url: str) -> str:
    """Convert either an ordinary or Wayback-rewritten href to its source URL."""
    absolute = urljoin(page_url, href)
    match = re.match(r"https?://web\.archive\.org/web/\d{1,14}(?:[a-z_]+)?/(https?://.+)", absolute)
    return match.group(1) if match else absolute


def linked_file_url(timestamp: str, original_page_url: str) -> str:
    """Load a page capture and return the source URL behind its requested link."""
    replay_url = f"{REPLAY_ROOT}/{timestamp}id_/{original_page_url}"
    body, headers, _ = request(replay_url)
    charset = headers.get_content_charset() or "utf-8"
    html = body.decode(charset, errors="replace")
    finder = LinkFinder(LINK_TEXT)
    finder.feed(html)
    unique_matches = list(dict.fromkeys(finder.matches))
    if not unique_matches:
        raise ValueError(f"link not found: {LINK_TEXT!r}")
    if len(unique_matches) > 1:
        print(f"  Found {len(unique_matches)} matching links; using the first one.")
    return source_url_from_archive_href(unique_matches[0], original_page_url)


def disposition_filename(headers: Message) -> str | None:
    value = headers.get_filename()
    if not value:
        return None
    return Path(unquote(value).replace("\\", "/")).name


def safe_filename(name: str) -> str:
    """Reduce a server-provided filename to a safe Windows basename."""
    name = Path(unquote(name).replace("\\", "/")).name.strip().rstrip(". ")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    if not name or name in {".", ".."}:
        return "voter_registration_statistics"
    return name


def download_linked_file(timestamp: str, file_url: str) -> tuple[bytes, str]:
    """Replay the linked resource at (or nearest to) the page capture time."""
    replay_url = f"{REPLAY_ROOT}/{timestamp}id_/{file_url}"
    body, headers, final_url = request(replay_url)
    name = disposition_filename(headers)
    if not name:
        source_path = urlparse(file_url).path or urlparse(final_url).path
        name = Path(source_path).name
    return body, safe_filename(name)


def xlsx_first_line(data: bytes) -> tuple[str, date | None]:
    try:
        import openpyxl  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Reading .xlsx files requires openpyxl; install it with: "
            f"{sys.executable} -m pip install openpyxl"
        ) from exc
    book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        sheet = book.worksheets[0]
        values: list[str] = []
        cell_date: date | None = None
        for cell in next(sheet.iter_rows(min_row=1, max_row=1), ()):
            value = cell.value
            if value is None:
                continue
            if isinstance(value, datetime):
                cell_date = value.date()
                values.append(value.strftime("%m/%d/%Y"))
            elif isinstance(value, date):
                cell_date = value
                values.append(value.strftime("%m/%d/%Y"))
            else:
                values.append(str(value).strip())
        return " ".join(filter(None, values)), cell_date
    finally:
        book.close()


def xls_first_line(data: bytes) -> tuple[str, date | None]:
    try:
        import xlrd  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Reading .xls files requires xlrd; install it with: "
            f"{sys.executable} -m pip install xlrd"
        ) from exc
    book = xlrd.open_workbook(file_contents=data, on_demand=True)
    try:
        sheet = book.sheet_by_index(0)
        values: list[str] = []
        cell_date: date | None = None
        for cell in sheet.row(0):
            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                continue
            if cell.ctype == xlrd.XL_CELL_DATE:
                parsed = xlrd.xldate.xldate_as_datetime(cell.value, book.datemode)
                cell_date = parsed.date()
                values.append(parsed.strftime("%m/%d/%Y"))
            else:
                values.append(str(cell.value).strip())
        return " ".join(filter(None, values)), cell_date
    finally:
        book.release_resources()


def text_first_line(data: bytes) -> tuple[str, None]:
    text = data.decode("utf-8-sig", errors="replace")
    row = next(csv.reader(io.StringIO(text)), [])
    return " ".join(value.strip() for value in row if value.strip()), None


def first_line(data: bytes, filename: str) -> tuple[str, date | None]:
    extension = Path(filename).suffix.casefold()
    if data.startswith(b"\xd0\xcf\x11\xe0") or extension == ".xls":
        return xls_first_line(data)
    if data.startswith(b"PK\x03\x04") or extension in {".xlsx", ".xlsm"}:
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise ValueError("download has an Excel extension but is not a valid workbook")
        return xlsx_first_line(data)
    if extension in {".csv", ".txt"}:
        return text_first_line(data)
    raise ValueError(f"unsupported downloaded file type: {extension or '(none)'}")


MONTH_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
DATE_PATTERNS = (
    (re.compile(r"(?P<value>\d{1,2}[/-]\d{1,2}[/-]\d{4})\s*$"), ("%m/%d/%Y", "%m-%d-%Y")),
    (re.compile(r"(?P<value>\d{4}-\d{1,2}-\d{1,2})\s*$"), ("%Y-%m-%d",)),
    (re.compile(rf"(?P<value>(?:{MONTH_PATTERN})\.?\s+\d{{1,2}},?\s+\d{{4}})\s*$", re.I),
     ("%B %d %Y", "%b %d %Y")),
)


def date_at_end(line: str, cell_date: date | None) -> date:
    cleaned = " ".join(line.split())
    for pattern, formats in DATE_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        value = match.group("value").replace(",", "").replace(".", "")
        value = re.sub(r"\bSept\b", "Sep", value, flags=re.I)
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass
    # A spreadsheet date cell at the end of row one may have been formatted by
    # Excel rather than stored as visible text.
    if cell_date is not None:
        return cell_date
    raise ValueError(f"no valid date found at the end of the first line: {line!r}")


def next_duplicate_path(destination: Path) -> Path:
    number = 1
    while True:
        candidate = destination.with_name(f"dup{number}_{destination.name}")
        if not candidate.exists():
            return candidate
        number += 1


def save_download(data: bytes, original_name: str, output_dir: Path) -> tuple[Path, Path | None]:
    """Validate, date-prefix, and atomically install one downloaded file."""
    line, cell_date = first_line(data, original_name)
    report_date = date_at_end(line, cell_date)
    destination = output_dir / f"{report_date:%y%m%d}_{original_name}"
    temporary_path: Path | None = None
    preserved_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=".pa_reg_", suffix=Path(original_name).suffix,
            dir=output_dir, delete=False
        ) as temporary:
            temporary.write(data)
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
    parser.add_argument("--from-year", type=int, default=2025, help="first capture year (default: 2025)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between dates (default: 1)")
    return parser.parse_args()


def run() -> int:
    args = parse_args()
    if args.from_year < 2025:
        print("Error: --from-year must be 2025 or later.", file=sys.stderr)
        return 2
    if args.delay < 0:
        print("Error: --delay cannot be negative.", file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Run started {datetime.now().astimezone().isoformat(timespec='seconds')} ===")
    print(f"Page: {PAGE_URL}")
    print(f"Output directory: {args.output_dir.resolve()}")
    captures = last_capture_each_day(args.from_year)
    print(f"Found {len(captures)} dates with successful archived page captures.")

    failures: list[str] = []
    for index, capture in enumerate(captures, start=1):
        timestamp = capture["timestamp"]
        print(f"[{index}/{len(captures)}] {timestamp[:8]} (last capture {timestamp}):")
        try:
            file_url = linked_file_url(timestamp, capture["original"])
            print(f"  Link target: {file_url}")
            data, original_name = download_linked_file(timestamp, file_url)
            destination, preserved = save_download(data, original_name, args.output_dir)
            if preserved is not None:
                print(f"  Existing file preserved as {preserved.name}")
            print(f"  Saved {destination.name}")
        except Exception as exc:
            message = f"{timestamp}: {type(exc).__name__}: {exc}"
            failures.append(message)
            print(f"  FAILED: {message}", file=sys.stderr)
        if index < len(captures) and args.delay:
            time.sleep(args.delay)

    if failures:
        print(f"\nCompleted with {len(failures)} failure(s):", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("\nAll available daily files were downloaded successfully.")
    return 0


def main() -> int:
    PROGRAM_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as log:
        original_stdout, original_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = Tee(original_stdout, log), Tee(original_stderr, log)
        try:
            print(f"Log file: {LOG_FILE}")
            return run()
        except KeyboardInterrupt:
            print("\nInterrupted by user.", file=sys.stderr)
            return 130
        except Exception as exc:
            print(f"Fatal error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            sys.stdout, sys.stderr = original_stdout, original_stderr


if __name__ == "__main__":
    raise SystemExit(main())
