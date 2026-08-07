"""Copy or download the official Swiss Ephemeris files required by this project."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - script also works before dependencies are installed
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

FILES = (
    "sepl_18.se1",
    "semo_18.se1",
    "seas_18.se1",
)
BASE_URL = "https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe"
PROJECT_ROOT = Path(__file__).resolve().parent
DESTINATION = PROJECT_ROOT / "ephe"
DEFAULT_LOCAL_SOURCE = PROJECT_ROOT.parent / "swisseph-master" / "ephe"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_source_dirs() -> tuple[Path, ...]:
    configured = os.getenv("SWISSEPH_SOURCE_DIR")
    if configured and configured.strip():
        source = Path(configured.strip()).expanduser()
        if not source.is_absolute():
            source = PROJECT_ROOT / source
        candidates = [source]
        if source.name != "ephe":
            candidates.append(source / "ephe")
        return tuple(candidates)

    return (DEFAULT_LOCAL_SOURCE,)


def _complete_source_dir() -> Path | None:
    for source_dir in _candidate_source_dirs():
        if all((source_dir / filename).is_file() for filename in FILES):
            return source_dir
    return None


def _copy_from_local(source_dir: Path) -> None:
    for filename in FILES:
        source = source_dir / filename
        destination = DESTINATION / filename
        print(f"Copying {source}")
        shutil.copy2(source, destination)
        print(f"Saved {destination} sha256={sha256(destination)}")


def _destination_complete() -> bool:
    return all((DESTINATION / filename).is_file() for filename in FILES)


def _report_existing_destination() -> None:
    for filename in FILES:
        destination = DESTINATION / filename
        print(f"Using existing {destination} sha256={sha256(destination)}")


def _download_from_github() -> int:
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


def main() -> int:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    source_dir = _complete_source_dir()
    if source_dir is not None:
        _copy_from_local(source_dir)
        return 0

    if _destination_complete():
        _report_existing_destination()
        return 0

    return _download_from_github()


if __name__ == "__main__":
    raise SystemExit(main())
