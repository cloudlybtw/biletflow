# Database and media recovery

Run from the repository's `backend/` directory with Docker access. Backups include
PostgreSQL custom-format dumps and all event/support uploads, a versioned manifest
and SHA-256 checksums. Output permissions are owner-only (umask 077). Keep backups
outside the checkout and copy them to a separately controlled backup location.
Encryption configuration belongs to deferred M11.6; these files are not encrypted.

```sh
uv run python -m app.scripts.backup backup \
  --project biletflow-rehearsal --destination /var/backups/biletflow --keep-days 14
```

The command stops the project's API writers, dumps the database and copies media,
then restarts the API in `finally`, including on failure. Expect a brief maintenance
window. All other writers must also be stopped. The web may return API errors
through that interval. Completed backups are published atomically; partial backups
are removed, concurrent backups are rejected, and completed backups older than the
chosen retention period are pruned. Checksum validation detects corruption, not
malicious replacement of the manifest; restrict write access to backup storage.

## Daily schedule

`deploy/systemd/biletflow-backup.service` and `.timer` provide a daily 03:00 host-time
schedule with 14-day retention and catch-up after downtime. On the deployment host,
set the service user, checkout/uv paths, Compose project and destination to actual
values; pre-create the backup directory with mode 0700 and the service user's
ownership. The service account needs Docker access (equivalent to host root).
Copy the units into `/etc/systemd/system/`, then run:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now biletflow-backup.timer
systemctl list-timers biletflow-backup.timer
journalctl -u biletflow-backup.service
```

The schedule is provided for installation; no timer has been installed on a
production host or the developer's machine. Alert on unsuccessful service runs and
missing daily backups. Keep 14 daily local backups, an independent off-host copy,
and repeat restore drills after schema/storage changes. A deployment operator must
choose off-host retention and recovery objectives appropriate to their data.

## Isolated restore drill

```sh
uv run python -m app.scripts.backup restore \
  --project biletflow-rehearsal --backup /var/backups/biletflow/backup-TIMESTAMP \
  --database biletflow_drill_restore --confirm biletflow_drill_restore \
  --media-destination /tmp/biletflow-restored-media
```

The database must be new, named `*_restore`, with an exact matching confirmation;
`createdb` refuses an existing name. Media destination must not exist. Checksums
and tar paths are checked before database creation. Symlinks and path traversal are
rejected. A failed restore may leave its isolated DB for diagnosis; it never drops
or overwrites a live database or live uploads. Never point a live API at a partially
restored database. Recovery drill evidence should compare table counts, migration
version and media hashes against the original, then smoke-test health, auth and
protected ticket/support downloads in an isolated API with email delivery disabled.

A real recovery requires restoring compatible application code, database and media,
validating them in isolation, then deliberately switching the deployment. The
script does not perform that switch or automatically send restored outbox mail.
