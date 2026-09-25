# The following program was created with codex and the following prompt:
# ----------------------------------------------------------------------
# Note: For the following [basepath] refers to the path containing subdirectory getdata (referred to as [basepath]/getdata which contains the python program being created. Currently [basepath] is C:\Users\bdavi\OneDrive\Documents\a.python\registration-stats\ but the program should work for any value of [basepath]
# Create python file [basepath]/getdata/get_ia_reg_files.py which will do the following:
# 1) Start at https://sos.iowa.gov/voter-registration-totals-county and download the Voter Registration Totals by County pdf files starting with January 2015 and reading through all those that are available for the current year.
# 2) Download the files to [basepath]/getdata/input/IA/reg/ . Create this directory if necessary.
# 3) Create file [basepath]/getdata/input/IA/file_urls.csv which contains a dataframe with columns filename and url. Filename should equal the name of each file downloaded and url should contain the corresponding URL.

"""Download Iowa voter-registration totals by county.

The output locations are derived from this file, so the project can be moved:

    <basepath>/getdata/input/IA/reg/*.pdf
    <basepath>/getdata/input/IA/file_urls.csv
"""

from __future__ import annotations

import csv
import re
import time
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen


ARCHIVE_URL = "https://sos.iowa.gov/voter-registration-totals-county"
FIRST_YEAR = 2015
TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 3
USER_AGENT = "Mozilla/5.0 (compatible; IowaRegistrationArchiveDownloader/1.0)"


class ArchiveParser(HTMLParser):
    """Collect PDF links together with the archive heading above each link."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_year: int | None = None
        self._in_heading = False
        self._heading_text: list[str] = []
        self.links: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "h2":
            self._in_heading = True
            self._heading_text = []
            return

        if tag.lower() != "a" or self.current_year is None:
            return

        href = dict(attrs).get("href")
        if href and urlparse(href).path.lower().endswith(".pdf"):
            self.links.append((self.current_year, href))

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "h2" or not self._in_heading:
            return

        heading = "".join(self._heading_text).strip()
        match = re.fullmatch(r"\s*(\d{4})\s*", heading)
        self.current_year = int(match.group(1)) if match else None
        self._in_heading = False


def open_url(url: str):
    """Open a URL with a useful user agent and retry transient failures."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return urlopen(request, timeout=TIMEOUT_SECONDS)
        except HTTPError as exc:
            if exc.code < 500 or attempt == MAX_ATTEMPTS:
                raise
        except URLError:
            if attempt == MAX_ATTEMPTS:
                raise
        time.sleep(2 ** (attempt - 1))
    raise RuntimeError("Retry loop ended unexpectedly")


def discover_files() -> list[tuple[str, str]]:
    """Return unique ``(filename, absolute URL)`` records in page order."""
    with open_url(ARCHIVE_URL) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        page = response.read().decode(encoding, errors="replace")

    parser = ArchiveParser()
    parser.feed(page)

    current_year = date.today().year
    records: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    seen_filenames: dict[str, str] = {}

    for year, href in parser.links:
        if not FIRST_YEAR <= year <= current_year:
            continue
        url = urljoin(ARCHIVE_URL, href)
        filename = Path(unquote(urlparse(url).path)).name
        if not filename or url in seen_urls:
            continue
        if filename in seen_filenames and seen_filenames[filename] != url:
            raise ValueError(f"Two URLs use the filename {filename!r}")
        seen_urls.add(url)
        seen_filenames[filename] = url
        records.append((filename, url))

    if not records:
        raise RuntimeError(
            f"No PDF links were found for {FIRST_YEAR}-{current_year}; "
            "the Iowa SOS page structure may have changed."
        )
    return records


def download_pdf(url: str, destination: Path) -> None:
    """Download one PDF atomically, replacing an older local copy."""
    temporary_name: str | None = None
    try:
        with open_url(url) as response, NamedTemporaryFile(
            mode="w+b", dir=destination.parent, prefix=destination.name + ".", suffix=".tmp", delete=False
        ) as temporary:
            temporary_name = temporary.name
            first_chunk = response.read(64 * 1024)
            if not first_chunk.startswith(b"%PDF-"):
                raise ValueError(f"URL did not return a PDF: {url}")
            temporary.write(first_chunk)
            while chunk := response.read(64 * 1024):
                temporary.write(chunk)
        Path(temporary_name).replace(destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def write_url_csv(records: list[tuple[str, str]], destination: Path) -> None:
    """Write the URL inventory atomically with the requested column names."""
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=destination.parent,
            prefix=destination.name + ".", suffix=".tmp", delete=False
        ) as temporary:
            temporary_name = temporary.name
            writer = csv.DictWriter(temporary, fieldnames=["filename", "url"])
            writer.writeheader()
            writer.writerows({"filename": filename, "url": url} for filename, url in records)
        Path(temporary_name).replace(destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    getdata_dir = Path(__file__).resolve().parent
    ia_dir = getdata_dir / "input" / "IA"
    download_dir = ia_dir / "reg"
    download_dir.mkdir(parents=True, exist_ok=True)

    records = discover_files()
    for number, (filename, url) in enumerate(records, start=1):
        print(f"[{number}/{len(records)}] {filename}")
        download_pdf(url, download_dir / filename)

    csv_path = ia_dir / "file_urls.csv"
    write_url_csv(records, csv_path)
    print(f"Downloaded {len(records)} PDFs to {download_dir}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
