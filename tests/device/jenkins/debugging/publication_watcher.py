"""Read only the closed, public debug publication; no device or cleanup API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

LIMITS = {"summary.json": 256 * 1024, "junit.xml": 256 * 1024,
          "diagnostic-events.safe.jsonl": 16 * 1024 * 1024}
MARKER = "debug-state.json"

class PublicationError(ValueError):
    pass

def need(value):
    if not value:
        raise PublicationError("PUBLICATION_ERROR")

def signature(s):
    return (s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode,
            s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result)
        result[key] = value
    return result

def read_at(directory, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
             and stat.S_IMODE(before.st_mode) == 0o600 and before.st_nlink == 1
             and 0 < before.st_size <= limit)
        chunks, total = [], 0
        while True:
            data = os.read(fd, min(65536, limit + 1 - total))
            if not data:
                break
            chunks.append(data)
            total += len(data)
            need(total <= limit)
        after = os.fstat(fd)
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        need(signature(before) == signature(after) == signature(current))
        body = b"".join(chunks)
        need(len(body) == before.st_size)
        return body, signature(before)
    finally:
        os.close(fd)

INDEX = "artifact-index.json"
CORE = set(LIMITS)

def relative(value):
    need(type(value) is str and 0 < len(value) <= 512)
    parts = value.split("/")
    need(len(parts) <= 8 and all(re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,119}", part)
                                 and part not in {".", ".."} for part in parts))
    return value

def reference(value, maximum):
    need(type(value) is dict and set(value) == {"sha256", "bytes"}
         and type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"])
         and type(value["bytes"]) is int and 0 < value["bytes"] <= maximum)
    return value

def validate_policy(policy):
    need(type(policy) is dict and set(policy) == {
        "schemaVersion", "literalFiles", "logDirectories", "maxFiles", "maxTotalBytes"})
    need(type(policy["schemaVersion"]) is int and policy["schemaVersion"] == 1
         and type(policy["maxFiles"]) is int and 3 <= policy["maxFiles"] <= 512
         and type(policy["maxTotalBytes"]) is int and 1 <= policy["maxTotalBytes"] <= 128 * 1024 * 1024
         and type(policy["literalFiles"]) is dict and CORE <= set(policy["literalFiles"])
         and len(policy["literalFiles"]) <= policy["maxFiles"]
         and type(policy["logDirectories"]) is list and len(policy["logDirectories"]) <= 16)
    for name, row in policy["literalFiles"].items():
        relative(name)
        need(name not in {MARKER, INDEX} and type(row) is dict
             and set(row) in ({"maxBytes", "required"}, {"maxBytes", "required", "sha256", "bytes"})
             and type(row["required"]) is bool and type(row["maxBytes"]) is int
             and 0 < row["maxBytes"] <= 16 * 1024 * 1024)
        if name in CORE:
            need(row["required"] is True and row["maxBytes"] <= LIMITS[name])
        if "sha256" in row:
            reference({k: row[k] for k in ("sha256", "bytes")}, row["maxBytes"])
    streams = set()
    for row in policy["logDirectories"]:
        need(type(row) is dict and set(row) == {
            "path", "required", "maxParts", "maxPartBytes", "indexMaxBytes"})
        name = relative(row["path"])
        need(name not in streams and type(row["required"]) is bool
             and type(row["maxParts"]) is int and 0 < row["maxParts"] <= 256
             and type(row["maxPartBytes"]) is int and 0 < row["maxPartBytes"] <= 1024 * 1024
             and type(row["indexMaxBytes"]) is int and 0 < row["indexMaxBytes"] <= 256 * 1024)
        need(not any(name == x or name.startswith(x + "/") or x.startswith(name + "/")
                     for x in streams | set(policy["literalFiles"])))
        streams.add(name)
    need(not any(a != b and (a.startswith(b + "/") or b.startswith(a + "/"))
                 for a in policy["literalFiles"] for b in policy["literalFiles"]))
    return policy

def read_relative(directory, name, limit):
    parts = relative(name).split("/")
    opened, current = [], directory
    try:
        for part in parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            opened.append(fd)
            info = os.fstat(fd)
            need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                 and stat.S_IMODE(info.st_mode) == 0o700)
            current = fd
        return read_at(current, parts[-1], limit)
    finally:
        for fd in reversed(opened):
            os.close(fd)

def scan_tree(directory, maximum):
    files, directories = {}, {}
    def walk(fd, prefix):
        initial = signature(os.fstat(fd))
        need(initial[2] == os.geteuid() and stat.S_IMODE(initial[4]) == 0o700)
        directories[prefix] = initial
        need(len(directories) + len(files) <= maximum * 2 + 1)
        for name in os.listdir(fd):
            path = relative(prefix + name)
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            need(info.st_uid == os.geteuid())
            if stat.S_ISDIR(info.st_mode):
                need(stat.S_IMODE(info.st_mode) == 0o700)
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    need(signature(os.fstat(child)) == signature(info))
                    walk(child, path + "/")
                    need(signature(os.stat(name, dir_fd=fd, follow_symlinks=False)) == signature(info))
                finally:
                    os.close(child)
            else:
                need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                     and stat.S_IMODE(info.st_mode) == 0o600)
                files[path] = signature(info)
                need(len(files) <= maximum)
        need(signature(os.fstat(fd)) == initial)
    walk(directory, "")
    return files, directories

def data_limit(name, policy):
    if name in policy["literalFiles"]:
        return policy["literalFiles"][name]["maxBytes"]
    for stream in policy["logDirectories"]:
        prefix = stream["path"] + "/"
        if name.startswith(prefix):
            leaf = name[len(prefix):]
            if leaf == "index.json":
                return stream["indexMaxBytes"]
            match = re.fullmatch(r"part-([0-9]{5})[.]log", leaf)
            need(match is not None and 1 <= int(match[1]) <= stream["maxParts"])
            return stream["maxPartBytes"]
    raise PublicationError("PUBLICATION_ERROR")

def inspect_publication(stage, run_id, context_sha256, policy):
    policy = validate_policy(policy)
    need(type(run_id) is str and re.fullmatch(r"[a-z0-9][a-z0-9-]{7,79}", run_id))
    need(type(context_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", context_sha256))
    need(stage.is_absolute() and stage == Path(os.path.normpath(stage))
         and stage.name in {"diagnostic-results", "public-debug"} and stage.parent.name == run_id)
    current = Path(stage.anchor)
    for part in stage.parts[1:]:
        current /= part
        need(not current.is_symlink())
    if not stage.exists():
        return {"state": "WAIT"}
    before = stage.lstat()
    need(stat.S_ISDIR(before.st_mode) and before.st_uid == os.geteuid()
         and stat.S_IMODE(before.st_mode) == 0o700)
    directory = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        need(signature(os.fstat(directory)) == signature(before))
        try:
            raw, marker_signature = read_at(directory, MARKER, 64 * 1024)
        except FileNotFoundError:
            return {"state": "WAIT"}
        marker = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        need(type(marker) is dict and set(marker) == {
            "schemaVersion", "state", "runId", "contextSha256", "generation", "checkedEpochMs", "artifacts"})
        need(type(marker["schemaVersion"]) is int and marker["schemaVersion"] == 1
             and marker["state"] in {"DEBUG_HOLD", "TERMINAL"}
             and marker["runId"] == run_id and marker["contextSha256"] == context_sha256
             and type(marker["generation"]) is int and marker["generation"] >= 1
             and type(marker["checkedEpochMs"]) is int and marker["checkedEpochMs"] > 0
             and type(marker["artifacts"]) is dict and set(marker["artifacts"]) == CORE | {INDEX})
        for name, row in marker["artifacts"].items():
            reference(row, 256 * 1024 if name == INDEX else LIMITS[name])
        index_raw, index_signature = read_at(directory, INDEX, 256 * 1024)
        need(len(index_raw) == marker["artifacts"][INDEX]["bytes"]
             and hashlib.sha256(index_raw).hexdigest() == marker["artifacts"][INDEX]["sha256"])
        index = json.loads(index_raw.decode("utf-8"), object_pairs_hook=unique)
        need(type(index) is dict and set(index) == {
            "schemaVersion", "runId", "contextSha256", "generation", "files"}
             and type(index["schemaVersion"]) is int and index["schemaVersion"] == 1
             and index["runId"] == run_id and index["contextSha256"] == context_sha256
             and type(index["generation"]) is int and index["generation"] == marker["generation"]
             and type(index["files"]) is list and 3 <= len(index["files"]) <= policy["maxFiles"] - 2)
        refs = {}
        for row in index["files"]:
            need(type(row) is dict and set(row) == {"path", "sha256", "bytes"})
            name = relative(row["path"])
            need(name not in refs and name not in {MARKER, INDEX})
            ref = reference({k: row[k] for k in ("sha256", "bytes")}, data_limit(name, policy))
            refs[name] = ref
        need({n for n, r in policy["literalFiles"].items() if r["required"]} <= set(refs))
        need(all(marker["artifacts"][n] == refs[n] for n in CORE))
        initial_tree = scan_tree(directory, policy["maxFiles"])
        need(set(initial_tree[0]) == set(refs) | {MARKER, INDEX})
        expected_dirs = {""}
        for name in initial_tree[0]:
            for parent in Path(name).parents:
                if str(parent) != ".": expected_dirs.add(parent.as_posix() + "/")
        need(set(initial_tree[1]) == expected_dirs)
        total = len(raw) + len(index_raw)
        stream_indexes = {}
        for name, ref in refs.items():
            total += ref["bytes"]
            need(total <= policy["maxTotalBytes"])
            body, _sig = read_relative(directory, name, data_limit(name, policy))
            need(len(body) == ref["bytes"] and hashlib.sha256(body).hexdigest() == ref["sha256"])
            literal = policy["literalFiles"].get(name)
            if literal and "sha256" in literal:
                need({k: literal[k] for k in ("sha256", "bytes")} == ref)
            if name.endswith("/index.json"):
                stream_indexes[name] = body
        for stream in policy["logDirectories"]:
            prefix = stream["path"] + "/"
            present = {n[len(prefix):]: r for n, r in refs.items() if n.startswith(prefix)}
            if not present:
                need(not stream["required"])
                continue
            need("index.json" in present)
            recorded = json.loads(stream_indexes[prefix + "index.json"].decode("utf-8"), object_pairs_hook=unique)
            need(type(recorded) is dict and recorded.get("schemaVersion") == 1
                 and recorded.get("scope") == "REDACTED_DIAGNOSTIC_NOT_TEST_ACCEPTANCE"
                 and recorded.get("truncated") is False and recorded.get("originalRetained") is True
                 and recorded.get("privacyAudit") == "passed" and type(recorded.get("parts")) is list
                 and len(recorded["parts"]) <= stream["maxParts"])
            expected_parts = {}
            for number, part in enumerate(recorded["parts"], 1):
                need(type(part) is dict and set(part) == {"name", "sha256", "bytes"}
                     and part["name"] == f"part-{number:05d}.log")
                expected_parts[part["name"]] = reference({k: part[k] for k in ("sha256", "bytes")}, stream["maxPartBytes"])
            need({n: r for n, r in present.items() if n != "index.json"} == expected_parts)
            need(type(recorded.get("publicBytes")) is int
                 and recorded["publicBytes"] == sum(r["bytes"] for r in expected_parts.values()))
            combined = hashlib.sha256()
            for part_name in expected_parts:
                body, _part_sig = read_relative(directory, prefix + part_name, stream["maxPartBytes"])
                combined.update(body)
            need(type(recorded.get("publicSha256")) is str
                 and recorded["publicSha256"] == combined.hexdigest())
        again, current_marker = read_at(directory, MARKER, 64 * 1024)
        index_again, current_index = read_at(directory, INDEX, 256 * 1024)
        need(again == raw and current_marker == marker_signature
             and index_again == index_raw and current_index == index_signature
             and scan_tree(directory, policy["maxFiles"]) == initial_tree
             and signature(stage.lstat()) == signature(os.fstat(directory)) == signature(before))
        refs[INDEX] = marker["artifacts"][INDEX]
        refs[MARKER] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        return {"state": marker["state"], "generation": marker["generation"],
                "contextSha256": context_sha256, "markerSha256": refs[MARKER]["sha256"],
                "artifactIndexSha256": refs[INDEX]["sha256"], "totalBytes": total,
                "archiveFiles": sorted(refs), "artifacts": refs}
    finally:
        os.close(directory)

def private_input(path, expected_sha256, maximum=256 * 1024):
    need(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256))
    need(path.is_absolute() and path.resolve(strict=True) == path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        raw, stamp = read_at(directory, path.name, maximum)
    finally:
        os.close(directory)
    need(hashlib.sha256(raw).hexdigest() == expected_sha256)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique), stamp

def copy_verified_publication(stage, destination, run_id, context_sha256, policy, observed):
    # This source is the already validated SAFE publication only, never private log inputs.
    need(observed.get("state") in {"DEBUG_HOLD", "TERMINAL"})
    need(destination.is_absolute() and destination == Path(os.path.normpath(destination))
         and destination.name == "diagnostic-results" and destination.parent.name == run_id
         and destination.parent.resolve(strict=True) == destination.parent
         and stage != destination)
    parent_stamp = destination.parent.lstat()
    need(stat.S_ISDIR(parent_stamp.st_mode) and parent_stamp.st_uid == os.geteuid()
         and not (stat.S_IMODE(parent_stamp.st_mode) & 0o022))
    source = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        original_tree = scan_tree(source, policy["maxFiles"])
        source_stamp = signature(os.fstat(source))
        need(set(original_tree[0]) == set(observed["archiveFiles"]))
        # Exclusive only. A partial prior copy is retained for diagnosis, never adopted.
        destination.mkdir(mode=0o700)
        destination.chmod(0o700)
        files = observed["artifacts"]
        names = [n for n in observed["archiveFiles"] if n != MARKER] + [MARKER]
        for name in names:
            raw, _stamp = read_relative(source, name, files[name]["bytes"])
            need(len(raw) == files[name]["bytes"]
                 and hashlib.sha256(raw).hexdigest() == files[name]["sha256"])
            target = destination
            parts = relative(name).split("/")
            for part in parts[:-1]:
                target /= part
                try:
                    target.mkdir(mode=0o700)
                except FileExistsError:
                    info = target.lstat()
                    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                         and stat.S_IMODE(info.st_mode) == 0o700)
                else:
                    target.chmod(0o700)
            target /= parts[-1]
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(os.dup(fd), "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(fd)
        need(scan_tree(source, policy["maxFiles"]) == original_tree
             and signature(stage.lstat()) == signature(os.fstat(source)) == source_stamp)
        need(inspect_publication(stage, run_id, context_sha256, policy) == observed)
        copied = inspect_publication(destination, run_id, context_sha256, policy)
        need(copied == observed)
        copied.update(archiveStage=str(destination), archiveCopyVerified=True)
        return copied
    finally:
        os.close(source)

def core_only_snapshot(stage, run_id, context_sha256):
    """A full-publication error may expose only independently verified safe core files."""
    need(stage.is_absolute() and stage.resolve(strict=True) == stage
         and stage.name == "public-debug" and stage.parent.name == run_id)
    info = stage.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
         and stat.S_IMODE(info.st_mode) == 0o700)
    directory = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        raw, stamp = read_at(directory, MARKER, 64 * 1024)
        marker = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
        need(type(marker) is dict and set(marker) == {"schemaVersion", "state", "runId",
            "contextSha256", "generation", "checkedEpochMs", "artifacts"})
        need(type(marker["schemaVersion"]) is int and marker["schemaVersion"] == 1
             and marker["state"] == "DEBUG_HOLD" and marker["runId"] == run_id
             and marker["contextSha256"] == context_sha256
             and type(marker["generation"]) is int and marker["generation"] >= 1
             and type(marker["checkedEpochMs"]) is int and marker["checkedEpochMs"] > 0
             and type(marker["artifacts"]) is dict and set(marker["artifacts"]) == CORE | {INDEX})
        files = {}
        identities = {}
        for name in sorted(CORE):
            ref = reference(marker["artifacts"][name], LIMITS[name])
            body, pin = read_at(directory, name, LIMITS[name])
            need(len(body) == ref["bytes"] and hashlib.sha256(body).hexdigest() == ref["sha256"])
            files[name] = body
            identities[name] = pin
        again, after = read_at(directory, MARKER, 64 * 1024)
        need(raw == again and stamp == after and signature(stage.lstat()) == signature(info))
        for name in CORE:
            need(signature(os.stat(name, dir_fd=directory, follow_symlinks=False)) == identities[name])
        return marker, files
    finally:
        os.close(directory)

def copy_core_only(stage, destination, run_id, context_sha256):
    marker, files = core_only_snapshot(stage, run_id, context_sha256)
    need(destination.is_absolute() and destination == Path(os.path.normpath(destination))
         and destination.name == "diagnostic-results" and destination.parent.name == run_id
         and destination.parent.resolve(strict=True) == destination.parent and stage != destination)
    parent = destination.parent.stat()
    need(parent.st_uid == os.geteuid() and not (stat.S_IMODE(parent.st_mode) & 0o022))
    destination.mkdir(mode=0o700)
    destination.chmod(0o700)
    refs = {}
    for name, body in files.items():
        fd = os.open(destination/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        refs[name] = {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    again, contents = core_only_snapshot(stage, run_id, context_sha256)
    need(marker == again and files == contents)
    directory = os.open(destination, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        need(set(os.listdir(directory)) == CORE)
        for name, body in files.items():
            observed, _stamp = read_at(directory, name, LIMITS[name])
            need(observed == body)
    finally:
        os.close(directory)
    return {"state": "PUBLICATION_ERROR", "generation": marker["generation"],
            "contextSha256": context_sha256, "fullLogPublicationVerified": False,
            "mandatoryOnlyCopyVerified": True, "archiveStage": str(destination),
            "archiveFiles": sorted(CORE), "artifacts": refs}

def progress_projection(private_root, module_ids, after_sequence):
    """Read a complete prefix of the producer's safe stream, never raw private logs."""
    need(type(after_sequence) is int and after_sequence >= 0
         and type(module_ids) is list and all(type(x) is str for x in module_ids))
    if not private_root.exists():
        return {"progress": [], "lastSequence": after_sequence, "progressPending": False}
    need(private_root.resolve(strict=True) == private_root)
    info = private_root.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
         and stat.S_IMODE(info.st_mode) == 0o700)
    directory = os.open(private_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fd = os.open("events.private.jsonl", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            return {"progress": [], "lastSequence": after_sequence, "progressPending": False}
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
                 and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600
                 and 0 <= before.st_size <= LIMITS["diagnostic-events.safe.jsonl"])
            raw = os.pread(fd, before.st_size, 0)
            after = os.fstat(fd)
            need(len(raw) == before.st_size and after.st_size >= before.st_size
                 and signature(before)[:6] == signature(after)[:6]
                 and os.pread(fd, before.st_size, 0) == raw
                 and signature(os.stat("events.private.jsonl", dir_fd=directory, follow_symlinks=False))[:6]
                     == signature(before)[:6])
        finally:
            os.close(fd)
    finally:
        os.close(directory)
    # A current append without newline is withheld, never invented or repaired.
    lines = raw.splitlines(keepends=True)
    if lines and not lines[-1].endswith(b"\n"):
        lines.pop()
    events, sequence = [], 0
    for line in lines:
        row = json.loads(line.decode("utf-8"), object_pairs_hook=unique)
        need(type(row) is dict and type(row.get("schemaVersion")) is int and row["schemaVersion"] == 1
             and type(row.get("sequence")) is int and row["sequence"] == sequence + 1
             and type(row.get("epochMs")) is int and row["epochMs"] > 0
             and row.get("phase") in {"nativePrerequisite", "module", "adapter", "debugHold", "terminal"}
             and row.get("event") in {"begin", "end", "error", "observation", "hold", "terminal"})
        sequence = row["sequence"]
        if "moduleId" in row:
            need(row["moduleId"] in module_ids)
        if sequence > after_sequence and len(events) < 1024:
            item = {k: row[k] for k in ("sequence", "epochMs", "phase", "event")}
            if "moduleId" in row: item["moduleId"] = row["moduleId"]
            events.append(item)
    last = events[-1]["sequence"] if events else after_sequence
    return {"progress": events, "lastSequence": last, "progressPending": sequence > last}

def observe_debug_config(config_path, config_sha256, expected_run_id, archive_stage=None, after_sequence=None):
    config, config_stamp = private_input(config_path, config_sha256)
    need(type(config) is dict and type(config.get("schemaVersion")) is int
         and config["schemaVersion"] == 1 and config.get("enabled") is True
         and config.get("runId") == expected_run_id)
    private_root = Path(config["privateRoot"])
    need(private_root.is_absolute() and private_root.name == "debug-private"
         and private_root.parent.name == expected_run_id)
    stage = Path(config["publicStage"])
    need(stage == private_root.parent / "public-debug")
    ref = config["publicationPolicy"]
    need(type(ref) is dict and set(ref) == {"path", "sha256"})
    policy_path = Path(ref["path"])
    policy, policy_stamp = private_input(policy_path, ref["sha256"])
    try:
        result = inspect_publication(stage, expected_run_id, config_sha256, policy)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        if archive_stage is None:
            core_only_snapshot(stage, expected_run_id, config_sha256)
            result = {"state": "PUBLICATION_ERROR", "fullLogPublicationVerified": False}
        else:
            result = copy_core_only(stage, archive_stage, expected_run_id, config_sha256)
    else:
        if result["state"] != "WAIT" and archive_stage is not None:
            result = copy_verified_publication(stage, archive_stage, expected_run_id, config_sha256, policy, result)
    if result["state"] == "WAIT" and (private_root / "HOLD.private.json").exists():
        result = {"state": "PUBLICATION_ERROR", "fullLogPublicationVerified": False}
    if after_sequence is not None:
        result.update(progress_projection(private_root, config.get("moduleIds"), after_sequence))
    again, stamp = private_input(config_path, config_sha256)
    policy_again, policy_after = private_input(policy_path, ref["sha256"])
    need(again == config and stamp == config_stamp and policy_again == policy and policy_after == policy_stamp)
    return result

def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--debug-config", type=Path, required=True)
    parser.add_argument("--debug-config-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--archive-stage", type=Path)
    parser.add_argument("--after-sequence", type=int)
    args = parser.parse_args()
    try:
        result = observe_debug_config(args.debug_config, args.debug_config_sha256,
                                      args.run_id, args.archive_stage, args.after_sequence)
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        print(json.dumps({"state": "PUBLICATION_ERROR"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 2 if result["state"] == "PUBLICATION_ERROR" else 0

if __name__ == "__main__":
    raise SystemExit(main())
