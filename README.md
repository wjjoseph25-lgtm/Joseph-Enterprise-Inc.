# Swiss Ephemeris data

Place these official files directly in this directory:

- `sepl_18.se1`
- `semo_18.se1`
- `seas_18.se1`

Run `python download_ephe.py` from the project root to download them from the official Astrodienst GitHub repository.

`seas_18.se1` is already present in this package. The build should verify all three files before production deployment.
