"""Public Kaggle download. Refuse HTML/login responses and unexpected ZIPs."""

import hashlib
import io
import json
import zipfile

import requests

from .config import ROOT, TABLE_FILES

URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"


def download():
    response = requests.get(URL, timeout=120)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        missing = set(TABLE_FILES.values()) - set(archive.namelist())
        if missing:
            raise ValueError(f"Missing Olist source files: {missing}")
        destination = ROOT / "data/raw"
        destination.mkdir(parents=True, exist_ok=True)
        expected = json.loads((ROOT / "data/source_manifest.json").read_text())["files"]
        for filename in TABLE_FILES.values():
            if hashlib.sha256(archive.read(filename)).hexdigest() != expected[filename]:
                raise ValueError(
                    f"Source changed: {filename}. Review before updating the source manifest."
                )
        for filename in TABLE_FILES.values():
            payload = archive.read(filename)
            (destination / filename).write_bytes(payload)
    return hashlib.sha256(response.content).hexdigest()
