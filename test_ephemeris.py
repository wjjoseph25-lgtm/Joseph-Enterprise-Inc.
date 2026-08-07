from app.ephemeris import EPHE_PATH, PROJECT_ROOT, _resolve_ephe_path, calculate_chart


def test_chart_has_all_twelve_cusps_and_timezone_dst():
    result = calculate_chart(
        year=2026,
        month=8,
        day=6,
        hour=16,
        minute=50,
        second=0,
        timezone_name="America/New_York",
        latitude=27.9506,
        longitude=-82.4572,
        house_system="R",
    )

    assert len(result["house_cusps"]) == 12
    assert [cusp["house"] for cusp in result["house_cusps"]] == list(range(1, 13))
    assert result["metadata"]["utc_offset_hours"] == -4.0
    assert result["metadata"]["house_system"] == "R"
    assert "Sun" in result["planets"]


def test_rejects_non_regiomontanus_houses():
    try:
        calculate_chart(
            year=2026,
            month=8,
            day=6,
            hour=16,
            minute=50,
            timezone_name="America/New_York",
            latitude=27.9506,
            longitude=-82.4572,
            house_system="P",
        )
    except ValueError as exc:
        assert str(exc) == "Only Regiomontanus houses are supported"
    else:
        raise AssertionError("Expected ValueError")


def test_timezone_offset_rolls_utc_date_backward_safely():
    result = calculate_chart(
        year=2026,
        month=1,
        day=1,
        hour=0,
        minute=30,
        second=0,
        timezone_offset=14,
        latitude=27.9506,
        longitude=-82.4572,
        house_system="R",
    )

    assert result["metadata"]["local_datetime"] == "2026-01-01T00:30:00+14:00"
    assert result["metadata"]["utc_datetime"] == "2025-12-31T10:30:00+00:00"
    assert len(result["house_cusps"]) == 12


def test_timezone_offset_rolls_utc_date_forward_safely():
    result = calculate_chart(
        year=2026,
        month=12,
        day=31,
        hour=23,
        minute=30,
        second=0,
        timezone_offset=-10,
        latitude=27.9506,
        longitude=-82.4572,
        house_system="R",
    )

    assert result["metadata"]["local_datetime"] == "2026-12-31T23:30:00-10:00"
    assert result["metadata"]["utc_datetime"] == "2027-01-01T09:30:00+00:00"
    assert len(result["house_cusps"]) == 12


def test_default_ephemeris_path_is_project_rooted():
    assert EPHE_PATH == str(PROJECT_ROOT / "ephe")


def test_empty_ephemeris_path_is_project_rooted(monkeypatch):
    monkeypatch.setenv("SWEPH_PATH", "")
    assert _resolve_ephe_path() == str(PROJECT_ROOT / "ephe")


def test_relative_ephemeris_path_is_project_rooted(monkeypatch):
    monkeypatch.setenv("SWEPH_PATH", "./ephe")
    assert _resolve_ephe_path() == str(PROJECT_ROOT / "ephe")
