#!/usr/bin/env python3
"""Product-independent actual Android ZIP/ELF output rejection regressions."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import warnings
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("android_native_apk", HERE / "apk_native.py")
APK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(APK)


def elf(soname, needed=("libc.so",), machine=183, alignment=16384):
    strings = b"\0"
    offsets = []
    for name in (soname, *needed):
        offsets.append(len(strings)); strings += name.encode() + b"\0"
    dynamic_size = 16 * (4 + len(needed)); dynamic_offset = 176
    string_offset = dynamic_offset + dynamic_size; size = string_offset + len(strings)
    header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF\x02\x01\x01" + b"\0" * 9,
                         3, machine, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    program = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, size, size, alignment)
    dynamic = struct.pack("<IIQQQQQQ", 2, 4, dynamic_offset, dynamic_offset, dynamic_offset, dynamic_size, dynamic_size, 8)
    tags = [(5, string_offset), (10, len(strings)), (14, offsets[0])]
    tags += [(1, offset) for offset in offsets[1:]] + [(0, 0)]
    return header + program + dynamic + b"".join(struct.pack("<qQ", *row) for row in tags) + strings


class NativeApkStructure(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.apk = self.root / "candidate.apk"
        self.entries = {"AndroidManifest.xml": b"fixture", "lib/arm64-v8a/libone.so": elf("libone.so", ("libtwo.so",)),
                        "lib/arm64-v8a/libtwo.so": elf("libtwo.so")}

    def archive(self):
        with zipfile.ZipFile(self.apk,"w") as archive:
            for name,data in self.entries.items():archive.writestr(name,data)
        return self.apk

    def test_real_native_elf_and_transitive_closure(self):
        result = APK.inspect_native(self.archive())
        self.assertEqual(set(result), {"libone.so", "libtwo.so"})
        self.assertEqual(result["libone.so"]["needed"], ["libtwo.so"])
        self.assertEqual(result["libtwo.so"]["needed"], ["libc.so"])

    def test_4k_and_host_elf_rejected(self):
        for options in ({"alignment":4096},{"machine":62}):
            self.entries["lib/arm64-v8a/libtwo.so"] = elf("libtwo.so", **options)
            with self.assertRaises(ValueError):APK.inspect_native(self.archive())

    def test_missing_needed_dependency_rejected(self):
        del self.entries["lib/arm64-v8a/libtwo.so"]
        with self.assertRaisesRegex(ValueError,"missing non-platform"):APK.inspect_native(self.archive())

    def test_soname_mismatch_rejected(self):
        self.entries["lib/arm64-v8a/libtwo.so"] = elf("libother.so")
        with self.assertRaisesRegex(ValueError,"SONAME differ"):APK.inspect_native(self.archive())

    def test_truncated_and_escaped_dynamic_strings_rejected(self):
        for data in (elf("libtwo.so")[:100],elf("../escaped.so")):
            self.entries["lib/arm64-v8a/libtwo.so"] = data
            with self.assertRaises(ValueError):APK.inspect_native(self.archive())

    def test_foreign_abi_and_unsafe_paths_rejected(self):
        for name in ("lib/x86_64/libtwo.so","../escape","assets/unsafe\\name"):
            self.entries[name] = b"unsafe"
            with self.assertRaises(ValueError):APK.inspect_native(self.archive())
            del self.entries[name]

    def test_duplicate_and_nonregular_zip_entries_rejected(self):
        self.archive()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore",UserWarning)
            with zipfile.ZipFile(self.apk,"a") as archive:archive.writestr("AndroidManifest.xml",b"duplicate")
        with self.assertRaisesRegex(ValueError,"Duplicate"):APK.inspect_native(self.apk)
        for mode in (0o120777,0o010600,0o020600):
            self.archive()
            with zipfile.ZipFile(self.apk,"a") as archive:
                entry=zipfile.ZipInfo("assets/special");entry.create_system=3;entry.external_attr=mode<<16
                archive.writestr(entry,b"special")
            with self.assertRaisesRegex(ValueError,"Unsafe"):APK.inspect_native(self.apk)

    def test_jar_signatures_rejected(self):
        for name in ("META-INF/CERT.RSA","META-INF/CERT.SF","META-INF/CERT.EC"):
            self.entries[name]=b"signature"
            with self.assertRaisesRegex(ValueError,"v1 JAR"):APK.unsigned_archive(self.archive())
            del self.entries[name]

    def test_actual_signing_block_location_rejected(self):
        self.archive()
        with zipfile.ZipFile(self.apk) as archive:central=archive.start_dir
        data=self.apk.read_bytes();block=struct.pack("<QQ",24,24)+b"APK Sig Block 42"
        data=bytearray(data[:central]+block+data[central:]);eocd=data.rfind(b"PK\x05\x06")
        struct.pack_into("<I",data,eocd+16,central+len(block));self.apk.write_bytes(data)
        with self.assertRaisesRegex(ValueError,"v2/v3 signing block"):APK.unsigned_archive(self.apk)

    def test_bounded_snapshot_positive_and_original_mutation_rejection(self):
        self.archive()
        with APK.bound_apk(self.apk) as (snapshot,digest):
            self.assertEqual(snapshot.read_bytes(),self.apk.read_bytes())
            self.assertEqual(snapshot.stat().st_mode&0o777,0o400)
        with self.assertRaisesRegex(ValueError,"Original APK changed"):
            with APK.bound_apk(self.apk) as (snapshot,digest):self.apk.write_bytes(b"changed")

    def test_snapshot_symlink_and_oversize_original_rejected(self):
        self.archive();link=self.root/"link.apk";link.symlink_to(self.apk)
        with self.assertRaises(ValueError):
            with APK.bound_apk(link):self.fail("Symlink accepted")
        with self.apk.open("wb") as stream:stream.truncate(APK.MAX_APK+1)
        with self.assertRaisesRegex(ValueError,"size/type"):
            with APK.bound_apk(self.apk):self.fail("Oversize APK accepted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
