#!/usr/bin/env python3
"""Real ZIP and ELF mutation checks for the unsigned Pico CI output verifier."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pico_ci_unsigned_verify", HERE / "verify_apk.py")
VERIFY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VERIFY)
LIBRARIES = {"libc++_shared.so", "libopenxr_loader.so", "libpicoInterface.so", "libpicoOpenXR.so",
             "libplugins_libopenxr.so", "libinterface.so", "libssl_3.so", "libcrypto_3.so"}


def elf(soname, needed=("libc.so",), *, machine=183, alignment=16384):
    strings = b"\0"
    offsets = []
    for name in (soname, *needed):
        offsets.append(len(strings))
        strings += name.encode() + b"\0"
    dynamic_size = 16 * (4 + len(needed))
    dynamic_offset = 64 + 56 * 2
    strings_offset = dynamic_offset + dynamic_size
    size = strings_offset + len(strings)
    header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF\x02\x01\x01" + b"\0" * 9,
                         3, machine, 1, 0, 64, 0, 0, 64, 56, 2, 0, 0, 0)
    load = struct.pack("<IIQQQQQQ", 1, 5, 0, 0, 0, size, size, alignment)
    dynamic = struct.pack("<IIQQQQQQ", 2, 4, dynamic_offset, dynamic_offset, dynamic_offset, dynamic_size, dynamic_size, 8)
    tags = [(5, strings_offset), (10, len(strings)), (14, offsets[0])]
    tags.extend((1, offset) for offset in offsets[1:])
    tags.append((0, 0))
    return header + load + dynamic + b"".join(struct.pack("<qQ", *tag) for tag in tags) + strings


class UnsignedPicoOutput(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.apk = Path(self.temp.name) / "pico-unsigned.apk"
        self.libraries = {name: elf(name) for name in LIBRARIES}
        self.extra = {}

    def archive(self):
        with zipfile.ZipFile(self.apk, "w") as archive:
            archive.writestr("AndroidManifest.xml", "fixture binary XML is not decoded by these structural tests")
            for name, value in self.libraries.items(): archive.writestr("lib/arm64-v8a/" + name, value)
            for name, value in self.extra.items(): archive.writestr(name, value)
        return self.apk

    def test_actual_aarch64_elf_soname_needed_and_unsigned_zip_shape(self):
        result = VERIFY.inspect_unsigned_native(self.archive())
        self.assertEqual(set(result), LIBRARIES)
        self.assertEqual(result["libinterface.so"]["needed"], ["libc.so"])

    def test_missing_transitive_nonplatform_dependency(self):
        self.libraries["libpicoInterface.so"] = elf("libpicoInterface.so", needed=("libinterface.so", "libmissing.so"))
        with self.assertRaisesRegex(ValueError, "missing non-platform dependency"):
            VERIFY.inspect_unsigned_native(self.archive())

    def test_nonmatching_soname(self):
        self.libraries["libinterface.so"] = elf("libunrelated.so")
        with self.assertRaisesRegex(ValueError, "filename and ELF SONAME"):
            VERIFY.inspect_unsigned_native(self.archive())

    def test_4k_or_host_elf_cannot_be_packaged(self):
        for options, expected in (({"alignment": 4096}, "16 KiB"), ({"machine": 62}, "AArch64")):
            self.libraries["libopenxr_loader.so"] = elf("libopenxr_loader.so", **options)
            with self.assertRaisesRegex(ValueError, expected): VERIFY.inspect_unsigned_native(self.archive())

    def test_missing_pico_plugin_and_interface(self):
        del self.libraries["libplugins_libopenxr.so"]
        with self.assertRaises((ValueError, RuntimeError)): VERIFY.inspect_unsigned_native(self.archive())
        self.libraries["libplugins_libopenxr.so"] = elf("libplugins_libopenxr.so")
        del self.libraries["libinterface.so"]
        with self.assertRaisesRegex(ValueError, "native output is missing"): VERIFY.inspect_unsigned_native(self.archive())

    def test_actual_v2_v3_signing_block_location_rejected(self):
        self.archive()
        with zipfile.ZipFile(self.apk) as archive: central = archive.start_dir
        data = self.apk.read_bytes()
        block = struct.pack("<QQ", 24, 24) + b"APK Sig Block 42"
        data = bytearray(data[:central] + block + data[central:])
        eocd = data.rfind(b"PK\x05\x06")
        struct.pack_into("<I", data, eocd + 16, central + len(block))
        self.apk.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "v2/v3 signing block"): VERIFY.inspect_unsigned_native(self.apk)

    def test_v1_signature_and_unsafe_zip_rejected(self):
        self.extra["META-INF/CERT.RSA"] = b"fixture signature"
        with self.assertRaisesRegex(ValueError, "v1 JAR"): VERIFY.inspect_unsigned_native(self.archive())
        self.extra = {"../outside": b"unsafe"}
        with self.assertRaisesRegex(RuntimeError, "unsafe ZIP"): VERIFY.inspect_unsigned_native(self.archive())

    def test_e2e_and_wrong_abi_and_legacy_ssl_forbidden(self):
        self.extra["assets/openxr/1/api_layers/explicit.d/overte_e2e_input.json"] = b"{}"
        with self.assertRaises((ValueError, RuntimeError)): VERIFY.inspect_unsigned_native(self.archive())
        self.extra = {"lib/x86_64/libwrong.so": elf("libwrong.so", machine=62)}
        with self.assertRaises((ValueError, RuntimeError)): VERIFY.inspect_unsigned_native(self.archive())
        self.extra = {}
        self.libraries["libssl_1_1.so"] = elf("libssl_1_1.so")
        with self.assertRaisesRegex(ValueError, "Legacy/renamed"): VERIFY.inspect_unsigned_native(self.archive())

    def test_truncated_and_unsafe_dynamic_table_rejected(self):
        self.libraries["libinterface.so"] = elf("../../outside.so")
        with self.assertRaisesRegex(ValueError, "Unsafe ELF dynamic"): VERIFY.inspect_unsigned_native(self.archive())
        self.libraries["libinterface.so"] = elf("libinterface.so")[:100]
        with self.assertRaises(ValueError): VERIFY.inspect_unsigned_native(self.archive())


if __name__ == "__main__":
    unittest.main(verbosity=2)
