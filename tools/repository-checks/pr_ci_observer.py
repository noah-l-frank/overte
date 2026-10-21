#!/usr/bin/env python3
"""Validate trusted execution records and original-source CodeQL uploads.

This module does not authenticate artifact transport or issue execution/reuse
authority. The caller must first authenticate the native run, attempt, workflow
source, successful producer job and downloaded artifact. API adapters expose
GET-only ``get(endpoint)`` objects and complete, bounded ``pages(endpoint)`` lists;
endpoints are relative to the fixed repository, never caller-supplied URLs.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import uuid
from urllib.parse import urlencode


_SPEC = importlib.util.spec_from_file_location(
    "pr_ci_observer_context", Path(__file__).with_name("pr_ci_context.py"))
C = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(C)

WORKFLOW = ".github/workflows/repository-checks.yml"
ANALYSIS_KEY = WORKFLOW + ":codeql"
LANGUAGES = ("javascript-typescript", "python")
MAX_ROWS = 1000


class ObserverError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ObserverError(message)


def _positive(value, label):
    require(type(value) is int and value > 0, "invalid " + label)
    return value


def _context(context):
    require(type(context) is dict and set(C.FIXED_FIELDS) <= context.keys(),
            "incomplete expected PR context")
    require(type(context["repository_id"]) is int and (context["repository"], context["repository_id"])
            == (C.REPOSITORY, C.REPOSITORY_ID), "foreign expected PR context")
    _positive(context["number"], "PR number")
    require(context["target"] in C.TARGETS and type(context["head_ref"]) is str
            and bool(context["head_ref"]), "invalid expected PR branch")
    try:
        for key in ("base", "head", "tree", "original_merge"):
            C.sha(context[key])
    except C.ContextError as error:
        raise ObserverError("invalid expected immutable PR context") from error


def _languages(value):
    require(type(value) is list and value == [name for name in LANGUAGES if name in value],
            "selected CodeQL languages are unknown, duplicated or unordered")
    return value


def expected_owners(plan):
    """Translate only a trusted complete plan into the eight native job duties."""
    require(type(plan) is dict, "trusted CI plan must be an object")
    for key in ("host_suites", "npm_projects"):
        values = plan.get(key)
        require(type(values) is list and all(type(item) is str and item for item in values)
                and len(values) == len(set(values)), "invalid trusted " + key)
    native = plan.get("native")
    require(type(native) is dict and native.get("mode") in {"skip", "core", "full"},
            "invalid trusted native selection")
    languages = _languages(plan.get("codeql_languages"))
    for key in ("workflow_security", "android_required", "ios_required"):
        require(type(plan.get(key)) is bool, "missing trusted selection " + key)
    return {"policy": True, "host": bool(plan["host_suites"]),
            "npm": bool(plan["npm_projects"]), "native": native["mode"] != "skip",
            "codeql": bool(languages), "security": plan["workflow_security"],
            "android": plan["android_required"], "ios": plan["ios_required"]}


def validate_record(record, expected_plan, expected_context, *, run_id, run_attempt):
    """Check content after native transport authentication; return it unchanged.

    Mutable observed merge metadata is not an execution identity. Every fixed
    context field, including the original tested merge, remains exact. The plan
    itself is compared in full; no plan field is dropped or normalized.
    """
    _context(expected_context)
    _positive(run_id, "native run ID")
    _positive(run_attempt, "native run attempt")
    for key, value in (("run_id", run_id), ("run_attempt", run_attempt)):
        if key in expected_context:
            require(type(expected_context[key]) is int and expected_context[key] == value,
                    "expected context names another native run or attempt")
    require(type(record) is dict and record.get("kind") == "pr-ci-execution-v1"
            and record.get("result") == "success", "successful execution record required")
    require(type(record.get("run_id")) is int and record["run_id"] == run_id
            and type(record.get("run_attempt")) is int and record["run_attempt"] == run_attempt,
            "execution record belongs to another native run or attempt")
    context = record.get("context")
    require(type(context) is dict and all(type(context.get(key)) is type(expected_context[key])
            and context.get(key) == expected_context[key]
            for key in C.FIXED_FIELDS), "execution record PR context changed")
    require(type(context.get("run_id")) is int and context["run_id"] == run_id
            and type(context.get("run_attempt")) is int and context["run_attempt"] == run_attempt,
            "execution context belongs to another native run or attempt")
    for key in ("caller_source", "execution_event", "controller"):
        if key in expected_context:
            require(context.get(key) == expected_context[key], "execution caller context changed")
    if "observed_context" in record:
        observed = record["observed_context"]
        require(type(observed) is dict and all(type(observed.get(key)) is type(expected_context[key])
                and observed.get(key) == expected_context[key] for key in C.FIXED_FIELDS),
                "execution completion bookend changed fixed PR inputs")
    require(type(record.get("plan")) is dict, "execution record has no complete plan")
    try:
        equal = C.canonical(record["plan"]) == C.canonical(expected_plan)
    except (TypeError, ValueError) as error:
        raise ObserverError("execution plan is not canonical JSON data") from error
    require(equal, "execution record plan differs from the trusted plan")
    owners = expected_owners(expected_plan)
    if "owners" in expected_plan:
        require(type(expected_plan["owners"]) is dict and C.canonical(expected_plan["owners"]) == C.canonical(owners),
                "trusted plan contains inconsistent owner declarations")
    try:
        C.require_jobs(record.get("owners"), owners)
    except C.ContextError as error:
        raise ObserverError(str(error)) from error
    return record


def _rows(api, endpoint):
    rows = api.pages(endpoint)
    require(type(rows) is list and len(rows) <= MAX_ROWS
            and all(type(row) is dict for row in rows), "incomplete or excessive CodeQL inventory")
    return rows


def _object(api, endpoint):
    value = api.get(endpoint)
    require(type(value) is dict, "CodeQL API object unavailable")
    return value


def _environment(value):
    require(type(value) is str, "CodeQL analysis environment must be JSON text")
    try:
        return json.loads(value, object_pairs_hook=C.unique,
            parse_constant=lambda _: require(False, "nonfinite CodeQL environment"))
    except (ValueError, TypeError) as error:
        raise ObserverError("malformed CodeQL analysis environment") from error


def _uploads(context, languages, proofs):
    require(type(proofs) is dict and set(proofs) == set(languages),
            "native CodeQL upload inventory differs from selected languages")
    run_id = _positive(context.get("run_id"), "trusted CodeQL run ID")
    attempt = _positive(context.get("run_attempt"), "trusted CodeQL run attempt")
    try:
        caller = C.sha(context.get("caller_source"))
    except C.ContextError as error:
        raise ObserverError("trusted CodeQL caller source unavailable") from error
    event = context.get("execution_event")
    require(event in {"pull_request", "pull_request_target", "workflow_dispatch"},
            "unsupported trusted CodeQL execution event")
    if event == "pull_request":
        require(caller == context["original_merge"], "ordinary CodeQL caller source changed")
    elif event == "workflow_dispatch":
        require(caller == context["head"], "manual CodeQL caller is not the reviewed PR head")
    ref = "refs/pull/" + str(context["number"]) + "/merge"
    ids = []
    for language in languages:
        proof = proofs[language]
        expected = {"schema": 1, "repository": C.REPOSITORY,
            "repository_id": C.REPOSITORY_ID, "run_id": run_id, "run_attempt": attempt,
            "language": language, "source_commit": context["original_merge"], "ref": ref,
            "workflow": WORKFLOW, "workflow_sha": caller}
        require(type(proof) is dict and set(proof) == {*expected, "sarif_id"}
                and all(type(proof[key]) is type(value) and proof[key] == value
                        for key, value in expected.items()),
                "native CodeQL upload source, run, attempt or workflow changed")
        upload = proof["sarif_id"]
        try:
            require(type(upload) is str and str(uuid.UUID(upload)) == upload,
                    "malformed native CodeQL SARIF UUID")
        except (ValueError, AttributeError) as error:
            raise ObserverError("malformed native CodeQL SARIF UUID") from error
        ids.append(upload)
    require(len(ids) == len(set(ids)), "selected CodeQL languages share an upload identity")
    return ref


def _alerts(api, context, ref, languages):
    categories = {"/language:" + language for language in languages}
    alerts = _rows(api, "code-scanning/alerts?" + urlencode(
        {"ref": ref, "state": "open", "tool_name": "CodeQL"}))
    seen = set()
    for alert in alerts:
        number = _positive(alert.get("number"), "open CodeQL alert number")
        require(number not in seen and alert.get("state") == "open"
                and type(alert.get("tool")) is dict and alert["tool"].get("name") == "CodeQL",
                "open CodeQL alert inventory changed")
        seen.add(number)
        instances = _rows(api, "code-scanning/alerts/" + str(number) + "/instances?"
                          + urlencode({"ref": ref}))
        require(bool(instances), "open CodeQL alert has no authenticated instances")
        for instance in instances:
            require(instance.get("ref") == ref and type(instance.get("category")) is str
                    and instance.get("state") in {"open", "fixed", "dismissed"},
                    "CodeQL alert instance reference, category or state changed")
            if instance["state"] == "open" and instance["category"] in categories:
                require(instance.get("commit_sha") == context["original_merge"],
                        "selected open CodeQL alert belongs to another source")
                raise ObserverError("open CodeQL finding in a selected category")


def verify_codeql(api, context, languages, upload_proofs):
    """Inspect original native uploads once; pending is not failure or success.

    The caller may wait for asynchronous SARIF processing and invoke this again;
    this function never schedules or retries an analyzer. Transport must already
    bind proofs to context's native run/attempt/caller_source/execution_event.
    PRT caller_source is the independently authenticated protected default; it
    is deliberately distinct from the analyzed original_merge.
    """
    _context(context)
    languages = _languages(languages)
    ref = _uploads(context, languages, upload_proofs)
    chosen, pending = {}, []
    for language in languages:
        upload = upload_proofs[language]["sarif_id"]
        status = _object(api, "code-scanning/sarifs/" + upload)
        require(status.get("errors") in (None, [])
                and status.get("processing_status") in {"pending", "complete"},
                "native CodeQL SARIF processing failed or is unknown")
        if status["processing_status"] == "pending":
            pending.append(language)
            continue
        endpoint = "code-scanning/analyses?" + urlencode({"sarif_id": upload})
        require(status.get("analyses_url") == "https://api.github.com/repos/"
                + C.REPOSITORY + "/" + endpoint, "SARIF analysis URL escaped its native upload")
        analyses = _rows(api, endpoint)
        require(len(analyses) == 1, "native CodeQL upload has missing or ambiguous analyses")
        analysis = analyses[0]
        require(analysis.get("sarif_id") == upload and analysis.get("ref") == ref
                and analysis.get("commit_sha") == context["original_merge"]
                and analysis.get("category") == "/language:" + language
                and analysis.get("analysis_key") == ANALYSIS_KEY
                and type(analysis.get("tool")) is dict
                and analysis["tool"].get("name") == "CodeQL"
                and analysis["tool"].get("version") == "2.27.2"
                and analysis.get("error") == ""
                and type(analysis.get("rules_count")) is int and analysis["rules_count"] > 0
                and _environment(analysis.get("environment")) == {"language": language},
                "processed CodeQL upload identity, original source or analysis changed")
        _positive(analysis.get("id"), "CodeQL analysis ID")
        chosen[language] = analysis
    if languages:
        _alerts(api, context, ref, languages)
    require(len({analysis["id"] for analysis in chosen.values()}) == len(chosen),
            "selected CodeQL languages share an analysis identity")
    return {"state": "pending" if pending else "complete", "languages": list(languages),
            "source_commit": context["original_merge"], "ref": ref,
            "pending_languages": pending, "analyses": chosen}
