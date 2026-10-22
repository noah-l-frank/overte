#!/usr/bin/env python3
"""Execute reviewed product contracts; verify same-run iOS build artifacts.

Candidate profiles are data, never authority to omit a protected product suite.
Hardware tests remain a separate Jenkins laboratory responsibility.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pr_ci_context as C
import pr_ci_run as R

ROOT = Path(__file__).resolve().parents[2]
POLICY = ".github/pr-ci-platforms.json"


def policy():
    value = json.loads((ROOT / POLICY).read_text(), object_pairs_hook=C.unique)
    C.require(type(value) is dict and set(value) == {"schema", "android", "ios"}
              and value["schema"] == 1
              and set(value["android"]) == {"android-main", "android-phone", "android-vr", "android-vr-pico"}
              and value["ios"] == {"target": "apple-ios", "commands": [["bash", "ios/tests/run-tests.sh"]]},
              "incomplete trusted platform ownership")
    for profile in value["android"].values():
        C.require(type(profile) is dict and set(profile) == {"schema", "platform", "suites"}
                  and profile["schema"] == 1 and profile["platform"] == "android"
                  and type(profile["suites"]) is list and bool(profile["suites"]),
                  "invalid trusted Android suite inventory")
        names = set()
        for suite in profile["suites"]:
            C.require(type(suite) is dict and set(suite) == {"name", "entrypoint", "interpreter"}
                      and type(suite["name"]) is str and suite["name"] not in names
                      and suite["interpreter"] in {"python", "bash"}
                      and type(suite["entrypoint"]) is str
                      and not Path(suite["entrypoint"]).is_absolute()
                      and ".." not in Path(suite["entrypoint"]).parts,
                      "unsafe or duplicate trusted platform command")
            names.add(suite["name"])
    return value


def authenticate(candidate, context, plan, recompute):
    candidate = Path(candidate).resolve(strict=True)
    def git(*args):
        return subprocess.check_output(["git", "--no-replace-objects", *args], cwd=candidate).decode().strip()
    C.require(git("rev-parse", "HEAD") == context["original_merge"]
              and git("rev-parse", "HEAD^{tree}") == context["tree"]
              and not git("diff", "HEAD", "--"), "platform checkout differs from its immutable source")
    C.require(C.canonical(recompute(candidate, context)) == C.canonical(plan),
              "platform ownership differs from the independently recomputed plan")
    return candidate


def commands(candidate, target, lane):
    value = policy()
    if lane == "ios":
        C.require(target == value["ios"]["target"], "iOS owner selected on another target")
        return value["ios"]["commands"]
    C.require(lane == "android" and target in value["android"], "Android owner selected on another target")
    profile = value["android"][target]
    actual = json.loads(subprocess.check_output(["git", "--no-replace-objects", "show",
        "HEAD:tests/platform-profile.json"], cwd=candidate), object_pairs_hook=C.unique)
    C.require(actual == profile, "candidate platform inventory differs from protected mandatory suites")
    return [[suite["interpreter"], suite["entrypoint"]] for suite in profile["suites"]]


def qml_runner():
    return next((path for path in ("/usr/lib/qt6/bin/qmltestrunner", "/usr/lib64/qt6/bin/qmltestrunner")
                 if Path(path).is_file()), None)


def execute(candidate, context, plan, lane, prepared_roots, *, recompute):
    candidate = authenticate(candidate, context, plan, recompute)
    C.require(lane in {"android", "ios"} and plan[lane + "_required"] is True,
              "unselected platform execution")
    results = []
    for arguments in commands(candidate, context["target"], lane):
        command = [sys.executable if item == "python" and index == 0 else item
                   for index, item in enumerate(arguments)]
        if lane == "ios":
            qml = qml_runner()
            C.require(qml is not None, "required iOS host QML tool is unavailable")
            command = ["/usr/bin/env", "OVERTE_REQUIRE_QML_TESTS=1",
                "OVERTE_HOST_TEST_NETWORK_RUNNER=/work/ios/ci/host-test-network.sh",
                "OVERTE_QML_TEST_RUNNER=" + qml, *command]
        status = R.run(candidate, command, prepared_roots=prepared_roots,
                       boundary="user-namespace", timeout=1200)
        C.require(status == 0, "selected product command failed: " + " ".join(arguments))
        authenticate(candidate, context, plan, recompute)
        results.append({"command": arguments, "result": "success"})
    C.require(bool(results), "selected product owner executed no contracts")
    return {"kind": "pr-ci-product-execution-v1", "source": context["original_merge"],
            "tree": context["tree"], "target": context["target"], "result": "success", "commands": results}


def ios_verifier():
    path = ROOT / "tools/ios-build-qualification/check.py"
    spec = importlib.util.spec_from_file_location("central_ios_artifact_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_ios(candidate, context, plan, artifacts, needs, api, *, recompute, pause=time.sleep):
    authenticate(candidate, context, plan, recompute)
    C.require(context["target"] == "apple-ios" and plan["ios_required"] is True,
              "unselected iOS product verification")
    C.require(type(needs) is dict and set(needs) == {"host", "qt", "client"}
              and needs["host"].get("result") == "success", "iOS host owner did not succeed")
    build = plan["ios_build_required"]
    for owner in ("qt", "client"):
        C.require(needs[owner].get("result") == ("success" if build else "skipped"),
                  "iOS build ownership differs from the selected inputs")
    C.bookend(api, context)
    artifact = None
    if build:
        verifier = ios_verifier()
        run, attempt = int(os.environ["GITHUB_RUN_ID"]), int(os.environ["GITHUB_RUN_ATTEMPT"])
        C.require((run, attempt) == (context["run_id"], context["run_attempt"]),
                  "iOS artifact belongs to another execution")
        deadline = time.monotonic() + 600
        while True:
            rows = api.pages(f"actions/runs/{run}/attempts/{attempt}/jobs", field="jobs")
            prefix = "iOS product owner / "
            jobs = [{**row, "name": row["name"].removeprefix(prefix)} for row in rows
                    if row.get("name", "").startswith(prefix)]
            C.require(not any(row.get("conclusion") in {"failure", "cancelled", "timed_out", "action_required"}
                              for row in jobs), "selected iOS execution failed")
            expected = {"iOS host contracts", "qt / qt-ios-source", "client / Host contracts",
                        "client / Static JITless V8 checkpoint", "client / Toolchain, dependencies, build and package"}
            selected = [row for row in jobs if row.get("name") in expected]
            if len(selected) == len(expected) and all(row.get("status") == "completed" for row in selected):
                verifier.verify_build_execution(jobs, run, attempt, context["head"])
                break
            C.require(time.monotonic() < deadline, "iOS terminal job metadata did not become available")
            pause(15)
        artifact = verifier.verify_ipa(Path(artifacts), context["original_merge"], int(os.environ["GITHUB_RUN_NUMBER"]))
    authenticate(candidate, context, plan, recompute)
    C.bookend(api, context)
    return {"result": "success", "source": context["original_merge"], "tree": context["tree"],
            "application_build_required": build, "artifact": artifact, "device_acceptance": "not-performed"}
