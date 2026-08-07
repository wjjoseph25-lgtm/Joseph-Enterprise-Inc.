"""Download the official Swiss Ephemeris files required by this project."""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

FILES = (
    "sepl_18.se1",
    "semo_18.se1",
    "seas_18.se1",
)
BASE_URL = "https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe"
DESTINATION = Path(__file__).resolve().parent / "ephe"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        destination = DESTINATION / filename
        url = f"{BASE_URL}/{filename}"
        print(f"Downloading {url}")
        try:
            urllib.request.urlretrieve(url, destination)
        except Exception as exc:
            print(f"Failed to download {filename}: {exc}", file=sys.stderr)
            return 1
        print(f"Saved {destination} sha256={sha256(destination)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
