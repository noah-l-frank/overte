#!/usr/bin/env python3
"""Own an ephemeral domain-server and assignment-client E2E fixture."""

from __future__ import annotations

import argparse
import hashlib
import hmac
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
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
from fixture.create_rez_authority import CreateRezAuthority, CreateRezControl, fixture_permissions
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
    token = ""
    transition = None
    collaboration = None
    mixer = None
    create_rez = None
    assets_backend = None
    assets_reader_token = None

    def assets_observation(self) -> None:
        """A separate credential can request only closed passive observations."""
        tokens = self.headers.get_all("X-Overte-Assets-Reader", [])
        expected = self.assets_reader_token
        if (type(expected) is not str or len(tokens) != 1 or not tokens[0].isascii() or not 32 <= len(tokens[0]) <= 128
                or not hmac.compare_digest(tokens[0], expected) or self.assets_backend is None):
            self.send_error(404)
            return
        try:
            from adapters.asset_backend_source import object_bytes
            from fixture.asset_backend_control import command as assets_command
            lengths = self.headers.get_all("Content-Length", [])
            if (len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= 1024
                    or self.headers.get("Transfer-Encoding") or self.headers.get("Content-Encoding")
                    or self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json"):
                raise ValueError("invalid bounded Assets observation")
            raw = self.rfile.read(int(lengths[0]))
            if len(raw) != int(lengths[0]):
                raise ValueError("incomplete Assets observation")
            result = self.assets_backend(assets_command(object_bytes(raw, 1024)))
            payload = json.dumps(result, separators=(",", ":"), allow_nan=False).encode("utf-8")
            if len(payload) > 4 * 1024 * 1024:
                raise ValueError("Assets original export exceeds its bound")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
        except (ValueError, UnicodeError):
            self.send_error(400, "invalid Assets observation")
        except (OSError, RuntimeError):
            self.send_error(503, "owned Assets observation is unavailable")

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
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
        if self.path == "/v1/assets-backend":
            self.assets_observation()
            return
        if self.path not in {"/v1/domain-state", "/v1/collaboration-edit", "/v1/messages-mixer-state", "/v1/create-rez"} or self.headers.get(
                "X-Overte-E2E-Token") != self.token:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 256:
                raise ValueError("invalid request length")
            command = json.loads(self.rfile.read(length))
            if self.path == "/v1/create-rez":
                if self.create_rez is None:
                    raise RuntimeError("Create rez control is not enabled")
                result = self.create_rez(command)
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


def assets_assignment_environment(environment, assignment_type, source_root, enabled):
    """Default-off source access is confined to the actual AssetServer role."""
    need(type(enabled) is bool)
    result = environment.copy()
    result.pop("OVERTE_E2E_ASSETS_SOURCE_ROOT", None)
    if enabled and assignment_type == "3":
        need(sys.platform.startswith("linux"))
        root = Path(source_root)
        need(root.is_absolute() and root.resolve(strict=True) == root)
        info = root.lstat()
        import stat
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == 0o700)
        result["OVERTE_E2E_ASSETS_SOURCE_ROOT"] = str(root)
    return result


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


def wait_for_domain(process: subprocess.Popen, url: str, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_error = "domain HTTP endpoint was unavailable"
    while time.monotonic() < deadline:
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
                                stopping: threading.Event) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if DomainResourceHandler.content_ready.is_set():
            return
        if stopping.is_set():
            raise RuntimeError("domain fixture stopped before content became ready")
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("domain fixture process exited before content became ready")
        time.sleep(0.1)
    raise RuntimeError("assignment-owned domain content did not become ready")


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
    parser.add_argument("--feature-create-rez", action="store_true",
                        help="Opt in isolated Create rez permission control through the normal owned domain settings API.")
    parser.add_argument("--feature-assets-backend", action="store_true",
                        help="Opt in passive original AssetServer observations; requires Linux and an instrumented owned Assignment Client.")
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
    return args


def main() -> int:
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
    if getattr(args, "feature_create_rez", False):
        description = json.loads((REPOSITORY / "domain-server/resources/describe-settings.json").read_text())
        config["security"] = {"standard_permissions": fixture_permissions(description)}
    config_path = output / "domain-config.json"
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
    # Only the explicit role-3 opt-in below may receive the passive source root.
    environment.pop("OVERTE_E2E_ASSETS_SOURCE_ROOT", None)
    owned_processes = OwnedProcesses(environment)

    domain_log = (output / "domain-server.log").open("w", encoding="utf-8")
    assignment_log = (output / "assignment-client.log").open("w", encoding="utf-8")
    assignment_agent_log = (output / "assignment-agent.log").open("w", encoding="utf-8")
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
    mixer_store = PrivateFeatureState(output / "messages-mixer-intent.json")
    mixer_expected = None
    stack_state = "offline"
    transition_lock = threading.Lock()
    stopping = threading.Event()
    assets_process = assets_source = assets_journal = assets_backend = None
    assets_reader_token = secrets.token_urlsafe(32) if getattr(args, "feature_assets_backend", False) else None

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
        nonlocal assets_process
        assignment_environment = assets_assignment_environment(environment, assignment_type, assets_source,
            getattr(args, "feature_assets_backend", False))
        process = subprocess.Popen(
            [str(assignment_client), "-t", assignment_type, "-a", "127.0.0.1",
             "--server-port", str(args.domain_port),
             "--disable-domain-port-auto-discovery",
             "--log-directory", str(output / "assignment-logs"),
             "--logOptions", "nocolor,process_id,milliseconds"],
            **process_options(assignment_environment, assignment_log))
        assignment_processes.append(process)
        if assignment_type == "3" and getattr(args, "feature_assets_backend", False):
            assets_process = process
        return process

    def start_stack() -> None:
        nonlocal domain_process, assignment_processes, assignment_agent_processes
        nonlocal domain_id, generation, stack_state, mixer
        nonlocal assets_source, assets_journal
        if stack_state == "online":
            return
        # The broker and assignment seed start afresh on each controlled
        # restart. Reusing persisted entities would retain the previous seed
        # and create two identically named shared objects. Preserve the domain
        # identity/configuration while keeping each seed's content isolated.
        content_runtime = runtime / f"stack-{generation + 1}"
        content_runtime.mkdir(mode=0o700)
        for name in ("data", "cache"):
            (content_runtime / name).mkdir(mode=0o700)
        if getattr(args, "feature_assets_backend", False):
            need(sys.platform.startswith("linux"))
            assets_source = content_runtime / "assets-backend-source"
            assets_journal = content_runtime / "assets-backend-journal"
            assets_source.mkdir(mode=0o700)
            assets_journal.mkdir(mode=0o700)
        environment.update(XDG_DATA_HOME=str(content_runtime / "data"),
                           XDG_CACHE_HOME=str(content_runtime / "cache"))
        DomainResourceHandler.content_ready.clear()
        DomainResourceHandler.collaboration.reset()
        domain_process = subprocess.Popen(
            [str(domain_server), "-d", expected_domain_id, "--user-config", str(config_path),
             "--logOptions", "nocolor,process_id,milliseconds"],
            **process_options(environment, domain_log))
        observed_id = wait_for_domain(
            domain_process, f"http://127.0.0.1:{args.http_port}/id",
            args.startup_timeout_seconds)
        if domain_id is not None and observed_id != domain_id:
            stop_process(domain_process)
            domain_process = None
            raise RuntimeError("controlled domain identity changed during restart")
        domain_id = observed_id
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
        deadline = time.monotonic() + args.assignment_warmup_seconds
        while time.monotonic() < deadline:
            if (domain_process.poll() is not None
                    or any(process.poll() is not None for process in assignment_processes)
                    or any(process.poll() is not None
                           for process in assignment_agent_processes)):
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
            args.startup_timeout_seconds, stopping)
        stack_state = "online"
        generation += 1

    def stop_stack() -> None:
        nonlocal domain_process, assignment_processes, assignment_agent_processes
        nonlocal generation, stack_state, mixer
        nonlocal assets_backend, assets_process
        was_online = stack_state == "online"
        stack_state = "offline"
        if assets_backend is not None:
            # Host detachment retains every original/WAL and makes no native
            # task, mapping, file or whole-journey retirement claim.
            assets_backend.detach()
            assets_backend = None
        assets_process = None
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
        if was_online:
            generation += 1

    def transition(action: str) -> dict:
        with transition_lock:
            if action == "online":
                try:
                    start_stack()
                except Exception:
                    stop_stack()
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

    create_rez = None

    def assets_backend_owner():
        nonlocal assets_backend
        from fixture.asset_backend_control import AssetsBackendControl
        from fixture.asset_backend_process import LinuxAssetsBackendProcess
        need(stack_state == "online" and assets_process is not None and assets_process.poll() is None)
        if assets_backend is None:
            binding = LinuxAssetsBackendProcess(assets_process.pid, assets_source, owned_processes.config_home,
                hashlib.sha256(assignment_client.read_bytes()).hexdigest(), hashlib.sha256(owned_processes.owner.encode("ascii")).hexdigest(), owned_processes.matches)
            assets_backend = AssetsBackendControl(binding, assets_journal)
        return assets_backend

    def assets_backend_control(command):
        with transition_lock:
            return assets_backend_owner().handle(command)

    def create_rez_control(command):
        with transition_lock:
            need(stack_state == "online" and create_rez is not None)
            return create_rez.handle(command)

    def request_stop(_signal=None, _frame=None) -> None:
        stopping.set()

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
    control = control_thread = None
    try:
        start_stack()
        DomainControlHandler.create_rez = None
        DomainControlHandler.assets_reader_token = assets_reader_token
        DomainControlHandler.assets_backend = staticmethod(assets_backend_control) if assets_reader_token is not None else None
        if getattr(args, "feature_create_rez", False):
            def owned_create_domain():
                need(stack_state == "online" and domain_process is not None
                     and domain_process.poll() is None and owned_processes.matches(domain_process.pid))
                actual = Path("/proc") / str(domain_process.pid)
                fields = (actual / "stat").read_text().rsplit(")", 1)[1].split()
                need(len(fields) > 19 and fields[0] not in ("Z", "X") and fields[19].isdecimal()
                     and (actual / "exe").resolve() == domain_server.resolve())
                command = (actual / "cmdline").read_bytes().split(b"\0")
                need(command.count(b"--user-config") == 1
                     and command[command.index(b"--user-config") + 1] == os.fsencode(config_path))
                env = (actual / "environ").read_bytes().split(b"\0")
                need(f"HIFI_DOMAIN_SERVER_HTTP_PORT={args.http_port}".encode() in env)
                return {"processId": domain_process.pid, "startIdentity": fields[19], "domainId": domain_id}
            authority = CreateRezAuthority(f"http://127.0.0.1:{args.http_port}",
                PrivateFeatureState(output / "create-rez-settings.json"), owned_create_domain)
            authority.prepare()
            create_rez = CreateRezControl(authority, PrivateFeatureState(output / "create-rez-control.json"))
            DomainControlHandler.create_rez = staticmethod(create_rez_control)
        control_token = secrets.token_urlsafe(32)
        DomainControlHandler.token = control_token
        DomainControlHandler.transition = staticmethod(transition)
        DomainControlHandler.mixer = staticmethod(mixer_control)
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
        if getattr(args, "feature_create_rez", False):
            ready["createRezControlUrl"] = f"http://127.0.0.1:{control.server_address[1]}/v1/create-rez"
        if assets_reader_token is not None:
            backend_process = assets_backend_owner().process
            ready["assetsBackendReader"] = dict(url=f"http://127.0.0.1:{control.server_address[1]}/v1/assets-backend", token=assets_reader_token,
                domainId=domain_id, processIdentity=backend_process.process_identity, executableSha256=backend_process.sha256,
                ownerSha256=backend_process.owner_sha256, sourceRootIdentity=backend_process.root)
        if args.feature_chat_receiver and mixer is not None:
            ready["messagesMixerControlUrl"] = f"http://127.0.0.1:{control.server_address[1]}/v1/messages-mixer-state"
        if args.ready_file:
            atomic_json(args.ready_file.resolve(), ready)
        print(json.dumps({key: value for key, value in ready.items()
                          if key not in {"controlToken", "assetsBackendReader"}}, sort_keys=True), flush=True)
        while not stopping.wait(0.25):
            # Serialize monitoring with an intentionally stopped service. Other
            # processes remain alive and are checked immediately afterwards.
            with transition_lock:
                if stack_state == "online" and domain_process.poll() is not None:
                    raise RuntimeError("domain-server exited while fixture was active")
                if stack_state == "online" and any(
                        process.poll() is not None
                        for process in (*assignment_processes, *assignment_agent_processes)):
                    raise RuntimeError("assignment-client exited while fixture was active")
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


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
