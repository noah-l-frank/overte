#!/usr/bin/env python3
"""Device-free checks for the controlled domain fixture controller."""

from __future__ import annotations

import json
import ast
import copy
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from types import SimpleNamespace
from urllib.request import Request, urlopen
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "fixture" / "domain.py"

FAKE_DOMAIN = r'''#!/usr/bin/env python3
import http.server, os, pathlib, signal, sys, uuid
identity = sys.argv[sys.argv.index("-d") + 1] if "-d" in sys.argv else str(uuid.uuid4())
(pathlib.Path(os.environ["XDG_DATA_HOME"]) / "domain-pid.json").write_text(str(os.getpid()))
identity_path = pathlib.Path(os.environ["XDG_DATA_HOME"]) / "served-domain-id"
identity_path.write_text(identity)
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/id":
            with identity_path.with_name("id-reads").open("a") as reads:
                reads.write("read\n")
            payload = (identity_path.read_text() + "\n").encode()
            self.send_response(200); self.send_header("Content-Length", str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
        else:
            self.send_error(404)
    def log_message(self, *args): pass
server = http.server.ThreadingHTTPServer(("127.0.0.1", int(os.environ["HIFI_DOMAIN_SERVER_HTTP_PORT"])), Handler)
def stop(*_):
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
server.serve_forever()
'''

FAKE_ASSIGNMENT = r'''#!/usr/bin/env python3
import json, os, pathlib, signal, sys, time, urllib.request
stopping = False
def stop(*_):
    global stopping
    if "-t" in sys.argv and sys.argv[sys.argv.index("-t") + 1] == "4": time.sleep(0.35)
    stopping = True
signal.signal(signal.SIGTERM, stop)
arguments = pathlib.Path(os.environ["XDG_DATA_HOME"]) / ("args-" + (sys.argv[sys.argv.index("--pool") + 1] if "--pool" in sys.argv else sys.argv[sys.argv.index("-t") + 1]) + ".json")
arguments.write_text(json.dumps(sys.argv))
arguments.with_name(arguments.name.replace("args-", "pid-")).write_text(str(os.getpid()))
if "--pool" in sys.argv and sys.argv[sys.argv.index("--pool") + 1] == "overte-e2e-domain":
    # Model the real entity server's persisted content across an outage. A
    # fresh assignment always seeds one shared object, so reused storage would
    # accumulate a second one and invalidate independent synchronization.
    persistence = pathlib.Path(os.environ["XDG_DATA_HOME"]) / "shared-entities.json"
    previous = json.loads(persistence.read_text()) if persistence.exists() else []
    persistence.write_text(json.dumps(previous + [{"name":"OVERTE_E2E_SHARED_COLOR"}]))
    config = pathlib.Path(os.environ["XDG_CONFIG_HOME"]).parents[1] / "domain-config.json"
    value = json.loads(config.read_text())
    script = value["scripts"]["persistent_scripts"][0]["url"]
    request = urllib.request.Request(
        script.rsplit("/", 1)[0] + "/domain-ready", method="POST",
        data=b'{"schemaVersion":1,"markerCount":4}',
        headers={"Content-Type": "application/json"})
    for _ in range(50):
        try:
            urllib.request.urlopen(request, timeout=1).close(); break
        except OSError:
            time.sleep(0.02)
while not stopping:
    time.sleep(0.05)
'''


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]


class DomainFixtureTest(unittest.TestCase):
    def online_noop_fixture(self):
        """Use the exact nested source with real private children and HTTP /id.

        Only the already-online branch is isolated from the controller monitor;
        otherwise its periodic failure exit could race the guard under test.
        The full controller's startup/recovery is checked separately below.
        """
        temporary = tempfile.TemporaryDirectory(prefix="overte-domain-online-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        domain_file = root / "domain.py"
        domain_file.write_text(FAKE_DOMAIN)
        identity = str(uuid.uuid4())
        port = free_port()
        environment = dict(os.environ, XDG_DATA_HOME=str(root),
                           HIFI_DOMAIN_SERVER_HTTP_PORT=str(port))
        domain = subprocess.Popen([sys.executable, str(domain_file), "-d", identity],
                                  env=environment, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def stop(process):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=3)
        self.addCleanup(stop, domain)
        self.addCleanup(stop, child)

        spec = importlib.util.spec_from_file_location("domain_online_counter", CONTROLLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(identity, module.wait_for_domain(
            domain, f"http://127.0.0.1:{port}/id", 3))
        tree = ast.parse(CONTROLLER.read_text())
        main = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "main")
        start = next(node for node in main.body
                     if isinstance(node, ast.FunctionDef) and node.name == "start_stack")
        names = ("domain_process", "assignment_processes", "assignment_agent_processes",
                 "domain_id", "generation", "stack_state", "mixer",
                 "create_permissions", "assets_permissions")
        factory = ast.parse("def bind_online(" + ",".join(names) + "):\n    pass\n").body[0]
        factory.body = [copy.deepcopy(start), ast.parse("return start_stack").body[0]]
        namespace = dict(vars(module), args=SimpleNamespace(
            http_port=port, startup_timeout_seconds=1))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                     str(CONTROLLER), "exec"), namespace)
        invoke = namespace["bind_online"](domain, [child], [], identity, 1, "online",
                                           None, None, None)
        return root, domain, child, invoke

    def test_online_noop_reads_current_id_and_rejects_foreign_identity(self):
        root, domain, child, invoke = self.online_noop_fixture()
        reads = root / "id-reads"
        before = len(reads.read_text().splitlines())
        self.assertIsNone(invoke())
        self.assertIsNone(invoke())
        self.assertEqual(before + 2, len(reads.read_text().splitlines()))
        (root / "served-domain-id").write_text(str(uuid.uuid4()))
        with self.assertRaisesRegex(RuntimeError, "readiness identity changed"):
            invoke()
        self.assertIsNone(domain.poll())
        self.assertIsNone(child.poll())

    def test_online_noop_rejects_exited_assignment_and_domain_without_ack(self):
        for kind in ("assignment", "domain"):
            with self.subTest(kind=kind):
                root, domain, child, invoke = self.online_noop_fixture()
                reads = root / "id-reads"
                before = reads.read_bytes()
                stopped = child if kind == "assignment" else domain
                stopped.terminate()
                stopped.wait(timeout=3)
                with self.assertRaisesRegex(RuntimeError, "stack is no longer running"):
                    invoke()
                self.assertEqual(before, reads.read_bytes())

    def test_domain_fixture_contract(self):
        result = subprocess.run(
            [sys.executable, str(CONTROLLER), "--check"], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("assignment-owned markers", result.stdout)

    def test_domain_spawn_uses_feet_on_the_known_floor_surface(self):
        manifest = json.loads((ROOT / "fixture/domain-manifest.json").read_text())
        self.assertEqual(0.0, manifest["spawnPosition"]["y"])
        self.assertEqual("/0.0,0.0,4.0/0,0,0,1", manifest["spawnPath"])
        # Use the actual validator against negative fixture manifests.
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location("fixture_domain_test", CONTROLLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for y in (-0.1, 2.0):
            invalid = json.loads(json.dumps(manifest))
            invalid["spawnPosition"]["y"] = y
            invalid["spawnPath"] = f"/0.0,{y},4.0/0,0,0,1"
            original = Path.read_text
            def read(path, *args, **kwargs):
                if path.name == "domain-manifest.json": return json.dumps(invalid)
                return original(path, *args, **kwargs)
            with self.subTest(y=y), patch.object(Path, "read_text", read):
                with self.assertRaisesRegex(ValueError, "known floor surface"):
                    module.validate_domain_fixture()

    @unittest.skipIf(os.name == "nt", "executable-script fixture is POSIX-specific")
    def test_controller_owns_stack_and_publishes_exact_ready_contract(self):
        self.check_controller(False)

    @unittest.skipIf(os.name == "nt", "native actor-host IPC is POSIX-specific")
    def test_chat_receiver_opt_in_is_private_and_limited_to_its_dedicated_peer(self):
        self.check_controller(True)

    def check_controller(self, chat_receiver):
        with tempfile.TemporaryDirectory(prefix="overte-domain-controller-test-") as temporary:
            root = Path(temporary)
            domain = root / "fake-domain.py"
            assignment = root / "fake-assignment.py"
            domain.write_text(FAKE_DOMAIN, encoding="utf-8")
            assignment.write_text(FAKE_ASSIGNMENT, encoding="utf-8")
            domain.chmod(0o700)
            assignment.chmod(0o700)
            ready = root / "ready.json"
            output = root / "output"
            http_port = free_port()
            process = subprocess.Popen([
                sys.executable, str(CONTROLLER),
                "--domain-server", str(domain),
                "--assignment-client", str(assignment),
                "--domain-port", str(free_port()),
                "--http-port", str(http_port),
                "--script-port", "0",
                "--assignment-warmup-seconds", "0.1",
                "--output-dir", str(output),
                "--ready-file", str(ready),
                *(["--feature-chat-receiver"] if chat_receiver else []),
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                if not ready.exists():
                    stdout, _ = process.communicate(timeout=2)
                    self.fail("domain fixture did not become ready:\n" + stdout)
                metadata = json.loads(ready.read_text(encoding="utf-8"))
                self.assertEqual(metadata["domainId"], str(uuid.UUID(metadata["domainId"])))
                self.assertTrue(metadata["domainUrl"].startswith("hifi://127.0.0.1:"))
                self.assertEqual(4, metadata["expectedEntityCount"])
                self.assertEqual("OVERTE_E2E_PEER", metadata["peerDisplayName"])
                with urlopen(metadata["bootstrapScriptUrl"], timeout=2) as response:
                    script = response.read().decode("utf-8")
                self.assertIn('Entities.addEntity(properties, "domain")', script)
                with urlopen(metadata["peerScriptUrl"], timeout=2) as response:
                    peer_script = response.read().decode("utf-8")
                self.assertIn("Agent.isAvatar = true", peer_script)
                if chat_receiver:
                    endpoint = metadata["messagesMixerControlUrl"]
                    def mixer_request(action=None, *, token=metadata["controlToken"], extra=None):
                        payload = None if action is None else json.dumps({"schemaVersion": 1, "action": action, **(extra or {})}).encode()
                        return urlopen(Request(endpoint, method="GET" if payload is None else "POST", data=payload,
                            headers={"X-Overte-E2E-Token": token, "Content-Type": "application/json"}), timeout=6)
                    deadline = time.monotonic() + 3
                    first_data = output / "runtime/stack-1/data"
                    while len(list(first_data.glob("pid-*.json"))) < 8 and time.monotonic() < deadline:
                        time.sleep(0.02)
                    before_pids = {path.name: int(path.read_text()) for path in first_data.glob("*pid*.json")}
                    mixer_pid = before_pids["pid-4.json"]
                    with self.assertRaises(HTTPError) as rejected:
                        mixer_request("offline", token="unowned")
                    self.assertEqual(404, rejected.exception.code);rejected.exception.close()
                    for extra in ({"schemaVersion": True}, {"expectedNode": "foreign"}):
                        with self.assertRaises(HTTPError) as rejected:
                            mixer_request("offline", extra=extra)
                        self.assertEqual(400, rejected.exception.code);rejected.exception.close()
                    with mixer_request() as response:
                        initial = json.loads(response.read())
                    self.assertTrue(initial["running"]);self.assertFalse(initial["pending"])
                    with mixer_request("offline") as response:
                        stopped = json.loads(response.read())
                    self.assertFalse(stopped["running"]);self.assertFalse(stopped["pending"])
                    self.assertFalse(Path(f"/proc/{mixer_pid}").exists())
                    for name, pid in before_pids.items():
                        if name != "pid-4.json":
                            self.assertTrue(Path(f"/proc/{pid}").exists(), name + " must survive mixer removal")
                    with mixer_request() as response:
                        self.assertEqual(stopped, json.loads(response.read()))
                    self.assertIsNone(process.poll(), "intentional slow mixer stop must not trip whole-stack monitoring")
                    try:
                        with mixer_request("online") as response:
                            restored = json.loads(response.read())
                    except HTTPError as error:
                        error.close();process.terminate();diagnostics, _ = process.communicate(timeout=10)
                        self.fail("mixer recovery failed:\n" + diagnostics)
                    self.assertTrue(restored["running"]);self.assertFalse(restored["pending"])
                    self.assertGreater(restored["generation"], stopped["generation"])
                    deadline = time.monotonic() + 3
                    while int((first_data / "pid-4.json").read_text()) == mixer_pid and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertNotEqual(mixer_pid, int((first_data / "pid-4.json").read_text()))
                    self.assertFalse((output / "messages-mixer-intent.json").exists())
                    for name, pid in before_pids.items():
                        if name != "pid-4.json":
                            self.assertEqual(pid, int((first_data / name).read_text()))
                previous_generation = None
                for action in ("offline", "online", "online"):
                    request = Request(
                        metadata["controlUrl"], method="POST",
                        data=json.dumps({"schemaVersion": 1, "action": action}).encode(),
                        headers={
                            "Content-Type": "application/json",
                            "X-Overte-E2E-Token": metadata["controlToken"],
                        },
                    )
                    with urlopen(request, timeout=5) as response:
                        transition = json.loads(response.read())
                    self.assertEqual(action, transition["state"])
                    self.assertGreaterEqual(transition["generation"], 2)
                    if action == "online":
                        with urlopen(f"http://127.0.0.1:{http_port}/id", timeout=2) as response:
                            self.assertEqual(metadata["domainId"], response.read().decode().strip())
                        if previous_generation is not None:
                            self.assertEqual(previous_generation, transition["generation"])
                        previous_generation = transition["generation"]
                self.assertIsNone(process.poll())
                configured = output / "chat-actor-config.json"
                self.assertEqual(chat_receiver, configured.exists())
                roles = {"args-" + role + ".json" for role in
                         ("0", "1", "3", "4", "5", "6", "overte-e2e-domain", "overte-e2e-peer")}
                # Domain readiness proves its marker, not that every separate
                # synthetic assignment interpreter has written its argv yet.
                # Both actual controlled stack births still owe all eight roles.
                deadline = time.monotonic() + 3
                while True:
                    arguments = list((output / "runtime").rglob("args-*.json"))
                    by_stack = {}
                    for path in arguments: by_stack.setdefault(path.parent, set()).add(path.name)
                    if len(by_stack) == 2 and all(names == roles for names in by_stack.values()): break
                    if time.monotonic() >= deadline: break
                    time.sleep(0.02)
                self.assertEqual(2, len(by_stack), "both original stack births must retain their own assignment argv")
                for directory, names in by_stack.items(): self.assertEqual(roles, names, str(directory))
                self.assertEqual(16, len(arguments))
                for path in arguments:
                    argv = json.loads(path.read_text())
                    role = path.stem.removeprefix("args-")
                    self.assertEqual("2" if role.startswith("overte-e2e-") else role, argv[argv.index("-t") + 1])
                    self.assertEqual(role.startswith("overte-e2e-"), "--pool" in argv)
                    if "--pool" in argv: self.assertEqual(role, argv[argv.index("--pool") + 1])
                    expected = chat_receiver and role == "overte-e2e-peer"
                    self.assertEqual(expected, "--testScript" in argv)
                    self.assertEqual(expected, "--e2eChatActorDir" in argv)
                    if expected:
                        actor_root = Path(argv[argv.index("--e2eChatActorDir") + 1])
                        self.assertEqual(0o700, actor_root.stat().st_mode & 0o777)
                        self.assertEqual(path.parent.parent / "chat-peer", actor_root)
                if chat_receiver:
                    private = json.loads(configured.read_text())
                    self.assertEqual(0o600, configured.stat().st_mode & 0o777)
                    self.assertEqual(output / "runtime/stack-3/chat-peer", Path(private["directory"]))
                    self.assertEqual(64, len(private["expectedScriptSha256"]))
                    self.assertEqual(64, len(private["expectedExecutableSha256"]))
                seeds = list((output / "runtime").rglob("shared-entities.json"))
                self.assertEqual(2, len(seeds), "both real controlled starts must retain their own seed")
                self.assertEqual(2, len({p.parent for p in seeds}), "recovery must use fresh content storage")
                for seed in seeds:
                    self.assertEqual([{"name": "OVERTE_E2E_SHARED_COLOR"}],
                                     json.loads(seed.read_text()),
                                     "recovery must not duplicate persisted shared entities")
            finally:
                process.terminate()
                stdout, _ = process.communicate(timeout=10)
            self.assertEqual(0, process.returncode, stdout)
            if chat_receiver:
                self.assertNotIn(private["ownerToken"], stdout)
                self.assertNotIn(private["directory"], stdout)
            self.assertTrue((output / "domain-config.json").is_file())
            saved_config = json.loads((output / "domain-config.json").read_text())
            self.assertEqual("/0.0,0.0,4.0/0,0,0,1", saved_config["paths"]["/"]["viewpoint"])
            self.assertTrue((output / "domain-server.log").is_file())
            self.assertTrue((output / "assignment-client.log").is_file())
            self.assertTrue((output / "assignment-agent.log").is_file())


if __name__ == "__main__":
    unittest.main()
