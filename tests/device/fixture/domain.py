#!/usr/bin/env python3
"""Own an ephemeral domain-server and assignment-client E2E fixture."""

from __future__ import annotations

import argparse
import hashlib
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixture.collaboration_broker import CollaborationBroker
from fixture.owned_processes import OwnedProcesses
from fixture.messages_mixer import MessagesMixer
from fixture.create_permissions import CreatePermissions, STANDARD, OVERRIDES, permission_request
from fixture.assets_permissions import AssetsPermissions, WRITE
from fixture.assets_originals import AssetsOriginals
from adapters.normal_feature_state import PrivateFeatureState, need


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
MANIFEST_PATH = ROOT / "domain-manifest.json"
MARKER = re.compile(r"OVERTE_E2E_DOMAIN_[A-Z]+(?![A-Z_])")
HOST = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$")


def validate_domain_fixture() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1:
        raise ValueError("unsupported domain fixture schema")
    expected = {
        "schemaVersion", "bootstrapScript", "expectedEntityCount", "requiredMarkers",
        "spawnPath", "spawnPosition", "minimumFloorThickness", "externalResources",
        "peerDisplayName", "peerScript",
    }
    if set(manifest) != expected:
        raise ValueError("domain fixture manifest contains unsupported fields")
    script_name = manifest.get("bootstrapScript")
    if (not isinstance(script_name, str) or Path(script_name).name != script_name
            or not script_name.endswith(".js")):
        raise ValueError("domain fixture bootstrap script is invalid")
    script_path = ROOT / script_name
    script = script_path.read_text(encoding="utf-8")
    markers = manifest.get("requiredMarkers")
    if (not isinstance(markers, list) or not markers
            or markers != sorted(set(markers))
            or not all(isinstance(item, str) and MARKER.fullmatch(item) for item in markers)):
        raise ValueError("domain fixture markers must be a sorted unique allowlist")
    if sorted(set(MARKER.findall(script))) != markers:
        raise ValueError("domain bootstrap marker set does not match its manifest")
    if manifest.get("expectedEntityCount") != len(markers):
        raise ValueError("domain fixture entity count does not match its markers")
    spawn = manifest.get("spawnPosition")
    if (not isinstance(spawn, dict) or set(spawn) != {"x", "y", "z"}
            or not all(isinstance(spawn[axis], (int, float)) and not isinstance(spawn[axis], bool)
                       for axis in ("x", "y", "z"))
            # AddressManager coordinates denote feet. The fixed floor ends at
            # y=0; a two-metre gap cannot satisfy Phone's nearby support ray.
            or spawn["y"] != 0.0 or abs(spawn["x"]) >= 9.0 or abs(spawn["z"]) >= 9.0):
        raise ValueError("domain fixture spawn feet must be on its known floor surface")
    expected_path = f"/{spawn['x']},{spawn['y']},{spawn['z']}/0,0,0,1"
    if manifest.get("spawnPath") != expected_path:
        raise ValueError("domain fixture spawn path and position disagree")
    if (not isinstance(manifest.get("minimumFloorThickness"), (int, float))
            or manifest["minimumFloorThickness"] < 0.5
            or manifest.get("externalResources") is not False):
        raise ValueError("domain fixture must be local and use a thick floor")
    if "Entities.addEntity(properties, \"domain\")" not in script:
        raise ValueError("domain bootstrap must create domain entities")
    if "Entities.serversExist() || !Entities.canRez()" not in script:
        raise ValueError("domain bootstrap must wait for entity server permissions")
    peer_name = manifest.get("peerScript")
    peer_path = ROOT / peer_name if isinstance(peer_name, str) else ROOT
    peer_script = peer_path.read_text(encoding="utf-8") if peer_path.is_file() else ""
    if (not isinstance(peer_name, str) or Path(peer_name).name != peer_name
            or not peer_name.endswith(".js")
            or manifest.get("peerDisplayName") != "OVERTE_E2E_PEER"
            or "Agent.isAvatar = true" not in peer_script
            or 'Avatar.displayName = "OVERTE_E2E_PEER"' not in peer_script
            or "Script.update.connect" not in peer_script):
        raise ValueError("domain controlled peer script is invalid")
    return manifest


class DomainControlHandler(BaseHTTPRequestHandler):
    debug_hold = None

    token = ""
    transition = None
    collaboration = None
    mixer = None
    create_permissions = None
    assets_permissions = None
    assets_originals = None
    assets_original_tokens = ()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.debug_hold is None:
            return self._get()
        with self.debug_hold.lock:
            if self.debug_hold.active.is_set():
                self.send_error(503, "failed domain is held for diagnostics")
                return
            return self._get()

    def _get(self) -> None:
        if self.path not in {"/v1/collaboration-state", "/v1/messages-mixer-state"} or self.headers.get("X-Overte-E2E-Token") != self.token:
            self.send_error(404)
            return
        try:
            actual = self.mixer(None) if self.path == "/v1/messages-mixer-state" else self.collaboration.state()
            payload = (json.dumps(actual, sort_keys=True) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (RuntimeError, OSError):
            self.send_error(503, "independent actor is not ready")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.debug_hold is None:
            return self._post()
        with self.debug_hold.lock:
            if self.debug_hold.active.is_set():
                self.send_error(503, "failed domain is held for diagnostics")
                return
            return self._post()

    def _post(self) -> None:
        if self.path == "/v1/assets-originals":
            if self.assets_originals is None or self.headers.get("X-Overte-E2E-Token") not in self.assets_original_tokens:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 512:
                    raise ValueError("invalid originals request length")
                command = json.loads(self.rfile.read(length))
                result = self.assets_originals(command)
                payload = (json.dumps(result, sort_keys=True) + "\n").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (RuntimeError, OSError, ValueError):
                self.send_error(503, "owned Assets originals are unavailable")
            return
        if self.path not in {"/v1/domain-state", "/v1/collaboration-edit", "/v1/messages-mixer-state", "/v1/create-permissions", "/v1/assets-permissions"} or self.headers.get(
                "X-Overte-E2E-Token") != self.token:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 512:
                raise ValueError("invalid request length")
            command = json.loads(self.rfile.read(length))
            if self.path in {"/v1/create-permissions", "/v1/assets-permissions"}:
                permission = self.create_permissions if self.path == "/v1/create-permissions" else self.assets_permissions
                if permission is None:
                    raise RuntimeError("owned feature permissions are not enabled")
                result = permission(command)
                payload = (json.dumps(result, sort_keys=True) + "\n").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path == "/v1/collaboration-edit":
                result = self.collaboration.submit(command)
                payload = (json.dumps(result, sort_keys=True) + "\n").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if (not isinstance(command, dict)
                    or set(command) != {"action", "schemaVersion"}
                    or command.get("schemaVersion") != 1
                    or command.get("action") not in {"offline", "online"}):
                raise ValueError("invalid domain control command")
            if self.path == "/v1/messages-mixer-state":
                if type(command["schemaVersion"]) is not int:
                    raise ValueError("invalid mixer control version")
                result = self.mixer(command["action"])
            else:
                result = self.transition(command["action"])
            payload = (json.dumps(result, sort_keys=True) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            self.send_error(400, str(error))
        except (OSError, RuntimeError) as error:
            import traceback
            print("domain-fixture-control-error:", type(error).__name__, [(Path(frame.filename).name, frame.lineno) for frame in traceback.extract_tb(error.__traceback__)], file=sys.stderr)
            self.send_error(503, "controlled stack transition failed")

    def log_message(self, format_string: str, *arguments: object) -> None:
        print("domain-fixture-control: " + format_string % arguments, file=sys.stderr)


class DomainResourceHandler(SimpleHTTPRequestHandler):
    script_paths: set[str] = set()
    content_ready = threading.Event()
    expected_marker_count = 0
    peer_state_path = None
    collaboration = None

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        if path == "/actor-command":
            payload = (json.dumps(self.collaboration.command(), sort_keys=True) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path == "/healthz":
            payload = b'{"ready":true,"schemaVersion":1}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path not in self.script_paths:
            self.send_error(404)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/actor-state":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 512:
                    raise ValueError("invalid actor observation size")
                self.collaboration.report(json.loads(self.rfile.read(length)))
                self.send_response(204)
                self.end_headers()
            except (ValueError, TypeError):
                self.send_error(400, "invalid independent actor observation")
            return
        if self.path == "/peer-state":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 256:
                    raise ValueError("invalid peer telemetry size")
                payload = json.loads(self.rfile.read(length))
                if (set(payload) != {"schemaVersion", "avatarEnabled", "displayName", "updates"}
                        or payload["schemaVersion"] != 1 or type(payload["avatarEnabled"]) is not bool
                        or payload["displayName"] != "OVERTE_E2E_PEER"
                        or type(payload["updates"]) is not int or payload["updates"] < 0):
                    raise ValueError("invalid controlled peer telemetry")
                atomic_json(self.peer_state_path, payload)
                self.send_response(204)
                self.end_headers()
            except (ValueError, TypeError):
                self.send_error(400, "invalid controlled peer telemetry")
            return
        if self.path != "/domain-ready":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 1 <= length <= 256:
                raise ValueError("invalid readiness payload length")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self.send_error(400)
            return
        if payload != {
                "schemaVersion": 1,
                "markerCount": self.expected_marker_count,
        }:
            self.send_error(400)
            return
        self.content_ready.set()
        self.send_response(204)
        self.end_headers()

    def log_message(self, format_string: str, *arguments: object) -> None:
        print("domain-fixture-http: " + format_string % arguments, file=sys.stderr)


def executable(value: str | None, label: str) -> Path:
    if not value:
        raise ValueError(f"{label} is required")
    path = Path(value).expanduser().resolve()
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(f"{label} must be an executable regular file")
    return path


def private_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == REPOSITORY or REPOSITORY in resolved.parents:
        raise ValueError("domain fixture output must be outside the source worktree")
    if resolved.exists() and (not resolved.is_dir() or any(resolved.iterdir())):
        raise ValueError("domain fixture output must be absent or empty")
    resolved.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(resolved, 0o700)
    return resolved


def process_options(environment: dict[str, str], log) -> dict:
    options = {"env": environment, "stdin": subprocess.DEVNULL,
               "stdout": log, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return options


def stop_process(process: subprocess.Popen | None, grace_seconds: int = 5) -> None:
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=10, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=grace_seconds)


def wait_for_domain(process: subprocess.Popen, url: str, timeout_seconds: int, memory_check=None) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_error = "domain HTTP endpoint was unavailable"
    while time.monotonic() < deadline:
        if memory_check is not None: memory_check("startup")
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"domain-server exited before becoming ready (exit code {exit_code})")
        try:
            with urlopen(url, timeout=1) as response:
                value = response.read(128).decode("ascii").strip()
            return str(uuid.UUID(value))
        except (OSError, UnicodeError, ValueError) as error:
            last_error = str(error)
            time.sleep(0.1)
    raise RuntimeError(f"domain-server readiness timed out: {last_error}")


def wait_for_assignment_content(processes: tuple[subprocess.Popen, ...],
                                timeout_seconds: int,
                                stopping: threading.Event, memory_check=None) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if memory_check is not None: memory_check("startup")
        if DomainResourceHandler.content_ready.is_set():
            return
        if stopping.is_set():
            raise RuntimeError("domain fixture stopped before content became ready")
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("domain fixture process exited before content became ready")
        time.sleep(0.1)
    raise RuntimeError("assignment-owned domain content did not become ready")


class DomainDebugHold:
    """Opt-in failed-state preservation; the sole release authorizes cleanup only."""

    def __init__(self, output: Path):
        self.lock = threading.RLock()
        self.active = threading.Event()
        self.processes = {}
        self.directory = output / "debug-hold"
        self.directory.mkdir(mode=0o700)
        self.fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(self.fd)
        self.directory_identity = (info.st_dev, info.st_ino)
        self.nonce = secrets.token_hex(16)
        self.context = {"schemaVersion": 1, "controller": self.process_birth(os.getpid()),
                        "sourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        "outputPathSha256": hashlib.sha256(str(output).encode()).hexdigest()}
        self.context_sha256 = hashlib.sha256(json.dumps(self.context, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        self.ready = None
        self.released = False
        self.original_error = None
        self.memory_guard = None
        self.write("OWNER.private.json", {"schemaVersion": 1, "context": self.context,
            "contextSha256": self.context_sha256, "nonce": self.nonce})

    @staticmethod
    def process_birth(pid, memory=False):
        descriptor = os.open(f"/proc/{pid}", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            def fields():
                with os.fdopen(os.open("stat", os.O_RDONLY | os.O_NOFOLLOW,
                                       dir_fd=descriptor)) as stream:
                    return stream.read().rsplit(")", 1)[1].split()
            before = fields()
            uid = os.fstat(descriptor).st_uid
            def proc_text(name):
                with os.fdopen(os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=descriptor)) as stream:
                    return stream.read(4097)
            cgroup = proc_text("cgroup")
            rss = int(proc_text("statm").split()[1])*os.sysconf("SC_PAGE_SIZE") if memory else None
            after = fields()
            if before[19] != after[19] or uid != os.geteuid() or cgroup != proc_text("cgroup"):
                raise RuntimeError("DOMAIN_DEBUG_PROCESS_IDENTITY_CHANGED")
            return {"pid": pid, "birth": before[19], "uid": uid,
                    "pgid": int(before[2]), "parentPid": int(before[1]),
                    "state": after[0], "cgroup": cgroup, **({"rssBytes":rss} if memory else {})}
        finally:
            os.close(descriptor)

    def register(self, process, role):
        identity = self.process_birth(process.pid)
        if identity["parentPid"] != os.getpid() or identity["pgid"] != process.pid:
            raise RuntimeError("DOMAIN_DEBUG_CHILD_NOT_OWNED")
        self.processes[process] = {"role": role, **identity}

    def check_directory(self):
        actual = self.directory.lstat()
        if (self.directory.resolve() != self.directory or
                (actual.st_dev, actual.st_ino) != self.directory_identity or
                actual.st_uid != os.geteuid() or stat.S_IMODE(actual.st_mode) != 0o700):
            raise RuntimeError("DOMAIN_DEBUG_DIRECTORY_CHANGED")

    def write(self, name, value):
        self.check_directory()
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.fd)
        os.fchmod(descriptor,0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(self.fd)

    @staticmethod
    def signature(info):
        return (info.st_dev, info.st_ino, info.st_uid, info.st_mode, info.st_nlink,
                info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def pin_ready(self, path):
        if path is None:
            return
        path = path.resolve()
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            before = os.fstat(stream.fileno())
            body = stream.read(65537)
            after = os.fstat(stream.fileno())
        if (len(body) > 65536 or self.signature(before) != self.signature(after)
                or self.signature(after) != self.signature(path.lstat())
                or after.st_uid != os.geteuid() or not stat.S_ISREG(after.st_mode)):
            raise RuntimeError("DOMAIN_DEBUG_READY_CHANGED")
        self.ready = (path, self.signature(after), body)

    def begin(self, code, processes, error=None, details=None):
        # Called under the same lock as control mutations and monitoring.
        self.active.set()
        self.original_error = error
        if self.memory_guard is not None and not (details or {}).get("freezeComplete"):
            details = dict(details or {})
            try:
                try: details["memory"] = self.memory_guard.sample("on-hold")
                except (OSError,ValueError,RuntimeError): details["memoryObservationRejected"] = True
                details.update(frozenProcesses=self.memory_guard.freeze(),freezeComplete=True)
            except (OSError,ValueError,RuntimeError):
                details.update(freezeComplete=False,freezeRejected=True)
        try:
            snapshot = [{**self.processes[p], "identityObservation": "AT_OWN_POPEN_SPAWN",
                         "returncodeObservation": "ACTUAL_POPEN_POLL_AT_FAILURE",
                         "returncode": p.poll()} for p in processes]
            self.write("FAILURE.private.json", {"schemaVersion": 1,
                "status": "FAILED_DOMAIN_DEBUG_HOLD", "failureCode": code,
                "exceptionClass": type(error).__name__ if error is not None else "RuntimeError", "observedEpochNs": time.time_ns(),
                "contextSha256": self.context_sha256, "processes": snapshot,
                "currentReadyHealthy": False, "cleanupAttempted": False,
            **({"details":details} if details is not None else {})})
            if self.ready is not None:
                path, signature, body = self.ready
                self.write("READY_BEFORE_FAILURE.private.json", json.loads(body))
                if self.signature(path.lstat()) != signature or path.read_bytes() != body:
                    raise RuntimeError("DOMAIN_DEBUG_READY_CHANGED")
                path.unlink()
        except (OSError, ValueError, RuntimeError, KeyError):
            # Recording failure cannot release resources or replace the original child-exit error.
            print("DOMAIN_DEBUG_HOLD_RECORDING_ERROR", flush=True)
        print("DOMAIN_DEBUG_HOLD_ACTIVE", flush=True)

    def release_requested(self):
        self.check_directory()
        try:
            descriptor = os.open("RELEASE_REQUEST.private.json", os.O_RDONLY | os.O_NOFOLLOW |
                                 os.O_NONBLOCK, dir_fd=self.fd)
        except FileNotFoundError:
            return False
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                    or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o600
                    or before.st_size > 1024):
                raise ValueError("DOMAIN_DEBUG_RELEASE_NOT_PRIVATE")
            raw = stream.read(1025)
            after = os.fstat(stream.fileno())
        path = os.stat("RELEASE_REQUEST.private.json", dir_fd=self.fd, follow_symlinks=False)
        if self.signature(before) != self.signature(after) or self.signature(after) != self.signature(path):
            raise ValueError("DOMAIN_DEBUG_RELEASE_CHANGED")
        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError("DOMAIN_DEBUG_RELEASE_DUPLICATE")
                value[key] = item
            return value
        request = json.loads(raw, object_pairs_hook=pairs)
        if (type(request) is not dict or set(request) != {"schemaVersion", "action", "contextSha256", "nonce"}
                or type(request["schemaVersion"]) is not int or request["schemaVersion"] != 1
                or request["action"] != "cleanup" or type(request["nonce"]) is not str
                or type(request["contextSha256"]) is not str
                or not secrets.compare_digest(request["nonce"], self.nonce)
                or not secrets.compare_digest(request["contextSha256"], self.context_sha256)):
            raise ValueError("DOMAIN_DEBUG_RELEASE_CONTEXT_REJECTED")
        if self.memory_guard is not None:
            self.memory_guard.resume()
        self.write("RELEASE_ACCEPTED.private.json", {"schemaVersion": 1,
            "contextSha256": self.context_sha256, "requestSha256": hashlib.sha256(raw).hexdigest(),
            "observedEpochNs": time.time_ns(), "action": "cleanup"})
        self.released = True
        return True

    def wait_release(self):
        # Signals do not authorize cleanup of an intentionally held failure.
        # SIGKILL cannot be prevented and is never reported as successful cleanup.
        last_error = None
        while True:
            try:
                if self.release_requested():
                    return
            except (OSError, ValueError, RuntimeError) as error:
                code = type(error).__name__
                if code != last_error:
                    print("DOMAIN_DEBUG_RELEASE_REJECTED", flush=True)
                    last_error = code
            time.sleep(0.1)


class DomainMemoryGuard:
    """Read own cgroup counters; preserve only proven owned workers on pressure."""

    def __init__(self, hold, expected_limit, cgroup=None):
        self.hold = hold
        self.stopped = []
        self.timeline = None
        self.last = None
        hold.memory_guard = self
        self.cgroup = self.resolve_cgroup() if cgroup is None else cgroup
        self.identity = self.cgroup.stat().st_dev, self.cgroup.stat().st_ino
        self.expected_limit = expected_limit
        self.next_sample = 0.0
        self.timeline = os.open("MEMORY_TIMELINE.private.jsonl", os.O_WRONLY | os.O_APPEND |
                                os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=hold.fd)
        os.fchmod(self.timeline,0o600)
        self.check("pre-launch", force=True)

    @staticmethod
    def resolve_cgroup(group_text=None, mountinfo=None):
        # Optional text seams exist only for host counters; CLI never accepts a path override.
        group_text = Path("/proc/self/cgroup").read_text() if group_text is None else group_text
        mountinfo = Path("/proc/self/mountinfo").read_text() if mountinfo is None else mountinfo
        groups = [line[3:] for line in group_text.splitlines() if line.startswith("0::")]
        if len(groups)!=1 or not groups[0].startswith("/") or ".." in Path(groups[0]).parts:
            raise RuntimeError("DOMAIN_MEMORY_OWN_CGROUP_UNPROVEN")
        group = Path(groups[0]);candidates = set()
        for line in mountinfo.splitlines():
            left, separator, right = line.partition(" - ")
            if not separator or right.split()[0] != "cgroup2":
                continue
            fields = left.split()
            decode = lambda s: re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), s)
            root, mounted = Path(decode(fields[3])), Path(decode(fields[4]))
            possible = [mounted]  # Handles a private cgroup-namespace root.
            if group.is_relative_to(root):
                possible.append(mounted / group.relative_to(root))
            for path in possible:
                if path.resolve() == path and (path / "cgroup.procs").is_file():
                    pids = (path / "cgroup.procs").read_text().split()
                    if str(os.getpid()) in pids: candidates.add(path)
        if len(candidates) != 1:
            raise RuntimeError("DOMAIN_MEMORY_OWN_CGROUP_UNPROVEN")
        return candidates.pop()

    def read_counter(self, name):
        actual = self.cgroup.stat()
        if self.cgroup.resolve() != self.cgroup or (actual.st_dev, actual.st_ino) != self.identity:
            raise RuntimeError("DOMAIN_MEMORY_CGROUP_CHANGED")
        with os.fdopen(os.open(self.cgroup / name, os.O_RDONLY | os.O_NOFOLLOW), "r") as stream:
            before = os.fstat(stream.fileno());text = stream.read(4097);after = os.fstat(stream.fileno())
        if len(text) > 4096 or (before.st_dev,before.st_ino) != (after.st_dev,after.st_ino):
            raise RuntimeError("DOMAIN_MEMORY_COUNTER_CHANGED")
        return text.strip()

    def sample(self, phase):
        if str(os.getpid()) not in self.read_counter("cgroup.procs").split():
            raise RuntimeError("DOMAIN_MEMORY_OWN_CGROUP_UNPROVEN")
        def number(name):
            value = self.read_counter(name)
            if not value.isdecimal():raise RuntimeError("DOMAIN_MEMORY_COUNTER_INVALID")
            return int(value)
        current, limit = number("memory.current"), number("memory.max")
        if limit != self.expected_limit:
            raise RuntimeError("DOMAIN_MEMORY_LIMIT_MISMATCH")
        reserve = max(256 * 1024**2, limit // 10)
        if reserve >= limit:raise RuntimeError("DOMAIN_MEMORY_HEADROOM_POLICY_INVALID")
        events = {}
        for line in self.read_counter("memory.events").splitlines():
            key, value = line.split()
            if re.fullmatch("[a-z_]+",key) is None or key in events or not value.isdecimal():
                raise RuntimeError("DOMAIN_MEMORY_EVENTS_INVALID")
            events[key] = int(value)
        own = []
        for process, pinned in self.hold.processes.items():
            returned = process.poll()
            if returned is not None:
                own.append({**pinned, "returncode": returned, "rssBytes": None});continue
            measured = self.hold.process_birth(process.pid, memory=True)
            if any(measured[k] != pinned[k] for k in ("pid","birth","uid","pgid","cgroup")):
                raise RuntimeError("DOMAIN_MEMORY_WORKER_CHANGED")
            own.append({"role":pinned["role"],**measured,"returncode":None})
        return {"scope":"ACTUAL_OWN_CGROUP_AND_OWN_PROCESS_RSS_NO_DEVICE_VERDICT",
                "phase":phase,"epochNs":time.time_ns(),"monotonicNs":time.monotonic_ns(),
                "currentBytes":current,"maxBytes":limit,"peakBytes":number("memory.peak"),
                "events":events,"ownRssBytes":own,"controller":self.hold.process_birth(os.getpid(), memory=True),
                "reserveBytes":reserve,"thresholdBytes":limit-reserve,
                "headroomPolicy":"max(256MiB,10pct_actual_memory.max)","atomicSnapshotClaimed":False}

    def freeze(self):
        leaders = {}
        for process, pin in self.hold.processes.items():
            if process.poll() is not None:continue
            measured = self.hold.process_birth(process.pid)
            if any(measured[k] != pin[k] for k in ("pid","birth","uid","pgid","cgroup")):
                raise RuntimeError("DOMAIN_MEMORY_FREEZE_OWNER_CHANGED")
            if measured["pgid"] != process.pid or measured["cgroup"] != self.hold.context["controller"]["cgroup"]:
                raise RuntimeError("DOMAIN_MEMORY_FREEZE_SCOPE_UNPROVEN")
            leaders[process.pid] = measured
        def members():
            found = []
            # Only public group metadata is read before selecting known owned PGs.
            for entry in Path("/proc").iterdir():
                if not entry.name.isdecimal():continue
                try:
                    if os.getpgid(int(entry.name)) not in leaders:continue
                    measured = self.hold.process_birth(int(entry.name))
                except (FileNotFoundError,ProcessLookupError):continue
                leader = leaders.get(measured["pgid"])
                if leader is None or measured["uid"] != leader["uid"] or measured["cgroup"] != leader["cgroup"]:
                    raise RuntimeError("DOMAIN_MEMORY_FOREIGN_GROUP_MEMBER")
                found.append(measured)
            if not set(leaders) <= {v["pid"] for v in found} or len(found)>256:
                raise RuntimeError("DOMAIN_MEMORY_GROUP_CHANGED")
            return found
        planned = members()
        for attempt in range(4):
            planned.sort(key=lambda pin:pin["pid"] not in leaders)
            already = {pin["pid"] for descriptor,pin in self.stopped}
            for pin in planned:
                if pin["pid"] in already:continue
                descriptor = os.pidfd_open(pin["pid"])
                try:
                    actual = self.hold.process_birth(pin["pid"])
                    if any(actual[k] != pin[k] for k in ("pid","birth","uid","pgid","cgroup")):
                        raise RuntimeError("DOMAIN_MEMORY_FREEZE_PID_CHANGED")
                    signal.pidfd_send_signal(descriptor,signal.SIGSTOP)
                    self.stopped.append((descriptor,pin));descriptor=None
                finally:
                    if descriptor is not None:os.close(descriptor)
            deadline = time.monotonic()+1
            while any(self.hold.process_birth(pin["pid"])["state"] not in ("T","t") for fd,pin in self.stopped):
                if time.monotonic()>=deadline:raise RuntimeError("DOMAIN_MEMORY_STOP_NOT_OBSERVED")
                time.sleep(.01)
            planned = members()
            if {v["pid"] for v in planned} <= {pin["pid"] for fd,pin in self.stopped}:
                return [{**pin,"stopObserved":True} for fd,pin in self.stopped]
        raise RuntimeError("DOMAIN_MEMORY_GROUP_DID_NOT_STABILIZE")

    def resume(self):
        for descriptor,pin in self.stopped:
            try:actual = self.hold.process_birth(pin["pid"])
            except (FileNotFoundError,ProcessLookupError):continue
            if any(actual[k] != pin[k] for k in ("pid","birth","uid","pgid","cgroup")):
                raise RuntimeError("DOMAIN_MEMORY_RESUME_OWNER_CHANGED")
            signal.pidfd_send_signal(descriptor,signal.SIGCONT)
        for descriptor,pin in self.stopped:os.close(descriptor)
        self.stopped = []

    def check(self, phase="periodic", force=False):
        if not force and time.monotonic() < self.next_sample:return
        self.next_sample = time.monotonic()+1
        self.last = self.sample(phase)
        def append():
            raw=(json.dumps(self.last,sort_keys=True)+"\n").encode()
            if os.fstat(self.timeline).st_size+len(raw)>8*1024**2:
                raise RuntimeError("DOMAIN_MEMORY_TIMELINE_LIMIT")
            while raw:
                written=os.write(self.timeline,raw)
                if written<=0:raise RuntimeError("DOMAIN_MEMORY_TIMELINE_WRITE_FAILED")
                raw=raw[written:]
            os.fsync(self.timeline)
        if self.last["currentBytes"]>=self.last["thresholdBytes"]:
            error = RuntimeError("DOMAIN_MEMORY_HEADROOM_LOW")
            details = {"memory":self.last,"freezeComplete":False,"frozenProcesses":[]}
            try:
                # Stop allocations before potentially slow evidence writes/fsync.
                details.update(frozenProcesses=self.freeze(),freezeComplete=True)
                append()
            finally:self.hold.begin("DOMAIN_MEMORY_HEADROOM_LOW",tuple(self.hold.processes),error,details)
            raise error
        append()

    def close(self):
        if self.timeline is not None: os.close(self.timeline)
        for descriptor,pin in self.stopped:os.close(descriptor)


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain-server")
    parser.add_argument("--assignment-client")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--public-host")
    parser.add_argument("--domain-host")
    parser.add_argument("--domain-port", type=int, default=40102)
    parser.add_argument("--http-port", type=int, default=40100)
    parser.add_argument("--script-port", type=int, default=0)
    parser.add_argument("--control-port", type=int, default=0)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--startup-timeout-seconds", type=int, default=30)
    parser.add_argument("--assignment-warmup-seconds", type=float, default=2.0)
    parser.add_argument("--feature-chat-receiver", action="store_true",
                        help="Opt in the dedicated peer to native E2E private Chat IPC; requires an instrumented Assignment Client.")
    parser.add_argument("--feature-create-permissions", action="store_true",
                        help="Opt in owned ephemeral-domain rez control and exact Settings restoration for Create E2E.")
    parser.add_argument("--feature-assets-permissions", action="store_true",
                        help="Opt in owned ephemeral-domain asset-write control and exact Settings restoration for Assets E2E.")
    parser.add_argument("--debug-hold-on-error", action="store_true",
                        help="Linux only: preserve an unexpectedly failed active stack until a private nonce-bound cleanup request.")
    parser.add_argument("--debug-memory-expected-limit-bytes", type=int,
                        help="Opt in own-cgroup memory/RSS sampling and owned-worker pressure freeze; requires debug hold.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name in ("domain_port", "http_port"):
        if not 1 <= getattr(args, name) <= 65535:
            parser.error(f"--{name.replace('_', '-')} must be from 1 through 65535")
    for name in ("script_port", "control_port"):
        if not 0 <= getattr(args, name) <= 65535:
            parser.error(f"--{name.replace('_', '-')} must be from 0 through 65535")
    if args.script_port != 0 and args.script_port == args.http_port:
        parser.error("--script-port and --http-port must differ")
    if args.control_port != 0 and args.control_port in {
            args.domain_port, args.http_port, args.script_port}:
        parser.error("--control-port must differ from all fixture service ports")
    if not 1 <= args.startup_timeout_seconds <= 300:
        parser.error("--startup-timeout-seconds must be from 1 through 300")
    if not 0.0 <= args.assignment_warmup_seconds <= 30.0:
        parser.error("--assignment-warmup-seconds must be from 0 through 30")
    if args.debug_hold_on_error and not sys.platform.startswith("linux"):
        parser.error("--debug-hold-on-error requires Linux process identity")
    if args.debug_memory_expected_limit_bytes is not None and (not args.debug_hold_on_error or args.debug_memory_expected_limit_bytes<=256*1024**2):
        parser.error("memory diagnostics require debug hold and a finite reviewed limit above256MiB")
    return args


def _controller_main(hold_state) -> int:
    args = parse_args()
    manifest = validate_domain_fixture()
    if args.check:
        print(f"PASS: domain fixture defines {manifest['expectedEntityCount']} assignment-owned markers")
        return 0
    domain_server = executable(args.domain_server, "--domain-server")
    assignment_client = executable(args.assignment_client, "--assignment-client")
    if args.output_dir is None:
        raise ValueError("--output-dir is required")
    output = private_output(args.output_dir)
    debug_hold = DomainDebugHold(output) if args.debug_hold_on_error else None
    hold_state.append(debug_hold)
    memory_guard = DomainMemoryGuard(debug_hold,args.debug_memory_expected_limit_bytes) if args.debug_memory_expected_limit_bytes is not None else None
    public_host = args.public_host or args.bind
    if public_host in {"0.0.0.0", "::"}:
        raise ValueError("--public-host is required when binding all interfaces")
    domain_host = args.domain_host or public_host
    for value, label in ((public_host, "--public-host"), (domain_host, "--domain-host")):
        if not HOST.fullmatch(value) or ".." in value:
            raise ValueError(f"{label} must be a DNS name or IPv4 address")

    DomainResourceHandler.script_paths = {
        f"/{manifest['bootstrapScript']}", f"/{manifest['peerScript']}"}
    DomainResourceHandler.expected_marker_count = manifest["expectedEntityCount"]
    DomainResourceHandler.content_ready = threading.Event()
    DomainResourceHandler.peer_state_path = output / "peer-state.json"
    DomainResourceHandler.collaboration = CollaborationBroker()
    DomainControlHandler.collaboration = DomainResourceHandler.collaboration
    handler = partial(DomainResourceHandler, directory=str(ROOT))
    resources = ThreadingHTTPServer((args.bind, args.script_port), handler)
    resource_thread = threading.Thread(target=resources.serve_forever, daemon=True)
    resource_thread.start()
    resource_base = f"http://{public_host}:{resources.server_address[1]}"
    script_url = f"{resource_base}/{manifest['bootstrapScript']}"
    peer_script_url = f"{resource_base}/{manifest['peerScript']}"

    config = {
        "version": 2.2,
        "metaverse": {
            "automatic_networking": "disabled",
            "enable_packet_verification": False,
            "local_port": args.domain_port,
        },
        "paths": {"/": {"viewpoint": manifest["spawnPath"]}},
        "scripts": {"persistent_scripts": [
            {"url": script_url, "num_instances": 1, "pool": "overte-e2e-domain"},
            {"url": peer_script_url, "num_instances": 1, "pool": "overte-e2e-peer"},
        ]},
    }
    config_path = output / "domain-config.json"
    if args.feature_create_permissions or args.feature_assets_permissions:
        config["security"] = {key: [] for key in OVERRIDES}
        config["security"]["standard_permissions"] = [
            dict(permissions_id=name, id_can_connect=True, id_can_rez_avatar_entities=True,
                 id_can_adjust_locks=True, id_can_rez=True, id_can_rez_tmp=True)
            for name in STANDARD]
        if args.feature_assets_permissions:
            for row in config["security"]["standard_permissions"]:
                row[WRITE] = True
    atomic_json(config_path, config)
    runtime = output / "runtime"
    for name in ("config", "data", "cache"):
        (runtime / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    environment = os.environ.copy()
    environment.update({
        "XDG_CONFIG_HOME": str(runtime / "config"),
        "XDG_DATA_HOME": str(runtime / "data"),
        "XDG_CACHE_HOME": str(runtime / "cache"),
        "HIFI_DOMAIN_SERVER_PORT": str(args.domain_port),
        "HIFI_DOMAIN_SERVER_HTTP_PORT": str(args.http_port),
        "OVERTE_DOMAIN_SERVER_WS_PORT": str(args.domain_port),
    })
    owned_processes = OwnedProcesses(environment)

    if debug_hold is None:
        domain_log = (output / "domain-server.log").open("w", encoding="utf-8")
    else:
        descriptor = os.open(output / "domain-server.log",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        os.fchmod(descriptor,0o600)
        domain_log = os.fdopen(descriptor,"w",encoding="utf-8")
    if debug_hold is None:
        assignment_log = (output / "assignment-client.log").open("w", encoding="utf-8")
    else:
        descriptor = os.open(output / "assignment-client.log",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        os.fchmod(descriptor,0o600)
        assignment_log = os.fdopen(descriptor,"w",encoding="utf-8")
    if debug_hold is None:
        assignment_agent_log = (output / "assignment-agent.log").open("w", encoding="utf-8")
    else:
        descriptor = os.open(output / "assignment-agent.log",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        os.fchmod(descriptor,0o600)
        assignment_agent_log = os.fdopen(descriptor,"w",encoding="utf-8")
    (output / "assignment-logs").mkdir(mode=0o700)
    domain_process = None
    assignment_processes: list[subprocess.Popen] = []
    assignment_agent_processes: list[subprocess.Popen] = []
    # Offline/recovery must preserve this fixture's domain identity. The server
    # generates a new UUID on every anonymous startup unless explicitly pinned.
    expected_domain_id = str(uuid.uuid4())
    domain_id = None
    generation = 0
    mixer = None
    create_permissions = None
    assets_permissions = None
    assets_originals = None
    mixer_store = PrivateFeatureState(output / "messages-mixer-intent.json")
    mixer_expected = None
    stack_state = "offline"
    transition_lock = debug_hold.lock if debug_hold is not None else threading.Lock()
    stopping = threading.Event()

    def write_mixer_intent(value):
        nonlocal mixer_expected
        need(mixer_expected is None and mixer_store.read() is None)
        mixer_expected = dict(value)
        mixer_store.write(value, None)

    def clear_mixer_intent():
        nonlocal mixer_expected
        actual = mixer_store.read()
        if actual is not None:
            need(mixer_expected is not None)
            mixer_store.discard(mixer_expected)
        else:
            need(mixer_expected is None or mixer is not None and not mixer.dispatched)
        mixer_expected = None

    def spawn_assignment(assignment_type):
        nonlocal assets_originals
        assignment_environment = environment.copy()
        if args.feature_assets_permissions and assignment_type == "3":
            directory = runtime / f"assets-originals-{generation + 1}"
            directory.mkdir(mode=0o700)
            assignment_environment["OVERTE_E2E_ASSETS_ORIGINALS"] = str(directory)
        else:
            assignment_environment.pop("OVERTE_E2E_ASSETS_ORIGINALS", None)
        process = subprocess.Popen(
            [str(assignment_client), "-t", assignment_type, "-a", "127.0.0.1",
             "--server-port", str(args.domain_port),
             "--disable-domain-port-auto-discovery",
             "--log-directory", str(output / "assignment-logs"),
             "--logOptions", "nocolor,process_id,milliseconds"],
            **process_options(assignment_environment, assignment_log))
        if args.feature_assets_permissions and assignment_type == "3":
            assets_originals = AssetsOriginals(directory, process, owned_processes.matches, domain_id)
        assignment_processes.append(process)
        if debug_hold is not None:
            debug_hold.register(process, "assignment:" + assignment_type)
        return process

    def start_stack() -> None:
        nonlocal domain_process, assignment_processes, assignment_agent_processes
        nonlocal domain_id, generation, stack_state, mixer, create_permissions, assets_permissions
        if stack_state == "online":
            if domain_process is None or any(process.poll() is not None for process in (
                    domain_process, *assignment_processes, *assignment_agent_processes)):
                raise RuntimeError("controlled domain stack is no longer running")
            observed_id = wait_for_domain(
                domain_process, f"http://127.0.0.1:{args.http_port}/id",
                args.startup_timeout_seconds, memory_guard.check if memory_guard is not None else None)
            if observed_id != domain_id:
                raise RuntimeError("controlled domain readiness identity changed")
            return
        # The broker and assignment seed start afresh on each controlled
        # restart. Reusing persisted entities would retain the previous seed
        # and create two identically named shared objects. Preserve the domain
        # identity/configuration while keeping each seed's content isolated.
        content_runtime = runtime / f"stack-{generation + 1}"
        content_runtime.mkdir(mode=0o700)
        for name in ("data", "cache"):
            (content_runtime / name).mkdir(mode=0o700)
        environment.update(XDG_DATA_HOME=str(content_runtime / "data"),
                           XDG_CACHE_HOME=str(content_runtime / "cache"))
        DomainResourceHandler.content_ready.clear()
        DomainResourceHandler.collaboration.reset()
        domain_process = subprocess.Popen(
            [str(domain_server), "-d", expected_domain_id, "--user-config", str(config_path),
             "--logOptions", "nocolor,process_id,milliseconds"],
            **process_options(environment, domain_log))
        if debug_hold is not None:
            debug_hold.register(domain_process, "domain-server")
        observed_id = wait_for_domain(
            domain_process, f"http://127.0.0.1:{args.http_port}/id",
            args.startup_timeout_seconds, memory_guard.check if memory_guard is not None else None)
        if domain_id is not None and observed_id != domain_id:
            if debug_hold is None:
                stop_process(domain_process)
                domain_process = None
            raise RuntimeError("controlled domain identity changed during restart")
        domain_id = observed_id
        if args.feature_create_permissions:
            create_permissions = CreatePermissions(domain_process, owned_processes.matches,
                args.http_port, domain_id, PrivateFeatureState(output / "create-permissions-intent.json"))
        if args.feature_assets_permissions:
            assets_permissions = AssetsPermissions(domain_process, owned_processes.matches,
                args.http_port, domain_id, PrivateFeatureState(output / "assets-permissions-intent.json"))
        mixer_process = None
        for assignment_type in ("0", "1", "3", "4", "5", "6"):
            process = spawn_assignment(assignment_type)
            if assignment_type == "4":
                mixer_process = process
        if sys.platform.startswith("linux"):
            need(mixer_store.read() is None and mixer_expected is None)
            mixer = MessagesMixer(mixer_process, owned_processes.matches,
                                  lambda: spawn_assignment("4"),
                                  write_mixer_intent, clear_mixer_intent, mixer_store.read)
        for pool in ("overte-e2e-domain", "overte-e2e-peer"):
            actor_options = []
            if args.feature_chat_receiver and pool == "overte-e2e-peer":
                # A fresh private directory per actual stack birth. The native
                # actor exclusively creates its original source/result files.
                actor_root = content_runtime / "chat-peer"
                actor_root.mkdir(mode=0o700)
                actor_options = ["--testScript", "--e2eChatActorDir", str(actor_root)]
                atomic_json(output / "chat-actor-config.json", {
                    "actorFilesVersion": 1,
                    "directory": str(actor_root),
                    "expectedScriptSha256": hashlib.sha256((ROOT / manifest["peerScript"]).read_bytes()).hexdigest(),
                    "expectedExecutableSha256": hashlib.sha256(assignment_client.read_bytes()).hexdigest(),
                    "ownerToken": owned_processes.owner,
                    "configHome": owned_processes.config_home,
                })
            assignment_agent_processes.append(subprocess.Popen(
                [str(assignment_client), "-t", "2", "--pool", pool,
                 "-a", "127.0.0.1", "--server-port", str(args.domain_port),
                 "--disable-domain-port-auto-discovery",
                 "--log-directory", str(output / "assignment-logs"),
                 "--logOptions", "nocolor,process_id,milliseconds", *actor_options],
                **process_options(environment, assignment_agent_log)))
            if debug_hold is not None:
                debug_hold.register(assignment_agent_processes[-1], "agent:" + pool)
        deadline = time.monotonic() + args.assignment_warmup_seconds
        while time.monotonic() < deadline:
            if memory_guard is not None: memory_guard.check("startup")
            if (domain_process.poll() is not None
                    or any(process.poll() is not None for process in assignment_processes)
                    or any(process.poll() is not None
                           for process in assignment_agent_processes)):
                if debug_hold is not None:
                    debug_hold.begin("DOMAIN_CHILD_EXIT_DURING_WARMUP",
                        (domain_process, *assignment_processes, *assignment_agent_processes))
                    raise RuntimeError("domain fixture process exited during assignment warmup")
                for process in reversed((*assignment_processes,
                                         *assignment_agent_processes)):
                    stop_process(process)
                stop_process(domain_process)
                domain_process = None
                assignment_processes = []
                assignment_agent_processes = []
                raise RuntimeError("domain fixture process exited during assignment warmup")
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        wait_for_assignment_content(
            (domain_process, *assignment_processes, *assignment_agent_processes),
            args.startup_timeout_seconds, stopping, memory_guard.check if memory_guard is not None else None)
        stack_state = "online"
        generation += 1

    def stop_stack() -> None:
        nonlocal domain_process, assignment_processes, assignment_agent_processes
        nonlocal generation, stack_state, mixer, create_permissions, assets_permissions
        was_online = stack_state == "online"
        stack_state = "offline"
        for process in reversed(assignment_agent_processes):
            stop_process(process)
        for process in reversed(assignment_processes):
            stop_process(process)
        stop_process(domain_process)
        owned_processes.stop()
        assignment_agent_processes = []
        assignment_processes = []
        domain_process = None
        mixer = None
        create_permissions = None
        assets_permissions = None
        if was_online:
            generation += 1

    def transition(action: str) -> dict:
        with transition_lock:
            if action == "online":
                try:
                    start_stack()
                except Exception as error:
                    if debug_hold is None:
                        stop_stack()
                    else:
                        debug_hold.begin("DOMAIN_START_OR_RUNTIME_ERROR",
                            tuple(debug_hold.processes), error)
                    raise
            else:
                stop_stack()
            return {"schemaVersion": 1, "state": stack_state,
                    "generation": generation}

    def mixer_control(action):
        with transition_lock:
            if stack_state != "online" or mixer is None:
                raise RuntimeError("owned MessagesMixer control is unavailable")
            if action is None:
                return mixer.state()
            original = mixer.process
            actual = mixer.transition(action)
            if original is not None and mixer.process is not original:
                need(original.poll() is not None and original in assignment_processes)
                assignment_processes.remove(original)
            return actual

    def create_permission_control(command):
        with transition_lock:
            if stack_state != "online" or create_permissions is None:
                raise RuntimeError("owned Create permission control is unavailable")
            return permission_request(create_permissions, assets_permissions, command)

    def assets_permission_control(command):
        with transition_lock:
            if stack_state != "online" or assets_permissions is None:
                raise RuntimeError("owned Assets permission control is unavailable")
            return permission_request(assets_permissions, create_permissions, command)

    def assets_original_control(command):
        with transition_lock:
            if stack_state != "online" or assets_originals is None:
                raise RuntimeError("owned Assets originals are unavailable")
            return assets_originals.read(command)

    def request_stop(_signal=None, _frame=None) -> None:
        stopping.set()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
    control = control_thread = None
    DomainControlHandler.debug_hold = debug_hold
    try:
        start_stack()
        control_token = secrets.token_urlsafe(32)
        DomainControlHandler.token = control_token
        DomainControlHandler.transition = staticmethod(transition)
        DomainControlHandler.mixer = staticmethod(mixer_control)
        DomainControlHandler.create_permissions = staticmethod(create_permission_control) if args.feature_create_permissions else None
        DomainControlHandler.assets_permissions = staticmethod(assets_permission_control) if args.feature_assets_permissions else None
        original_tokens = (secrets.token_urlsafe(32), secrets.token_urlsafe(32)) if args.feature_assets_permissions else ()
        DomainControlHandler.assets_originals = staticmethod(assets_original_control) if args.feature_assets_permissions else None
        DomainControlHandler.assets_original_tokens = original_tokens
        control = ThreadingHTTPServer(("127.0.0.1", args.control_port), DomainControlHandler)
        control_thread = threading.Thread(target=control.serve_forever, daemon=True)
        control_thread.start()
        ready = {
            "schemaVersion": 1,
            "domainUrl": f"hifi://{domain_host}:{args.domain_port}{manifest['spawnPath']}",
            "domainHost": domain_host,
            "domainId": domain_id,
            "requiredMarkers": manifest["requiredMarkers"],
            "expectedEntityCount": manifest["expectedEntityCount"],
            "bootstrapScriptUrl": script_url,
            "peerScriptUrl": peer_script_url,
            "peerDisplayName": manifest["peerDisplayName"],
            "controlUrl": f"http://127.0.0.1:{control.server_address[1]}/v1/domain-state",
            "controlToken": control_token,
            "collaborationEditUrl": f"http://127.0.0.1:{control.server_address[1]}/v1/collaboration-edit",
            "collaborationStateUrl": f"http://127.0.0.1:{control.server_address[1]}/v1/collaboration-state",
        }
        if args.feature_chat_receiver and mixer is not None:
            ready["messagesMixerControlUrl"] = f"http://127.0.0.1:{control.server_address[1]}/v1/messages-mixer-state"
        if args.feature_create_permissions:
            ready["createPermissionsControlUrl"] = f"http://127.0.0.1:{control.server_address[1]}/v1/create-permissions"
        if args.feature_assets_permissions:
            ready["assetsPermissionsControlUrl"] = f"http://127.0.0.1:{control.server_address[1]}/v1/assets-permissions"
            ready["assetsOriginalsControlUrl"] = f"http://127.0.0.1:{control.server_address[1]}/v1/assets-originals"
            ready["assetsOriginalsPrimaryToken"], ready["assetsOriginalsActorToken"] = original_tokens
        if args.ready_file:
            atomic_json(args.ready_file.resolve(), ready)
            if debug_hold is not None:
                debug_hold.pin_ready(args.ready_file)
        print(json.dumps({key: value for key, value in ready.items()
                          if key not in ("controlToken", "assetsOriginalsPrimaryToken", "assetsOriginalsActorToken")}, sort_keys=True), flush=True)
        while not stopping.wait(0.25):
            # Serialize monitoring with an intentionally stopped service. Other
            # processes remain alive and are checked immediately afterwards.
            with transition_lock:
                if memory_guard is not None: memory_guard.check()
                if debug_hold is not None and debug_hold.active.is_set():
                    raise debug_hold.original_error or RuntimeError("DOMAIN_DEBUG_FAILED_CONTROL_OPERATION")
                if stack_state == "online" and domain_process.poll() is not None:
                    if debug_hold is not None:
                        debug_hold.begin("DOMAIN_PROCESS_EXIT_WHILE_ONLINE",
                            (domain_process, *assignment_processes, *assignment_agent_processes))
                    raise RuntimeError("domain-server exited while fixture was active")
                if stack_state == "online" and any(
                        process.poll() is not None
                        for process in (*assignment_processes, *assignment_agent_processes)):
                    if debug_hold is not None:
                        debug_hold.begin("ASSIGNMENT_PROCESS_EXIT_WHILE_ONLINE",
                            (domain_process, *assignment_processes, *assignment_agent_processes))
                    raise RuntimeError("assignment-client exited while fixture was active")
    except Exception as error:
        if debug_hold is not None:
            with transition_lock:
                if not debug_hold.active.is_set():
                    debug_hold.begin("DOMAIN_START_OR_RUNTIME_ERROR",
                        tuple(debug_hold.processes), error)
            debug_hold.wait_release()
        raise  # Preserve the original failed verdict after explicit cleanup release.
    finally:
        with transition_lock:
            stop_stack()
        if control is not None:
            control.shutdown()
            control.server_close()
        if control_thread is not None:
            control_thread.join(timeout=2)
        resources.shutdown()
        resources.server_close()
        resource_thread.join(timeout=2)
        assignment_log.close()
        assignment_agent_log.close()
        domain_log.close()
    return 0


def main() -> int:
    hold_state = []
    try:
        return _controller_main(hold_state)
    except Exception as error:
        # Setup/admission can fail before stack resources or the inner finally exist.
        debug_hold = hold_state[0] if hold_state else None
        if debug_hold is not None and not debug_hold.released:
            if not debug_hold.active.is_set():
                debug_hold.begin("DOMAIN_START_OR_RUNTIME_ERROR",
                    tuple(debug_hold.processes), error)
            debug_hold.wait_release()
        raise
    finally:
        if hold_state and hold_state[0] is not None:
            if hold_state[0].memory_guard is not None:
                hold_state[0].memory_guard.close()
            os.close(hold_state[0].fd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
