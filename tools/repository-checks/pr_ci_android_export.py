#!/usr/bin/env python3
"""Export an already sealed runtime as a reproducible bounded data archive.

This producer-side tool executes no payload program and grants no qualification.
The protected consumer must verify the resulting archive and original inventory.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tarfile
import tempfile

SPEC = importlib.util.spec_from_file_location("runtime_payload", Path(__file__).with_name("pr_ci_android_runtime.py"))
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)


class SealedReader:
    def __init__(self, stream):
        self.stream, self.digest = stream, hashlib.sha256()

    def read(self, size):
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def pack(root, ledger, inventory_sha256, destination):
    root, destination = Path(root).resolve(strict=True), Path(destination)
    expected = R.verify(root, ledger, inventory_sha256)
    R.require(not destination.exists() and not destination.is_symlink(), "archive output already exists")
    R.require(destination.parent.resolve(strict=True) == destination.parent
              and not destination.is_relative_to(root), "archive output must be outside the payload")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".android-export-", dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            with gzip.GzipFile(filename="", fileobj=output, mode="wb", compresslevel=1, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as archive:
                    for name, entry in sorted(expected["entries"].items()):
                        path = root / name
                        info = tarfile.TarInfo(name)
                        info.mtime = info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        if entry["type"] == "directory":
                            info.type, info.mode = tarfile.DIRTYPE, entry["mode"]
                            archive.addfile(info)
                        elif entry["type"] == "symlink":
                            info.type, info.mode, info.linkname = tarfile.SYMTYPE, 0o777, entry["target"]
                            archive.addfile(info)
                        else:
                            # Construct regular entries explicitly: tarfile.add
                            # may turn filesystem hardlinks into tar hardlinks,
                            # which the protected extractor deliberately refuses.
                            R.require(not path.is_symlink(), "runtime file changed to a symlink")
                            info.size, info.mode = entry["size"], entry["mode"]
                            with path.open("rb") as source:
                                reader = SealedReader(source)
                                archive.addfile(info, reader)
                                R.require(reader.digest.hexdigest() == entry["sha256"]
                                          and path.stat().st_size == entry["size"],
                                          "runtime file changed while exporting")
            output.flush()
        R.require(temporary.stat().st_size <= R.MAX_BYTES, "runtime archive size bound exceeded")
        # Link publishes the complete file atomically without replacing a file
        # another producer created after the initial absence check.
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"kind": "overte-android-runtime-archive-v1", "archive_sha256": R.digest(destination),
            "archive_bytes": destination.stat().st_size, "inventory_sha256": inventory_sha256,
            "unpacked_bytes": expected["total_bytes"], "entries": len(expected["entries"]),
            "build_qualified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(pack(args.root, args.inventory, args.inventory_sha256, args.out), sort_keys=True))


if __name__ == "__main__":
    main()
