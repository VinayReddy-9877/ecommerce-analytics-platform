import hashlib
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from olist import download


def archive_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_changed_source_does_not_overwrite_existing_files(tmp_path, monkeypatch):
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    (raw / "orders.csv").write_text("original")
    (tmp_path / "data/source_manifest.json").write_text(
        json.dumps({"files": {"orders.csv": hashlib.sha256(b"original").hexdigest()}})
    )
    monkeypatch.setattr(download, "ROOT", tmp_path)
    monkeypatch.setattr(download, "TABLE_FILES", {"orders": "orders.csv"})
    response = SimpleNamespace(
        content=archive_bytes({"orders.csv": "changed"}), raise_for_status=lambda: None
    )
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: response)
    with pytest.raises(ValueError, match="Source changed"):
        download.download()
    assert (raw / "orders.csv").read_text() == "original"


def test_missing_csv_rejects_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "ROOT", tmp_path)
    monkeypatch.setattr(download, "TABLE_FILES", {"orders": "orders.csv"})
    response = SimpleNamespace(
        content=archive_bytes({"other.csv": "x"}), raise_for_status=lambda: None
    )
    monkeypatch.setattr(download.requests, "get", lambda *a, **k: response)
    with pytest.raises(ValueError, match="Missing Olist"):
        download.download()
