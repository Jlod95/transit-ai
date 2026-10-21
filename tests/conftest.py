"""Shared test helpers. pytest loads this file automatically for every test in tests/."""

import csv
import io
import zipfile
from pathlib import Path

import pytest

MINI_FEED_DIR = Path(__file__).parent / "fixtures" / "mini_feed"


def zip_mini_feed(zip_path, edit=None):
    """Zip the hand-made mini feed into zip_path and return the path.

    edit, if given, is called as edit(file_name, rows) for every table, where rows is a list
    of dicts; it returns the rows to write. Use it to make a variant of the feed for one test.
    """
    with zipfile.ZipFile(zip_path, "w") as zf:
        for txt in sorted(MINI_FEED_DIR.glob("*.txt")):
            if edit is None:
                zf.write(txt, arcname=txt.name)
                continue
            with txt.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames
                rows = edit(txt.name, list(reader))
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            zf.writestr(txt.name, out.getvalue())
    return zip_path


@pytest.fixture
def mini_feed(tmp_path):
    """The mini feed, zipped into pytest's temporary folder."""
    return zip_mini_feed(tmp_path / "mini_feed.zip")
