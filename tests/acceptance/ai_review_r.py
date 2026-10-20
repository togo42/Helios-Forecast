#!/usr/bin/env python3
"""Independent mandatory-review acceptance using throwaway Git fixtures.

All provider output is explicitly OFFLINE SIMULATION. Never authorizes delivery.
Invokes the real CLI; does not import producer implementation or its tests.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(argv, cwd, env=None):
    return subprocess.run(
        [str(x) for x in argv],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=35,
    )


def git(repo, *args):
    result = invoke(["git", *args], repo)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def write(repo, name, value):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def commit(repo, message):
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=Offline R",
        "-c",
        "user.email=offline@example.invalid",
        "commit",
        "-qm",
        message,
    )
    return git(repo, "rev-parse", "HEAD")


FAKE = r"""#!/usr/bin/env python3
# Independent offline simulator; no real provider contacted.
import json, os, re, sys
from pathlib import Path
args = sys.argv[1:]
if '--help' in args:
    print('--input-format stream-json --output-format stream-json')
    raise SystemExit(0)
if '--version' in args:
    print('OFFLINE-SIMULATION')
    raise SystemExit(0)
with Path(os.environ['R_CALLS']).open('a') as log:
    log.write(json.dumps(args) + '\n')
mode = os.environ.get('R_CASE', 'success')
if mode == 'exit_failure':
    print('permanent independent simulation failure', file=sys.stderr)
    raise SystemExit(17)
for line in sys.stdin:
    message = json.loads(line)['message']['content']
    with Path(os.environ['R_TURNS']).open('a') as log:
        log.write(json.dumps(message) + '\n')
    match = re.match(r'Speichere diesen Kontext-Chunk (\d+)/', message)
    if match:
        response = 'OK CHUNK ' + match.group(1)
        if mode == 'wrong_ack': response = 'OK CHUNK 900.'
        if mode == 'ack_suffix': response += ' extra'
        if mode == 'missing_ack': raise SystemExit(0)
    else:
        if mode == 'missing_final': raise SystemExit(0)
        response = json.dumps({'verdict':'mergeable', 'findings':[], 'conditions':[]})
        if mode == 'empty_final': response = ''
        if mode == 'malformed_verdict': response = '{invalid'
        if mode == 'blocker': response = json.dumps({'verdict':'blocked', 'findings':[{'severity':'high','file':'docs/new.md','reason':'independent blocker'}], 'conditions':[]})
        if mode == 'conditions': response = json.dumps({'verdict':'conditional', 'findings':[], 'conditions':['must fix before delivery']})
        if mode == 'mergeable_conditions': response = json.dumps({'verdict':'mergeable', 'findings':[], 'conditions':['unmet']})
        if mode == 'unknown_verdict': response = json.dumps({'verdict':'looks fine', 'findings':[], 'conditions':[]})
        if mode == 'missing_findings': response = json.dumps({'verdict':'mergeable', 'conditions':[]})
        if mode == 'duplicate_keys': response = '{"verdict":"blocked","verdict":"mergeable","findings":[],"conditions":[]}'
    if mode == 'malformed_transport':
        print('{broken', flush=True)
        raise SystemExit(0)
    print(json.dumps({'event':'result','result':{'status':'SUCCESS','response':response}}), flush=True)
"""


def exercise(source, work):
    repo = work / "fixture"
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    for name in (
        "ai_review.py",
        "ai_review.sh",
        "ai_review_provider.sh",
        "ai_review_transport.sh",
    ):
        candidate = source / "scripts" / name
        if not candidate.exists():
            candidate = source / name
        write(repo, "scripts/" + name, candidate.read_text())
    for name in (
        "AGENTS.md",
        "docs/ai_review_context.md",
        "docs/fork_workflow.md",
        "CONTRACT.md",
        "PROVENANCE_API.md",
        "TRAINING_API.md",
        "WEATHER_API.md",
        "docs/fork_release_review_context.md",
    ):
        write(repo, name, "Independent offline fixture policy context.\n")
    write(repo, ".gitignore", "reviews/ai/\n")
    write(repo, "custom_components/helios_forecast/runtime.py", "old_runtime = 1\n")
    base = commit(repo, "offline baseline")
    write(
        repo,
        "custom_components/helios_forecast/runtime.py",
        "independent_runtime_marker = 2\n",
    )
    write(
        repo,
        "docs/new.md",
        "independent_document_marker\n" + "R context coverage line\n" * 6000 + "independent_document_tail\n",
    )
    write(repo, ".github/workflows/test.yml", "independent_ci_marker: yes\n")
    target = commit(repo, "offline complete delivery")
    binary = work / "bin"
    binary.mkdir()
    agy = binary / "agy"
    agy.write_text(FAKE)
    agy.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "R_CALLS": str(work / "calls.jsonl"),
        "R_TURNS": str(work / "turns.jsonl"),
        "AI_REVIEW_CHUNK_BYTES": "100000",
        "AI_REVIEW_CHUNK_SLEEP_SECONDS": "0",
        "AI_REVIEW_INITIAL_BACKOFF_SECONDS": "1",
        "AI_REVIEW_MAX_RETRIES": "0",
        "AI_REVIEW_RETRY_BUDGET_SECONDS": "3",
    }
    records = []

    def cli(
        case,
        action="run",
        ok=True,
        receipt=None,
        ref=base,
        selected=None,
        extra_env=None,
        mode="full",
    ):
        argv = [
            sys.executable,
            repo / "scripts/ai_review.py",
            action,
            "--repo",
            repo,
            "--ref",
            ref,
            "--mode",
            mode,
        ]
        if receipt:
            argv += ["--receipt", receipt]
        if selected:
            argv += ["--target", selected]
        result = invoke(argv, repo, {**env, "R_CASE": case, **(extra_env or {})})
        records.append(
            {
                "case": case,
                "action": action,
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        assert (result.returncode == 0) == ok, records[-1]
        return result

    prepared = cli("prepare", "prepare")
    directory = Path(prepared.stdout.strip().splitlines()[0])
    prompt = (directory / "prompt.md").read_text()
    for marker in (
        "independent_runtime_marker",
        "independent_document_marker",
        "independent_ci_marker",
        "independent_document_tail",
    ):
        assert marker in prompt, marker
    snapshot = json.loads((directory / "snapshot.json").read_text())
    assert snapshot["base"] == base and snapshot["target"] == target
    assert {
        ".github/workflows/test.yml",
        "docs/new.md",
        "custom_components/helios_forecast/runtime.py",
    } <= set(snapshot["files"])
    positive = cli("success")
    receipt = Path(positive.stdout.strip().splitlines()[0]) / "receipt.json"
    positive_turns = [json.loads(line) for line in (work / "turns.jsonl").read_text().splitlines()]
    assert sum(t.startswith("Speichere diesen Kontext-Chunk ") for t in positive_turns) >= 3, (
        "multiple real context turns required"
    )
    assert len(positive_turns) >= 4 and not positive_turns[-1].startswith("Speichere diesen Kontext-Chunk "), (
        "separate final turn missing"
    )
    cli("valid_receipt", "check", receipt=receipt)
    reviewed_artifacts = {
        name: digest(receipt.parent / name) for name in ("prompt.md", "response.json", "snapshot.json")
    }
    positive_receipt = json.loads(receipt.read_text())
    for name, expected_digest in reviewed_artifacts.items():
        assert positive_receipt["artifacts"][name] == expected_digest, "actual artifact hash mismatch: " + name
    for case in (
        "exit_failure",
        "wrong_ack",
        "ack_suffix",
        "missing_ack",
        "missing_final",
        "empty_final",
        "malformed_verdict",
        "blocker",
        "conditions",
        "mergeable_conditions",
        "unknown_verdict",
        "missing_findings",
        "duplicate_keys",
        "malformed_transport",
    ):
        cli(case, ok=False)
    cli("success", mode="meta")

    def push(case, pushed, previous, ok):
        result = subprocess.run(
            [
                sys.executable,
                str(repo / "scripts/ai_review.py"),
                "pre-push",
                "--repo",
                str(repo),
            ],
            cwd=repo,
            env=env,
            input=f"refs/heads/offline {pushed} refs/heads/offline {previous}\n",
            text=True,
            capture_output=True,
            timeout=35,
        )
        records.append(
            {
                "case": case,
                "action": "pre-push",
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        assert (result.returncode == 0) == ok, records[-1]

    push("missing_selected_base", target, base, False)
    git(repo, "config", "aiReview.deliveryBase", base)
    push("actual_pushed_target", target, base, True)
    push("branch_creation_full_scope", target, "0" * 40, True)
    git(repo, "config", "aiReview.deliveryBase", target)
    push("branch_creation_wrong_scope", target, "0" * 40, False)
    git(repo, "config", "aiReview.deliveryBase", base)
    push("unrelated_pushed_target", base, base, False)
    for name in ("docs/new.md", "untracked.txt"):
        file = repo / name
        before = file.read_bytes() if file.exists() else None
        file.write_text("independent drift\n")
        cli("dirty_" + name.replace("/", "_"), "check", ok=False, receipt=receipt)
        if before is None:
            file.unlink()
        else:
            file.write_bytes(before)
    cli("different_base", "check", ok=False, receipt=receipt, ref=target)
    cli("different_target", "check", ok=False, receipt=receipt, selected=base)
    for field, replacement in (("exit", 17), ("command", ["unrelated command"])):
        original = receipt.read_bytes()
        changed = json.loads(original)
        changed[field] = replacement
        receipt.write_text(json.dumps(changed))
        cli("receipt_" + field, "check", ok=False, receipt=receipt)
        receipt.write_bytes(original)
    original = agy.read_bytes()
    agy.write_bytes(original + b"\n# independent provider drift\n")
    cli("provider_drift", "check", ok=False, receipt=receipt)
    agy.write_bytes(original)
    for name in ("response.json", "prompt.md", "snapshot.json"):
        artifact = receipt.parent / name
        original = artifact.read_bytes()
        artifact.write_bytes(original + b"\n")
        cli("tamper_" + name, "check", ok=False, receipt=receipt)
        artifact.write_bytes(original)
        artifact.unlink()
        cli("delete_" + name, "check", ok=False, receipt=receipt)
        artifact.write_bytes(original)
    copied = work / "copied-repository"
    shutil.copytree(repo, copied)
    copied_result = invoke(
        [
            sys.executable,
            copied / "scripts/ai_review.py",
            "check",
            "--repo",
            copied,
            "--ref",
            base,
            "--mode",
            "full",
            "--receipt",
            receipt,
        ],
        copied,
        env,
    )
    records.append(
        {
            "case": "receipt_other_repository",
            "exit": copied_result.returncode,
            "stderr": copied_result.stderr,
        }
    )
    assert copied_result.returncode != 0, records[-1]
    write(repo, "docs/after-review.md", "independent later committed source drift\n")
    commit(repo, "later unreviewed change")
    cli("different_head", "check", ok=False, receipt=receipt)
    cli(
        "different_policy_head_same_target",
        "check",
        ok=False,
        receipt=receipt,
        selected=target,
    )
    argv = json.loads((work / "calls.jsonl").read_text().splitlines()[0])
    assert argv[argv.index("--model") + 1] == "Gemini 3.8 Flash (High)", argv
    turns = [json.loads(line) for line in (work / "turns.jsonl").read_text().splitlines()]
    assert sum(t.startswith("Speichere diesen Kontext-Chunk ") for t in turns) > 2
    assert any(not t.startswith("Speichere diesen Kontext-Chunk ") for t in turns)
    return {
        "offline_simulation_only": True,
        "positive_artifact_sha256": reviewed_artifacts,
        "base": base,
        "target": target,
        "cases": records,
        "helper_sha256": {p.name: digest(p) for p in (repo / "scripts").glob("ai_review*")},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--mutants", action="store_true")
    parser.add_argument("--expected-rev")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    preservation = {}
    if (args.source / ".git").exists():
        assert args.expected_rev, "--expected-rev required for repository acceptance"
        assert git(args.source, "rev-parse", "HEAD") == args.expected_rev, "candidate HEAD drift"
        for path in (args.source / "scripts").glob("ai_review*"):
            committed = subprocess.check_output(
                ["git", "-C", str(args.source), "show", args.expected_rev + ":scripts/" + path.name]
            )
            assert path.read_bytes() == committed, "candidate helper drift: " + path.name
        frozen = "a8ba20b2257cc7a747542fc45c08528273f0f664"
        paths = subprocess.check_output(
            [
                "git",
                "-C",
                str(args.source),
                "ls-tree",
                "-rz",
                "--name-only",
                frozen,
                "--",
                "custom_components",
                "hacs.json",
                "tests/acceptance/fork_release_r.py",
                "tests/acceptance/clock_fixture_r.py",
            ]
        ).split(b"\0")
        for raw in filter(None, paths):
            name = raw.decode()
            before = subprocess.check_output(["git", "-C", str(args.source), "show", frozen + ":" + name])
            assert (args.source / name).read_bytes() == before, "protected source changed: " + name
            preservation[name] = hashlib.sha256(before).hexdigest()
        assert git(args.source, "rev-parse", "refs/tags/v2026.10.0rc1") == "391e386a6a5d7144e585671f0e5f08552681a916", (
            "rc1 tag moved"
        )
    result = exercise(args.source, args.work)
    result["preserved_file_sha256"] = preservation
    result["source_commit"] = args.expected_rev
    if args.mutants:
        negatives = []
        for name, filename, needle, replacement, expected_case in (
            (
                "clean-guard-removed",
                "ai_review.py",
                'if git(repo, "status",',
                'if False and git(repo, "status",',
                "dirty_docs_new.md",
            ),
            (
                "ack-guard-removed",
                "ai_review_transport.sh",
                'response.strip() != f"OK CHUNK {index}"',
                "False",
                "wrong_ack",
            ),
        ):
            mutated = args.work / name
            (mutated / "scripts").mkdir(parents=True)
            for original in (args.source / "scripts").glob("ai_review*"):
                shutil.copy2(original, mutated / "scripts" / original.name)
            path = mutated / "scripts" / filename
            text = path.read_text()
            assert needle in text, "mutation target absent: " + name
            path.write_text(text.replace(needle, replacement))
            trial = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--source",
                    str(mutated),
                    "--work",
                    str(args.work / (name + "-trial")),
                ],
                cwd=args.work,
                text=True,
                capture_output=True,
                timeout=90,
            )
            assert trial.returncode != 0 and "AssertionError" in trial.stderr and expected_case in trial.stderr, (
                trial.stdout + trial.stderr
            )
            (args.work / (name + ".stderr")).write_text(trial.stderr)
            negatives.append(
                {
                    "mutation": name,
                    "harness_exit": trial.returncode,
                    "real_assertion_failure": True,
                    "case": expected_case,
                }
            )
        result["negative_controls"] = negatives
    (args.work / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": True,
                "cases": len(result["cases"]),
                "offline_simulation_only": True,
            }
        )
    )


if __name__ == "__main__":
    main()
