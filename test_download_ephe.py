import download_ephe


def test_download_ephe_detects_configured_source_root(monkeypatch, tmp_path):
    source_root = tmp_path / "swisseph-master"
    source_ephe = source_root / "ephe"
    source_ephe.mkdir(parents=True)
    for filename in download_ephe.FILES:
        (source_ephe / filename).write_text(filename)

    monkeypatch.setenv("SWISSEPH_SOURCE_DIR", str(source_root))

    assert download_ephe._complete_source_dir() == source_ephe


def test_download_ephe_detects_configured_ephe_dir(monkeypatch, tmp_path):
    source_ephe = tmp_path / "ephe"
    source_ephe.mkdir()
    for filename in download_ephe.FILES:
        (source_ephe / filename).write_text(filename)

    monkeypatch.setenv("SWISSEPH_SOURCE_DIR", str(source_ephe))

    assert download_ephe._complete_source_dir() == source_ephe


def test_download_ephe_rejects_incomplete_source(monkeypatch, tmp_path):
    source_ephe = tmp_path / "ephe"
    source_ephe.mkdir()
    (source_ephe / download_ephe.FILES[0]).write_text("only one file")

    monkeypatch.setenv("SWISSEPH_SOURCE_DIR", str(source_ephe))

    assert download_ephe._complete_source_dir() is None


def test_download_ephe_accepts_complete_destination(monkeypatch, tmp_path):
    destination = tmp_path / "ephe"
    destination.mkdir()
    for filename in download_ephe.FILES:
        (destination / filename).write_text(filename)

    monkeypatch.setattr(download_ephe, "DESTINATION", destination)

    assert download_ephe._destination_complete()
