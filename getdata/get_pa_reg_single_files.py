# THIS PROGRAM WAS CREATED BY CODEX WITH THE FOLLOWING PROMPT (between dashed lines)
#-----------------------------------------------------------------------------------
# Create a python program at [basepath]/getdata/get_pa_reg_single_files.py that does the following:
# 1. download https://web.archive.org/web/20170121151614/http://www.dos.pa.gov/_layouts/download.aspx?SourceUrl=http://www.dos.pa.gov/VotingElections/OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls to file [basepath]/getdata/input/PA/reg/170116_currentvotestats.xls
# 2. download https://web.archive.org/web/20170623175726/http://www.dos.pa.gov/_layouts/download.aspx?SourceUrl=http://www.dos.pa.gov/VotingElections/OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls to file [basepath]/getdata/input/PA/reg/170905_currentvotestats.xls
# 3. download https://web.archive.org/web/20180125012731/http://www.dos.pa.gov/_layouts/download.aspx?SourceUrl=http://www.dos.pa.gov/VotingElections/OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls to file [basepath]/getdata/input/PA/reg/180305_currentvotestats.xls
# 4. download https://web.archive.org/web/20180730054219/https://www.dos.pa.gov/_layouts/download.aspx?SourceUrl=https://www.dos.pa.gov/VotingElections/OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls to file [basepath]/getdata/input/PA/reg/190729_currentvotestats.xls
#-----------------------------------------------------------------------------------

"""Download PA registration files through the default web browser, then rename them."""

from __future__ import annotations

import shutil
import time
import webbrowser
from pathlib import Path

basepath =    str(Path(__file__).resolve().parent.parent) + "/"
getdatapath = str(Path(__file__).resolve().parent) + "/"
DOWNLOAD_DIRECTORY = Path.home() / "Downloads"
DOWNLOAD_TIMEOUT_SECONDS = 180

DOWNLOADS = (
    (
        "https://web.archive.org/web/20170121151614/http://www.dos.pa.gov/"
        "_layouts/download.aspx?SourceUrl=http://www.dos.pa.gov/VotingElections/"
        "OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls",
        Path(getdatapath + "input/PA/reg/170116_currentvotestats.xls"),
    ),
    (
        "https://web.archive.org/web/20170623175726/http://www.dos.pa.gov/"
        "_layouts/download.aspx?SourceUrl=http://www.dos.pa.gov/VotingElections/"
        "OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls",
        Path(getdatapath + "input/PA/reg/170905_currentvotestats.xls"),
    ),
    (
        "https://web.archive.org/web/20180125012731/http://www.dos.pa.gov/"
        "_layouts/download.aspx?SourceUrl=http://www.dos.pa.gov/VotingElections/"
        "OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls",
        Path(getdatapath + "input/PA/reg/180305_currentvotestats.xls"),
    ),
    (
        "https://web.archive.org/web/20180730054219/https://www.dos.pa.gov/"
        "_layouts/download.aspx?SourceUrl=https://www.dos.pa.gov/VotingElections/"
        "OtherServicesEvents/VotingElectionStatistics/Documents/currentvotestats.xls",
        Path(getdatapath + "input/PA/reg/190729_currentvotestats.xls"),
    ),
)


def file_state(directory: Path) -> dict[Path, tuple[int, int]]:
    """Return each completed Excel download's modification time and size."""
    state = {}
    for path in directory.glob("*.xls"):
        try:
            details = path.stat()
            state[path] = (details.st_mtime_ns, details.st_size)
        except FileNotFoundError:
            pass
    return state


def wait_for_browser_download(before: dict[Path, tuple[int, int]]) -> Path:
    """Wait for a new or changed XLS file whose size has stopped changing."""
    deadline = time.monotonic() + DOWNLOAD_TIMEOUT_SECONDS
    candidate = None
    previous_size = -1
    stable_checks = 0

    while time.monotonic() < deadline:
        current = file_state(DOWNLOAD_DIRECTORY)
        changed = [path for path, details in current.items() if before.get(path) != details]

        if changed:
            newest = max(changed, key=lambda path: current[path][0])
            size = current[newest][1]
            partial_exists = newest.with_suffix(newest.suffix + ".crdownload").exists()

            if newest == candidate and size == previous_size and size > 0 and not partial_exists:
                stable_checks += 1
                if stable_checks >= 2:
                    return newest
            else:
                candidate = newest
                previous_size = size
                stable_checks = 0

        time.sleep(1)

    raise TimeoutError(
        f"No completed .xls download appeared in {DOWNLOAD_DIRECTORY} "
        f"within {DOWNLOAD_TIMEOUT_SECONDS} seconds."
    )


def download_with_browser(url: str, destination: Path) -> None:
    before = file_state(DOWNLOAD_DIRECTORY)
    print(f"Opening in browser: {url}")
    if not webbrowser.open(url, new=0, autoraise=True):
        raise RuntimeError("Python could not open the default web browser.")

    downloaded_file = wait_for_browser_download(before)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    shutil.move(str(downloaded_file), str(destination))
    print(f"Moved {downloaded_file.name} to {destination}")


def main() -> None:
    if not DOWNLOAD_DIRECTORY.is_dir():
        raise FileNotFoundError(f"Download directory not found: {DOWNLOAD_DIRECTORY}")

    for url, destination in DOWNLOADS:
        download_with_browser(url, destination)


if __name__ == "__main__":
    main()
