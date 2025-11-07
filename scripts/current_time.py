#!/usr/bin/env python3
"""Fetch the actual current date/time from WorldTimeAPI and cache it locally.

The script helps AI agents avoid relying on the host OS clock (which may drift).
It fetches https://worldtimeapi.org/api/ip by default, stores the normalized
payload under config/current_time.json, and prints a concise summary.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict
from urllib.error import URLError
from urllib.request import urlopen

DEFAULT_API_URL = "https://worldtimeapi.org/api/ip"
CACHE_PATH = Path("config/current_time.json")


def _fetch_once(api_url: str) -> Dict[str, Any]:
    with urlopen(api_url, timeout=10) as response:  # type: ignore[arg-type]
        payload = json.load(response)

    iso_datetime = payload.get("datetime")
    if not iso_datetime:
        raise ValueError("WorldTimeAPI response missing 'datetime'")

    timezone = payload.get("timezone", "UTC")
    unix_ts = payload.get("unixtime")
    utc_iso = payload.get("utc_datetime")

    now_utc = dt.datetime.now(dt.timezone.utc)
    return {
        "source": api_url,
        "timezone": timezone,
        "datetime_iso": iso_datetime,
        "utc_iso": utc_iso,
        "unix": unix_ts,
        "retrieved_at": now_utc.isoformat().replace("+00:00", "Z"),
    }


def fetch_remote_time(api_url: str, retries: int = 3, delay: float = 1.0) -> Dict[str, Any]:
    """Fetch the current time payload with simple retries."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return _fetch_once(api_url)
        except (URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay)
            else:
                raise
    # Should never reach here
    raise RuntimeError(f"Failed to fetch remote time: {last_error}")


def read_cache() -> Dict[str, Any]:
    with CACHE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_cache(data: Dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def fallback_from_system_clock() -> Dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc).astimezone()
    return {
        "source": "system_clock",
        "timezone": now.tzname() or "local",
        "datetime_iso": now.isoformat(),
        "utc_iso": now.astimezone(dt.timezone.utc).isoformat(),
        "unix": int(now.timestamp()),
        "retrieved_at": now.isoformat(),
    }


def make_human_summary(time_data: Dict[str, Any]) -> str:
    iso_value = time_data.get("datetime_iso")
    tz_name = time_data.get("timezone", "UTC")
    try:
        dt_obj = dt.datetime.fromisoformat(str(iso_value))
        human = dt_obj.strftime("%Y-%m-%d %H:%M:%S %z")
        if tz_name:
            human = f"{human} ({tz_name})"
    except Exception:
        human = f"{iso_value} ({tz_name})"
    return human


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="Skip the network call and read the cached value",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Do not update the cache; just print whatever is available",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("TIME_SYNC_URL", DEFAULT_API_URL),
        help="Override the WorldTimeAPI endpoint (default: %(default)s)",
    )
    args = parser.parse_args()

    time_data: Dict[str, Any] | None = None
    status = ""

    if not args.cache_only and not args.print_only:
        try:
            time_data = fetch_remote_time(args.api_url)
            write_cache(time_data)
            status = "fresh"
        except (URLError, TimeoutError, ValueError) as exc:
            print(
                f"[warn] Failed to fetch remote time ({exc}); falling back to cache",
                file=sys.stderr,
            )
        except Exception as exc:  # pragma: no cover - defensive catch
            print(
                f"[warn] Unexpected error fetching remote time: {exc}",
                file=sys.stderr,
            )

    if time_data is None:
        try:
            time_data = read_cache()
            status = status or "cached"
        except FileNotFoundError:
            time_data = fallback_from_system_clock()
            status = status or "system"

    human = make_human_summary(time_data)
    print(f"Current real-world time ({status}): {human}")
    print(f"Details cached at: {CACHE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
