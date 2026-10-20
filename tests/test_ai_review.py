"""Offline provider simulation: receipts are bound to disposable repository paths."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAKE = """#!/usr/bin/env python3
import json, os, pathlib, re, sys
counter=pathlib.Path(os.environ["FAKE_COUNTER"])
count=int(counter.read_text())+1 if counter.exists() else 1
counter.write_text(str(count))
mode=os.environ.get('FAKE_MODE','ok')
if mode == 'transient' and count == 1:
    print('503 Service Unavailable', file=sys.stderr); sys.exit(7)
if mode == 'permanent':
    print('Permission denied 503', file=sys.stderr); sys.exit(7)
for line in sys.stdin:
    message=json.loads(line)['message']['content']
    chunk=message.startswith('Speichere diesen Kontext-Chunk ')
    if chunk:
        n=re.search(r'Kontext-Chunk (\\d+)/',message).group(1)
        if mode == 'missing_ack': sys.exit(0)
        response=('WRONG' if mode == 'wrong_ack' else '' if mode == 'empty_ack' else 'OK CHUNK '+n)
    else:
        if mode == 'missing_final': sys.exit(0)
        response=json.dumps({'verdict':'mergeable','findings':[],'conditions':[]})
        if mode == 'empty_final': response=''
        if mode == 'bad_report': response='{"findings":[]}'
        if mode == 'conditional': response=json.dumps({'verdict':'conditional','findings':[],'conditions':['fix']})
        if mode == 'malformed': print('broken'); sys.exit(0)
    print(json.dumps({'event':'result','result':{'status':'SUCCESS','response':response}}),flush=True)
"""


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE).decode().strip()


@pytest.fixture
def review_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "offline@example.invalid")
    git(repo, "config", "user.name", "Offline simulation")
    (repo / "scripts").mkdir()
    for path in (ROOT / "scripts").glob("ai_review*"):
        shutil.copy(path, repo / "scripts" / path.name)
    (repo / "docs").mkdir()
    for name in (
        "AGENTS.md",
        "CONTRACT.md",
        "PROVENANCE_API.md",
        "TRAINING_API.md",
        "WEATHER_API.md",
        "docs/ai_review_context.md",
        "docs/fork_workflow.md",
        "docs/fork_release_review_context.md",
    ):
        (repo / name).write_text("Offline fixture context\n")
    (repo / ".gitignore").write_text("reviews/ai/\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    (repo / "docs/change.md").write_text("Complete changed documentation\n")
    (repo / ".github").mkdir()
    (repo / ".github/test.yml").write_text("complete CI change\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "delivery")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    agy = bindir / "agy"
    agy.write_text(FAKE)
    agy.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
        "AI_REVIEW_MAX_RETRIES": "0",
        "AI_REVIEW_CHUNK_BYTES": "2000",
        "FAKE_COUNTER": str(tmp_path / "provider.calls"),
    }
    return repo, base, env


def cli(source, command="run", *, extra=(), ok=True, mode="ok", input=None):
    repo, base, env = source
    result = subprocess.run(
        [sys.executable, str(repo / "scripts/ai_review.py"), command, "--repo", str(repo), "--ref", base, *extra],
        env={**env, "FAKE_MODE": mode},
        text=True,
        capture_output=True,
        input=input,
    )
    assert (result.returncode == 0) is ok, result.stdout + result.stderr
    return result


def test_full_delivery_receipt_and_drift(review_repo):
    repo, base, _ = review_repo
    result = cli(review_repo)
    directory = Path(result.stdout.strip())
    receipt = directory / "receipt.json"
    prompt = (directory / "prompt.md").read_text()
    assert "Complete changed documentation" in prompt
    assert "complete CI change" in prompt
    cli(review_repo, "check", extra=("--receipt", str(receipt)))
    (repo / "docs/new.md").write_text("Untracked cannot be omitted")
    cli(review_repo, "check", extra=("--receipt", str(receipt)), ok=False)
    (repo / "docs/new.md").unlink()
    (repo / "docs/change.md").write_text("mutated source")
    cli(review_repo, "check", extra=("--receipt", str(receipt)), ok=False)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "drift")
    cli(review_repo, "check", extra=("--receipt", str(receipt)), ok=False)
    assert base != git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "mode",
    [
        "wrong_ack",
        "empty_ack",
        "missing_ack",
        "missing_final",
        "empty_final",
        "bad_report",
        "conditional",
        "malformed",
        "permanent",
    ],
)
def test_transport_and_report_fail_closed(review_repo, mode):
    result = cli(review_repo, ok=False, mode=mode)
    directory = Path(result.stdout.strip())
    receipt = json.loads((directory / "receipt.json").read_text())
    assert (directory / "stderr.txt").exists()
    assert receipt["snapshot"]["model"] == "Gemini 3.8 Flash (High)"
    cli(review_repo, "check", extra=("--receipt", str(directory / "receipt.json")), ok=False)


def test_artifact_and_provider_tampering(review_repo):
    result = cli(review_repo)
    directory = Path(result.stdout.strip())
    receipt = directory / "receipt.json"
    (directory / "response.json").write_text('{"verdict":"mergeable","findings":[],"conditions":[]} ')
    cli(review_repo, "check", extra=("--receipt", str(receipt)), ok=False)


def test_existing_target_and_pre_push_requires_explicit_base(review_repo):
    repo, base, _ = review_repo
    target = git(repo, "rev-parse", "HEAD")
    (repo / "docs/later.md").write_text("later governance")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "later")
    result = cli(review_repo, extra=("--target", target))
    directory = Path(result.stdout.strip())
    cli(review_repo, "check", extra=("--target", target, "--receipt", str(directory / "receipt.json")))
    line = f"refs/heads/existing {target} refs/heads/existing {base}\n"
    cli(review_repo, "pre-push", input=line, ok=False)
    git(repo, "config", "aiReview.deliveryBase", base)
    # Policy/CI changes require a separate meta receipt.
    cli(review_repo, "pre-push", input=line, ok=False)
    cli(review_repo, extra=("--target", target, "--mode", "meta"))
    cli(review_repo, "pre-push", input=line)
    wrong = git(repo, "rev-parse", "HEAD")
    cli(review_repo, "pre-push", input=line.replace(target, wrong), ok=False)


def test_transient_retry_and_protocol_failures_never_retry(review_repo):
    repo, base, env = review_repo
    env.update(
        {"AI_REVIEW_MAX_RETRIES": "2", "AI_REVIEW_INITIAL_BACKOFF_SECONDS": "1", "AI_REVIEW_RETRY_BUDGET_SECONDS": "15"}
    )
    counter = Path(env["FAKE_COUNTER"])
    cli(review_repo, mode="transient")
    assert counter.read_text() == "2"
    for mode in ("permanent", "wrong_ack", "malformed", "missing_final"):
        counter.unlink()
        cli(review_repo, mode=mode, ok=False)
        assert counter.read_text() == "1", mode
