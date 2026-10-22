#!/usr/bin/env python3
"""Exercise immutable runtime transport with real files and hostile tar inputs."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime", ROOT / "tools/repository-checks/pr_ci_android_runtime.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)
EXPORT_SPEC = importlib.util.spec_from_file_location("runtime_export", ROOT / "tools/repository-checks/pr_ci_android_export.py")
EXPORT = importlib.util.module_from_spec(EXPORT_SPEC)
EXPORT_SPEC.loader.exec_module(EXPORT)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.payload = self.root / "payload"
        (self.payload / "tools").mkdir(parents=True)
        (self.payload / "tools/compiler").write_bytes(b"actual test fixture bytes\n")
        (self.payload / "tools/compiler").chmod(0o755)
        (self.payload / "bin").mkdir()
        (self.payload / "bin/cc").symlink_to("../tools/compiler")
        self.ledger = self.root / "inventory.json"
        self.expected = R.inventory(self.payload)
        self.ledger.write_bytes(R.canonical(self.expected))
        self.identity = R.digest(self.ledger)
        self.archive = self.root / "runtime.tar.gz"

    def tearDown(self):
        self.temporary.cleanup()

    def archive_entries(self, extra=None, omit=None):
        with tarfile.open(self.archive, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for name in sorted(self.expected["entries"]):
                if name != omit:
                    archive.add(self.payload / name, arcname=name, recursive=False)
            if extra:
                info, payload = extra
                archive.addfile(info, io.BytesIO(payload) if payload is not None else None)

    def extract(self, **overrides):
        args = {"archive_path": self.archive, "destination": self.root / "restored",
                "ledger": self.ledger, "inventory_sha256": self.identity,
                "archive_sha256": R.digest(self.archive), "archive_bytes": self.archive.stat().st_size}
        args.update(overrides)
        return R.extract(**args)

    def test_exact_roundtrip_includes_executable_and_symlink(self):
        self.archive_entries()
        self.assertEqual(self.extract(), self.expected)
        self.assertEqual(R.inventory(self.root / "restored"), self.expected)
        self.assertEqual(os.readlink(self.root / "restored/bin/cc"), "../tools/compiler")
        self.assertEqual((self.root / "restored/tools/compiler").stat().st_mode & 0o777, 0o755)

    def test_file_mutation_rejected_despite_local_resealed_inventory(self):
        (self.payload / "tools/compiler").write_bytes(b"changed payload\n")
        self.ledger.write_bytes(R.canonical(R.inventory(self.payload)))
        with self.assertRaisesRegex(ValueError, "protected digest"):
            R.verify(self.payload, self.ledger, self.identity)

    def test_payload_mutation_with_original_inventory_rejected(self):
        (self.payload / "tools/compiler").write_bytes(b"changed payload\n")
        with self.assertRaisesRegex(ValueError, "payload differs"):
            R.verify(self.payload, self.ledger, self.identity)

    def test_mtime_only_is_not_a_payload_change(self):
        os.utime(self.payload / "tools/compiler", (12, 34))
        self.assertEqual(R.verify(self.payload, self.ledger, self.identity), self.expected)

    def test_mode_change_rejected(self):
        (self.payload / "tools/compiler").chmod(0o644)
        with self.assertRaisesRegex(ValueError, "payload differs"):
            R.verify(self.payload, self.ledger, self.identity)

    def test_extra_file_rejected(self):
        (self.payload / "injected").write_text("unlisted")
        with self.assertRaisesRegex(ValueError, "payload differs"):
            R.verify(self.payload, self.ledger, self.identity)

    def test_missing_file_rejected(self):
        (self.payload / "bin/cc").unlink()
        (self.payload / "tools/compiler").unlink()
        with self.assertRaisesRegex(ValueError, "payload differs"):
            R.verify(self.payload, self.ledger, self.identity)

    def test_absolute_and_escaping_symlink_rejected(self):
        for target in ("/etc/passwd", "../../outside"):
            with self.subTest(target=target):
                (self.payload / "bin/cc").unlink()
                (self.payload / "bin/cc").symlink_to(target)
                with self.assertRaises(ValueError):
                    R.inventory(self.payload)

    def test_symlink_chain_escape_rejected(self):
        (self.payload / "bin/cc").unlink()
        (self.payload / "bin/cc").symlink_to("../other")
        (self.payload / "other").symlink_to("../outside")
        (self.root / "outside").write_text("outside")
        with self.assertRaisesRegex(ValueError, "escapes"):
            R.inventory(self.payload)

    def test_cyclic_symlink_rejected(self):
        (self.payload / "bin/cc").unlink()
        (self.payload / "bin/cc").symlink_to("cc")
        with self.assertRaisesRegex(ValueError, "cyclic"):
            R.inventory(self.payload)

    def test_fifo_and_special_mode_rejected(self):
        os.mkfifo(self.payload / "fifo")
        with self.assertRaisesRegex(ValueError, "special"):
            R.inventory(self.payload)
        (self.payload / "fifo").unlink()
        (self.payload / "tools/compiler").chmod(0o4755)
        with self.assertRaisesRegex(ValueError, "special"):
            R.inventory(self.payload)

    def test_archive_digest_and_size_checked_before_extract(self):
        self.archive_entries()
        for overrides in ({"archive_sha256": "0" * 64}, {"archive_bytes": 1}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.extract(**overrides)
            self.assertFalse((self.root / "restored").exists())
            self.assertFalse(list(self.root.glob(".android-runtime-*")))

    def test_hostile_archive_paths_rejected_without_escape(self):
        for name in ("../escaped", "/tmp/escaped", "./extra", "bin//extra", "bin/../extra"):
            with self.subTest(name=name):
                info = tarfile.TarInfo(name)
                info.size = 1
                self.archive_entries((info, b"x"))
                with self.assertRaises(ValueError):
                    self.extract()
                self.assertFalse((self.root / "restored").exists())
                self.assertFalse(list(self.root.glob(".android-runtime-*")))
        self.assertFalse((self.root / "escaped").exists())

    def test_duplicate_and_unlisted_archive_entries_rejected(self):
        for name in ("tools/compiler", "unlisted"):
            with self.subTest(name=name):
                info = tarfile.TarInfo(name)
                info.size = 1
                self.archive_entries((info, b"x"))
                with self.assertRaisesRegex(ValueError, "duplicate or unlisted"):
                    self.extract()

    def test_missing_archive_entry_rejected(self):
        self.archive_entries(omit="tools/compiler")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.extract()

    def test_archive_hardlink_rejected_even_if_target_exists(self):
        info = tarfile.TarInfo("tools/compiler")
        info.type = tarfile.LNKTYPE
        info.linkname = "bin/cc"
        self.archive_entries((info, None), omit="tools/compiler")
        with self.assertRaisesRegex(ValueError, "hardlink"):
            self.extract()

    def test_wrong_archive_payload_rejected_before_publish(self):
        (self.payload / "tools/compiler").write_bytes(b"x" * self.expected["entries"]["tools/compiler"]["size"])
        self.archive_entries()
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.extract()
        self.assertFalse((self.root / "restored").exists())

    def test_existing_destination_not_merged_or_removed(self):
        self.archive_entries()
        (self.root / "restored").mkdir()
        (self.root / "restored/keep").write_text("existing")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.extract()
        self.assertEqual((self.root / "restored/keep").read_text(), "existing")

    def test_readonly_directory_failure_removes_staging_without_following_links(self):
        (self.payload / "tools").chmod(0o555)
        self.expected = R.inventory(self.payload)
        self.ledger.write_bytes(R.canonical(self.expected))
        self.identity = R.digest(self.ledger)
        # Keep the protected original digest but put different same-size bytes
        # into the archived read-only directory. Cleanup must not mask rejection.
        (self.payload / "tools/compiler").write_bytes(b"x" * self.expected["entries"]["tools/compiler"]["size"])
        self.archive_entries()
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.extract()
        self.assertFalse((self.root / "restored").exists())
        self.assertFalse(list(self.root.glob(".android-runtime-*")))
        (self.payload / "tools").chmod(0o755)

    def test_readonly_directory_success_preserves_permissions(self):
        (self.payload / "tools").chmod(0o555)
        self.expected = R.inventory(self.payload)
        self.ledger.write_bytes(R.canonical(self.expected))
        self.identity = R.digest(self.ledger)
        self.archive_entries()
        self.extract()
        self.assertEqual((self.root / "restored/tools").stat().st_mode & 0o777, 0o555)
        # Test fixture cleanup is separate from the extractor's success path.
        (self.root / "restored/tools").chmod(0o755)
        (self.payload / "tools").chmod(0o755)

    def test_symlink_parent_inventory_rejected(self):
        value = json.loads(self.ledger.read_text())
        value["entries"]["bin/cc/nested"] = {"type": "directory", "mode": 0o755}
        self.ledger.write_bytes(R.canonical(value))
        with self.assertRaisesRegex(ValueError, "ancestor"):
            R.read_inventory(self.ledger, R.digest(self.ledger))

    def test_boolean_size_and_duplicate_json_key_rejected(self):
        value = json.loads(self.ledger.read_text())
        value["total_bytes"] = True
        self.ledger.write_bytes(R.canonical(value))
        with self.assertRaises(ValueError):
            R.read_inventory(self.ledger, R.digest(self.ledger))
        self.ledger.write_text('{"kind":"first","kind":"second"}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            R.read_inventory(self.ledger, R.digest(self.ledger))

    def test_producer_export_roundtrip_and_content_identity(self):
        record = EXPORT.pack(self.payload, self.ledger, self.identity, self.archive)
        self.assertFalse(record["build_qualified"])
        self.assertEqual(record["archive_sha256"], R.digest(self.archive))
        self.assertEqual(self.extract(), self.expected)

    def test_export_regular_hardlinks_remain_regular_archive_entries(self):
        os.link(self.payload / "tools/compiler", self.payload / "tools/compiler-copy")
        self.expected = R.inventory(self.payload)
        self.ledger.write_bytes(R.canonical(self.expected))
        self.identity = R.digest(self.ledger)
        EXPORT.pack(self.payload, self.ledger, self.identity, self.archive)
        with tarfile.open(self.archive) as archive:
            self.assertTrue(archive.getmember("tools/compiler").isfile())
            self.assertTrue(archive.getmember("tools/compiler-copy").isfile())
        self.assertEqual(self.extract(), self.expected)

    def test_export_rejects_unsealed_payload_without_publishing_archive(self):
        (self.payload / "tools/compiler").write_text("modified before export")
        with self.assertRaisesRegex(ValueError, "payload differs"):
            EXPORT.pack(self.payload, self.ledger, self.identity, self.archive)
        self.assertFalse(self.archive.exists())

    def test_export_does_not_replace_a_concurrently_published_archive(self):
        from unittest.mock import patch
        link = os.link
        def concurrent(source, destination):
            Path(destination).write_bytes(b"another producer's completed archive")
            return link(source, destination)
        with patch.object(EXPORT.os, "link", side_effect=concurrent):
            with self.assertRaises(FileExistsError):
                EXPORT.pack(self.payload, self.ledger, self.identity, self.archive)
        self.assertEqual(self.archive.read_bytes(), b"another producer's completed archive")
        self.assertEqual(list(self.archive.parent.glob(".android-export-*")), [])


if __name__ == "__main__":
    unittest.main()
