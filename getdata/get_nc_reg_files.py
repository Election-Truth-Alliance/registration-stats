from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode

import pandas as pd
import os


FIRSTYEAR = 2017
LASTYEAR = 2026
BASE_URL = "https://vt.ncsbe.gov/RegStat"
REG_PATH = str(Path(__file__).with_name("input")) + "\\NC\\reg\\"
#OUTPUT_PATH = Path(__file__).with_name("get_nc_reg1.csv")
OUTPUT_PATH = REG_PATH + "get_nc_reg1.csv"
os.makedirs(REG_PATH, exist_ok=True)


def get_token(html: str) -> str:
    match = re.search(
        r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html
    )
    if match is None:
        raise RuntimeError("The anti-forgery token was not found.")
    return match.group(1)


COOKIE_PATH = Path(__file__).with_name(".regstat_cookies.txt")


def fetch(url: str, data: dict[str, str] | None = None, **headers) -> str:
    command = [
        "curl.exe",
        "--ssl-no-revoke",
        "-sS",
        "-L",
        "--fail-with-body",
        "--max-time",
        "90",
        "-b",
        str(COOKIE_PATH),
        "-c",
        str(COOKIE_PATH),
    ]
    for name, value in headers.items():
        command.extend(["-H", f"{name}: {value}"])
    if data is not None:
        command.extend(["--data", urlencode(data)])
    command.append(url)
    result = subprocess.run(
        command, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout


def get_dates(year: int) -> list[str]:
    html = fetch(
        f"{BASE_URL}?{urlencode({'handler': 'YearDropdownPartial', 'year': year})}",
        **{"X-Requested-With": "XMLHttpRequest"},
    )
    dates = re.findall(r'<option\s+value="(\d{2}/\d{2}/\d{4})"', html)
    if not dates:
        raise RuntimeError(f"No reporting dates found for {year}.")
    return dates


def get_table(
    token: str, year: int, edate: str
) -> pd.DataFrame:
    html = fetch(
        BASE_URL,
        {
            "RegistrationStatisticsSearchFilter.SelectedYear": str(year),
            "RegistrationStatisticsSearchFilter.SelectedDate": edate,
            "__RequestVerificationToken": token,
        },
    )
    marker = '"data":{"Data":['
    marker_at = html.find(marker)
    if marker_at < 0:
        raise RuntimeError(f"No embedded results data found for {edate}.")
    array_start = marker_at + len(marker) - 1
    depth = 0
    in_string = False
    escaped = False
    array_end = -1
    for index in range(array_start, len(html)):
        char = html[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                array_end = index + 1
                break
    if array_end < 0:
        raise RuntimeError(f"Embedded results data was incomplete for {edate}.")
    js_array = html[array_start:array_end]
    json_array = re.sub(r"([{,])([A-Za-z][A-Za-z0-9_]*):", r'\1"\2":', js_array)
    records = json.loads(json_array)
    display_columns = {
        "CountyName": "County",
        "Democrats": "Democratic",
        "Green": "Green",
        "Libertarians": "Libertarian",
        "Republicans": "Republican",
        "Unaffiliated": "Unaffiliated",
        "White": "White",
        "Black": "Black",
        "AmericanIndian": "American Indian/Alaska Native",
        "Asian": "Asian",
        "NativeHawaiian": "Native Hawaiian/Other Pacific",
        "Multiracial": "Multiracial",
        "Other": "Other",
        "Undesignated": "Undesignated",
        "Hispanic": "Hispanic",
        "Male": "Male",
        "Female": "Female",
        "Total": "Total",
    }
    frame = pd.DataFrame.from_records(records)[list(display_columns)].rename(
        columns=display_columns
    )
    filepath = REG_PATH + edate[-2:] + edate[:-4].replace("/", "") + "_nc.csv"
    frame.to_csv(filepath)
    frame["edate"] = edate
    return frame


def main() -> None:
    landing = fetch(
        BASE_URL,
        **{
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/136.0 Safari/537.36"
            )
        },
    )
    token = get_token(landing)

    frames: list[pd.DataFrame] = []
    report_count = 0
    started = time.monotonic()

    for year in range(LASTYEAR, FIRSTYEAR - 1, -1):
        dates = get_dates(year)
        print(f"{year}: {len(dates)} reporting dates", flush=True)
        for position, edate in enumerate(dates, start=1):
            frame = get_table(token, year, edate)
            frames.append(frame)
            report_count += 1
            if position % 10 == 0 or position == len(dates):
                elapsed = time.monotonic() - started
                print(
                    f"  {position:>2}/{len(dates)} dates; "
                    f"{report_count} total reports; {elapsed:.0f}s elapsed",
                    flush=True,
                )

    dd = pd.concat(frames, ignore_index=True)
    dd.to_csv(OUTPUT_PATH, index=False)
    COOKIE_PATH.unlink(missing_ok=True)
    print(
        f"Wrote {len(dd):,} rows x {len(dd.columns)} columns "
        f"to {OUTPUT_PATH}",
        flush=True,
    )


if __name__ == "__main__":
    main()
