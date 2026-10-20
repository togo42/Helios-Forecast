#!/usr/bin/env python3
"""Independent RC2 release acceptance against a clean, committed candidate.

Only local Git clones, subprocess CLI calls and standard-library oracles are used.
This does not import the release producer or change the source repository. Use a
new absolute --work path below /tmp; every command and result is retained there.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import warnings
import zipfile

BASE = "569074a42399a2e5e954b01da8ce34240fa1341e"
VERSION = "2026.10.0rc2"
TAG = "v2026.10.0rc2"
PREFIX = "custom_components/helios_forecast/"
ARCHIVE = "helios_forecast.zip"
RECEIPT = "release-receipt.json"
NEW_RUNTIME = {"weather_history.py"}
RUNTIME_CHANGES = {
    "__init__.py",
    "analog.py",
    "checkup.py",
    "consumption.py",
    "coordinator.py",
    "forecast.py",
    "manifest.json",
    "openmeteo.py",
    "strings.json",
    "weather_history.py",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


def blobs(repo: Path, revision: str) -> dict[str, bytes]:
    result = {}
    for row in git(repo, "ls-tree", "-rz", revision, "--", PREFIX).split(b"\0"):
        if not row:
            continue
        metadata, path = row.split(b"\t", 1)
        mode, kind, _oid = metadata.decode().split()
        assert mode == "100644" and kind == "blob", "nonregular runtime input"
        full = path.decode()
        assert full.startswith(PREFIX)
        result[full[len(PREFIX) :]] = git(repo, "show", revision + ":" + full)
    assert result, "empty runtime inventory"
    return result


def runtime_oracle(repo: Path, revision: str) -> dict[str, bytes]:
    """Bind actual Git blobs and reject runtime changes outside the RC2 scope."""
    git(repo, "merge-base", "--is-ancestor", BASE, revision)
    expected, before = blobs(repo, revision), blobs(repo, BASE)
    assert set(expected) == set(before) | NEW_RUNTIME, "unexpected runtime inventory"
    changed = {name for name, content in expected.items() if before.get(name) != content}
    allowed = RUNTIME_CHANGES | {name for name in before if name.startswith("translations/") and name.endswith(".json")}
    assert changed <= allowed, "runtime scope violation: " + ", ".join(sorted(changed - allowed))
    manifest, old_manifest = json.loads(expected["manifest.json"]), json.loads(before["manifest.json"])
    assert manifest["version"] == VERSION and manifest["domain"] == "helios_forecast"
    assert {k: v for k, v in manifest.items() if k != "version"} == {
        k: v for k, v in old_manifest.items() if k != "version"
    }, "manifest identity, dependencies or ownership changed"
    hacs = git(repo, "show", revision + ":hacs.json")
    assert hacs == git(repo, "show", BASE + ":hacs.json"), "HACS metadata changed"
    assert json.loads(hacs) == {
        "name": "Helios Forecast (togo42 fork)",
        "homeassistant": "2025.11.0",
        "hide_default_branch": True,
        "zip_release": True,
        "filename": ARCHIVE,
    }
    return expected


def oracle(repo: Path, revision: str, output: Path) -> dict:
    """Check archive structure, every Git blob, sidecar and literal extraction."""
    expected = runtime_oracle(repo, revision)
    raw = (output / ARCHIVE).read_bytes()
    assert raw[-22:-18] == b"PK\x05\x06" and raw[-2:] == b"\0\0", "trailing data or ZIP comment"
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        names = bundle.namelist()
        assert names == sorted(expected), "missing, duplicate, extra or reordered ZIP member"
        position = 0
        for member in bundle.infolist():
            path = PurePosixPath(member.filename)
            assert not path.is_absolute() and str(path) == member.filename
            assert all(part not in (".", "..") and not part.startswith(".") for part in path.parts)
            assert not any(char in member.filename for char in "\\:\0\r\n")
            assert member.date_time == (1980, 1, 1, 0, 0, 0)
            assert member.compress_type == zipfile.ZIP_STORED and member.create_system == 3
            assert member.external_attr == 0o100644 << 16
            assert member.internal_attr == 0 and member.create_version == member.extract_version == 20
            assert member.reserved == 0 and member.volume == 0
            assert member.extra == member.comment == b"" and member.flag_bits == 0
            assert member.header_offset == position, "unexpected bytes between ZIP members"
            signature, *_fields, name_len, extra_len = struct.unpack("<4s5H3I2H", raw[position : position + 30])
            assert signature == b"PK\x03\x04" and extra_len == 0
            assert raw[position + 30 : position + 30 + name_len].decode("utf-8") == member.filename
            position += 30 + name_len + extra_len + member.compress_size
            assert bundle.read(member) == expected[member.filename], "ZIP/blob mismatch: " + member.filename
        assert position == bundle.start_dir, "unexpected pre-directory ZIP data"
    receipt_raw = (output / RECEIPT).read_bytes()
    receipt = json.loads(receipt_raw)
    assert receipt == {
        "schema": "helios.fork.release.v1",
        "revision": revision,
        "version": VERSION,
        "tag": TAG,
        "archive": ARCHIVE,
        "archive_sha256": sha(raw),
        "files": {name: sha(content) for name, content in expected.items()},
    }, "receipt not bound to the complete pinned payload"
    assert receipt_raw == (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(), "noncanonical receipt"
    return {
        "archive_sha256": sha(raw),
        "receipt_sha256": sha(receipt_raw),
        "runtime_files": {name: sha(content) for name, content in sorted(expected.items())},
    }


def snapshot(directory: Path) -> dict[str, str]:
    return {p.relative_to(directory).as_posix(): sha(p.read_bytes()) for p in directory.rglob("*") if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-rev", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--version-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--oracle-only", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    assert re.fullmatch(r"[0-9a-f]{40}", args.expected_rev), "full committed candidate SHA required"
    if args.oracle_only:
        oracle(args.repo, args.expected_rev, args.oracle_only)
        return 0
    assert args.work.is_absolute() and args.work.resolve().is_relative_to(Path("/tmp"))
    assert args.work.resolve() != Path("/tmp"), "use a unique new directory under /tmp"
    assert git(args.repo, "rev-parse", "HEAD").decode().strip() == args.expected_rev
    assert not git(args.repo, "status", "--porcelain", "--untracked-files=all"), "source must be clean"
    args.work.mkdir(parents=True, exist_ok=False)
    records = []

    def run(label: str, argv: list, *, ok: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run([str(x) for x in argv], capture_output=True, text=True, check=False)
        records.append(
            {
                "case": label,
                "argv": [str(x) for x in argv],
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        (args.work / "commands.json").write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
        assert (result.returncode == 0) == ok, label + ": " + result.stdout + result.stderr
        return result

    repo = args.work / "source"
    run("clone-local", ["git", "clone", "--quiet", "--no-hardlinks", args.repo.resolve(), repo])
    git(repo, "checkout", "--quiet", "--detach", args.expected_rev)
    expected = runtime_oracle(repo, args.expected_rev)
    script = repo / "scripts/build_fork_release.py"

    def cli(label, action, output, *, ok=True, revision=None, version=VERSION, tag=TAG):
        before = snapshot(output) if output.exists() else None
        result = run(
            label,
            [
                sys.executable,
                script,
                action,
                "--repo",
                repo,
                "--expected-rev",
                revision or args.expected_rev,
                "--version",
                version,
                "--tag",
                tag,
                "--output",
                output,
            ],
            ok=ok,
        )
        if not ok:
            assert result.returncode != 0, "negative CLI case must actually fail"
            if before is None:
                assert not output.exists(), "rejected build created output"
            else:
                assert snapshot(output) == before, "rejected operation overwrote artifacts"

    run(
        "version-ordering",
        [
            args.version_python,
            "-c",
            "from awesomeversion import AwesomeVersion as A; from packaging.version import Version as V; "
            'assert A("2026.9.6") < A("2026.10.0rc1") < A("2026.10.0rc2") < A("2026.10.0"); '
            'assert V("2026.9.6") < V("2026.10.0rc1") < V("2026.10.0rc2") < V("2026.10.0"); '
            'assert A("2026.10.0rc2").strategy.value == "CalVer"',
        ],
    )
    first, second = args.work / "build-one", args.work / "build-two"
    cli("build-one", "build", first)
    evidence = oracle(repo, args.expected_rev, first)
    cli("verify-one", "verify", first)
    cli("build-two", "build", second)
    oracle(repo, args.expected_rev, second)
    assert snapshot(first) == snapshot(second), "build bytes are not reproducible"
    cli("existing-output", "build", first, ok=False)
    cli("wrong-pin", "build", args.work / "wrong-pin", ok=False, revision="0" * 40)
    cli("wrong-head", "build", args.work / "wrong-head", ok=False, revision=BASE)
    cli("wrong-version", "build", args.work / "wrong-version", ok=False, version="2026.10.0rc1", tag="v2026.10.0rc1")
    cli("wrong-tag", "build", args.work / "wrong-tag", ok=False, tag="v2026.10.0rc1")
    runtime = repo / PREFIX
    tracked = runtime / "__init__.py"
    tracked.write_bytes(tracked.read_bytes() + b"\n# acceptance dirty input\n")
    cli("tracked-dirty", "build", args.work / "tracked-dirty", ok=False)
    git(repo, "add", "--", PREFIX + "__init__.py")
    cli("staged-dirty", "build", args.work / "staged-dirty", ok=False)
    git(repo, "restore", "--staged", "--worktree", "--", PREFIX + "__init__.py")
    for label, path in (("runtime-untracked", runtime / "r-untracked.txt"), ("outside-untracked", repo / "r-note.txt")):
        path.write_text("uncommitted acceptance input\n")
        cli(label, "build", args.work / label, ok=False)
        path.unlink()
    ignored = runtime / ".pytest_cache" / "r-site.json"
    ignored.parent.mkdir()
    ignored.write_text('{"private": "synthetic acceptance input"}\n')
    run("ignored-runtime-confirmed", ["git", "-C", repo, "check-ignore", "--quiet", ignored])
    cli("ignored-runtime", "build", args.work / "ignored-runtime", ok=False)
    ignored.unlink()
    ignored.parent.rmdir()

    def tampered(label: str) -> None:
        output = args.work / ("tampered-" + label)
        shutil.copytree(first, output)
        archive_path = output / ARCHIVE
        receipt_path = output / RECEIPT
        receipt = json.loads(receipt_path.read_bytes())
        if label == "receipt":
            receipt["revision"] = BASE
        elif label == "receipt-format":
            receipt_path.write_text(json.dumps(receipt))
        elif label == "trailing-data":
            archive_path.write_bytes(archive_path.read_bytes() + b"tampered")
        else:
            with zipfile.ZipFile(archive_path) as source:
                members = [(i.filename, source.read(i)) for i in source.infolist()]
            if label == "changed":
                members = [(n, v + b"\n# changed\n" if n == "weather_history.py" else v) for n, v in members]
            elif label == "missing":
                members = [(n, v) for n, v in members if n != "weather_history.py"]
            else:
                name = {
                    "extra": "site-config.json",
                    "duplicate": "manifest.json",
                    "traversal": "../outside.py",
                    "absolute": "/tmp/rc2-outside.py",
                    "backslash": "..\\outside.py",
                }[label]
                members.append((name, b"unexpected"))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as target:
                    for name, data in members:
                        member = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                        member.create_system = 3
                        member.external_attr = 0o100644 << 16
                        target.writestr(member, data)
        if label != "receipt-format":
            # A forged matching sidecar cannot authorize different source bytes.
            receipt["archive_sha256"] = sha(archive_path.read_bytes())
            if label not in ("receipt", "trailing-data"):
                with zipfile.ZipFile(archive_path) as changed:
                    receipt["files"] = {i.filename: sha(changed.read(i)) for i in changed.infolist()}
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        cli("tampered-" + label, "verify", output, ok=False)
        run(
            "oracle-reject-" + label,
            [
                sys.executable,
                Path(__file__).resolve(),
                "--repo",
                repo,
                "--expected-rev",
                args.expected_rev,
                "--work",
                args.work,
                "--oracle-only",
                output,
            ],
            ok=False,
        )

    for label in (
        "receipt",
        "receipt-format",
        "trailing-data",
        "changed",
        "missing",
        "extra",
        "duplicate",
        "traversal",
        "absolute",
        "backslash",
    ):
        tampered(label)

    installed = args.work / "extracted-runtime"
    installed.mkdir()
    with zipfile.ZipFile(first / ARCHIVE) as bundle:
        for name in bundle.namelist():
            target = installed.joinpath(*PurePosixPath(name).parts)
            assert target.resolve().is_relative_to(installed.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(name))
    actual = {p.relative_to(installed).as_posix(): p.read_bytes() for p in installed.rglob("*") if p.is_file()}
    assert actual == expected and "weather_history.py" in actual, "literal extraction differs from pinned Git"
    assert not git(repo, "status", "--porcelain", "--untracked-files=all"), "test clone left dirty"
    assert not git(args.repo, "status", "--porcelain", "--untracked-files=all"), "source changed during acceptance"
    assert git(args.repo, "rev-parse", "HEAD").decode().strip() == args.expected_rev
    report = {
        "schema": "helios.rc2.release.acceptance.v1",
        "passed": True,
        "baseline": BASE,
        "candidate": args.expected_rev,
        "version": VERSION,
        "tag": TAG,
        "evidence": evidence,
        "cases": records,
        "extracted_runtime_matches_git": True,
        "harness_sha256": sha(Path(__file__).read_bytes()),
    }
    (args.work / "rc2-release-r.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": True,
                "cases": len(records),
                "runtime_files": len(expected),
                "candidate": args.expected_rev,
                "archive_sha256": evidence["archive_sha256"],
                "receipt_sha256": evidence["receipt_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
