#!/usr/bin/env python3
"""Pure bounded Android APK snapshot, unsigned ZIP and native ELF checks."""
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import hashlib
import importlib.util
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
MAX_APK = 2 * 1024 * 1024 * 1024
MAX_UNCOMPRESSED = 4 * 1024 * 1024 * 1024
MAX_LIBRARY = 512 * 1024 * 1024
SYSTEM_LIBRARIES = frozenset({
    "libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so", "libEGL.so",
    "libGLESv1_CM.so", "libGLESv2.so", "libGLESv3.so", "libOpenSLES.so", "libjnigraphics.so",
    "libz.so", "libvulkan.so", "libmediandk.so", "libnativewindow.so", "libcamera2ndk.so", "libaaudio.so",
})

def require(value, message):
    if not value:
        raise ValueError(message)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def elf_dynamic(path):
    common = load(HERE / "verify.py", "android_apk_common_elf")
    common.android_elf(path)
    require(path.stat().st_size <= MAX_LIBRARY, "Oversized APK native library")
    with path.open("rb") as stream:
        header = struct.unpack("<16sHHIQQQIHHHHHH", stream.read(64))
        loads, dynamics = [], []
        for number in range(header[10]):
            stream.seek(header[5] + number * header[9])
            row = struct.unpack("<IIQQQQQQ", stream.read(56))
            if row[0] == 1: loads.append(row)
            if row[0] == 2: dynamics.append(row)
        require(len(dynamics) == 1, "Expected one ELF dynamic table")
        dynamic = dynamics[0]
        require(0 < dynamic[5] <= 16 * 1024 * 1024 and dynamic[5] % 16 == 0 and
                dynamic[2] + dynamic[5] <= path.stat().st_size, "Invalid ELF dynamic bounds")
        stream.seek(dynamic[2])
        entries, terminated = {}, False
        for _ in range(dynamic[5] // 16):
            tag, value = struct.unpack("<qQ", stream.read(16))
            if tag == 0:
                terminated = True
                break
            entries.setdefault(tag, []).append(value)
        require(terminated and len(entries.get(5, [])) == 1 and len(entries.get(10, [])) == 1 and
                len(entries.get(14, [])) == 1, "Missing/ambiguous ELF SONAME/string table")
        address, size = entries[5][0], entries[10][0]
        require(0 < size <= 16 * 1024 * 1024, "Invalid ELF string table size")
        mappings = [row for row in loads if row[3] <= address and address + size <= row[3] + row[5]]
        require(len(mappings) == 1, "ELF string table is not in one file-backed LOAD segment")
        row = mappings[0]
        stream.seek(row[2] + address - row[3])
        strings = stream.read(size)
        require(len(strings) == size, "Truncated ELF string table")

    def name(offset):
        require(0 <= offset < len(strings), "ELF dynamic string escaped")
        end = strings.find(b"\0", offset)
        require(end > offset, "Invalid ELF dynamic string")
        value = strings[offset:end].decode("ascii")
        require(re.fullmatch(r"[A-Za-z0-9_.+-]+[.]so(?:[.][0-9]+)*", value), "Unsafe ELF dynamic library name")
        return value

    needed = [name(offset) for offset in entries.get(1, [])]
    require(len(needed) == len(set(needed)), "Duplicate ELF NEEDED entries")
    return {"soname": name(entries[14][0]), "needed": sorted(needed), "sha256": common.digest(path)}

def unsigned_archive(apk):
    """Refuse JAR signatures and the actual APK v2/v3 signing-block location."""
    with zipfile.ZipFile(apk) as archive:
        for name in archive.namelist():
            upper = name.upper()
            require(not (upper.startswith("META-INF/") and upper.endswith((".SF", ".RSA", ".DSA", ".EC"))),
                    "CI APK contains a v1 JAR signature")
        central = archive.start_dir
    with apk.open("rb") as stream:
        if central >= 16:
            stream.seek(central - 16)
            require(stream.read(16) != b"APK Sig Block 42", "CI APK contains an APK v2/v3 signing block")

@contextmanager
def bound_apk(apk):
    require(apk.is_file() and not apk.is_symlink(), "APK must be a regular non-symlink file")
    with tempfile.TemporaryDirectory(prefix="overte-native-apk-") as directory:
        snapshot = Path(directory) / "candidate.apk"
        with os.fdopen(os.open(apk, os.O_RDONLY | os.O_NOFOLLOW), "rb") as source:
            initial = os.fstat(source.fileno())
            require(stat.S_ISREG(initial.st_mode) and 0 < initial.st_size <= MAX_APK, "APK size/type exceeds bound")
            digest = hashlib.sha256()
            copied = 0
            with snapshot.open("xb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    copied += len(chunk)
                    require(copied <= MAX_APK, "APK exceeds snapshot bound")
                    digest.update(chunk); output.write(chunk)
            identity = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
            require(copied == initial.st_size and identity(os.fstat(source.fileno())) == identity(initial),
                    "APK changed during snapshot")
        snapshot.chmod(0o400)
        checksum = digest.hexdigest()
        yield snapshot, checksum
        require(not apk.is_symlink() and identity(apk.stat()) == identity(initial), "Original APK changed during verification")
        with apk.open("rb") as stream:
            require(hashlib.file_digest(stream, "sha256").hexdigest() == checksum, "Original APK bytes changed")
        with snapshot.open("rb") as stream:
            require(hashlib.file_digest(stream, "sha256").hexdigest() == checksum, "Private APK snapshot changed")


def inspect_native(apk):
    """Validate every actual ZIP native DSO and its complete packaged closure."""
    libraries = {}
    with zipfile.ZipFile(apk) as archive, tempfile.TemporaryDirectory(prefix="android-native-elf-") as temp:
        entries = archive.infolist()
        require(len(entries) <= 50000 and sum(row.file_size for row in entries) <= MAX_UNCOMPRESSED,
                "APK ZIP exceeds entry/expanded-byte bounds")
        require(len({row.filename for row in entries}) == len(entries), "Duplicate APK ZIP entry")
        for row in entries:
            path = PurePosixPath(row.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in row.filename and
                    not any(ord(c) < 32 or ord(c) == 127 for c in row.filename) and
                    (row.external_attr >> 16) & 0o170000 != 0o120000, "Unsafe APK ZIP path/type")
            if not row.filename.startswith("lib/") or row.is_dir(): continue
            parts = row.filename.split("/")
            require(len(parts) == 3 and parts[1] == "arm64-v8a" and parts[2].endswith(".so"),
                    "Unexpected APK native ABI/path")
            require(0 < row.file_size <= MAX_LIBRARY, "Oversized or empty APK native library")
            output = Path(temp) / parts[2]
            with archive.open(row) as source, output.open("xb") as target:
                total = 0
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    total += len(chunk)
                    require(total <= MAX_LIBRARY, "Oversized extracted APK library")
                    target.write(chunk)
            require(total == row.file_size, "Truncated APK native library")
            info = elf_dynamic(output)
            require(info["soname"] == parts[2], "Packaged filename and ELF SONAME differ")
            libraries[parts[2]] = info
            output.unlink()
    require(libraries, "APK has no native libraries")
    for name, info in libraries.items():
        require(set(info["needed"]) <= libraries.keys() | SYSTEM_LIBRARIES,
                "Packaged ELF has a missing non-platform dependency: " + name)
    return libraries
