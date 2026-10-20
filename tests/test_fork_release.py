"""Exercise the release command as an external process in disposable Git repositories."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

CLI = Path(__file__).resolve().parents[1] / "scripts/build_fork_release.py"
VERSION = "2026.10.0rc1"


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE).decode().strip()


@pytest.fixture
def source(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Release test")
    git(repo, "config", "user.email", "release@example.invalid")
    runtime = repo / "custom_components/helios_forecast"
    (runtime / "translations").mkdir(parents=True)
    (runtime / "brand").mkdir()
    (runtime / "manifest.json").write_text(json.dumps({"domain": "helios_forecast", "version": VERSION}))
    (runtime / "__init__.py").write_bytes(b"# a committed integration\n")
    (runtime / "brand/icon.png").write_bytes(b"\x89PNG\x00\x01")
    (runtime / "translations/de.json").write_text('{"title":"Sonne"}\n')
    (repo / ".gitignore").write_text("dist/\n__pycache__/\n*.private\n")
    (repo / "private-site.json").write_text('{"not":"for release"}')
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "fixture")
    return repo, git(repo, "rev-parse", "HEAD"), runtime


def cli(source, command="build", output=None, *, rev=None, version=VERSION, tag=None, ok=True):
    repo, pin, _ = source
    output = output or repo / "dist/candidate"
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            command,
            "--repo",
            str(repo),
            "--expected-rev",
            rev or pin,
            "--version",
            version,
            "--tag",
            tag or f"v{version}",
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is ok, result.stdout + result.stderr
    return output


def test_reproducible_complete_git_payload_and_receipt(source):
    repo, pin, _ = source
    first = cli(source)
    second = cli(source, output=repo / "dist/second")
    data = (first / "helios_forecast.zip").read_bytes()
    assert data == (second / "helios_forecast.zip").read_bytes()
    with zipfile.ZipFile(first / "helios_forecast.zip") as archive:
        assert archive.namelist() == ["__init__.py", "brand/icon.png", "manifest.json", "translations/de.json"]
        assert archive.read("brand/icon.png") == b"\x89PNG\x00\x01"
        assert archive.read("translations/de.json") == b'{"title":"Sonne"}\n'
        for member in archive.infolist():
            assert member.date_time == (1980, 1, 1, 0, 0, 0)
            assert member.external_attr >> 16 == 0o100644
            assert member.compress_type == zipfile.ZIP_STORED
    receipt = json.loads((first / "release-receipt.json").read_bytes())
    assert receipt["revision"] == pin
    assert receipt["version"] == VERSION
    assert receipt["tag"] == f"v{VERSION}"
    assert receipt["archive_sha256"] == hashlib.sha256(data).hexdigest()
    assert receipt["files"]["__init__.py"] == hashlib.sha256(b"# a committed integration\n").hexdigest()
    cli(source, "verify", first)
    cli(source, output=first, ok=False)
    assert data == (first / "helios_forecast.zip").read_bytes()


@pytest.mark.parametrize("kwargs", [{"rev": "0" * 40}, {"rev": "HEAD"}, {"version": "2026.10.0"}, {"tag": "vother"}])
def test_wrong_pins_fail_before_creating_output(source, kwargs):
    output = cli(source, ok=False, **kwargs)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["tracked", "staged", "untracked", "ignored", "outside"])
def test_dirty_input_fails_closed(source, kind):
    repo, _, runtime = source
    target = runtime / (
        "manifest.json" if kind in ("tracked", "staged") else "site.private" if kind == "ignored" else "site.json"
    )
    if kind == "outside":
        target = repo / "notes.txt"
    target.write_text("private or changed")
    if kind == "staged":
        git(repo, "add", ".")
    assert not cli(source, ok=False).exists()


@pytest.mark.parametrize(
    "kind", ["changed", "missing", "extra", "duplicate", "traversal", "absolute", "backslash", "receipt"]
)
def test_tampering_rejected_even_with_rehashed_receipt(source, kind):
    output = cli(source)
    path = output / "helios_forecast.zip"
    if kind == "receipt":
        (output / "release-receipt.json").write_text("{}")
    else:
        with zipfile.ZipFile(path) as archive:
            members = [(i.filename, archive.read(i)) for i in archive.infolist()]
        if kind == "changed":
            members[0] = (members[0][0], b"tampered")
        elif kind == "missing":
            members.pop()
        else:
            name = {
                "extra": "site.json",
                "duplicate": "manifest.json",
                "traversal": "../outside",
                "absolute": "/tmp/outside",
                "backslash": "..\\outside",
            }[kind]
            members.append((name, b"unexpected"))
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in members:
                archive.writestr(name, content)
        receipt_path = output / "release-receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        receipt["archive_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt))
    cli(source, "verify", output, ok=False)


def test_committed_symlink_and_existing_wrong_tag_rejected(source):
    repo, _, runtime = source
    git(repo, "tag", f"v{VERSION}")
    (runtime / "alias").symlink_to("manifest.json")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "unsafe alias")
    source = repo, git(repo, "rev-parse", "HEAD"), runtime
    assert not cli(source, ok=False).exists()
    git(repo, "tag", "-d", f"v{VERSION}")
    assert not cli(source, ok=False).exists()


def test_symlink_output_collision_preserves_target(source, tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep").write_text("keep")
    output = tmp_path / "linked-output"
    output.symlink_to(target, target_is_directory=True)
    cli(source, output=output, ok=False)
    assert (target / "keep").read_text() == "keep"
    assert list(target.iterdir()) == [target / "keep"]
