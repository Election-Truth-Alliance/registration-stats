# THIS PROGRAM WAS CREATED BY CODEX WITH THE FOLLOWING PROMPT (between dashed lines)
#-----------------------------------------------------------------------------------
# Note: For the following [basepath] refers to the path containing subdirectory getdata (referred to as [basepath]/getdata which contains the python program being created. Currently [basepath] is C:\Users\bdavi\OneDrive\Documents\a.python\registration-stats\ but the program should work for any value of [basepath]
# Create python file [basepath]/getdata/get_nj_reg_files.py which will do the following:
# 1) Navigate to all of the pages pointed to by links at https://www.nj.gov/state/elections/election-information-svrs.shtml from the page of the link labelled "April 2015 Voter Registration by County" in the '2015 Statewide Voter Registration Statistics' section up to the page of the link labelled "2026 Primary Election Day Voter Registration by County" in the '2026 Statewide Voter Registration Statistics' section.  Include only the pages for those link labels end with "Voter Registration by County".
# 2) Download the files to [basepath]/getdata/input/NJ/reg/ . Create this directory if necessary.
# 3) Create file [basepath]/getdata/input/NJ/file_urls.csv which contains a dataframe with columns filename and url. Filename should equal the name of each file downloaded and url should contain the corresponding URL.
#-----------------------------------------------------------------------------------

"""Download New Jersey voter-registration-by-county archive files.

Output paths are relative to this script, so the project can be moved:

    <basepath>/getdata/input/NJ/reg/<downloaded files>
    <basepath>/getdata/input/NJ/file_urls.csv
"""

from __future__ import annotations

import csv
import time
from html.parser import HTMLParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen


ARCHIVE_URL = "https://www.nj.gov/state/elections/election-information-svrs.shtml"
FIRST_LABEL = "April 2015 Voter Registration by County"
LAST_LABEL = "2026 Primary Election Day Voter Registration by County"
REQUIRED_SUFFIX = "Voter Registration by County"
TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 3
USER_AGENT = "Mozilla/5.0 (compatible; NJRegistrationArchiveDownloader/1.0)"


class LinkParser(HTMLParser):
    """Collect links and their visible text in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._href: str | None = None
        self._text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            label = " ".join("".join(self._text).split())
            self.links.append((label, self._href))
            self._href = None
            self._text = []


def open_url(url: str):
    """Open a URL, retrying transient server and network failures."""
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
    """Return unique ``(filename, URL)`` records for the requested link range."""
    with open_url(ARCHIVE_URL) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        page = response.read().decode(encoding, errors="replace")

    parser = LinkParser()
    parser.feed(page)

    labels = [label for label, _ in parser.links]
    try:
        first_index = labels.index(FIRST_LABEL)
        last_index = labels.index(LAST_LABEL)
    except ValueError as exc:
        missing = [label for label in (FIRST_LABEL, LAST_LABEL) if label not in labels]
        raise RuntimeError(
            "Required archive endpoint link(s) not found: " + ", ".join(missing)
        ) from exc

    low, high = sorted((first_index, last_index))
    records: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    filenames: dict[str, str] = {}

    for label, href in parser.links[low : high + 1]:
        if not label.endswith(REQUIRED_SUFFIX):
            continue
        url = urljoin(ARCHIVE_URL, href)
        filename = Path(unquote(urlparse(url).path)).name
        if not filename or url in seen_urls:
            continue
        if filename in filenames and filenames[filename] != url:
            raise ValueError(
                f"Two archive URLs use filename {filename!r}: "
                f"{filenames[filename]} and {url}"
            )
        seen_urls.add(url)
        filenames[filename] = url
        records.append((filename, url))

    if not records:
        raise RuntimeError(
            "No matching county-registration links were found in the requested range."
        )
    return records


def download_file(url: str, destination: Path) -> None:
    """Download one file atomically, replacing an older file of the same name."""
    temporary_name: str | None = None
    try:
        with open_url(url) as response, NamedTemporaryFile(
            mode="w+b",
            dir=destination.parent,
            prefix=destination.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            while chunk := response.read(64 * 1024):
                temporary.write(chunk)
        Path(temporary_name).replace(destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def write_url_csv(records: list[tuple[str, str]], destination: Path) -> None:
    """Write the requested two-column URL inventory atomically."""
    temporary_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=destination.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            writer = csv.DictWriter(temporary, fieldnames=["filename", "url"])
            writer.writeheader()
            writer.writerows(
                {"filename": filename, "url": url} for filename, url in records
            )
        Path(temporary_name).replace(destination)
        temporary_name = None
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main() -> None:
    getdata_dir = Path(__file__).resolve().parent
    nj_dir = getdata_dir / "input" / "NJ"
    download_dir = nj_dir / "reg"
    download_dir.mkdir(parents=True, exist_ok=True)

    records = discover_files()
    for number, (filename, url) in enumerate(records, start=1):
        print(f"[{number}/{len(records)}] {filename}", flush=True)
        download_file(url, download_dir / filename)

    csv_path = nj_dir / "file_urls.csv"
    write_url_csv(records, csv_path)
    print(f"Downloaded {len(records)} files to {download_dir}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
