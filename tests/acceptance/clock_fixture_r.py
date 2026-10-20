#!/usr/bin/env python3
"""Independent narrow clock-fixture acceptance; invokes the original real HA test."""

import argparse
import ast
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

BASE = "95e96d73938feb3abf6210b092573d778836308b"
TEST = "tests/ha/test_init.py"
TARGET = "test_hour_rollover_triggers_off_cycle_refresh"
RUNTIME = "custom_components/helios_forecast/__init__.py"
LISTENER = "    entry.async_on_unload(async_track_time_change(hass, _hour_rolled_over, minute=minute, second=second))\n"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


def dump(node):
    return ast.dump(node, include_attributes=False)


def assertion_ast(module):
    return [
        dump(node)
        for node in ast.walk(module)
        if isinstance(node, ast.Assert)
        or (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert_")
        )
    ]


def check_scope(repo, revision):
    before = ast.parse(git(repo, "show", BASE + ":" + TEST))
    after = ast.parse(git(repo, "show", revision + ":" + TEST))
    originals = assertion_ast(before)
    assert originals == assertion_ast(after), "original assertion AST changed"
    target = next(node for node in after.body if isinstance(node, ast.AsyncFunctionDef) and node.name == TARGET)
    baseline_target = next(
        node for node in before.body if isinstance(node, ast.AsyncFunctionDef) and node.name == TARGET
    )
    assert [a.arg for a in target.args.args] == [a.arg for a in baseline_target.args.args] + ["freezer"]
    target.args.args.pop()
    freezes = [
        (i, node)
        for i, node in enumerate(target.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and isinstance(node.value.func.value, ast.Name)
        and node.value.func.value.id == "freezer"
        and node.value.func.attr == "move_to"
    ]
    assert len(freezes) == 1, "exactly one fixed initial freezer move required"
    index, statement = freezes[0]
    assert index == 1, "freeze must precede original setup after docstring"
    call = statement.value
    assert len(call.args) == 1 and not call.keywords
    assert isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)
    initial = datetime.fromisoformat(call.args[0].value)
    assert (initial.minute, initial.second) > (9, 23), "initial clock is before entry phase"
    target.body.pop(index)
    assert dump(before) == dump(after), "scope exceeds freezer fixture, fixed clock and comments"
    names = git(repo, "ls-tree", "-rz", "--name-only", BASE, "--", "custom_components").split(b"\0")
    assert names == git(repo, "ls-tree", "-rz", "--name-only", revision, "--", "custom_components").split(b"\0")
    for name in filter(None, names):
        path = name.decode()
        assert git(repo, "show", BASE + ":" + path) == git(repo, "show", revision + ":" + path), path
    assert git(repo, "show", BASE + ":scripts/build_fork_release.py") == git(
        repo, "show", revision + ":scripts/build_fork_release.py"
    )
    return {
        "original_assertion_nodes": len(originals),
        "normalized_module_ast_identical": True,
        "fixed_initial_time": initial.isoformat(),
        "entry_phase": [9, 23],
        "runtime_and_builder_bytes_identical": True,
    }


def probe(python, repo, output):
    argv = [
        str(python),
        "-m",
        "pytest",
        "-o",
        "asyncio_mode=auto",
        "-q",
        TEST + "::" + TARGET,
        "--junitxml=" + str(output),
    ]
    result = subprocess.run(
        argv, cwd=repo, capture_output=True, text=True, timeout=180, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    )
    cases = list(ET.parse(output).getroot().iter("testcase"))
    failures = [item.text or "" for case in cases for item in case if item.tag in ("failure", "error")]
    return {
        "exit": result.returncode,
        "test_count": len(cases),
        "skip_count": sum(case.find("skipped") is not None for case in cases),
        "failures": failures,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "argv": argv,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--expected-rev", required=True)
    parser.add_argument("--ha-python", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    clone = args.work / "candidate"
    result = subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(args.repo), str(clone)], capture_output=True
    )
    assert result.returncode == 0, result.stderr.decode()
    git(clone, "checkout", "--quiet", "--detach", args.expected_rev)
    scope = check_scope(clone, args.expected_rev)
    positive = probe(args.ha_python, clone, args.work / "positive.xml")
    assert (
        positive["exit"] == 0
        and positive["test_count"] == 1
        and not positive["skip_count"]
        and not positive["failures"]
    ), positive
    assert git(clone, "status", "--porcelain") == b""
    source = clone / RUNTIME
    original = source.read_bytes()
    text = original.decode()
    assert text.count(LISTENER) == 1
    source.write_text(text.replace(LISTENER, "    # independent mutation: hourly listener omitted\n"))
    negative = probe(args.ha_python, clone, args.work / "listener-removed.xml")
    assert negative["exit"] == 1 and negative["test_count"] == 1 and not negative["skip_count"]
    assert len(negative["failures"]) == 1
    failure = negative["failures"][0]
    assert "assert_awaited_once" in failure and "Awaited 0 times" in failure, failure
    source.write_bytes(original)
    assert git(clone, "status", "--porcelain") == b""
    report = {
        "passed": True,
        "candidate": args.expected_rev,
        "scope_base": BASE,
        "scope": scope,
        "positive": positive,
        "effective_listener_mutation": negative,
        "harness_sha256": sha(Path(__file__).read_bytes()),
        "source_restored_clean": True,
    }
    output = args.work / "clock-fixture-r.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "passed": True,
                "candidate": args.expected_rev,
                "scope": scope,
                "real_test_passes": 1,
                "effective_mutations": 1,
                "report_sha256": sha(output.read_bytes()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
