import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("watcher_v3", Path(__file__).with_name("publication_watcher.py"))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
ORIGINAL = Path(__file__).resolve().parents[1] / "diagnostic_logs.py"
spec = importlib.util.spec_from_file_location("original_diagnostic_logs", ORIGINAL)
logs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logs)

class IndexedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_id = "domain-enter-one-fixture"
        self.stage = self.root / self.run_id / "diagnostic-results"
        self.stage.parent.mkdir(mode=0o700)
        self.context = "a" * 64
        self.policy = {"schemaVersion": 1,
            "literalFiles": {n: {"maxBytes": v, "required": True} for n, v in w.LIMITS.items()},
            "logDirectories": [{"path": "logs/runner", "required": True,
                "maxParts": 64, "maxPartBytes": 1048576, "indexMaxBytes": 262144}],
            "maxFiles": 128, "maxTotalBytes": 64*1024*1024}

    def write(self, path, raw):
        path.write_bytes(raw)
        path.chmod(0o600)

    def encoded(self, value):
        return (json.dumps(value, sort_keys=True) + "\n").encode()

    def finalize(self):
        files = []
        for file in sorted(self.stage.rglob("*")):
            if file.is_file() and file.name not in {w.MARKER, w.INDEX}:
                body = file.read_bytes()
                files.append({"path": file.relative_to(self.stage).as_posix(),
                              "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
        value = {"schemaVersion": 1, "runId": self.run_id, "contextSha256": self.context,
                 "generation": "a"*32, "files": files}
        self.write(self.stage/w.INDEX, self.encoded(value))
        refs = {}
        for name in [*w.CORE, w.INDEX]:
            body = (self.stage/name).read_bytes()
            refs[name] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
        self.write(self.stage/w.MARKER, self.encoded({"schemaVersion": 1, "state": "DEBUG_HOLD",
            "runId": self.run_id, "contextSha256": self.context, "generation": "a"*32,
            "checkedEpochMs": 1, "artifacts": refs}))

    def ready(self, text=None):
        self.stage.mkdir(mode=0o700)
        self.stage.chmod(0o700)
        for name, body in {"summary.json": b'{"status":"failed"}\n',
                           "junit.xml": b'<testsuite tests="1" errors="1"/>\n',
                           "diagnostic-events.safe.jsonl": b'{"code":"DEBUG_HOLD"}\n'}.items():
            self.write(self.stage/name, body)
        (self.stage/"logs").mkdir(mode=0o700)
        (self.stage/"logs").chmod(0o700)
        raw = self.root/"original.private.log"
        self.write(raw, (text if text is not None else ("static native failure private-canary\n"*15)).encode())
        before = raw.read_bytes(), w.signature(raw.stat())
        self.original_result = logs.publish_log(raw, self.stage/"logs/runner", {"private-canary"}, chunk_bytes=128)
        self.assertEqual((raw.read_bytes(), w.signature(raw.stat())), before)
        self.finalize()

    def inspect(self):
        return w.inspect_publication(self.stage, self.run_id, self.context, self.policy)

    def test_real_original_redactor_all_parts_are_verified_and_enumerated(self):
        self.ready()
        result = self.inspect()
        actual = sorted(p.relative_to(self.stage).as_posix() for p in self.stage.rglob("*") if p.is_file())
        self.assertEqual(result["state"], "DEBUG_HOLD")
        self.assertEqual(result["archiveFiles"], actual)
        self.assertGreater(len(self.original_result["parts"]), 1)
        self.assertTrue(all("*" not in p and "," not in p for p in result["archiveFiles"]))
        for part in (self.stage/"logs/runner").glob("*.log"):
            self.assertNotIn(b"private-canary", part.read_bytes())

    def test_unindexed_extra_or_unapproved_indexed_file_never_archives(self):
        self.ready()
        extra = self.stage/"unreviewed.log"
        self.write(extra, b"unapproved raw fixture")
        with self.assertRaises(w.PublicationError): self.inspect()
        self.finalize()
        with self.assertRaises(w.PublicationError): self.inspect()

    def test_missing_changed_alias_or_hardlink_part_rejected(self):
        self.ready()
        part = self.stage/"logs/runner/part-00001.log"
        original = part.read_bytes()
        part.write_bytes(b"changed")
        with self.assertRaises(w.PublicationError): self.inspect()
        part.unlink()
        with self.assertRaises(w.PublicationError): self.inspect()
        outside = self.root/"outside.safe.log"
        self.write(outside, original)
        part.symlink_to(outside)
        with self.assertRaises(w.PublicationError): self.inspect()
        part.unlink(); os.link(outside, part)
        with self.assertRaises(w.PublicationError): self.inspect()

    def test_literal_fixed_input_sha_is_independent_of_observed_index(self):
        self.ready()
        fixed = self.stage/"native-history.log"
        self.write(fixed, b"actual known safe historical fixture\n")
        body = fixed.read_bytes()
        self.policy["literalFiles"][fixed.name] = {"maxBytes": len(body), "required": True,
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        self.finalize()
        self.assertIn(fixed.name, self.inspect()["archiveFiles"])
        fixed.write_bytes(body.replace(b"known", b"other"))
        self.finalize()
        with self.assertRaises(w.PublicationError): self.inspect()

    def test_forged_truncated_or_incomplete_inner_stream_is_rejected(self):
        self.ready()
        path = self.stage/"logs/runner/index.json"
        original = json.loads(path.read_bytes())
        for change in [{"truncated": True}, {"publicSha256": "b"*64},
                       {"parts": original["parts"][:-1]}, {"privacyAudit": "unknown"}]:
            self.write(path, self.encoded(dict(original, **change)))
            self.finalize()
            with self.assertRaises(w.PublicationError): self.inspect()

    def test_missing_or_wrong_context_index_and_path_traversal_rejected(self):
        self.ready()
        path = self.stage/w.INDEX
        original = json.loads(path.read_bytes())
        for change in [{"runId": "foreign-run"}, {"contextSha256": "b"*64},
                       {"files": original["files"] + [dict(original["files"][0])]},
                       {"files": [dict(original["files"][0], path="../outside")] + original["files"][1:]}]:
            self.write(path, self.encoded(dict(original, **change)))
            with self.assertRaises(w.PublicationError): self.inspect()
        path.unlink()
        with self.assertRaises(FileNotFoundError): self.inspect()

    def test_empty_original_log_is_explicit_untruncated_zero_parts(self):
        self.ready(text="")
        self.assertEqual(self.original_result["parts"], [])
        self.assertIn("logs/runner/index.json", self.inspect()["archiveFiles"])
        self.assertFalse(any("part-" in p for p in self.inspect()["archiveFiles"]))

    def test_sparse_positive_cursors_and_opaque_generation_are_actual_protocol(self):
        self.ready()
        self.assertEqual(self.inspect()["generation"], "a"*32)
        private = self.root/"private-safe"
        private.mkdir(mode=0o700);private.chmod(0o700)
        rows = [{"schemaVersion":1,"sequence":1041242101238079,"epochMs":123,
                 "phase":"module","event":"begin","moduleId":"domain-enter"},
                {"schemaVersion":1,"sequence":1041245935561306,"epochMs":124,
                 "phase":"module","event":"end","moduleId":"domain-enter"}]
        self.write(private/"events.private.jsonl", b"".join(self.encoded(row) for row in rows))
        result = w.progress_projection(private, ["domain-enter"], 0)
        self.assertEqual([row["sequence"] for row in result["progress"]], [row["sequence"] for row in rows])
        result = w.progress_projection(private, ["domain-enter"], rows[0]["sequence"])
        self.assertEqual([row["sequence"] for row in result["progress"]], [rows[1]["sequence"]])

    def test_missing_publication_waits_and_wrong_mode_is_never_normalized(self):
        self.assertEqual(self.inspect(), {"state": "WAIT"})
        self.ready()
        path = self.stage/"summary.json"
        path.chmod(0o644); before = w.signature(path.stat())
        with self.assertRaises(w.PublicationError): self.inspect()
        self.assertEqual(w.signature(path.stat()), before)

class ConfigPublicationCopyTests(unittest.TestCase):
    setUp = IndexedPublicationTests.setUp
    write = IndexedPublicationTests.write
    encoded = IndexedPublicationTests.encoded
    finalize = IndexedPublicationTests.finalize
    ready = IndexedPublicationTests.ready
    def configured(self):
        self.ready()
        # Actual source publication uses the owned run root, not guessed Jenkins workspace.
        self.source = self.stage.with_name("public-debug")
        self.stage.rename(self.source)
        policy_path = self.root/"policy.json"
        self.write(policy_path, self.encoded(self.policy))
        config = {"schemaVersion": 1, "enabled": True, "runId": self.run_id,
                  "privateRoot": str(self.source.parent/"debug-private"),
                  "publicStage": str(self.source),
                  "moduleIds": ["launch-smoke", "domain-enter"],
                  "publicationPolicy": {"path": str(policy_path),
                      "sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest()}}
        self.config_path = self.root/"debug-config.json"
        self.write(self.config_path, self.encoded(config))
        self.config_sha = hashlib.sha256(self.config_path.read_bytes()).hexdigest()
        self.context = self.config_sha
        old = self.stage
        self.stage = self.source
        self.finalize()
        self.stage = old
        workspace = self.root/"workspace"
        workspace.mkdir(mode=0o700)
        parent = workspace/self.run_id
        parent.mkdir(mode=0o700)
        self.destination = parent/"diagnostic-results"

    def test_actual_safe_generation_copies_exclusively_then_verifies_full_tree(self):
        self.configured()
        before = {p.relative_to(self.source).as_posix(): (p.read_bytes(), w.signature(p.stat()))
                  for p in self.source.rglob("*") if p.is_file()}
        result = w.observe_debug_config(self.config_path, self.config_sha, self.run_id, self.destination)
        self.assertIs(result["archiveCopyVerified"], True)
        self.assertEqual(result["archiveStage"], str(self.destination))
        self.assertEqual({p.relative_to(self.source).as_posix(): (p.read_bytes(), w.signature(p.stat()))
                          for p in self.source.rglob("*") if p.is_file()}, before)
        self.assertEqual(sorted(p.relative_to(self.destination).as_posix() for p in self.destination.rglob("*")
                                if p.is_file()), result["archiveFiles"])
        with self.assertRaises(FileExistsError):
            w.observe_debug_config(self.config_path, self.config_sha, self.run_id, self.destination)

    def test_foreign_context_policy_or_destination_is_rejected_before_copy(self):
        self.configured()
        with self.assertRaises(w.PublicationError):
            w.observe_debug_config(self.config_path, "b"*64, self.run_id, self.destination)
        self.assertFalse(self.destination.exists())
        with self.assertRaises(w.PublicationError):
            w.observe_debug_config(self.config_path, self.config_sha, "foreign-run", self.destination)
        self.assertFalse(self.destination.exists())
        policy = self.root/"policy.json"
        policy.write_bytes(policy.read_bytes()+b" ")
        with self.assertRaises(w.PublicationError):
            w.observe_debug_config(self.config_path, self.config_sha, self.run_id, self.destination)
        self.assertFalse(self.destination.exists())

class FailureAndProgressTests(unittest.TestCase):
    setUp = IndexedPublicationTests.setUp
    write = IndexedPublicationTests.write
    encoded = IndexedPublicationTests.encoded
    finalize = IndexedPublicationTests.finalize
    ready = IndexedPublicationTests.ready
    configured = ConfigPublicationCopyTests.configured
    def test_full_failure_copies_only_bound_safe_core_and_never_claims_complete(self):
        self.configured()
        # An extra unindexed output can never be published through the full-file path.
        extra = self.source/"private-unapproved.log"
        self.write(extra, b"private-canary")
        result = w.observe_debug_config(self.config_path, self.config_sha, self.run_id, self.destination)
        self.assertEqual(result["state"], "PUBLICATION_ERROR")
        self.assertIs(result["fullLogPublicationVerified"], False)
        self.assertIs(result["mandatoryOnlyCopyVerified"], True)
        self.assertEqual(set(p.name for p in self.destination.iterdir()), w.CORE)
        self.assertEqual(set(result["archiveFiles"]), w.CORE)
        self.assertEqual(extra.read_bytes(), b"private-canary")

    def test_invalid_core_never_mints_fallback_archive(self):
        self.configured()
        (self.source/"summary.json").write_bytes(b"tampered private data")
        with self.assertRaises(w.PublicationError):
            w.observe_debug_config(self.config_path, self.config_sha, self.run_id, self.destination)
        self.assertFalse(self.destination.exists())

    def test_live_prefix_projects_only_closed_fields_and_withholds_partial_line(self):
        private = self.root/"private-safe"
        private.mkdir(mode=0o700)
        private.chmod(0o700)
        rows = [{"schemaVersion":1,"sequence":1,"epochMs":123,"phase":"module",
                 "event":"begin","moduleId":"domain-enter","message":"never-export-private-canary"},
                {"schemaVersion":1,"sequence":2,"epochMs":124,"phase":"debugHold","event":"hold"}]
        file = private/"events.private.jsonl"
        self.write(file, self.encoded(rows[0]) + self.encoded(rows[1]).rstrip(b"\n"))
        result = w.progress_projection(private, ["domain-enter"], 0)
        self.assertEqual(result["lastSequence"], 1)
        self.assertEqual(result["progress"], [{"sequence":1,"epochMs":123,"phase":"module",
                                              "event":"begin","moduleId":"domain-enter"}])
        self.assertNotIn("canary", json.dumps(result))
        with file.open("ab") as stream: stream.write(b"\n")
        result = w.progress_projection(private, ["domain-enter"], 1)
        self.assertEqual(result["progress"], [{"sequence":2,"epochMs":124,"phase":"debugHold","event":"hold"}])

    def test_foreign_module_and_reordered_sequence_are_not_forwarded(self):
        private = self.root/"private-safe"
        private.mkdir(mode=0o700);private.chmod(0o700)
        row = {"schemaVersion":1,"sequence":1,"epochMs":123,"phase":"module",
               "event":"error","moduleId":"foreign-module"}
        self.write(private/"events.private.jsonl", self.encoded(row))
        with self.assertRaises(w.PublicationError): w.progress_projection(private, ["domain-enter"], 0)
        row["moduleId"] = "domain-enter";row["sequence"] = 20
        self.write(private/"events.private.jsonl", self.encoded(row)+self.encoded(dict(row,sequence=19)))
        with self.assertRaises(w.PublicationError): w.progress_projection(private, ["domain-enter"], 0)

if __name__ == "__main__":
    unittest.main()
