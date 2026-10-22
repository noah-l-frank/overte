#!/usr/bin/env python3
"""Verify the built parent-owned Android native closure, without executing it.

This is output/source validation, not a substitute for the authenticated CI
selection, immutable dependency provenance, or an actual successful build.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess


REQUIRED = frozenset({
    "interface", "shared", "networking", "script-engine", "shaders", "gl",
    "gpu", "entities", "physics", "audio", "audio-client",
    "overte-android-common-runtime",
})
ALLOWED_SOURCE_ROOTS = ("interface/", "libraries/", "android/common/")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def regular_inside(path, root):
    path = path.resolve(strict=True)
    require(path.is_relative_to(root) and path.is_file(),
            "Input/output escapes its declared root or is not a regular file")
    return path


def android_elf(path):
    """Check an actual ELF64 Android DSO and every LOAD segment's 16 KiB ABI."""
    with path.open("rb") as stream:
        header = stream.read(64)
        require(len(header) == 64 and header[:7] == b"\x7fELF\x02\x01\x01",
                "Expected a little-endian ELF64 artifact")
        fields = struct.unpack("<16sHHIQQQIHHHHHH", header)
        require(fields[1] == 3 and fields[2] == 183, "Expected an AArch64 shared library")
        offset, entry_size, count = fields[5], fields[9], fields[10]
        require(entry_size == 56 and 0 < count <= 4096,
                "Invalid ELF program header table")
        require(offset >= 64 and offset + entry_size * count <= path.stat().st_size,
                "Truncated ELF program header table")
        loads = 0
        for number in range(count):
            stream.seek(offset + number * entry_size)
            row = struct.unpack("<IIQQQQQQ", stream.read(entry_size))
            if row[0] != 1:
                continue
            loads += 1
            alignment = row[7]
            require(alignment >= 16384 and alignment & (alignment - 1) == 0,
                    "ELF LOAD segment is not 16 KiB aligned")
            require(row[2] % alignment == row[3] % alignment,
                    "ELF LOAD file/address alignment differs")
            require(row[2] + row[5] <= path.stat().st_size and row[5] <= row[6],
                    "Invalid ELF LOAD segment bounds")
        require(loads > 0, "ELF has no LOAD segments")


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args])


def query(build):
    path = build / ".cmake/api/v1/query/client-overte-common-native"
    path.mkdir(parents=True, exist_ok=True)
    (path / "codemodel-v2").write_text("")


def inspect(source, build, expected_head):
    source, build = source.resolve(strict=True), build.resolve(strict=True)
    require(not build.is_relative_to(source), "Use a fresh build directory outside the candidate tree")
    require(re.fullmatch(r"[0-9a-f]{40}", expected_head) is not None, "Invalid candidate SHA")
    require(git(source, "rev-parse", "HEAD").decode().strip() == expected_head,
            "Candidate HEAD differs from the authenticated selection")
    require(subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--"],
                           check=False).returncode == 0, "Tracked candidate inputs changed")
    reply = build / ".cmake/api/v1/reply"
    indexes = sorted(reply.glob("index-*.json"))
    require(len(indexes) == 1, "Expected one fresh CMake File API reply")
    index = json.loads(indexes[0].read_text())
    response = index.get("reply", {}).get("client-overte-common-native", {}).get("codemodel-v2", {})
    require(response.get("kind") == "codemodel", "Missing requested CMake codemodel")

    def read_reply(name):
        require(isinstance(name, str) and Path(name).name == name, "Invalid CMake reply path")
        return json.loads(regular_inside(reply / name, reply.resolve()).read_text())

    model = read_reply(response.get("jsonFile"))
    require(Path(model["paths"]["source"]).resolve() == source and
            Path(model["paths"]["build"]).resolve() == build, "CMake source/build roots differ")
    configs = model["configurations"]
    require(len(configs) == 1 and configs[0]["name"] in {"Debug", "RelWithDebInfo"},
            "Unexpected Android consumer configuration")
    targets, inputs, outputs = {}, {}, []
    for reference in configs[0]["targets"]:
        target = read_reply(reference["jsonFile"])
        if target["type"] not in {"SHARED_LIBRARY", "MODULE_LIBRARY", "STATIC_LIBRARY", "OBJECT_LIBRARY", "EXECUTABLE"}:
            continue
        name = target["name"]
        require(name not in targets, "Duplicate CMake target")
        require(target["type"] == "SHARED_LIBRARY", "Unexpected non-shared native build target")
        fragments = target.get("link", {}).get("commandFragments", [])
        require(any("--no-undefined" in token.split(",")
                    for row in fragments for token in shlex.split(row["fragment"])),
                "Native target lacks the strict undefined-symbol link contract: " + name)
        count = 0
        for entry in target.get("sources", []):
            if "compileGroupIndex" not in entry:
                continue
            count += 1
            candidate = Path(entry["path"])
            if not candidate.is_absolute():
                candidate = source / candidate
            candidate = candidate.resolve(strict=True)
            require(candidate.is_file(), "Compiled source is not regular")
            if candidate.is_relative_to(build):
                # AUTOMOC/RCC and generated entity/shader translation units.
                continue
            require(candidate.is_relative_to(source), "Compiled source is outside the candidate tree")
            relative = candidate.relative_to(source).as_posix()
            require(relative.startswith(ALLOWED_SOURCE_ROOTS),
                    "Compiled source is not parent-owned common code: " + relative)
            blob = git(source, "cat-file", "blob", expected_head + ":" + relative)
            require(hashlib.sha256(blob).hexdigest() == digest(candidate),
                    "Compiled source differs from the candidate Git blob")
            inputs[relative] = digest(candidate)
        require(count > 0, "Native target has no compiled sources")
        artifacts = target.get("artifacts", [])
        require(len(artifacts) == 1, "Expected one shared library output per target")
        artifact = Path(artifacts[0]["path"])
        artifact = regular_inside(artifact if artifact.is_absolute() else build / artifact, build)
        android_elf(artifact)
        outputs.append({"target": name, "path": artifact.relative_to(build).as_posix(),
                        "sha256": digest(artifact), "compiled_source_count": count})
        targets[name] = target
    require(REQUIRED <= targets.keys(), "Missing required production native targets")
    require(any(p.startswith("interface/src/") for p in inputs), "Missing Interface production source")
    require(any(p.startswith("android/common/") for p in inputs), "Missing Android common production source")
    # Close the source window; an executing wrapper also binds this result to
    # its authenticated dependency/runtime/build invocation and final CI gate.
    require(git(source, "rev-parse", "HEAD").decode().strip() == expected_head,
            "Candidate HEAD changed during output verification")
    require(subprocess.run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--"],
                           check=False).returncode == 0, "Candidate changed during output verification")
    return {"schema": 1, "scope": "parent-owned-android-common-native-elf",
            "candidate_sha": expected_head, "candidate_tree": git(source, "rev-parse", "HEAD^{tree}").decode().strip(),
            "configuration": configs[0]["name"], "abi": "arm64-v8a", "page_size": 16384,
            "source_inputs": dict(sorted(inputs.items())),
            "outputs": sorted(outputs, key=lambda row: row["target"]),
            "apk_qualified": False, "device_tested": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--query", action="store_true", help="Request the codemodel before configuring a fresh build")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--expected-head")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.query:
        query(args.build)
    else:
        require(args.source and args.expected_head and args.receipt,
                "Output verification requires source, expected-head and receipt")
        result = inspect(args.source, args.build, args.expected_head)
        args.receipt.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
