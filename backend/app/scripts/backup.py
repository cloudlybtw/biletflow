"""Local Compose backup and isolated recovery. Never restores over a live database."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def compose(project, *args, **kwargs):
    return subprocess.run(
        ["docker", "compose", "-p", project, *args], cwd=ROOT, check=True, **kwargs
    )


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_archive(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest.get("version") != 1 or set(manifest.get("sha256", {})) != {
        "database.dump",
        "media.tar.gz",
    }:
        raise ValueError("Unsupported or incomplete backup manifest.")
    for name, expected in manifest["sha256"].items():
        if digest(folder / name) != expected:
            raise ValueError(f"Backup checksum mismatch: {name}")
    with tarfile.open(folder / "media.tar.gz") as archive:
        for item in archive.getmembers():
            if (
                Path(item.name).is_absolute()
                or ".." in Path(item.name).parts
                or not (item.isfile() or item.isdir())
            ):
                raise ValueError("Backup contains an unsafe media path or link.")
    return manifest


def backup(args):
    destination = args.destination.resolve()
    if destination == (ROOT / "backend" / "media").resolve() or destination.is_relative_to(
        (ROOT / "backend" / "media").resolve()
    ):
        raise ValueError("Backup destination must be outside live media.")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination, 0o700)
    with (destination / ".backup.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder = Path(tempfile.mkdtemp(prefix=".incomplete-", dir=destination))
        stopped = False
        try:
            # Stop all application writers for DB/file consistency; DB stays online.
            running = compose(
                args.project,
                "ps",
                "--status",
                "running",
                "--services",
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            if "api" in running:
                compose(args.project, "stop", "api", stdout=subprocess.DEVNULL)
                stopped = True
            with (folder / "database.dump").open("wb") as output:
                compose(
                    args.project,
                    "exec",
                    "-T",
                    "db",
                    "sh",
                    "-c",
                    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',
                    stdout=output,
                )
            with tarfile.open(folder / "media.tar.gz", "w:gz") as archive:
                media = ROOT / "backend" / "media"
                if media.exists():
                    for path in sorted(media.rglob("*")):
                        if path.is_symlink():
                            raise ValueError("Media symlinks are not allowed in backups.")
                        if path.is_file():
                            archive.add(path, arcname=str(path.relative_to(media)), recursive=False)
            now = datetime.now(UTC)
            manifest = {
                "version": 1,
                "created_at": now.isoformat(),
                "project": args.project,
                "consistency": "application writers stopped",
                "sha256": {
                    name: digest(folder / name) for name in ("database.dump", "media.tar.gz")
                },
            }
            (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            validate_archive(folder)
            final = destination / now.strftime("backup-%Y%m%dT%H%M%S%fZ")
            folder.rename(final)
            for old in destination.glob("backup-*"):
                if (
                    old.is_dir()
                    and (old / "manifest.json").is_file()
                    and old.stat().st_mtime < (now - timedelta(days=args.keep_days)).timestamp()
                ):
                    saved = json.loads((old / "manifest.json").read_text())
                    if (
                        not old.is_symlink()
                        and saved.get("project") == args.project
                        and saved.get("version") == 1
                    ):
                        shutil.rmtree(old)
            print(f"Verified backup: {final}")
        finally:
            if stopped:
                compose(args.project, "start", "api", stdout=subprocess.DEVNULL)
            if folder.exists():
                shutil.rmtree(folder)


def restore(args):
    if not re.fullmatch(r"[a-z][a-z0-9_]*_restore", args.database) or args.confirm != args.database:
        raise ValueError("Restore requires a fresh *_restore database and matching --confirm.")
    folder = args.backup.resolve()
    validate_archive(folder)
    destination = args.media_destination.resolve()
    live_media = (ROOT / "backend" / "media").resolve()
    if destination == live_media or destination.is_relative_to(live_media):
        raise ValueError("Restore media must be outside live uploads.")
    if destination.exists():
        raise ValueError("Restore media destination must not exist.")
    # createdb fails if the target already exists. Never drop or overwrite it.
    compose(
        args.project,
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'exec createdb -U "$POSTGRES_USER" "$1"',
        "restore",
        args.database,
    )
    with (folder / "database.dump").open("rb") as source:
        compose(
            args.project,
            "exec",
            "-T",
            "db",
            "sh",
            "-c",
            'exec pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error --no-owner --no-privileges',
            "restore",
            args.database,
            stdin=source,
        )
    destination.mkdir(parents=True, mode=0o700)
    with tarfile.open(folder / "media.tar.gz") as archive:
        archive.extractall(destination, filter="data")
    print(
        f"Restored isolated database {args.database} and media {destination}. Live services were not changed."
    )


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("backup")
    create.add_argument("--project", required=True)
    create.add_argument("--destination", type=Path, required=True)
    create.add_argument("--keep-days", type=int, default=14)
    recover = sub.add_parser("restore")
    recover.add_argument("--project", required=True)
    recover.add_argument("--backup", type=Path, required=True)
    recover.add_argument("--database", required=True)
    recover.add_argument("--confirm", required=True)
    recover.add_argument("--media-destination", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "backup" and args.keep_days < 1:
        parser.error("--keep-days must be positive")
    (backup if args.command == "backup" else restore)(args)


if __name__ == "__main__":
    main()
