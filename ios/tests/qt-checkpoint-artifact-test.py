#!/usr/bin/env python3
"""Offline contracts for the Qt workflow-artifact checkpoint helper."""

# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import warnings
from unittest import mock
import zipfile
import datetime as dt
import base64
import copy
import hashlib
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "ios/ci/qt-checkpoint-artifact.py"
WORKFLOW = (ROOT / ".github/workflows/ios-qt-source.yml").read_text(encoding="utf-8")
spec = importlib.util.spec_from_file_location("qt_checkpoint", TOOL)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def run(*arguments, ok=True):
    result = subprocess.run([sys.executable, str(TOOL), *map(str, arguments)], text=True, capture_output=True)
    if ok and result.returncode:
        raise AssertionError(result.stderr + result.stdout)
    if not ok and result.returncode == 0:
        raise AssertionError("command unexpectedly succeeded")
    return result


def artifact_zip(payload: Path, destination: Path):
    with zipfile.ZipFile(destination, "w") as output:
        output.write(payload / "checkpoint.tar.gz", "checkpoint.tar.gz")
        output.write(payload / "manifest.json", "manifest.json")


with tempfile.TemporaryDirectory(prefix="qt-checkpoint-test-") as temporary_name:
    temporary = Path(temporary_name)
    prefix = temporary / "prefix"
    (prefix / "bin").mkdir(parents=True)
    executable = prefix / "bin/qmake"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    (prefix / ".qt-hidden").write_text("hidden", encoding="utf-8")
    os.symlink("qmake", prefix / "bin/qmake-link")
    payload = temporary / "payload"
    run(
        "create", "--prefix", prefix, "--kind", "host", "--cache-key", "qt-key",
        "--producer-repository-id", "42", "--producer-branch", "apple-ios", "--output-dir", payload,
    )

    workflow_zip = temporary / "artifact.zip"
    artifact_zip(payload, workflow_zip)
    original_download = module.download_latest
    created_at = dt.datetime.now(dt.timezone.utc).isoformat()
    selected = {"id": 7, "created_at": created_at}
    module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: (
        destination.write_bytes(workflow_zip.read_bytes()) and selected
    )
    try:
        output = temporary / "github-output"
        install = temporary / "restored"
        args = type("Args", (), dict(
            artifact_prefix="qt-host", kind="host", cache_key="qt-key", install_root=str(install),
            github_output=str(output), expected_repository_id=42, expected_branch="apple-ios", max_age_days=21,
        ))()
        module.restore(args)
        assert "restored=true\n" in output.read_text()
        restored_prefix = install / "macos"
        assert (restored_prefix / ".qt-hidden").read_text() == "hidden"
        stat_mode = (restored_prefix / "bin/qmake").stat().st_mode & 0o777
        assert stat_mode == 0o755
        assert (restored_prefix / "bin/qmake-link").is_symlink()
        assert os.readlink(restored_prefix / "bin/qmake-link") == "qmake"

        for field, value in (("cacheKey", "wrong"), ("kind", "ios")):
            bad = temporary / f"bad-{field}"
            bad.mkdir()
            (bad / "checkpoint.tar.gz").write_bytes((payload / "checkpoint.tar.gz").read_bytes())
            manifest = json.loads((payload / "manifest.json").read_text())
            manifest[field] = value
            (bad / "manifest.json").write_text(json.dumps(manifest))
            try:
                module.validate_manifest(bad, "host", "qt-key")
                raise AssertionError(f"accepted wrong {field}")
            except SystemExit:
                pass

        corrupt = temporary / "corrupt"
        corrupt.mkdir()
        (corrupt / "checkpoint.tar.gz").write_bytes(b"corrupt")
        (corrupt / "manifest.json").write_bytes((payload / "manifest.json").read_bytes())
        try:
            module.validate_manifest(corrupt, "host", "qt-key")
            raise AssertionError("accepted wrong SHA")
        except SystemExit:
            pass

        traversal = temporary / "traversal.tar.gz"
        with tarfile.open(traversal, "w:gz") as archive:
            info = tarfile.TarInfo("../escape")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        target = temporary / "traversal-target"
        target.mkdir()
        try:
            module.safe_extract(traversal, target)
            raise AssertionError("accepted path traversal")
        except SystemExit:
            pass
        assert not (temporary / "escape").exists()

        missing_output = temporary / "missing-output"
        module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: None
        missing_args = type("Args", (), dict(
            artifact_prefix="missing", kind="host", cache_key="qt-key", install_root=str(temporary / "unused"),
            github_output=str(missing_output), expected_repository_id=42, expected_branch="apple-ios", max_age_days=21,
        ))()
        module.restore(missing_args)
        assert "restored=false\n" in missing_output.read_text()

        stale_restore_output = temporary / "stale-restore-output"
        stale_install = temporary / "stale-restored"
        stale_selected = {
            "id": 8,
            "created_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=22)).isoformat(),
        }
        module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: (
            destination.write_bytes(workflow_zip.read_bytes()) and stale_selected
        )
        stale_args = type("Args", (), dict(
            artifact_prefix="qt-host", kind="host", cache_key="qt-key",
            install_root=str(stale_install), github_output=str(stale_restore_output),
            expected_repository_id=42, expected_branch="apple-ios", max_age_days=21,
        ))()
        module.restore(stale_args)
        assert stale_restore_output.read_text() == "available=true\nfresh=false\nrestored=true\n"
        assert (stale_install / "macos/bin/qmake").is_file()

        v8_payload = temporary / "v8-payload"
        run(
            "create", "--prefix", prefix, "--kind", "v8", "--cache-key", "v8-key",
            "--producer-repository-id", "42", "--producer-branch", "apple-ios",
            "--output-dir", v8_payload,
        )
        v8_zip = temporary / "v8-artifact.zip"
        artifact_zip(v8_payload, v8_zip)
        module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: (
            destination.write_bytes(v8_zip.read_bytes()) and selected
        )
        v8_output = temporary / "v8-output"
        v8_install = temporary / "v8-restored"
        v8_args = type("Args", (), dict(
            artifact_prefix="v8", kind="v8", cache_key="v8-key",
            install_root=str(v8_install), github_output=str(v8_output),
            expected_repository_id=42, expected_branch="apple-ios", max_age_days=21,
        ))()
        module.restore(v8_args)
        assert v8_output.read_text() == "available=true\nfresh=true\nrestored=true\n"
        assert (v8_install / "v8-ios/bin/qmake").stat().st_mode & 0o777 == 0o755

        conan_payload = temporary / "conan-payload"
        run(
            "create", "--prefix", prefix, "--kind", "conan", "--cache-key", "conan-key",
            "--producer-repository-id", "42", "--producer-branch", "apple-ios",
            "--output-dir", conan_payload,
        )
        conan_zip = temporary / "conan-artifact.zip"
        artifact_zip(conan_payload, conan_zip)
        module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: (
            destination.write_bytes(conan_zip.read_bytes()) and selected
        )
        conan_output = temporary / "conan-output"
        conan_install = temporary / "conan-restored"
        conan_args = type("Args", (), dict(
            artifact_prefix="conan", kind="conan", cache_key="conan-key",
            install_root=str(conan_install), github_output=str(conan_output),
            expected_repository_id=42, expected_branch="apple-ios", max_age_days=21,
        ))()
        module.restore(conan_args)
        assert conan_output.read_text() == "available=true\nfresh=true\nrestored=true\n"
        assert (conan_install / "conan-home/.qt-hidden").read_text() == "hidden"

        compiler_payload = temporary / "compiler-payload"
        run("create", "--prefix", prefix, "--kind", "client-sccache", "--cache-key", "compiler-key",
            "--producer-repository-id", "42", "--producer-branch", "apple-ios", "--output-dir", compiler_payload)
        compiler_zip = temporary / "compiler.zip"
        artifact_zip(compiler_payload, compiler_zip)
        module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: (
            destination.write_bytes(compiler_zip.read_bytes()) and selected)
        compiler_args = type("Args", (), dict(
            artifact_prefix="compiler", kind="client-sccache", cache_key="compiler-key",
            install_root=str(temporary / "compiler-restored"), github_output=str(temporary / "compiler-output"),
            expected_repository_id=42, expected_branch="apple-ios", max_age_days=21))()
        module.restore(compiler_args)
        assert (temporary / "compiler-restored/client-sccache/.qt-hidden").read_text() == "hidden"
        # The new object kind must retain the exact same provenance/key gates.
        for field, value in (("expected_repository_id", 43), ("expected_branch", "other"), ("cache_key", "other")):
            bad_args = type("Args", (), {})()
            for key in ("artifact_prefix", "kind", "cache_key", "install_root", "github_output",
                        "expected_repository_id", "expected_branch", "max_age_days"):
                setattr(bad_args, key, getattr(compiler_args, key))
            setattr(bad_args, field, value)
            bad_args.install_root = str(temporary / ("bad-compiler-" + field))
            try:
                module.restore(bad_args)
                raise AssertionError("compiler checkpoint accepted mismatching " + field)
            except SystemExit:
                pass

        qt_compiler_payload = temporary / "qt-compiler-payload"
        run("create", "--prefix", prefix, "--kind", "qt-sccache", "--cache-key", "compiler-key",
            "--producer-repository-id", "42", "--producer-branch", "apple-ios", "--output-dir", qt_compiler_payload)
        qt_compiler_zip = temporary / "qt-compiler.zip"
        artifact_zip(qt_compiler_payload, qt_compiler_zip)
        module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: (
            destination.write_bytes(qt_compiler_zip.read_bytes()) and selected)
        qt_compiler_args = type("Args", (), dict(
            artifact_prefix="compiler", kind="qt-sccache", cache_key="compiler-key",
            install_root=str(temporary / "qt-compiler-restored"), github_output=str(temporary / "qt-compiler-output"),
            expected_repository_id=42, expected_branch="apple-ios", max_age_days=21))()
        module.restore(qt_compiler_args)
        assert (temporary / "qt-compiler-restored/qt-sccache/.qt-hidden").read_text() == "hidden"
        # The new object kind must retain the exact same provenance/key gates.
        for field, value in (("expected_repository_id", 43), ("expected_branch", "other"), ("cache_key", "other")):
            bad_args = type("Args", (), {})()
            for key in ("artifact_prefix", "kind", "cache_key", "install_root", "github_output",
                        "expected_repository_id", "expected_branch", "max_age_days"):
                setattr(bad_args, key, getattr(qt_compiler_args, key))
            setattr(bad_args, field, value)
            bad_args.install_root = str(temporary / ("bad-qt-compiler-" + field))
            try:
                module.restore(bad_args)
                raise AssertionError("compiler checkpoint accepted mismatching " + field)
            except SystemExit:
                pass

        source_prefix = temporary / "source-downloads"
        source_prefix.mkdir()
        source_name = "qt-everywhere-src-6.11.1.tar.xz"
        source_bytes = lzma.compress(b"pinned Qt source archive fixture")
        (source_prefix / source_name).write_bytes(source_bytes)
        source_payload = temporary / "source-payload"
        run("create", "--prefix", source_prefix, "--kind", "qt-source", "--cache-key", "source-sha-key",
            "--producer-repository-id", "42", "--producer-branch", "apple-ios", "--output-dir", source_payload)
        source_zip = temporary / "source.zip"
        artifact_zip(source_payload, source_zip)
        source_install = temporary / "qt-work"
        module.download_latest = lambda artifact_prefix, repository_id, branch, destination, kind: (
            destination.write_bytes(source_zip.read_bytes()) and selected)
        source_args = type("Args", (), dict(
            artifact_prefix="source", kind="qt-source", cache_key="source-sha-key",
            install_root=str(source_install), github_output=str(temporary / "source-output"),
            expected_repository_id=42, expected_branch="apple-ios", max_age_days=21))()
        module.restore(source_args)
        restored_source = source_install / "downloads" / source_name
        assert restored_source.read_bytes() == source_bytes
        assert module.sha256(restored_source) == module.sha256(source_prefix / source_name)
        assert list((source_install / "downloads").iterdir()) == [restored_source]
        source_manifest = json.loads((source_payload / "manifest.json").read_text())
        assert source_manifest["kind"] == "qt-source"
        assert source_manifest["cacheKey"] == "source-sha-key"
        assert source_manifest["sha256"] == module.sha256(source_payload / "checkpoint.tar.gz")
        # Retain the checkpoint digest gate before the existing source consumer
        # independently verifies the pinned upstream XZ SHA-256.
        with (source_payload / "checkpoint.tar.gz").open("ab") as damaged:
            damaged.write(b"corrupt")
        try:
            module.validate_manifest(source_payload, "qt-source", "source-sha-key")
            raise AssertionError("Qt source checkpoint accepted corrupt payload")
        except SystemExit:
            pass

        # The Qt object kind retains extraction safety and its own size limit.
        qt_unsafe_target = temporary / "qt-unsafe"
        qt_unsafe_target.mkdir()
        try:
            module.safe_extract(traversal, qt_unsafe_target, "qt-sccache")
            raise AssertionError("Qt compiler checkpoint accepted path traversal")
        except SystemExit:
            pass
        qt_limit = module.EXPANDED_LIMITS["qt-sccache"]
        module.EXPANDED_LIMITS["qt-sccache"] = 1
        try:
            try:
                module.safe_extract(qt_compiler_payload / "checkpoint.tar.gz", qt_unsafe_target, "qt-sccache")
                raise AssertionError("Qt compiler checkpoint ignored expanded-size limit")
            except SystemExit:
                pass
        finally:
            module.EXPANDED_LIMITS["qt-sccache"] = qt_limit

        for bad_name in ("nested/manifest.json", "extra"):
            invalid_zip = temporary / (bad_name.replace("/", "-") + ".zip")
            with zipfile.ZipFile(invalid_zip, "w") as archive:
                archive.write(payload / "checkpoint.tar.gz", "checkpoint.tar.gz")
                archive.write(payload / "manifest.json", "manifest.json")
                archive.writestr(bad_name, b"x")
            invalid_destination = temporary / (bad_name.replace("/", "-") + "-out")
            invalid_destination.mkdir()
            try:
                module.unpack_payload(invalid_zip, invalid_destination, "host")
                raise AssertionError("accepted nested/extra ZIP member")
            except SystemExit:
                pass

        duplicate_zip = temporary / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(duplicate_zip, "w") as archive:
                archive.write(payload / "checkpoint.tar.gz", "checkpoint.tar.gz")
                archive.write(payload / "manifest.json", "manifest.json")
                archive.write(payload / "manifest.json", "manifest.json")
        duplicate_out = temporary / "duplicate-out"
        duplicate_out.mkdir()
        try:
            module.unpack_payload(duplicate_zip, duplicate_out, "host")
            raise AssertionError("accepted duplicate ZIP member")
        except SystemExit:
            pass

        oversized_manifest = temporary / "oversized-manifest"
        oversized_manifest.mkdir()
        (oversized_manifest / "manifest.json").write_bytes(b"x" * (module.MANIFEST_LIMIT + 1))
        (oversized_manifest / "checkpoint.tar.gz").write_bytes(b"x")
        try:
            module.validate_manifest(oversized_manifest, "host", "qt-key")
            raise AssertionError("accepted oversized manifest")
        except SystemExit:
            pass

        expanded = temporary / "expanded.tar.gz"
        with tarfile.open(expanded, "w:gz") as archive:
            info = tarfile.TarInfo("large")
            info.size = 2
            archive.addfile(info, io.BytesIO(b"xx"))
        original_expanded_limit = module.EXPANDED_LIMITS["host"]
        module.EXPANDED_LIMITS["host"] = 1
        try:
            try:
                module.safe_extract(expanded, target)
                raise AssertionError("accepted oversized expanded archive")
            except SystemExit:
                pass
        finally:
            module.EXPANDED_LIMITS["host"] = original_expanded_limit
    finally:
        module.download_latest = original_download

artifacts = [
    {"id": 1, "name": "qt-host-1-1", "created_at": "2026-01-01T00:00:00Z", "expired": False,
     "workflow_run": {"repository_id": 42, "head_repository_id": 42, "head_branch": "apple-ios"}},
    {"id": 2, "name": "qt-host-2-1", "created_at": "2026-02-01T00:00:00Z", "expired": True,
     "workflow_run": {"repository_id": 42, "head_repository_id": 42, "head_branch": "apple-ios"}},
    {"id": 3, "name": "qt-hostile-3-1", "created_at": "2026-03-01T00:00:00Z", "expired": False,
     "workflow_run": {"repository_id": 42, "head_repository_id": 42, "head_branch": "apple-ios"}},
    {"id": 4, "name": "qt-host-4-1", "created_at": "2026-02-01T00:00:00Z", "expired": False,
     "workflow_run": {"repository_id": 42, "head_repository_id": 42, "head_branch": "apple-ios"}},
    {"id": 5, "name": "qt-host-5-1", "created_at": "2026-04-01T00:00:00Z", "expired": False,
     "workflow_run": {"repository_id": 99, "head_repository_id": 99, "head_branch": "apple-ios"}},
    {"id": 6, "name": "qt-host-6-1", "created_at": "2026-05-01T00:00:00Z", "expired": False,
     "workflow_run": {"repository_id": 42, "head_repository_id": 42, "head_branch": "other"}},
]
assert module.select_artifact(artifacts, "qt-host", 42, "apple-ios")["id"] == 4
assert module.select_artifact(artifacts, "qt-host", 99, "apple-ios")["id"] == 5
assert module.select_artifact(artifacts, "qt-host", 42, "other")["id"] == 6
assert module.select_artifact(artifacts, "absent", 42, "apple-ios") is None

# The Actions artifact API records a PR's head branch, not its synthetic merge
# ref. Keep exact branch and head-repository validation rather than broadening the
# selector to make the wrong ref work.
pr_artifacts = [
    {"id": 7, "name": "client-objects-7-1", "created_at": "2026-09-26T00:00:00Z", "expired": False,
     "workflow_run": {"repository_id": 42, "head_repository_id": 42, "head_branch": "fix/ios/cache"}},
    {"id": 8, "name": "client-objects-8-1", "created_at": "2026-09-26T01:00:00Z", "expired": False,
     "workflow_run": {"repository_id": 42, "head_repository_id": 99, "head_branch": "fix/ios/cache"}},
]
assert module.select_artifact(pr_artifacts, "client-objects", 42, "973/merge") is None
assert module.select_artifact(pr_artifacts, "client-objects", 42, "fix/ios/cache")["id"] == 7
assert module.select_artifact(pr_artifacts, "client-objects", 42, "apple-ios") is None

# The opt-in index reuses only complete, recent repository listings. Selection
# still runs for each request, including every repository/branch provenance gate.
with tempfile.TemporaryDirectory(prefix="artifact-index-test-") as index_temp:
    index = Path(index_temp) / "index.json"
    env = {"GITHUB_TOKEN": "test-token", "GITHUB_REPOSITORY": "noah-l-frank/overte",
           "OVERTE_ARTIFACT_INDEX_CACHE": str(index)}
    with mock.patch.dict(os.environ, env), mock.patch.object(module.time, "time", return_value=1000):
        response = json.dumps({"artifacts": artifacts}).encode()
        with mock.patch.object(module, "_github_request", return_value=response) as api:
            assert module.find_latest("qt-host", 42, "apple-ios")[0]["id"] == 4
            assert module.find_latest("qt-host", 42, "other")[0]["id"] == 6
            assert module.find_latest("qt-host", 99, "apple-ios")[0]["id"] == 5
            assert module.find_latest("missing", 42, "apple-ios")[0] is None
            assert api.call_count == 1
        good = json.loads(index.read_text())
        for bad in (
            {**good, "fetchedAt": 879}, {**good, "fetchedAt": 1001},
            {**good, "repository": "another/repository"}, {**good, "schema": 99},
            {**good, "artifacts": [None]}, {**good, "artifacts": [{"name": 42}]},
            {**good, "artifacts": [{"name": "qt-host-1", "workflow_run": None}]},
            {**good, "artifacts": [{**artifacts[0], "id": "not-an-id"}]},
            {**good, "artifacts": [{**artifacts[0], "created_at": []}]},
            {**good, "artifacts": [{**artifacts[0], "expired": "false"}]},
            [], "invalid JSON",
        ):
            index.write_text(bad if isinstance(bad, str) else json.dumps(bad))
            with mock.patch.object(module, "_github_request", return_value=response) as api:
                assert module.find_latest("qt-host", 42, "apple-ios")[0]["id"] == 4
                assert api.call_count == 1
                assert json.loads(index.read_text()) == good

        # No configured path means no cache and preserves fresh-list behavior.
        with mock.patch.dict(os.environ, {"OVERTE_ARTIFACT_INDEX_CACHE": ""}), \
             mock.patch.object(module, "_github_request", return_value=response) as api:
            module.find_latest("qt-host", 42, "apple-ios")
            module.find_latest("qt-host", 42, "apple-ios")
            assert api.call_count == 2

        # Failed second-page fetch must not overwrite even an expired index.
        expired = json.dumps({**good, "fetchedAt": 1})
        index.write_text(expired)
        page = json.dumps({"artifacts": [artifacts[0]] * 100}).encode()
        error = module.urllib.error.HTTPError("https://api.github.com/test", 503, "unavailable", {}, None)
        with mock.patch.object(module, "_github_request", side_effect=[page, error]) as api:
            try:
                module.find_latest("qt-host", 42, "apple-ios")
                raise AssertionError("API failure was ignored")
            except module.urllib.error.HTTPError:
                pass
            assert api.call_count == 2
            assert index.read_text() == expired
        with mock.patch.object(module, "_github_request", side_effect=[page, response]) as api:
            assert module.find_latest("qt-host", 42, "apple-ios")[0]["id"] == 4
            assert api.call_count == 2
            assert len(json.loads(index.read_text())["artifacts"]) == 106

        # Preserve the existing 100-page bound but never cache a truncated index.
        index.write_text(expired)
        with mock.patch.object(module, "_github_request", return_value=page) as api:
            assert module.find_latest("qt-host", 42, "apple-ios")[0]["id"] == 1
            assert api.call_count == 100
            assert index.read_text() == expired

for step_name in (
    "Probe validated Qt host artifact fallback",
    "Probe validated Qt iOS artifact fallback",
    "Restore validated Qt host artifact fallback",
    "Restore validated Qt iOS artifact fallback",
):
    start = WORKFLOW.index(f"- name: {step_name}")
    following = WORKFLOW.find("\n      - name:", start + 1)
    step = WORKFLOW[start:following if following >= 0 else len(WORKFLOW)]
    assert "continue-on-error: true" in step, f"optional artifact step can block rebuild: {step_name}"


class FakeResponse:
    def __init__(self, body=b"", headers=None):
        self.body = io.BytesIO(body)
        self.headers = headers or {}
    def read(self, size=-1): return self.body.read(size)
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *unused): self.close()


requests = []
def fake_open(request):
    requests.append(request)
    if len(requests) == 1:
        return FakeResponse(headers={"Location": "https://objects.example/checkpoint"})
    return FakeResponse(b"zip-data")

with tempfile.TemporaryDirectory(prefix="qt-redirect-test-") as redirect_temp:
    downloaded = Path(redirect_temp) / "artifact.zip"
    module.download_artifact(
        "https://api.github.com/artifact", "secret", downloaded,
        module.DOWNLOAD_LIMITS["host"], opener=fake_open,
    )
    assert requests[0].get_header("Authorization") == "Bearer secret"
    assert requests[1].get_header("Authorization") is None
    assert downloaded.read_bytes() == b"zip-data"

fresh = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat()}
stale = {"created_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=22)).isoformat()}
assert module.is_fresh(fresh, 21)
assert not module.is_fresh(stale, 21)

original_find_latest = module.find_latest
try:
    with tempfile.TemporaryDirectory(prefix="qt-probe-test-") as probe_temp:
        probe_output = Path(probe_temp) / "output"
        module.find_latest = lambda prefix, repository_id, branch: (fresh, "token")
        probe_args = type("Args", (), dict(
            artifact_prefix="qt-host", expected_repository_id=42, expected_branch="apple-ios",
            max_age_days=21, github_output=str(probe_output),
        ))()
        module.probe(probe_args)
        assert probe_output.read_text() == "available=true\nfresh=true\n"
        stale_output = Path(probe_temp) / "stale-output"
        module.find_latest = lambda prefix, repository_id, branch: (stale, "token")
        probe_args.github_output = str(stale_output)
        module.probe(probe_args)
        assert stale_output.read_text() == "available=true\nfresh=false\n"
finally:
    module.find_latest = original_find_latest


class TransientUrlOpen:
    def __init__(self):
        self.calls = 0

    def __call__(self, request, timeout):
        assert timeout == 30
        self.calls += 1
        if self.calls < 3:
            raise module.urllib.error.URLError("transient TLS route")
        return FakeResponse(b'{"artifacts": []}')


original_urlopen = module.urllib.request.urlopen
original_sleep = module.time.sleep
try:
    transient = TransientUrlOpen()
    delays = []
    module.urllib.request.urlopen = transient
    module.time.sleep = delays.append
    assert module._github_request("https://api.github.com/test", "token") == b'{"artifacts": []}'
    assert transient.calls == 3
    assert delays == [1, 2]
finally:
    module.urllib.request.urlopen = original_urlopen
    module.time.sleep = original_sleep

try:
    module._read_limited(FakeResponse(b"12345"), 4)
    raise AssertionError("accepted oversized streamed response")
except SystemExit:
    pass
print("Qt checkpoint workflow-artifact tests passed")


class CompilerNativeFixture:
    """Immutable tiny Git objects and native API records, with no network."""

    def __init__(self):
        self.responses, self.log_reads = {}, 0
        self.token = "fake-token"
        entries = []
        for name in module.COMPILER_WRITER_PATHS:
            path = ROOT / name
            raw = path.read_bytes()
            oid = self.object_id("blob", raw)
            mode = "100755" if path.stat().st_mode & 0o111 else "100644"
            entries.append({"path": name, "mode": mode, "type": "blob", "sha": oid})
            self.responses["git/blobs/" + oid] = {
                "sha": oid, "size": len(raw), "encoding": "base64",
                "content": base64.b64encode(raw).decode()}
        self.tree = self.object_id("tree", json.dumps(entries, sort_keys=True).encode())
        self.responses[f"git/trees/{self.tree}?recursive=1"] = {
            "sha": self.tree, "truncated": False, "tree": entries}
        self.base = self.commit("base", [])
        self.head = self.commit("accepted feature", [self.base])
        self.merge = self.commit("native tested merge", [self.base, self.head])
        self.normal = self.commit("normal protected integration", [self.base, self.head])
        self.current = self.commit("current protected apple-ios", [self.normal])
        self.key = "c" * 64
        self.prefix = "overte-ios-client-objects-v2-ARM64-" + self.key
        self.env = {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": module.COMPILER_REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(module.COMPILER_REPOSITORY_ID),
            "GITHUB_REF": "refs/heads/apple-ios", "GITHUB_REF_PROTECTED": "true",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_JOB": "integrated-configure",
            "GITHUB_RUN_ID": "900", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": self.current,
            "GITHUB_WORKFLOW_SHA": self.current,
            "GITHUB_WORKFLOW_REF": module.COMPILER_REPOSITORY +
                "/.github/workflows/ios-integrated.yml@refs/heads/apple-ios"}
        self.responses["branches/apple-ios"] = {
            "name": "apple-ios", "protected": True, "commit": {"sha": self.current}}
        self.responses["actions/workflows/ios-integrated.yml"] = {
            "id": 80, "path": ".github/workflows/ios-integrated.yml", "state": "active"}
        self.responses["actions/workflows/ios-build-qualification.yml"] = {
            "id": 70, "path": module.COMPILER_WORKFLOW, "state": "active",
            "name": "iOS device build qualification"}
        self.responses["actions/runs/900"] = self.run(900, self.current, "apple-ios", "in_progress")
        self.responses["actions/runs/900/attempts/1/jobs?per_page=100"] = {"total_count": 1, "jobs": [{
            "id": 910, "run_id": 900, "run_attempt": 1, "head_sha": self.current,
            "status": "in_progress", "name": "Toolchain, dependencies, build and package",
            "check_run_url": f"https://api.github.com/repos/{module.COMPILER_REPOSITORY}/check-runs/911"}]}
        self.responses["check-runs/911"] = {
            "id": 911, "app": {"id": 15368}, "head_sha": self.current, "status": "in_progress",
            "conclusion": None, "check_suite": {"id": 700}, "name": "Toolchain, dependencies, build and package"}
        original = self.run(400, self.head, "fix/ios/accepted-feature", "completed")
        original.update({"event": "pull_request", "path": module.COMPILER_WORKFLOW, "workflow_id": 70,
                         "check_suite_id": 600, "referenced_workflows": [
            {"path": f"{module.COMPILER_REPOSITORY}/.github/workflows/{name}@{self.merge}",
             "sha": self.merge, "ref": "refs/pull/17/merge"}
            for name in ("ios-integrated.yml", "ios-qt-source.yml")]})
        self.responses["actions/runs/400"] = original
        self.responses["pulls/17"] = {
            "state": "closed", "merged": True, "merge_commit_sha": self.normal,
            "merged_at": "2026-10-17T02:00:00Z",
            "head": {"sha": self.head, "repo": {"id": module.COMPILER_REPOSITORY_ID}},
            "base": {"ref": "apple-ios", "repo": {"id": module.COMPILER_REPOSITORY_ID}}}
        self.job = {
            "id": 500, "name": module.COMPILER_JOB, "run_id": 400, "run_attempt": 1,
            "head_sha": self.head, "status": "completed", "conclusion": "success",
            "check_run_url": f"https://api.github.com/repos/{module.COMPILER_REPOSITORY}/check-runs/501",
            "started_at": "2026-10-17T00:00:00Z", "completed_at": "2026-10-17T01:02:00Z",
            "steps": [
                {"name": name, "number": number, "status": "completed", "conclusion": "success",
                 "started_at": f"2026-10-17T01:00:{second:02d}Z",
                 "completed_at": f"2026-10-17T01:00:{second + 1:02d}Z"}
                for number, second, name in (
                    (46, 0, "Verify full-client compiler checkpoint activity"),
                    (48, 2, "Stop full-client compiler checkpoint server"),
                    (50, 4, "Save reusable full-client compiler checkpoint"),
                    (51, 6, module.COMPILER_UPLOAD))]}
        self.responses["actions/runs/400/attempts/1/jobs?per_page=100"] = {
            "total_count": 1, "jobs": [self.job]}
        self.check = {
            "id": 501, "app": {"id": 15368}, "name": module.COMPILER_JOB, "head_sha": self.head,
            "status": "completed", "conclusion": "success", "check_suite": {"id": 600},
            "started_at": self.job["started_at"], "completed_at": self.job["completed_at"]}
        self.responses["check-runs/501"] = self.check
        self.artifact = self.artifact_record(300, 400, "fix/ios/accepted-feature", self.head,
                                            "2026-10-17T01:00:07Z")
        self.protected = self.artifact_record(100, 200, "apple-ios", self.base,
                                             "2026-10-16T01:00:07Z")
        self.responses["actions/artifacts/300"] = self.artifact
        self.responses["actions/artifacts/100"] = self.protected

    @staticmethod
    def object_id(kind, raw):
        return hashlib.sha1(f"{kind} {len(raw)}\0".encode() + raw).hexdigest()

    def commit(self, name, parents):
        raw = f"tree {self.tree}\n".encode()
        raw += b"".join(f"parent {parent}\n".encode() for parent in parents)
        raw += b"author Fixture <fixture@example.invalid> 1 +0000\ncommitter Fixture <fixture@example.invalid> 1 +0000\n\n"
        raw += name.encode() + b"\n"
        sha = self.object_id("commit", raw)
        self.responses["git/commits/" + sha] = {
            "sha": sha, "tree": {"sha": self.tree}, "parents": [{"sha": item} for item in parents]}
        return sha

    def run(self, identity, head, branch, status):
        return {"id": identity, "run_attempt": 1,
                "repository": {"id": module.COMPILER_REPOSITORY_ID, "full_name": module.COMPILER_REPOSITORY},
                "head_repository": {"id": module.COMPILER_REPOSITORY_ID}, "head_sha": head,
                "head_branch": branch, "status": status,
                "conclusion": "success" if status == "completed" else None,
                "path": ".github/workflows/ios-integrated.yml", "workflow_id": 80,
                "event": "workflow_dispatch", "check_suite_id": 700}

    def artifact_record(self, identity, run, branch, head, created):
        return {"id": identity, "name": f"{self.prefix}-{run}-1", "expired": False,
                "created_at": created, "size_in_bytes": 1, "digest": "sha256:" + "a" * 64,
                "archive_download_url": f"https://api.github.com/repos/{module.COMPILER_REPOSITORY}/actions/artifacts/{identity}/zip",
                "workflow_run": {"id": run, "repository_id": module.COMPILER_REPOSITORY_ID,
                                 "head_repository_id": module.COMPILER_REPOSITORY_ID,
                                 "head_branch": branch, "head_sha": head}}

    def get(self, endpoint):
        if endpoint.startswith("compare/"):
            ancestor, protected = endpoint.removeprefix("compare/").removesuffix("?per_page=1").split("...")
            assert protected == self.current
            assert ancestor in (self.head, self.normal)
            return {"status": "ahead", "ahead_by": 1, "behind_by": 0,
                    "base_commit": {"sha": ancestor}, "merge_base_commit": {"sha": ancestor}}
        if endpoint not in self.responses:
            raise AssertionError("unexpected native API endpoint: " + endpoint)
        return copy.deepcopy(self.responses[endpoint])

    def log(self, job_id):
        assert job_id == 500
        self.log_reads += 1
        return self.upload_log()

    def archive(self, artifact, destination):
        # Fake transport only; the real deadline/copy implementation has its
        # own slow-response regression below.
        module.download_artifact(artifact["archive_download_url"], self.token, destination,
                                 module.DOWNLOAD_LIMITS["client-sccache"])

    def upload_log(self):
        return (f"2026-10-17T01:00:06.1000000Z ##[group]Run {module.COMPILER_UPLOAD_ACTION}\n"
                f"2026-10-17T01:00:06.2000000Z   name: {self.artifact['name']}\n"
                "2026-10-17T01:00:06.3000000Z ##[endgroup]\n"
                f"2026-10-17T01:00:07.2000000Z SHA256 digest of uploaded artifact zip is {self.artifact['digest'][7:]}\n"
                f"2026-10-17T01:00:07.4000000Z Artifact ID {self.artifact['id']}\n").encode()

    def selected(self):
        return mock.patch.multiple(module, _CompilerAPI=mock.Mock(return_value=self),
                                   _artifact_listing=mock.Mock(return_value=([self.protected, self.artifact], self.token)))


class IntegratedCompilerDataTests(unittest.TestCase):
    def test_json_and_origin_logs_share_a_hard_deadline_for_slow_bodies(self):
        for operation, seconds in (("JSON", 30), ("origin log", 60)):
            with self.subTest(operation=operation):
                api = module._CompilerAPI("fake-token")
                clock, calls = [100.0], []
                api.deadline = 1000.0

                class SlowResponse(FakeResponse):
                    def read(self, size=-1):
                        clock[0] += seconds + 1
                        return super().read(size)

                def opener(request, timeout):
                    self.assertGreater(timeout, 0)
                    self.assertLessEqual(timeout, 30)
                    calls.append(request)
                    if operation == "origin log" and len(calls) == 1:
                        return FakeResponse(headers={"Location": "https://objects.example/original-native-log"})
                    return SlowResponse(b'{"id": 1}')

                api.opener = opener
                with mock.patch.object(module.time, "monotonic", side_effect=lambda: clock[0]), \
                        mock.patch.object(module.signal, "getitimer", return_value=(0.0, 0.0)), \
                        mock.patch.object(module.signal, "getsignal", return_value=module.signal.SIG_DFL), \
                        mock.patch.object(module.signal, "signal") as handler, \
                        mock.patch.object(module.signal, "setitimer") as timer:
                    with self.assertRaisesRegex(module.CompilerUnavailable, operation + " deadline exhausted"):
                        api.get("actions/runs/400") if operation == "JSON" else api.log(500)
                    self.assertEqual(timer.call_args_list, [mock.call(module.signal.ITIMER_REAL, float(seconds)),
                                                           mock.call(module.signal.ITIMER_REAL, 0)])
                    self.assertEqual(handler.call_args_list[-1], mock.call(module.signal.SIGALRM, module.signal.SIG_DFL))
                    # The installed real-time signal also interrupts a blocked
                    # read that has not returned a chunk to the clock checks.
                    with self.assertRaisesRegex(module.CompilerUnavailable, operation + " deadline exhausted"):
                        handler.call_args_list[0].args[1](module.signal.SIGALRM, None)
                self.assertEqual(len(calls), 1 if operation == "JSON" else 2)
                self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake-token")
                if operation == "origin log":
                    self.assertIsNone(calls[1].get_header("Authorization"))
                self.assertEqual(api.remaining, 199)

    def test_new_archive_transport_bounds_open_and_slow_copy_without_changing_old_transport(self):
        api = module._CompilerAPI("fake-token")
        clock = [100.0]
        api.deadline = 1000.0
        calls = []

        class SlowResponse(FakeResponse):
            def read(self, size=-1):
                clock[0] += module.COMPILER_ARCHIVE_SECONDS + 1
                return super().read(size)

        def opener(request, timeout):
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 30)
            calls.append(request)
            if len(calls) % 2:
                return FakeResponse(headers={"Location": "https://objects.example/one-compiler-zip"})
            return SlowResponse(b"must not be installed")

        api.opener = opener
        artifact = {"archive_download_url": "https://api.github.com/repos/noah-l-frank/overte/actions/artifacts/300/zip"}
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(module.time, "monotonic", side_effect=lambda: clock[0]), \
                mock.patch.object(module.signal, "getitimer", return_value=(0.0, 0.0)), \
                mock.patch.object(module.signal, "getsignal", return_value=module.signal.SIG_DFL), \
                mock.patch.object(module.signal, "signal") as handler, \
                mock.patch.object(module.signal, "setitimer") as timer:
            destination = Path(temporary) / "artifact.zip"
            with self.assertRaisesRegex(module.CompilerUnavailable, "archive deadline exhausted"):
                api.archive(artifact, destination)
            self.assertEqual(destination.read_bytes(), b"")
            self.assertEqual(timer.call_args_list, [mock.call(module.signal.ITIMER_REAL, 600.0),
                                                   mock.call(module.signal.ITIMER_REAL, 0)])
            self.assertEqual(handler.call_args_list[-1], mock.call(module.signal.SIGALRM, module.signal.SIG_DFL))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake-token")
        self.assertIsNone(calls[1].get_header("Authorization"))

    def test_origin_log_transport_is_bounded_and_drops_authorization_at_storage(self):
        api = module._CompilerAPI("fake-token")
        calls = []

        def opener(request, timeout):
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 30)
            calls.append(request)
            if len(calls) == 1:
                return FakeResponse(headers={"Location": "https://objects.example/native-log"})
            return FakeResponse(b"bounded native log")

        api.opener = opener
        self.assertEqual(api.log(500), b"bounded native log")
        self.assertEqual(calls[0].full_url,
                         "https://api.github.com/repos/noah-l-frank/overte/actions/jobs/500/logs")
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer fake-token")
        self.assertIsNone(calls[1].get_header("Authorization"))
        with mock.patch.object(module.time, "monotonic", return_value=api.deadline + 1):
            with self.assertRaises(module.CompilerUnavailable):
                api.log(500)
        self.assertEqual(len(calls), 2)

    def test_newest_integrated_native_writer_selected_without_archive_download(self):
        case = CompilerNativeFixture()
        with mock.patch.dict(os.environ, case.env), case.selected(), \
                mock.patch.object(module, "download_artifact") as download:
            result = module._select_compiler_data(case.prefix)
        self.assertEqual(result.artifact["id"], 300)
        self.assertEqual(result.origin["source"], case.merge)
        self.assertEqual(case.log_reads, 1)
        download.assert_not_called()

    def test_failed_build_preserves_successfully_published_partial_data(self):
        case = CompilerNativeFixture()
        case.responses["actions/runs/400"]["conclusion"] = "failure"
        case.job["conclusion"] = case.check["conclusion"] = "failure"
        with mock.patch.dict(os.environ, case.env), case.selected():
            result = module._select_compiler_data(case.prefix)
        self.assertEqual(result.artifact["id"], 300)
        self.assertEqual(result.origin["job"]["conclusion"], "failure")

    def test_unrelated_pr_presentation_drift_is_not_a_compiler_input(self):
        case = CompilerNativeFixture()
        with mock.patch.dict(os.environ, case.env), case.selected():
            selected = module._select_compiler_data(case.prefix)
            case.responses["pulls/17"]["comments"] = 9
            case.responses["pulls/17"]["title"] = "A later presentation edit"
            selected.recheck()
            case.responses["pulls/17"]["head"]["sha"] = "0" * 40
            with self.assertRaises(module.CompilerUnavailable):
                selected.recheck()

    def test_foreign_retried_unreviewed_or_incomplete_origins_fall_back_before_download(self):
        changes = (
            lambda c: c.responses["actions/runs/400"].update(run_attempt=2),
            lambda c: c.responses["actions/runs/400"]["head_repository"].update(id=99),
            lambda c: c.check["app"].update(id=99),
            lambda c: c.job["steps"][-1].update(conclusion="failure"),
            lambda c: c.job["steps"][0].update(conclusion="skipped"),
            lambda c: c.responses["actions/runs/400"].update(status="in_progress"),
            lambda c: c.responses["pulls/17"].update(merged=False),
            lambda c: c.responses[f"git/trees/{c.tree}?recursive=1"].update(truncated=True),
            lambda c: c.responses["actions/runs/400"]["referenced_workflows"].pop(),
            lambda c: c.responses["git/commits/" + c.merge]["parents"].reverse(),
            lambda c: c.responses["actions/runs/400/attempts/1/jobs?per_page=100"].update(total_count=2),
            lambda c: c.responses["pulls/17"].update(merged_at="2026-10-17T00:30:00Z"),
        )
        for change in changes:
            with self.subTest(change=changes.index(change)):
                case = CompilerNativeFixture()
                change(case)
                # A truncated current tree declines the entire new mode, rather
                # than turning a missing original proof into protected authority.
                with mock.patch.dict(os.environ, case.env), case.selected(), \
                        mock.patch.object(module, "download_artifact") as download:
                    if case.responses[f"git/trees/{case.tree}?recursive=1"]["truncated"]:
                        with self.assertRaises(module.CompilerUnavailable):
                            module._select_compiler_data(case.prefix)
                    else:
                        self.assertEqual(module._select_compiler_data(case.prefix).artifact["id"], 100)
                download.assert_not_called()

    def test_nonancestor_and_changed_writer_modes_or_bytes_decline(self):
        for field, value in (("mode", "120000"), ("sha", "0" * 40)):
            case = CompilerNativeFixture()
            # Use a distinct original tree so protected source remains intact.
            original_tree = "1" * 40
            old = copy.deepcopy(case.responses[f"git/trees/{case.tree}?recursive=1"])
            old["sha"] = original_tree
            old["tree"][3][field] = value
            case.responses[f"git/trees/{original_tree}?recursive=1"] = old
            for sha in (case.merge, case.head, case.normal):
                case.responses["git/commits/" + sha]["tree"]["sha"] = original_tree
            with self.subTest(field=field), mock.patch.dict(os.environ, case.env), case.selected():
                self.assertEqual(module._select_compiler_data(case.prefix).artifact["id"], 100)
        case = CompilerNativeFixture()
        actual_get = case.get
        case.get = lambda endpoint: ({"status": "diverged"} if endpoint.startswith("compare/") else actual_get(endpoint))
        with mock.patch.dict(os.environ, case.env), case.selected():
            self.assertEqual(module._select_compiler_data(case.prefix).artifact["id"], 100)

    def test_upload_id_digest_name_and_precision_are_native_bound(self):
        case = CompilerNativeFixture()
        log = case.upload_log()
        step = case.job["steps"][-1]
        module._compiler_upload_binding(log, case.artifact, step)
        for bad in (
            log.replace(b"Artifact ID 300", b"Artifact ID 301"),
            log.replace(b"a" * 64, b"b" * 64),
            log.replace(case.artifact["name"].encode(), b"unrelated-checkpoint"),
            log.replace(b"01:00:07.2000000Z", b"01:00:08.0000000Z"),
            log + log,
        ):
            with self.subTest(log=hashlib.sha256(bad).hexdigest()), self.assertRaises(module.CompilerUnavailable):
                module._compiler_upload_binding(bad, case.artifact, step)

    def test_wrong_protected_native_context_cannot_enable_the_new_mode(self):
        for field, value in (("GITHUB_REF", "refs/pull/17/merge"), ("GITHUB_REF_PROTECTED", "false"),
                             ("GITHUB_REPOSITORY", "overte-org/overte"), ("GITHUB_JOB", "other-job"),
                             ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_WORKFLOW_SHA", "0" * 40)):
            case = CompilerNativeFixture()
            case.env[field] = value
            with self.subTest(field=field), mock.patch.dict(os.environ, case.env), case.selected():
                with self.assertRaises(module.CompilerUnavailable):
                    module._select_compiler_data(case.prefix)

    def test_one_whole_zip_then_original_manifest_and_staged_restore(self):
        with tempfile.TemporaryDirectory(prefix="integrated-compiler-data-") as temporary_name:
            temporary = Path(temporary_name)
            case = CompilerNativeFixture()
            source = temporary / "source"
            source.mkdir()
            (source / "object").write_bytes(b"compiler semantic key and object")
            payload = temporary / "payload"
            module.create(type("Args", (), dict(prefix=source, kind="client-sccache", cache_key=case.key,
                          producer_repository_id=module.COMPILER_REPOSITORY_ID,
                          producer_branch="fix/ios/accepted-feature", output_dir=payload))())
            archive = temporary / "fixture.zip"
            artifact_zip(payload, archive)
            case.artifact.update(size_in_bytes=archive.stat().st_size, digest="sha256:" + module.sha256(archive))
            args = type("Args", (), dict(artifact_prefix=case.prefix, cache_key=case.key,
                        install_root=temporary / "installed", github_output=temporary / "output",
                        kind="client-sccache", expected_repository_id=module.COMPILER_REPOSITORY_ID,
                        expected_branch="apple-ios", max_age_days=21))()
            with mock.patch.dict(os.environ, case.env), case.selected(), \
                    mock.patch.object(module, "download_artifact",
                                      side_effect=lambda url, token, destination, limit: destination.write_bytes(archive.read_bytes())) as download:
                module.restore_protected_compiler(args)
            self.assertEqual(download.call_count, 1)
            self.assertEqual((args.install_root / "client-sccache/object").read_bytes(), b"compiler semantic key and object")
            self.assertIn("restored=true", args.github_output.read_text())

    def test_outer_digest_corruption_and_changed_bookend_never_install(self):
        for mutation in ("zip", "branch"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary_name:
                temporary = Path(temporary_name)
                case = CompilerNativeFixture()
                with mock.patch.dict(os.environ, case.env), case.selected():
                    selected = module._select_compiler_data(case.prefix)
                    if mutation == "zip":
                        selected.artifact["size_in_bytes"] = 3
                        args = type("Args", (), dict(artifact_prefix=case.prefix, kind="client-sccache", cache_key=case.key,
                            install_root=temporary / "installed", github_output=temporary / "output",
                            expected_repository_id=module.COMPILER_REPOSITORY_ID, expected_branch="apple-ios", max_age_days=21))()
                        with mock.patch.object(module, "download_artifact", side_effect=lambda u, t, p, l: p.write_bytes(b"bad")):
                            with self.assertRaises(module.CompilerUnavailable):
                                module.restore(args, selection=selected)
                    else:
                        case.responses["branches/apple-ios"]["commit"]["sha"] = "0" * 40
                        with self.assertRaises(module.CompilerUnavailable):
                            selected.recheck()
                self.assertFalse((temporary / "installed/client-sccache").exists())


class PRCompilerNativeFixture(CompilerNativeFixture):
    """Only private copies and fake native metadata; never a live PR/device."""

    def __init__(self):
        super().__init__()
        self.temporary = tempfile.TemporaryDirectory(prefix="pr-compiler-data-")
        self.workspace = Path(self.temporary.name)
        self.parser_path = self.workspace / module.COMPILER_PR_DIRECTORY / "ios/ci/qt-checkpoint-artifact.py"
        self.parser_path.parent.mkdir(parents=True)
        self.parser_path.write_bytes(TOOL.read_bytes())
        self.parser_path.chmod(TOOL.stat().st_mode & 0o777)
        key_path = self.parser_path.with_name("client-compiler-cache-key.py")
        key_path.write_bytes((ROOT / "ios/ci/client-compiler-cache-key.py").read_bytes())
        key_path.chmod((ROOT / "ios/ci/client-compiler-cache-key.py").stat().st_mode & 0o777)
        self.pr_head = self.commit("live feature consumer", [self.current])
        self.pr_merge = self.commit("current native consumer merge", [self.current, self.pr_head])
        self.pr_branch = "fix/ios/matching-compiler-consumer"
        self.env.update(GITHUB_REF="refs/pull/29/merge", GITHUB_EVENT_NAME="pull_request",
                        GITHUB_BASE_REF="apple-ios", GITHUB_HEAD_REF=self.pr_branch,
                        GITHUB_SHA=self.pr_merge, GITHUB_WORKFLOW_SHA=self.pr_merge,
                        GITHUB_WORKFLOW_REF=module.COMPILER_REPOSITORY +
                            "/" + module.COMPILER_WORKFLOW + "@refs/pull/29/merge",
                        GITHUB_WORKSPACE=str(self.workspace))
        self.responses["pulls/29"] = {
            "number": 29, "state": "open", "merged": False, "merge_commit_sha": self.pr_merge,
            "head": {"sha": self.pr_head, "ref": self.pr_branch, "repo": {
                "id": module.COMPILER_REPOSITORY_ID, "full_name": module.COMPILER_REPOSITORY}},
            "base": {"sha": self.current, "ref": "apple-ios", "repo": {
                "id": module.COMPILER_REPOSITORY_ID, "full_name": module.COMPILER_REPOSITORY}}}
        current = self.responses["actions/runs/900"]
        current.update(head_sha=self.pr_head, head_branch=self.pr_branch, event="pull_request",
                       path=module.COMPILER_WORKFLOW, workflow_id=70, pull_requests=[{
                           "number": 29, "base": {"sha": self.current}, "head": {"sha": self.pr_head}}],
                       referenced_workflows=[{
                           "path": f"{module.COMPILER_REPOSITORY}/.github/workflows/{name}@{self.pr_merge}",
                           "sha": self.pr_merge, "ref": "refs/pull/29/merge"}
                           for name in ("ios-integrated.yml", "ios-qt-source.yml")])
        self.responses["actions/runs/900/attempts/1"] = copy.deepcopy(current)
        owner = self.responses["actions/runs/900/attempts/1/jobs?per_page=100"]["jobs"][0]
        owner.update(head_sha=self.pr_head, name=module.COMPILER_JOB, conclusion=None, steps=[{
            "name": module.COMPILER_PR_CHECKOUT, "number": 30, "status": "completed", "conclusion": "success",
            "started_at": "2026-10-17T03:00:00Z", "completed_at": "2026-10-17T03:00:01Z"}, {
            "name": module.COMPILER_PR_NAMESPACE, "number": 31, "status": "completed", "conclusion": "success",
            "started_at": "2026-10-17T03:00:02Z", "completed_at": "2026-10-17T03:00:03Z"}, {
            "name": module.COMPILER_PR_RESTORE, "number": 32, "status": "in_progress", "conclusion": None,
            "started_at": "2026-10-17T03:00:04Z"}])
        self.responses["check-runs/911"].update(head_sha=self.pr_head, name=module.COMPILER_JOB)
        self.responses["actions/runs/200"] = self.run(200, self.base, "apple-ios", "completed")
        producer = copy.deepcopy(self.job)
        producer.update(id=250, run_id=200, head_sha=self.base,
                        name="Toolchain, dependencies, build and package",
                        check_run_url=f"https://api.github.com/repos/{module.COMPILER_REPOSITORY}/check-runs/251")
        self.responses["actions/runs/200/attempts/1/jobs?per_page=100"] = {"total_count": 1, "jobs": [producer]}
        protected_check = copy.deepcopy(self.check)
        protected_check.update(id=251, head_sha=self.base, name=producer["name"], check_suite={"id": 700})
        self.responses["check-runs/251"] = protected_check
        self.protected.update(created_at="2026-10-17T01:00:07Z")
        self.published_digest = self.protected["digest"]

    def get(self, endpoint):
        if endpoint.startswith("compare/"):
            ancestor, protected = endpoint.removeprefix("compare/").removesuffix("?per_page=1").split("...")
            assert protected == self.current and ancestor in (self.base, self.head, self.normal)
            return {"status": "ahead", "ahead_by": 1, "behind_by": 0,
                    "base_commit": {"sha": ancestor}, "merge_base_commit": {"sha": ancestor}}
        return super().get(endpoint)

    def log(self, job_id):
        assert job_id == 250
        self.log_reads += 1
        return (f"2026-10-17T01:00:06.1000000Z ##[group]Run {module.COMPILER_UPLOAD_ACTION}\n"
                f"2026-10-17T01:00:06.2000000Z   name: {self.protected['name']}\n"
                "2026-10-17T01:00:06.3000000Z ##[endgroup]\n"
                f"2026-10-17T01:00:07.2000000Z SHA256 digest of uploaded artifact zip is {self.published_digest[7:]}\n"
                f"2026-10-17T01:00:07.4000000Z Artifact ID {self.protected['id']}\n").encode()

    def __enter__(self):
        from contextlib import ExitStack
        self.stack = ExitStack()
        self.stack.callback(self.temporary.cleanup)
        self.stack.enter_context(mock.patch.dict(os.environ, self.env))
        self.stack.enter_context(mock.patch.object(module, "__file__", str(self.parser_path)))
        # These are offline API/parser checks. The actual isolated startup flags
        # are also mandatory in the immutable workflow contract below.
        self.stack.enter_context(mock.patch.object(sys, "flags", type("Flags", (), {
            "isolated": 1, "ignore_environment": 1, "no_site": 1})()))
        self.stack.enter_context(mock.patch.object(sys, "dont_write_bytecode", True))
        self.stack.enter_context(self.selected())
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)


class PRCompilerDataTests(unittest.TestCase):
    def test_current_original_pr_reads_only_one_actual_protected_writer(self):
        with PRCompilerNativeFixture() as case, mock.patch.object(module, "download_artifact") as download:
            selected = module._select_pr_compiler_data(case.prefix)
            self.assertEqual(selected.artifact["id"], case.protected["id"])
            self.assertEqual(selected.protected_origin["source"], case.base)
            self.assertEqual(selected.consumer["sha"], case.current)
            self.assertEqual((selected.consumer["head"], selected.consumer["merge"]), (case.pr_head, case.pr_merge))
            self.assertEqual(case.log_reads, 1)
            self.assertIsNone(selected.origin)
            download.assert_not_called()

    def test_newer_invalid_protected_label_falls_back_before_the_single_download(self):
        with PRCompilerNativeFixture() as case, mock.patch.object(module, "download_artifact") as download:
            later = case.artifact_record(101, 201, "apple-ios", case.base, "2026-10-17T02:00:00Z")
            case.responses["actions/artifacts/101"] = later
            foreign = case.run(201, case.base, "apple-ios", "completed")
            foreign["event"] = "pull_request"
            case.responses["actions/runs/201"] = foreign
            with mock.patch.object(module, "_artifact_listing", return_value=([case.protected, later], case.token)):
                selected = module._select_pr_compiler_data(case.prefix)
            self.assertEqual(selected.artifact["id"], 100)
            self.assertEqual(case.log_reads, 1)
            download.assert_not_called()

    def test_integrated_feature_artifact_is_never_a_direct_pr_candidate(self):
        with PRCompilerNativeFixture() as case, mock.patch.object(module, "download_artifact") as download:
            case.responses.pop("actions/artifacts/100")
            with mock.patch.object(module, "_artifact_listing", return_value=([case.artifact], case.token)):
                self.assertIsNone(module._select_pr_compiler_data(case.prefix))
            self.assertEqual(case.log_reads, 0)
            download.assert_not_called()

    def test_foreign_retry_stale_base_merge_app_or_native_association_declines_before_download(self):
        changes = (
            lambda c: c.env.update(GITHUB_EVENT_NAME="pull_request_target"),
            lambda c: c.env.update(GITHUB_RUN_ATTEMPT="2"),
            lambda c: c.env.update(GITHUB_WORKFLOW_SHA="0" * 40),
            lambda c: c.responses["pulls/29"]["head"]["repo"].update(id=99),
            lambda c: c.responses["pulls/29"]["head"].update(ref="docs/ios/foreign-kind"),
            lambda c: c.responses["branches/apple-ios"]["commit"].update(sha=c.base),
            lambda c: c.responses["pulls/29"].update(merge_commit_sha=c.merge),
            lambda c: c.responses["git/commits/" + c.pr_merge]["parents"].reverse(),
            lambda c: c.responses["actions/runs/900/attempts/1"].update(run_attempt=2),
            lambda c: c.responses["actions/runs/900"]["pull_requests"][0].update(number=30),
            lambda c: c.responses["check-runs/911"]["app"].update(id=99),
            lambda c: c.responses["actions/runs/900"]["referenced_workflows"].pop(),
            lambda c: c.responses["actions/runs/900/attempts/1/jobs?per_page=100"]["jobs"][0]["steps"].insert(0,
                {"name": "Set Apple compiler budget", "number": 1, "status": "completed", "conclusion": "success"}),
            lambda c: c.responses["actions/runs/900/attempts/1/jobs?per_page=100"]["jobs"][0]["steps"][0].update(conclusion="failure"),
        )
        for index, change in enumerate(changes):
            with self.subTest(change=index), PRCompilerNativeFixture() as case, \
                    mock.patch.object(module, "download_artifact") as download:
                change(case)
                # patch.dict has copied the environment; explicit changed env
                # values must be made current before executing the real parser.
                with mock.patch.dict(os.environ, case.env), self.assertRaises(module.CompilerUnavailable):
                    module._select_pr_compiler_data(case.prefix)
                download.assert_not_called()

    def test_changed_candidate_tooling_and_protected_parser_alias_or_bytes_are_rejected(self):
        for mutation in ("candidate-mode", "candidate-key", "parser-bytes", "parser-symlink", "startup"):
            with self.subTest(mutation=mutation), PRCompilerNativeFixture() as case:
                if mutation.startswith("candidate-"):
                    tree = copy.deepcopy(case.responses[f"git/trees/{case.tree}?recursive=1"])
                    tree["sha"] = "d" * 40
                    row = next(row for row in tree["tree"] if row["path"] == "ios/ci/client-compiler-cache-key.py")
                    row["mode" if mutation == "candidate-mode" else "sha"] = "120000" if mutation == "candidate-mode" else "e" * 40
                    case.responses[f"git/trees/{tree['sha']}?recursive=1"] = tree
                    case.responses["git/commits/" + case.pr_merge]["tree"]["sha"] = tree["sha"]
                elif mutation == "parser-bytes":
                    case.parser_path.write_bytes(b"foreign parser")
                elif mutation == "parser-symlink":
                    original = case.parser_path.with_suffix(".real")
                    case.parser_path.rename(original)
                    case.parser_path.symlink_to(original.name)
                else:
                    sys.flags.no_site = 0
                with self.assertRaises(module.CompilerUnavailable):
                    module._select_pr_compiler_data(case.prefix)

    def test_protected_label_without_original_native_upload_or_ancestor_is_not_authority(self):
        changes = (
            lambda c: c.responses["actions/runs/200"].update(event="pull_request"),
            lambda c: c.responses["actions/runs/200"].update(run_attempt=2),
            lambda c: c.responses["check-runs/251"]["app"].update(id=99),
            lambda c: c.responses["actions/runs/200/attempts/1/jobs?per_page=100"]["jobs"][0]["steps"][-1].update(conclusion="skipped"),
            lambda c: c.protected.update(digest="sha256:" + "b" * 64),
        )
        for index, change in enumerate(changes):
            with self.subTest(change=index), PRCompilerNativeFixture() as case, \
                    mock.patch.object(module, "download_artifact") as download:
                change(case)
                self.assertIsNone(module._select_pr_compiler_data(case.prefix))
                download.assert_not_called()
        with PRCompilerNativeFixture() as case:
            get = case.get
            case.get = lambda endpoint: ({"status": "diverged"} if endpoint.startswith("compare/") else get(endpoint))
            self.assertIsNone(module._select_pr_compiler_data(case.prefix))

    def test_safe_partial_protected_data_and_changed_final_bookends(self):
        with PRCompilerNativeFixture() as case:
            case.responses["actions/runs/200"]["conclusion"] = "failure"
            case.responses["actions/runs/200/attempts/1/jobs?per_page=100"]["jobs"][0]["conclusion"] = "failure"
            case.responses["check-runs/251"]["conclusion"] = "failure"
            selected = module._select_pr_compiler_data(case.prefix)
            self.assertEqual(selected.protected_origin["job"]["conclusion"], "failure")
            case.responses["pulls/29"]["head"]["sha"] = case.head
            with self.assertRaises(module.CompilerUnavailable):
                selected.recheck()

    def test_one_verified_zip_installs_only_after_final_pr_and_writer_bookends(self):
        for race in (False, True):
            with self.subTest(race=race), PRCompilerNativeFixture() as case:
                source = case.workspace / "objects"
                source.mkdir()
                (source / "semantic-key").write_bytes(b"unchanged source/header/argv object")
                payload = case.workspace / "payload"
                module.create(type("Args", (), dict(prefix=source, kind="client-sccache", cache_key=case.key,
                    producer_repository_id=module.COMPILER_REPOSITORY_ID, producer_branch="apple-ios", output_dir=payload))())
                archive = case.workspace / "artifact.zip"
                artifact_zip(payload, archive)
                case.protected.update(size_in_bytes=archive.stat().st_size, digest="sha256:" + module.sha256(archive))
                case.published_digest = case.protected["digest"]
                args = type("Args", (), dict(artifact_prefix=case.prefix, cache_key=case.key, kind="client-sccache",
                    install_root=case.workspace / "installed", github_output=case.workspace / "output",
                    expected_repository_id=module.COMPILER_REPOSITORY_ID, expected_branch="apple-ios", max_age_days=21))()
                def copy_once(url, token, destination, limit):
                    destination.write_bytes(archive.read_bytes())
                    if race:
                        case.responses["branches/apple-ios"]["commit"]["sha"] = case.base
                with mock.patch.object(module, "download_artifact", side_effect=copy_once) as download:
                    if race:
                        with self.assertRaises(module.CompilerUnavailable):
                            module.restore_pr_compiler(args)
                    else:
                        module.restore_pr_compiler(args)
                    self.assertEqual(download.call_count, 1)
                self.assertEqual((args.install_root / "client-sccache/semantic-key").exists(), not race)
                if not race:
                    self.assertEqual((args.install_root / "client-sccache/semantic-key").read_bytes(),
                                     b"unchanged source/header/argv object")


if __name__ == "__main__":
    unittest.main()
