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
import re
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


def android_suites(candidate, target, profile, plan):
    """Prune only a reviewed closed case; unknown/mixed changes keep all suites.

    Fingerprints bind every supporting test/harness source in the reviewed
    closure. If those tests evolve, exclusions stop until the closure is reviewed
    again. Presence of a product directory never assigns ownership of that code.
    """
    suites = profile["suites"]
    if not plan or not plan.get("paths") or plan.get("regular") is not True:
        return suites
    inputs = json.loads((ROOT / ".github/pr-ci-platform-inputs.json").read_text(), object_pairs_hook=C.unique)
    C.require(type(inputs) is dict and set(inputs) == {"schema", "android", "infrastructure", "fallback"}
              and inputs["schema"] == 2 and inputs["fallback"] == "complete-reviewed-profile"
              and type(inputs["android"]) is list and type(inputs["infrastructure"]) is list,
              "invalid platform input closure policy")
    C.require(type(plan["paths"]) is list and all(type(path) is str and path
              and not Path(path).is_absolute() and ".." not in Path(path).parts
              for path in plan["paths"]), "invalid platform change paths")
    known = {suite["name"] for suite in suites}
    conditional = {}
    owners = policy()["android"]
    for closure in inputs["infrastructure"]:
        C.require(type(closure) is dict and set(closure) == {"name", "targets", "inputs"}
                  and type(closure["name"]) is str and closure["name"] not in conditional
                  and type(closure["targets"]) is list and bool(closure["targets"])
                  and len(set(closure["targets"])) == len(closure["targets"])
                  and set(closure["targets"]).issubset(owners)
                  and type(closure["inputs"]) is list and bool(closure["inputs"])
                  and all(type(path) is str and path and not Path(path).is_absolute()
                          and ".." not in Path(path).parts for path in closure["inputs"]),
                  "invalid infrastructure suite input closure")
        for owner in closure["targets"]:
            C.require(closure["name"] in {suite["name"] for suite in owners[owner]["suites"]},
                      "infrastructure closure names an unowned suite")
        conditional[closure["name"]] = closure
    selected = [suite for suite in suites if suite["name"] not in conditional
                or bool(set(plan["paths"]) & set(conditional[suite["name"]]["inputs"]))]
    for case in inputs["android"]:
        C.require(type(case) is dict and set(case) == {"target", "paths_under", "suffix", "inventory", "omit"}
                  and type(case["paths_under"]) is str and case["paths_under"].startswith("android/")
                  and ".." not in Path(case["paths_under"]).parts
                  and case["suffix"] == ".java" and type(case["inventory"]) is dict
                  and bool(case["inventory"]) and type(case["omit"]) is list,
                  "invalid reviewed Android closure")
        if target != case["target"] or not all(type(path) is str and path.startswith(case["paths_under"])
                and path.endswith(case["suffix"]) for path in plan["paths"]):
            continue
        for path, expected in case["inventory"].items():
            C.require(type(path) is str and not Path(path).is_absolute() and ".." not in Path(path).parts
                      and type(expected) is str and re.fullmatch(r"[0-9a-f]{40}", expected),
                      "invalid Android harness input fingerprint")
            try:
                actual = subprocess.check_output(["git", "--no-replace-objects", "rev-parse", "HEAD:" + path],
                                                 cwd=candidate, stderr=subprocess.DEVNULL).decode().strip()
            except subprocess.CalledProcessError:
                return selected
            if actual != expected:
                return selected
        C.require(set(case["omit"]).issubset(known), "Android input closure names an unowned suite")
        return [suite for suite in selected if suite["name"] not in case["omit"]]
    return selected


def commands(candidate, target, lane, plan=None):
    value = policy()
    if lane == "ios":
        C.require(target == value["ios"]["target"], "iOS owner selected on another target")
        return value["ios"]["commands"]
    C.require(lane == "android" and target in value["android"], "Android owner selected on another target")
    profile = value["android"][target]
    actual = json.loads(subprocess.check_output(["git", "--no-replace-objects", "show",
        "HEAD:tests/platform-profile.json"], cwd=candidate), object_pairs_hook=C.unique)
    C.require(actual == profile, "candidate platform inventory differs from protected mandatory suites")
    return [[suite["interpreter"], suite["entrypoint"]]
            for suite in android_suites(candidate, target, profile, plan)]


def qml_runner():
    return next((path for path in ("/usr/lib/qt6/bin/qmltestrunner", "/usr/lib64/qt6/bin/qmltestrunner")
                 if Path(path).is_file()), None)


def android_compile_commands(target, plan, runtime, prepared_roots):
    products = plan.get("android_compile_products", [])
    C.require(type(products) is list and len(products) == len(set(products))
              and set(products).issubset({"common", "phone", "pico"}), "invalid Android compile ownership")
    if not products:
        return []
    owner = {"android-main": "common", "android-vr": "common",
             "android-phone": "phone", "android-vr-pico": "pico"}
    C.require(products == [owner.get(target)], "Android compiler selected an unowned product")
    C.require(runtime is not None, "selected Android compilation requires its real API runtime")
    runtime = Path(runtime).resolve(strict=True)
    roots = [Path(path).resolve(strict=True) for path in prepared_roots]
    C.require(any(runtime == root or root in runtime.parents for root in roots),
              "Android runtime is outside the explicit prepared inputs")
    script = (ROOT / "tools/repository-checks/pr_ci_android.py").read_text()
    # The controller supplies this exact reviewed compiler, not a candidate
    # script capable of claiming success without compiling production source.
    return [[sys.executable, "-I", "-S", "-B", "-c", script, "compile",
             "--runtime", str(runtime), "--product", product] for product in products]


def execute(candidate, context, plan, lane, prepared_roots, *, recompute, android_runtime=None,
            android_native_runtime=None):
    candidate = authenticate(candidate, context, plan, recompute)
    C.require(lane in {"android", "ios"} and plan[lane + "_required"] is True,
              "unselected platform execution")
    if lane == 'android' and plan.get('android_native_products'):
        import pr_ci_android_native as native
        native.prerequisites(candidate, plan, context['target'])
        C.require(android_native_runtime is not None, 'Selected Android native build requires its immutable runtime')
        root = Path(android_native_runtime).resolve(strict=True)
        C.require(any(root == Path(path).resolve(strict=True) or Path(path).resolve(strict=True) in root.parents
                      for path in prepared_roots), 'Android native runtime is outside explicit prepared inputs')
    results = []
    for arguments in commands(candidate, context["target"], lane, plan):
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
    if lane == "android":
        for command in android_compile_commands(context["target"], plan, android_runtime, prepared_roots):
            status = R.run(candidate, command, prepared_roots=prepared_roots,
                           boundary="user-namespace", timeout=600)
            C.require(status == 0, "selected Android production Java/resource compilation failed")
            authenticate(candidate, context, plan, recompute)
            results.append({"command": ["android-production-compile", "--product", command[-1]],
                            "scope": "production-java-and-resources", "result": "success"})
        if plan.get('android_native_products'):
            import pr_ci_android_native as native
            result = native.execute(candidate, context, plan, android_native_runtime,
                authenticate=lambda: authenticate(candidate, context, plan, recompute))
            results.append({'command': ['android-native-offline', '--product', result['product']],
                            'scope': 'production-native-product', 'result': 'success', 'qualification': result})
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
