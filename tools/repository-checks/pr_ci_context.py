#!/usr/bin/env python3
"""One read-only PR source boundary for planning and final CI acceptance.

The original tested commit remains the execution identity. A regenerated GitHub
test merge is equivalent only while its complete tree and ordered parents match
that original, and both protected base and head refs are still unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

REPOSITORY = "noah-l-frank/overte"
REPOSITORY_ID = 1319052603
TARGETS = frozenset(("main", "android-main", "android-phone", "android-vr",
                     "android-vr-pico", "apple-main", "apple-ios"))
FIXED_FIELDS = ("repository", "repository_id", "number", "target", "base",
                "head_ref", "head", "tree", "original_merge")


class ContextError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContextError(message)


def sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value)
            and value != "0" * 40, "missing or invalid immutable Git object")
    return value


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON field")
        result[key] = value
    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, target):
        raise ContextError("repository metadata redirect refused")


class GitHub:
    """Bounded GET-only client; the host, fork and credentials are not inputs."""
    extra_endpoints = None
    json_types = (dict,)
    max_calls = 24
    def __init__(self, deadline=None):
        self.deadline = time.monotonic() + 90 if deadline is None else deadline
        self.calls = 0

    def get(self, endpoint):
        source_endpoint = type(endpoint) is str and re.fullmatch(
            r"(?:|pulls/[1-9][0-9]*|branches/(?:" + "|".join(sorted(TARGETS))
            + r")|git/ref/heads/(?:[A-Za-z0-9._~-]|%[0-9A-F]{2})+"
              r"|commits/refs/pull/[1-9][0-9]*/merge|git/commits/[0-9a-f]{40})",
            endpoint)
        require(source_endpoint or (type(endpoint) is str and self.extra_endpoints is not None
                and re.fullmatch(self.extra_endpoints, endpoint)),
                "unsupported PR source metadata endpoint")
        self.calls += 1
        remaining = self.deadline - time.monotonic()
        require(self.calls <= self.max_calls and remaining > 0, "PR source metadata budget exhausted")
        token = os.environ.get("GH_TOKEN", "")
        require(bool(token), "read-only GitHub metadata credential unavailable")
        url = "https://api.github.com/repos/" + REPOSITORY + ("/" + endpoint if endpoint else "")
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}, method="GET")
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=min(15, remaining)) as response:
            require(response.status == 200 and response.geturl() == url,
                    "PR source metadata status or endpoint changed")
            raw = response.read(4_000_001)
        require(len(raw) <= 4_000_000 and time.monotonic() <= self.deadline,
                "PR source metadata exceeds time or size limit")
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: require(False, "nonfinite JSON"))
        require(type(value) in self.json_types, "PR source metadata has an unsupported JSON type")
        return value


def repository(value):
    require(type(value) is dict and (value.get("full_name"), value.get("id"))
            == (REPOSITORY, REPOSITORY_ID), "PR source belongs to another repository")


def immutable_merge(api, revision, base, head):
    revision = sha(revision)
    commit = api.get("git/commits/" + revision)
    require(commit.get("sha") == revision, "immutable merge metadata rebound")
    parents = commit.get("parents")
    require(type(parents) is list and all(type(p) is dict for p in parents)
            and [p.get("sha") for p in parents] == [base, head],
            "test merge ordered parents differ from the current protected base and PR head")
    require(type(commit.get("tree")) is dict, "immutable merge tree metadata is missing")
    return sha(commit["tree"].get("sha"))


def capture(api, number, *, event_pr=None, original_merge=None):
    require(type(number) is int and number > 0, "positive PR number required")
    repository(api.get(""))
    pr = api.get("pulls/" + str(number))
    require(pr.get("number") == number and pr.get("state") == "open",
            "PR is closed or its identity changed")
    require(type(pr.get("base")) is dict and type(pr.get("head")) is dict,
            "incomplete PR source context")
    base_side, head_side = pr["base"], pr["head"]
    for side in (base_side, head_side):
        repository(side.get("repo"))
    target, head_ref = base_side.get("ref"), head_side.get("ref")
    require(target in TARGETS and type(head_ref) is str and bool(head_ref),
            "unsupported target or missing head branch")
    base, head = sha(base_side.get("sha")), sha(head_side.get("sha"))
    branch = api.get("branches/" + target)
    require(branch.get("name") == target and branch.get("protected") is True
            and branch.get("commit", {}).get("sha") == base,
            "protected target advanced or is no longer protected")
    ref = api.get("git/ref/heads/" + urllib.parse.quote(head_ref, safe=""))
    require(ref.get("ref") == "refs/heads/" + head_ref
            and ref.get("object", {}).get("type") == "commit"
            and ref["object"].get("sha") == head, "PR head branch advanced")
    if event_pr is not None:
        require(type(event_pr) is dict and event_pr.get("number") == number,
                "event PR identity differs")
        for key, side in (("base", base_side), ("head", head_side)):
            prior = event_pr.get(key, {})
            repository(prior.get("repo"))
            require((prior.get("ref"), prior.get("sha")) == (side["ref"], side["sha"]),
                    "PR source changed since the triggering event")
    observed = sha(api.get("commits/refs/pull/" + str(number) + "/merge").get("sha"))
    original = observed if original_merge is None else sha(original_merge)
    tree = immutable_merge(api, original, base, head)
    if observed != original:
        require(immutable_merge(api, observed, base, head) == tree,
                "regenerated test merge has different content")
    reported = pr.get("merge_commit_sha")
    if reported is not None and reported not in (original, observed):
        require(immutable_merge(api, reported, base, head) == tree,
                "reported test merge has different content")
    return {"repository": REPOSITORY, "repository_id": REPOSITORY_ID,
            "number": number, "target": target, "base": base, "head_ref": head_ref,
            "head": head, "tree": tree, "original_merge": original,
            "observed_merge": observed, "reported_merge": reported}


def bookend(api, context):
    require(type(context) is dict and set(FIXED_FIELDS) <= context.keys(),
            "incomplete planned PR source context")
    current = capture(api, context["number"], original_merge=context["original_merge"])
    require(all(current[key] == context[key] for key in FIXED_FIELDS),
            "tested PR inputs or target basis changed before acceptance")
    return current


def require_jobs(needs, expected):
    """No selected failure, cancellation, missing job or skipped owner is green."""
    require(type(needs) is dict and type(expected) is dict
            and all(type(k) is str and type(v) is bool for k, v in expected.items()),
            "invalid expected CI owner set")
    require(set(needs) == set(expected), "CI owner inventory differs from the trusted plan")
    for name, selected in expected.items():
        value = needs[name]
        require(type(value) is dict and value.get("result") == ("success" if selected else "skipped"),
                "CI owner " + name + " did not match its planned result")
    return True
