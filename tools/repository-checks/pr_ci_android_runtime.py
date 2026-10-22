#!/usr/bin/env python3
"""Seal and verify Android runtime payload bytes before candidate execution.

An inventory is transport evidence, not build provenance or qualification. Its
digest must come from protected policy, never from the downloaded payload itself.
No candidate source, Conan recipe, or archive command is executed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile

KIND = "overte-android-runtime-inventory-v1"
SHA256 = re.compile(r"[0-9a-f]{64}")
MAX_ENTRIES = 500_000
MAX_BYTES = 64 * 1024 ** 3


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate inventory key")
        result[key] = value
    return result


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(value):
    require(type(value) is str and bool(value) and "\\" not in value
            and not any(ord(char) < 32 for char in value)
            and not value.startswith("/")
            and all(part not in {"", ".", ".."} for part in value.split("/")),
            "noncanonical runtime path")
    return PurePosixPath(value)


def link_target(name, target):
    require(type(target) is str and bool(target) and not target.startswith("/")
            and "\\" not in target and not any(ord(char) < 32 for char in target),
            "runtime symlink must be relative")
    parts = list(relative(name).parent.parts)
    for part in target.split("/"):
        if part == "..":
            require(bool(parts), "runtime symlink escapes payload")
            parts.pop()
        elif part not in {"", "."}:
            parts.append(part)


def inventory(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), "runtime root must be a real directory")
    root = root.resolve(strict=True)
    entries, total = {}, 0

    def visit(directory):
        nonlocal total
        for path in sorted(directory.iterdir()):
            name = path.relative_to(root).as_posix()
            relative(name)
            info = path.lstat()
            mode = stat.S_IMODE(info.st_mode)
            require(not mode & 0o7000, "special runtime permissions refused")
            require(len(entries) < MAX_ENTRIES, "runtime inventory entry bound exceeded")
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(path)
                link_target(name, target)
                try:
                    resolved = path.resolve(strict=True)
                except (OSError, RuntimeError) as error:
                    raise ValueError("dangling or cyclic runtime symlink") from error
                require(resolved == root or root in resolved.parents, "runtime symlink escapes payload")
                entries[name] = {"type": "symlink", "target": target}
            elif stat.S_ISREG(info.st_mode):
                total += info.st_size
                require(total <= MAX_BYTES, "runtime payload size bound exceeded")
                entries[name] = {"type": "file", "mode": mode, "size": info.st_size,
                                 "sha256": digest(path)}
            elif stat.S_ISDIR(info.st_mode):
                entries[name] = {"type": "directory", "mode": mode}
                visit(path)
            else:
                raise ValueError("special runtime filesystem entry refused")

    visit(root)
    require(bool(entries), "empty runtime payload")
    return {"kind": KIND, "total_bytes": total, "entries": entries}


def read_inventory(path, expected_sha256):
    require(type(expected_sha256) is str and SHA256.fullmatch(expected_sha256),
            "protected inventory digest required")
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 150_000_000,
            "runtime inventory missing or oversized")
    payload = path.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == expected_sha256,
            "runtime inventory differs from protected digest")
    value = json.loads(payload, object_pairs_hook=unique)
    require(type(value) is dict and set(value) == {"kind", "total_bytes", "entries"}
            and value["kind"] == KIND and type(value["total_bytes"]) is int
            and 0 <= value["total_bytes"] <= MAX_BYTES
            and type(value["entries"]) is dict and 0 < len(value["entries"]) <= MAX_ENTRIES,
            "invalid runtime inventory envelope")
    total = 0
    for name, entry in value["entries"].items():
        relative(name)
        require(type(entry) is dict, "invalid runtime inventory entry")
        kind = entry.get("type")
        if kind == "symlink":
            require(set(entry) == {"type", "target"}, "invalid runtime symlink entry")
            link_target(name, entry["target"])
        else:
            keys = {"type", "mode", "size", "sha256"} if kind == "file" else {"type", "mode"}
            require(kind in {"file", "directory"} and set(entry) == keys
                    and type(entry["mode"]) is int and 0 <= entry["mode"] <= 0o777,
                    "invalid runtime file/directory entry")
            if kind == "file":
                require(type(entry["size"]) is int and 0 <= entry["size"] <= MAX_BYTES
                        and type(entry["sha256"]) is str and SHA256.fullmatch(entry["sha256"]),
                        "invalid runtime file digest/size")
                total += entry["size"]
        for parent in PurePosixPath(name).parents:
            if str(parent) != ".":
                require(value["entries"].get(str(parent), {}).get("type") == "directory",
                        "runtime ancestor must be an inventoried real directory")
    require(total == value["total_bytes"], "runtime inventory total differs")
    return value


def verify(root, ledger, expected_sha256):
    expected = read_inventory(ledger, expected_sha256)
    require(inventory(root) == expected, "runtime payload differs from protected inventory")
    return expected


def extract(archive_path, destination, ledger, inventory_sha256, archive_sha256, archive_bytes):
    """Verify a fixed archive, materialize into a fresh sibling, then publish.

    Hard links and special entries are refused. Symlinks are created only after
    regular files, and may never be an ancestor of another archive entry.
    Existing destination trees are never merged with an untrusted cache restore.
    """
    expected = read_inventory(ledger, inventory_sha256)
    archive_path, destination = Path(archive_path), Path(destination)
    require(type(archive_sha256) is str and SHA256.fullmatch(archive_sha256)
            and type(archive_bytes) is int and 0 < archive_bytes <= MAX_BYTES,
            "protected archive digest and size required")
    require(archive_path.is_file() and not archive_path.is_symlink()
            and archive_path.stat().st_size == archive_bytes, "runtime archive size differs")
    require(not destination.exists() and not destination.is_symlink(), "runtime destination already exists")
    require(destination.parent.is_dir() and destination.parent.resolve() == destination.parent,
            "runtime destination parent must be a canonical real directory")
    staging = Path(tempfile.mkdtemp(prefix=".android-runtime-", dir=destination.parent))
    try:
        with archive_path.open("rb") as source:
            require(hashlib.file_digest(source, "sha256").hexdigest() == archive_sha256,
                    "runtime archive digest differs")
            source.seek(0)
            with tarfile.open(fileobj=source, mode="r:*") as archive:
                seen, links, directories, unpacked = set(), [], [], 0
                for member in archive:
                    name = member.name.rstrip("/") if member.isdir() else member.name
                    relative(name)
                    require(name not in seen and name in expected["entries"],
                            "runtime archive contains duplicate or unlisted entry")
                    seen.add(name)
                    entry = expected["entries"][name]
                    path = staging / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if member.isdir():
                        require(entry["type"] == "directory" and member.mode == entry["mode"],
                                "runtime archive directory differs")
                        path.mkdir(exist_ok=True)
                        directories.append((path, entry["mode"]))
                    elif member.issym():
                        require(entry == {"type": "symlink", "target": member.linkname},
                                "runtime archive symlink differs")
                        links.append((path, member.linkname))
                    elif member.isfile():
                        require(entry["type"] == "file" and member.mode == entry["mode"]
                                and member.size == entry["size"], "runtime archive file differs")
                        unpacked += member.size
                        require(unpacked <= expected["total_bytes"], "runtime unpacked size exceeded")
                        payload = archive.extractfile(member)
                        require(payload is not None, "runtime archive file unavailable")
                        with path.open("xb") as output:
                            shutil.copyfileobj(payload, output, length=1024 * 1024)
                        path.chmod(entry["mode"])
                    else:
                        raise ValueError("runtime archive special or hardlink entry refused")
                require(seen == set(expected["entries"]), "runtime archive inventory incomplete")
                for path, target in links:
                    path.symlink_to(target)
                # Children were created under writable temporary directories.
                for path, mode in sorted(directories, key=lambda item: len(item[0].parts), reverse=True):
                    path.chmod(mode)
        require(inventory(staging) == expected, "extracted runtime payload checksum mismatch")
        staging.rename(destination)
    finally:
        if staging.exists():
            # A verified archive may legitimately contain read-only package
            # directories. Failed payload verification must still remove the
            # private staging tree, without following directory symlinks.
            for parent, directories, _ in os.walk(staging, topdown=True, followlinks=False):
                Path(parent).chmod(Path(parent).stat().st_mode | 0o700)
                for name in directories:
                    path = Path(parent) / name
                    info = path.lstat()
                    if stat.S_ISDIR(info.st_mode):
                        path.chmod(stat.S_IMODE(info.st_mode) | 0o700)
            shutil.rmtree(staging)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("inventory")
    seal.add_argument("--root", required=True)
    seal.add_argument("--output", required=True)
    check = commands.add_parser("verify")
    check.add_argument("--root", required=True)
    check.add_argument("--inventory", required=True)
    check.add_argument("--inventory-sha256", required=True)
    unpack = commands.add_parser("extract")
    unpack.add_argument("--archive", required=True)
    unpack.add_argument("--destination", required=True)
    unpack.add_argument("--inventory", required=True)
    unpack.add_argument("--inventory-sha256", required=True)
    unpack.add_argument("--archive-sha256", required=True)
    unpack.add_argument("--archive-bytes", required=True, type=int)
    args = parser.parse_args()
    if args.command == "inventory":
        output = Path(args.output)
        require(not output.exists() and not output.is_symlink(), "inventory output already exists")
        require(Path(args.root).resolve() not in output.resolve().parents,
                "inventory output must be outside its payload")
        output.write_bytes(canonical(inventory(args.root)))
        print(digest(output))
    elif args.command == "verify":
        verify(args.root, args.inventory, args.inventory_sha256)
        print("Runtime payload matches protected inventory; build qualification is separate.")
    else:
        extract(args.archive, args.destination, args.inventory, args.inventory_sha256,
                args.archive_sha256, args.archive_bytes)
        print("Runtime archive and every extracted entry match protected digests.")


if __name__ == "__main__":
    main()
