import hashlib
import io
import json
import tarfile
from argparse import Namespace

import pytest

from app.scripts.backup import restore, validate_archive


def archive(tmp_path, name="ticket.txt", data=b"private media"):
    (tmp_path / "database.dump").write_bytes(b"database backup")
    with tarfile.open(tmp_path / "media.tar.gz", "w:gz") as tar:
        member = tarfile.TarInfo(name)
        member.size = len(data)
        tar.addfile(member, io.BytesIO(data))
    manifest = {
        "version": 1,
        "sha256": {
            name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
            for name in ["database.dump", "media.tar.gz"]
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))


def test_backup_integrity_rejects_corruption_and_path_traversal(tmp_path):
    archive(tmp_path)
    assert validate_archive(tmp_path)["version"] == 1
    (tmp_path / "database.dump").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        validate_archive(tmp_path)
    archive(tmp_path, "../escape.txt")
    with pytest.raises(ValueError, match="unsafe"):
        validate_archive(tmp_path)


@pytest.mark.parametrize(
    "database,confirm",
    [
        ("biletflow", "biletflow"),
        ("biletflow_demo", "biletflow_demo"),
        ("safe_restore", "wrong"),
        ("x;drop_restore", "x;drop_restore"),
    ],
)
def test_restore_refuses_live_or_unconfirmed_targets(database, confirm):
    with pytest.raises(ValueError, match="fresh"):
        restore(Namespace(database=database, confirm=confirm))
