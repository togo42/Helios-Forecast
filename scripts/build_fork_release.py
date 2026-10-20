#!/usr/bin/env python3
"""Build or verify an offline HACS asset from an explicitly pinned clean commit."""

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile

PREFIX = "custom_components/helios_forecast/"
ASSET = "helios_forecast.zip"
RECEIPT = "release-receipt.json"
STAMP = (1980, 1, 1, 0, 0, 0)


def git(repo: Path, *args: str) -> bytes:
    """Run Git without a shell, and never substitute worktree bytes for blobs."""
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def safe_path(name: str) -> None:
    """Reject paths with ambiguous or escaping extraction semantics."""
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or str(path) != name
        or any(p in (".", "..") or p.startswith(".") for p in path.parts)
        or any(c in name for c in "\\:\x00\r\n")
    ):
        raise ValueError(f"unsafe payload path: {name!r}")


def payload(repo: Path, rev: str, version: str, tag: str) -> dict[str, bytes]:
    """Read the complete tracked integration tree, with its version and inputs bound."""
    if not re.fullmatch(r"[0-9a-f]{40}", rev):
        raise ValueError("expected-rev must be a full lowercase commit SHA")
    if git(repo, "rev-parse", "HEAD").decode().strip() != rev:
        raise ValueError("HEAD does not match expected-rev")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("repository has dirty or untracked inputs")
    # Ignored caches never enter the archive; ignored runtime changes must still fail.
    if git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "--", PREFIX).strip():
        # Python test caches are harmless and common, but are never payload.
        ignored = git(repo, "ls-files", "--others", "--ignored", "--exclude-standard", "--", PREFIX)
        if any("/__pycache__/" not in p for p in ignored.decode().splitlines()):
            raise ValueError("ignored non-cache runtime inputs")
    if not re.fullmatch(r"\d{4}\.\d{1,2}\.\d+(?:rc\d+)?", version) or tag != f"v{version}":
        raise ValueError("invalid version/tag binding")
    # A tag may be planned before publication; an existing tag must bind this commit.
    refs = git(repo, "tag", "--list", tag).decode().splitlines()
    if refs and git(repo, "rev-parse", f"refs/tags/{tag}^{{commit}}").decode().strip() != rev:
        raise ValueError("existing release tag points to another commit")
    files = {}
    for record in git(repo, "ls-tree", "-rz", rev, "--", PREFIX).split(b"\0"):
        if not record:
            continue
        meta, raw_path = record.split(b"\t", 1)
        mode, kind, blob = meta.decode().split()
        name = raw_path.decode().removeprefix(PREFIX)
        safe_path(name)
        if mode != "100644" or kind != "blob":
            raise ValueError(f"non-regular runtime file: {name}")
        files[name] = git(repo, "cat-file", "blob", blob)
    manifest = json.loads(files["manifest.json"])
    if manifest["domain"] != "helios_forecast" or manifest["version"] != version:
        raise ValueError("manifest domain/version mismatch")
    return dict(sorted(files.items()))


def archive_bytes(files: dict[str, bytes]) -> bytes:
    """Stored ZIP avoids compressor-version differences; metadata is fixed."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in files.items():
            entry = zipfile.ZipInfo(name, STAMP)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    return stream.getvalue()


def receipt_bytes(files: dict[str, bytes], archive: bytes, rev: str, version: str, tag: str) -> bytes:
    """The sidecar is outside the installed integration."""
    data = {
        "schema": "helios.fork.release.v1",
        "revision": rev,
        "tag": tag,
        "version": version,
        "archive": ASSET,
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def verify(directory: Path, files: dict[str, bytes], expected: bytes, receipt: bytes) -> None:
    """Check members against Git, then require canonical bytes and receipt."""
    actual = (directory / ASSET).read_bytes()
    with zipfile.ZipFile(io.BytesIO(actual)) as archive:
        names = archive.namelist()
        for name in names:
            safe_path(name)
        if names != list(files):
            raise ValueError("archive has missing, extra, duplicate or reordered members")
        for name, content in files.items():
            if archive.read(name) != content:
                raise ValueError(f"archive differs from Git blob: {name}")
    if actual != expected:
        raise ValueError("archive bytes/metadata are not canonical")
    if (directory / RECEIPT).read_bytes() != receipt:
        raise ValueError("receipt differs from pinned Git inputs and archive hash")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expected-rev", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, required=True, help="new directory for build; existing for verify")
    args = parser.parse_args()
    try:
        files = payload(args.repo, args.expected_rev, args.version, args.tag)
        archive = archive_bytes(files)
        receipt = receipt_bytes(files, archive, args.expected_rev, args.version, args.tag)
        if args.command == "build":
            # mkdir is exclusive, including dangling symlinks: never overwrite an output.
            args.output.mkdir(parents=True, exist_ok=False)
            (args.output / ASSET).write_bytes(archive)
            (args.output / RECEIPT).write_bytes(receipt)
        verify(args.output, files, archive, receipt)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f"release {args.command} failed: {error}", file=sys.stderr)
        return 1
    print(f"{args.command} verified: {args.expected_rev} {args.tag} {hashlib.sha256(archive).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
