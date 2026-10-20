#!/usr/bin/env python3
"""Independent real-CLI release acceptance; never imports producer code.

Run against a committed candidate using --repo, --expected-rev and a fresh --work.
All clones, artifacts and raw logs remain in --work. No network is used.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

PREFIX = "custom_components/helios_forecast/"
EXPECT = json.loads(Path(__file__).with_name("expectations.json").read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(argv, cwd=None):
    return subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True, text=True)


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


def blobs(repo, revision):
    names = git(repo, "ls-tree", "-rz", "--name-only", revision, "--", PREFIX).split(b"\0")
    return {n.decode()[len(PREFIX) :]: git(repo, "show", revision + ":" + n.decode()) for n in names if n}


def oracle(repo, revision, output):
    """Independent source/blob and extraction checks, without producer helpers."""
    expected = blobs(repo, revision)
    original = blobs(repo, EXPECT["baseline"])
    assert set(expected) == set(original), "runtime inventory changed"
    for name, value in expected.items():
        if name != "manifest.json":
            assert value == original[name], "unauthorized runtime delta: " + name
    manifest = json.loads(expected["manifest.json"])
    before = json.loads(original["manifest.json"])
    for key in set(manifest) | set(before):
        if key not in EXPECT["manifest_changes"]:
            assert manifest.get(key) == before.get(key), "manifest invariant: " + key
    assert manifest["version"] == EXPECT["version"]
    assert manifest["domain"] == EXPECT["domain"]
    for key, value in EXPECT["metadata"].items():
        assert manifest[key] == value, "fork ownership metadata mismatch"
    assert json.loads(git(repo, "show", revision + ":hacs.json")) == EXPECT["hacs"]
    raw = (output / EXPECT["archive"]).read_bytes()
    assert raw[-22:-18] == b"PK\x05\x06" and raw[-2:] == b"\x00\x00", "trailing archive data or comment"

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), "duplicate paths"
        for name in names:
            path = PurePosixPath(name)
            assert not path.is_absolute() and ".." not in path.parts, "unsafe path"
            assert all(not part.startswith(".") for part in path.parts), "hidden payload path"
            assert "\\" not in name and ":" not in name, "ambiguous payload path"
            assert name == str(path), "non-normalized payload path"
        assert set(names) == set(expected), "ZIP inventory differs from Git"
        for name in names:
            assert archive.read(name) == expected[name], "ZIP/Git bytes differ: " + name
    receipt = json.loads((output / EXPECT["receipt"]).read_text())
    assert receipt["schema"] == "helios.fork.release.v1"
    assert receipt["revision"] == revision
    assert receipt["version"] == EXPECT["version"]
    assert receipt["tag"] == EXPECT["tag"]
    assert receipt["archive"] == EXPECT["archive"]
    assert receipt["archive_sha256"] == sha(raw)
    assert receipt["files"] == {name: sha(value) for name, value in expected.items()}
    return {
        "archive_sha256": sha(raw),
        "receipt_sha256": sha((output / EXPECT["receipt"]).read_bytes()),
        "file_count": len(expected),
        "runtime_file_sha256": {n: sha(v) for n, v in expected.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-rev", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--version-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--oracle-only", type=Path)
    args = parser.parse_args()
    if args.oracle_only:
        oracle(args.repo, args.expected_rev, args.oracle_only)
        return 0
    args.work.mkdir(parents=True, exist_ok=False)
    repo = args.work / "source"
    result = command(["git", "clone", "--no-hardlinks", "--quiet", args.repo, repo])
    assert result.returncode == 0, result.stderr
    git(repo, "checkout", "--quiet", "--detach", args.expected_rev)
    script = repo / "scripts/build_fork_release.py"
    records = []
    version_probe = command(
        [
            args.version_python,
            "-c",
            "from awesomeversion import AwesomeVersion as A; from packaging.version import Version as V; "
            'assert A("2026.9.6") < A("2026.10.0rc1") < A("2026.10.0"); '
            'assert V("2026.9.6") < V("2026.10.0rc1") < V("2026.10.0"); '
            'assert A("2026.10.0rc1").strategy.value == "CalVer"',
        ]
    )
    assert version_probe.returncode == 0, version_probe.stderr

    def cli(label, action, output, success=True, revision=None, version=None, tag=None, program=None):
        argv = [
            sys.executable,
            program or script,
            action,
            "--repo",
            repo,
            "--expected-rev",
            revision or args.expected_rev,
            "--version",
            version or EXPECT["version"],
            "--tag",
            tag or EXPECT["tag"],
            "--output",
            output,
        ]
        probe = command(argv)
        records.append(
            {
                "case": label,
                "exit": probe.returncode,
                "stdout": probe.stdout,
                "stderr": probe.stderr,
                "argv": [str(x) for x in argv],
            }
        )
        assert (probe.returncode == 0) == success, label + ": " + probe.stdout + probe.stderr

    first, second = args.work / "build-one", args.work / "build-two"
    cli("build-one", "build", first)
    evidence = oracle(repo, args.expected_rev, first)
    cli("verify-positive", "verify", first)
    cli("build-two", "build", second)
    oracle(repo, args.expected_rev, second)
    for name in (EXPECT["archive"], EXPECT["receipt"]):
        assert (first / name).read_bytes() == (second / name).read_bytes(), "not reproducible"
    cli("wrong-revision", "build", args.work / "wrong-rev", False, revision="0" * 40)
    cli("wrong-version", "build", args.work / "wrong-version", False, version="2026.10.0rc2", tag="v2026.10.0rc2")
    cli("wrong-tag", "build", args.work / "wrong-tag", False, tag="v2026.10.0")
    cli("existing-output", "build", first, False)
    runtime = repo / PREFIX / "__init__.py"
    runtime.write_bytes(runtime.read_bytes() + b"\n# dirty acceptance probe\n")
    cli("tracked-dirty", "build", args.work / "dirty", False)
    git(repo, "restore", "--", PREFIX)
    extra = repo / PREFIX / "r_untracked.txt"
    extra.write_text("not a committed asset")
    cli("untracked-input", "build", args.work / "untracked", False)
    extra.unlink()

    def bad_archive(label, mode):
        output = args.work / label
        shutil.copytree(first, output)
        archive = output / EXPECT["archive"]
        if mode == "raw":
            archive.write_bytes(archive.read_bytes() + b"tampered")
        else:
            with zipfile.ZipFile(first / EXPECT["archive"]) as source:
                members = [(x, source.read(x)) for x in source.namelist()]
            if mode == "missing":
                members = [(n, v) for n, v in members if n != "__init__.py"]
            elif mode == "replace":
                members = [(n, v + b"\n# replaced\n" if n == "__init__.py" else v) for n, v in members]
            else:
                members += [
                    ("__init__.py" if mode == "duplicate" else "../escape.py" if mode == "slip" else "added.py", b"bad")
                ]
            with zipfile.ZipFile(archive, "w") as target:
                for name, value in members:
                    target.writestr(name, value)
        receipt_path = output / EXPECT["receipt"]
        receipt = json.loads(receipt_path.read_text())
        receipt["archive_sha256"] = sha(archive.read_bytes())
        with zipfile.ZipFile(archive) as altered:
            receipt["files"] = {n: sha(altered.read(n)) for n in altered.namelist()}
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        cli(label, "verify", output, False)
        probe = command(
            [
                sys.executable,
                __file__,
                "--repo",
                repo,
                "--expected-rev",
                args.expected_rev,
                "--work",
                args.work,
                "--oracle-only",
                output,
            ]
        )
        assert probe.returncode != 0 and "AssertionError" in probe.stderr, (
            "independent oracle failed to reject " + label
        )
        return output

    bad = {}
    for mode in ("raw", "addition", "missing", "replace", "slip", "duplicate"):
        bad[mode] = bad_archive("bad-" + mode, mode)
    original_script = script.read_text()
    mutants = []
    # Mutant 1 retains all CLI guards but corrupts the pinned blob payload on read.
    needle = 'files[name] = git(repo, "cat-file", "blob", blob)'
    assert original_script.count(needle) == 1
    mutant = args.work / "mutant-blob.py"
    mutant.write_text(
        original_script.replace(
            needle,
            needle
            + '\n        if name == "__init__.py":\n            files[name] += b"\\n# mutant unbound payload\\n"',
        )
    )
    mutant_output = args.work / "mutant-blob-output"
    cli("mutant-blob-build", "build", mutant_output, program=mutant)
    probe = command(
        [
            sys.executable,
            __file__,
            "--repo",
            repo,
            "--expected-rev",
            args.expected_rev,
            "--work",
            args.work,
            "--oracle-only",
            mutant_output,
        ]
    )
    assert probe.returncode != 0 and "AssertionError" in probe.stderr
    mutants.append(
        {
            "name": "unbound-blob",
            "producer_exit": 0,
            "oracle_exit": probe.returncode,
            "assertion": probe.stderr.splitlines()[-1],
            "mutant_sha256": sha(mutant.read_bytes()),
        }
    )
    # Mutant 2 bypasses artifact validation; the actual CLI accepts a traversal archive.
    needle = "        verify(args.output, files, archive, receipt)"
    assert original_script.count(needle) == 1
    mutant = args.work / "mutant-validation.py"
    mutant.write_text(original_script.replace(needle, "        # mutation: artifact validation removed"))
    cli("mutant-safety-verify", "verify", bad["slip"], program=mutant)
    probe = command(
        [
            sys.executable,
            __file__,
            "--repo",
            repo,
            "--expected-rev",
            args.expected_rev,
            "--work",
            args.work,
            "--oracle-only",
            bad["slip"],
        ]
    )
    assert probe.returncode != 0 and "AssertionError" in probe.stderr
    mutants.append(
        {
            "name": "artifact-validation-removed",
            "producer_exit": 0,
            "oracle_exit": probe.returncode,
            "assertion": probe.stderr.splitlines()[-1],
            "mutant_sha256": sha(mutant.read_bytes()),
        }
    )
    # Install the literal release payload into a disposable clean pinned clone.
    installed = args.work / "installed-payload"
    probe = command(["git", "clone", "--no-hardlinks", "--quiet", repo, installed])
    assert probe.returncode == 0, probe.stderr
    git(installed, "checkout", "--quiet", "--detach", args.expected_rev)
    package = installed / PREFIX
    expected = blobs(repo, args.expected_rev)
    shutil.rmtree(package)
    package.mkdir()
    with zipfile.ZipFile(first / EXPECT["archive"]) as archive:
        for name in archive.namelist():
            destination = package.joinpath(*PurePosixPath(name).parts)
            assert destination.resolve().is_relative_to(package.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
    actual = {p.relative_to(package).as_posix(): p.read_bytes() for p in package.rglob("*") if p.is_file()}
    assert actual == expected, "installed release payload differs from Git"
    assert git(installed, "status", "--porcelain") == b""
    assert git(repo, "status", "--porcelain") == b""
    report = {
        "candidate": args.expected_rev,
        "baseline": EXPECT["baseline"],
        "passed": True,
        "installed_payload_clean": True,
        "evidence": evidence,
        "cases": records,
        "effective_mutations": mutants,
        "harness_sha256": sha(Path(__file__).read_bytes()),
        "expectations_sha256": sha(Path(__file__).with_name("expectations.json").read_bytes()),
    }
    (args.work / "release-r.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": True,
                "real_cli_cases": len(records),
                "mutations": len(mutants),
                "archive_sha256": evidence["archive_sha256"],
                "receipt_sha256": evidence["receipt_sha256"],
                "file_count": evidence["file_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
