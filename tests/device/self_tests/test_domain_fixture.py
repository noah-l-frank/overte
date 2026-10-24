#!/usr/bin/env python3
"""Device-free checks for the controlled domain fixture controller."""

from __future__ import annotations

import json
import ast
import copy
import hashlib
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
    def failed_worker_fixture(self, debug, phase="active"):
        temporary = tempfile.TemporaryDirectory(prefix="overte-domain-hold-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        domain, assignment = root / "domain.py", root / "assignment.py"
        domain.write_text(FAKE_DOMAIN)
        trigger = root / "exit-owned-worker"
        assignment.write_text(FAKE_ASSIGNMENT.replace("while not stopping:\n",
            "while not stopping:\n    if '--pool' in sys.argv and sys.argv[sys.argv.index('--pool') + 1] == 'overte-e2e-domain' and pathlib.Path(" + repr(str(trigger)) + ").exists(): raise SystemExit(17)\n"))
        if phase == "content-timeout":
            assignment.write_text(assignment.read_text().replace(
                "urllib.request.urlopen(request, timeout=1).close(); break", "break"))
        if phase == "warmup": trigger.touch()
        for p in (domain, assignment): p.chmod(0o700)
        output, ready = root / "output", root / "ready.json"
        argv = [sys.executable, str(CONTROLLER), "--domain-server", str(domain),
                "--assignment-client", str(assignment), "--domain-port", str(free_port()),
                "--http-port", str(free_port()), "--output-dir", str(output),
                "--ready-file", str(ready), "--assignment-warmup-seconds",
                "2" if phase == "warmup" else "0.1", "--startup-timeout-seconds", "1"]
        if phase == "admission": argv.extend(["--bind", "0.0.0.0"])
        if debug: argv.append("--debug-hold-on-error")
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True, umask=0o077)
        def release():
            if process.poll() is not None: return
            owner = output / "debug-hold/OWNER.private.json"
            failure = output / "debug-hold/FAILURE.private.json"
            if owner.is_file() and failure.is_file():
                data = json.loads(owner.read_text())
                request = output / "debug-hold/RELEASE_REQUEST.private.json"
                if request.exists() or request.is_symlink(): request.unlink()
                request.write_text(json.dumps({"schemaVersion": 1, "action": "cleanup",
                    "contextSha256": data["contextSha256"], "nonce": data["nonce"]}))
                request.chmod(0o600)
            else: process.terminate()
            process.communicate(timeout=10)
        self.addCleanup(release)
        deadline = time.monotonic() + 8
        data_root = output / "runtime/stack-1/data"
        required = ready if phase == "active" else output / "debug-hold/FAILURE.private.json"
        while (not required.exists() or phase != "admission" and len(list(data_root.glob("pid-*.json"))) < 8) and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertIsNone(process.poll())
        self.assertTrue(required.is_file())
        pids = {p.stem: int(p.read_text()) for p in data_root.glob("*pid*.json")}
        self.assertEqual(0 if phase == "admission" else 9, len(pids))
        return root, output, ready, process, trigger, pids

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned process identity")
    def test_default_child_exit_still_cleans_and_preserves_failed_verdict(self):
        root, output, ready, process, trigger, pids = self.failed_worker_fixture(False)
        trigger.touch()
        stdout, _ = process.communicate(timeout=10)
        self.assertEqual(2, process.returncode)
        self.assertIn(b"assignment-client exited while fixture was active", stdout)
        self.assertFalse((output / "debug-hold").exists())
        self.assertTrue(ready.exists(), "default historical READY behavior is unchanged")
        for pid in pids.values(): self.assertFalse(Path(f"/proc/{pid}").exists())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned process identity")
    def test_debug_hold_preserves_survivors_denies_controls_and_releases_only_exact_request(self):
        root, output, ready, process, trigger, pids = self.failed_worker_fixture(True)
        original_ready = ready.read_bytes();metadata = json.loads(original_ready)
        trigger.touch();held = output / "debug-hold"
        deadline = time.monotonic() + 5
        while ready.exists() and process.poll() is None and time.monotonic() < deadline: time.sleep(0.02)
        failure = json.loads((held / "FAILURE.private.json").read_text())
        self.assertFalse(ready.exists());self.assertEqual(original_ready,(held / "READY_BEFORE_FAILURE.private.json").read_bytes())
        self.assertIsNone(process.poll());self.assertFalse(failure["cleanupAttempted"])
        self.assertEqual("ASSIGNMENT_PROCESS_EXIT_WHILE_ONLINE",failure["failureCode"])
        failed = [p for p in failure["processes"] if p["returncode"] is not None]
        self.assertEqual(1,len(failed));self.assertEqual(17,failed[0]["returncode"])
        self.assertEqual("agent:overte-e2e-domain",failed[0]["role"]);self.assertTrue(failed[0]["birth"].isdigit())
        survivors = [p for p in failure["processes"] if p["returncode"] is None]
        for p in survivors:self.assertTrue(Path(f"/proc/{p['pid']}").exists())
        for name in ("OWNER.private.json","FAILURE.private.json","READY_BEFORE_FAILURE.private.json"):
            self.assertEqual(0o600,(held/name).stat().st_mode & 0o777)
        self.assertEqual(0o700,held.stat().st_mode & 0o777)
        with self.assertRaises(HTTPError) as rejected:
            urlopen(Request(metadata["controlUrl"], method="POST",data=b'{"schemaVersion":1,"action":"online"}',headers={"X-Overte-E2E-Token":metadata["controlToken"]}),timeout=2)
        self.assertEqual(503,rejected.exception.code);rejected.exception.close()
        with self.assertRaises(HTTPError) as rejected_get:
            urlopen(Request(metadata["controlUrl"].replace("domain-state","collaboration-state"), headers={"X-Overte-E2E-Token":metadata["controlToken"]}),timeout=2)
        self.assertEqual(503,rejected_get.exception.code);rejected_get.exception.close()
        self.assertEqual("AT_OWN_POPEN_SPAWN",failed[0]["identityObservation"])
        self.assertEqual("ACTUAL_POPEN_POLL_AT_FAILURE",failed[0]["returncodeObservation"])
        owner=json.loads((held/"OWNER.private.json").read_text());request=held/"RELEASE_REQUEST.private.json"
        value={"schemaVersion":1,"action":"cleanup","contextSha256":owner["contextSha256"],"nonce":owner["nonce"]}
        foreign=root/"foreign-release.json";foreign.write_text(json.dumps(value));foreign.chmod(0o600)
        for kind in ("wrong-nonce","wrong-context","wrong-mode","symlink"):
            if request.exists() or request.is_symlink():request.unlink()
            if kind=="symlink":request.symlink_to(foreign)
            else:
                bad=dict(value)
                if kind=="wrong-nonce":bad["nonce"]="0"*32
                if kind=="wrong-context":bad["contextSha256"]="0"*64
                request.write_text(json.dumps(bad));request.chmod(0o644 if kind=="wrong-mode"else 0o600)
            time.sleep(0.15);self.assertIsNone(process.poll(),kind)
            for p in survivors:self.assertTrue(Path(f"/proc/{p['pid']}").exists(),kind)
            self.assertFalse((held/"RELEASE_ACCEPTED.private.json").exists())
        self.assertEqual(value,json.loads(foreign.read_text()))
        process.terminate();time.sleep(0.15);self.assertIsNone(process.poll(),"SIGTERM is not cleanup authorization while held")
        request.unlink();request.write_text(json.dumps(value));request.chmod(0o600)
        stdout,_=process.communicate(timeout=10)
        self.assertEqual(2,process.returncode);self.assertIn(b"assignment-client exited while fixture was active",stdout)
        self.assertNotIn(owner["nonce"].encode(),stdout);self.assertTrue((held/"RELEASE_ACCEPTED.private.json").exists())
        for pid in pids.values():self.assertFalse(Path(f"/proc/{pid}").exists())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned process identity")
    def test_debug_hold_also_preserves_warmup_content_timeout_and_zero_child_admission_errors(self):
        for phase in ("warmup", "content-timeout", "admission"):
            with self.subTest(phase=phase):
                root, output, ready, process, trigger, pids = self.failed_worker_fixture(True, phase)
                held = output / "debug-hold";failure = json.loads((held/"FAILURE.private.json").read_text())
                self.assertFalse(ready.exists());self.assertFalse(failure["cleanupAttempted"]);self.assertIsNone(process.poll())
                expected = "DOMAIN_CHILD_EXIT_DURING_WARMUP" if phase == "warmup" else "DOMAIN_START_OR_RUNTIME_ERROR"
                self.assertEqual(expected,failure["failureCode"])
                if phase == "admission":self.assertEqual([],failure["processes"]);self.assertEqual("ValueError",failure["exceptionClass"])
                else:
                    self.assertEqual(9,len(failure["processes"]))
                    for child in failure["processes"]:
                        if child["returncode"] is None:self.assertTrue(Path(f"/proc/{child['pid']}").exists())
                    observed = [child["returncode"] for child in failure["processes"] if child["returncode"] is not None]
                    self.assertEqual([17] if phase == "warmup" else [], observed)
                owner=json.loads((held/"OWNER.private.json").read_text());request=held/"RELEASE_REQUEST.private.json"
                request.write_text(json.dumps({"schemaVersion":1,"action":"cleanup","contextSha256":owner["contextSha256"],"nonce":owner["nonce"]}));request.chmod(0o600)
                stdout,_=process.communicate(timeout=10)
                self.assertEqual(2,process.returncode);self.assertTrue((held/"RELEASE_ACCEPTED.private.json").exists())
                self.assertNotIn(owner["nonce"].encode(),stdout)
                for pid in pids.values():self.assertFalse(Path(f"/proc/{pid}").exists())

    def memory_counter_fixture(self, timeline_part_bytes=8*1024**2):
        temporary = tempfile.TemporaryDirectory(prefix="overte-domain-memory-test-")
        self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        spec=importlib.util.spec_from_file_location("domain_memory_counter",CONTROLLER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        hold=module.DomainDebugHold(root);self.addCleanup(os.close,hold.fd)
        cgroup=root/"fake-cgroup";cgroup.mkdir()
        values={"cgroup.procs":str(os.getpid()),"memory.current":"0","memory.max":str(1024**3),"memory.peak":"0","memory.events":"low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n"}
        for name,value in values.items():(cgroup/name).write_text(value)
        guard=module.DomainMemoryGuard(hold,1024**3,cgroup,
                                       timeline_part_bytes=timeline_part_bytes)
        self.addCleanup(guard.close)
        counter=root/"allocation-count"
        script="import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); values=[]\nwhile True:\n values.append(bytearray(4096)); p.write_text(str(len(values))); time.sleep(.02)\n"
        process=subprocess.Popen([sys.executable,"-c",script,str(counter)],start_new_session=True,
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.addCleanup(module.stop_process,process)
        hold.register(process,"assignment:0")
        deadline=time.monotonic()+2
        while (not counter.exists() or not counter.read_text()) and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(counter.exists())
        return module,root,hold,guard,cgroup,counter,process

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned process context")
    def test_memory_timeline_rotates_losslessly_without_stopping_owned_child(self):
        module,root,hold,guard,cgroup,counter,process=self.memory_counter_fixture(4096)
        before=counter.read_bytes()
        for index in range(20):guard.check("rotation-counter",force=True)
        time.sleep(.1)
        self.assertIsNone(process.poll());self.assertNotIn(
            module.DomainDebugHold.process_birth(process.pid)["state"],("T","t"))
        self.assertNotEqual(before,counter.read_bytes());self.assertEqual([],guard.stopped)
        self.assertFalse(hold.active.is_set())
        receipts=[json.loads(line)for line in
                  (hold.directory/"MEMORY_TIMELINE_INDEX.private.jsonl").read_text().splitlines()]
        latest={row["part"]:row for row in receipts}
        self.assertGreater(len(latest),1);samples=[]
        for part,row in sorted(latest.items()):
            path=hold.directory/row["file"];data=path.read_bytes()
            self.assertLessEqual(len(data),4096);self.assertEqual(len(data),row["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(),row["sha256"])
            self.assertEqual(hold.context_sha256,row["contextSha256"])
            self.assertEqual(hold.context["sourceSha256"],row["sourceSha256"])
            self.assertEqual(0o600,path.stat().st_mode&0o777);self.assertEqual(1,path.stat().st_nlink)
            rows=[json.loads(line)for line in data.splitlines()]
            for key in ("sequence","epochNs"):
                self.assertEqual(rows[0][key],row["first"][key])
                self.assertEqual(rows[-1][key],row["last"][key])
            self.assertEqual(part!=max(latest),row["closed"]);samples.extend(rows)
        self.assertEqual(list(range(1,22)),[row["sequence"]for row in samples])
        self.assertEqual(0o600,(hold.directory/"MEMORY_TIMELINE_INDEX.private.jsonl").stat().st_mode&0o777)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned process context")
    def test_memory_timeline_does_not_replace_foreign_rotation_alias(self):
        module,root,hold,guard,cgroup,counter,process=self.memory_counter_fixture(4096)
        foreign=root/"foreign";foreign.write_bytes(b"foreign bytes")
        alias=hold.directory/"MEMORY_TIMELINE.part-000002.private.jsonl";alias.symlink_to(foreign)
        guard.timeline_part_bytes=guard.timeline_bytes+len(json.dumps(guard.sample("counter")))//2
        with self.assertRaises(FileExistsError):guard.check("counter",force=True)
        self.assertTrue(alias.is_symlink());self.assertEqual(b"foreign bytes",foreign.read_bytes())
        self.assertIsNone(process.poll());self.assertEqual([],guard.stopped)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned process context")
    def test_memory_timeline_keeps_real_filesystem_reserve_failure_explicit(self):
        from unittest.mock import patch
        module,root,hold,guard,cgroup,counter,process=self.memory_counter_fixture()
        before=(hold.directory/"MEMORY_TIMELINE.private.jsonl").read_bytes()
        with patch.object(module.os,"fstatvfs",return_value=SimpleNamespace(f_bavail=0,f_frsize=4096)):
            with self.assertRaisesRegex(RuntimeError,"DOMAIN_MEMORY_FILESYSTEM_RESERVE_LOW"):
                guard.check(force=True)
        self.assertEqual(before,(hold.directory/"MEMORY_TIMELINE.private.jsonl").read_bytes())
        self.assertEqual([],guard.stopped)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux cgroup and pidfd counter")
    def test_memory_pressure_freezes_real_owned_allocation_then_exact_release_resumes_cleanup(self):
        module,root,hold,guard,cgroup,counter,process=self.memory_counter_fixture()
        (cgroup/"memory.current").write_text(str(guard.last["thresholdBytes"]+1))
        with self.assertRaisesRegex(RuntimeError,"DOMAIN_MEMORY_HEADROOM_LOW"):
            guard.check(force=True)
        self.assertIsNone(process.poll());self.assertIn(module.DomainDebugHold.process_birth(process.pid)["state"],("T","t"))
        before=counter.read_bytes();time.sleep(.2);self.assertEqual(before,counter.read_bytes())
        failure=json.loads((hold.directory/"FAILURE.private.json").read_text());self.assertTrue(failure["details"]["freezeComplete"])
        self.assertEqual(process.pid,failure["details"]["frozenProcesses"][0]["pid"])
        timeline=hold.directory/"MEMORY_TIMELINE.private.jsonl";raw=timeline.read_bytes();time.sleep(.1);self.assertEqual(raw,timeline.read_bytes());self.assertEqual(0o600,timeline.stat().st_mode&0o777)
        (hold.directory/"RELEASE_REQUEST.private.json").write_text(json.dumps({"schemaVersion":1,"action":"cleanup","contextSha256":hold.context_sha256,"nonce":hold.nonce}));(hold.directory/"RELEASE_REQUEST.private.json").chmod(0o600)
        self.assertTrue(hold.release_requested())
        deadline=time.monotonic()+2
        while counter.read_bytes()==before and time.monotonic()<deadline:time.sleep(.02)
        self.assertNotEqual(before,counter.read_bytes());module.stop_process(process);self.assertIsNotNone(process.poll())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned process context")
    def test_memory_foreign_cgroup_pin_rejects_before_signal_and_limit_mismatch_rejects(self):
        module,root,hold,guard,cgroup,counter,process=self.memory_counter_fixture()
        hold.processes[process]["cgroup"]="foreign-cgroup"
        before=counter.read_bytes()
        with self.assertRaisesRegex(RuntimeError,"FREEZE_OWNER_CHANGED"):guard.freeze()
        self.assertEqual([],guard.stopped);self.assertNotIn(module.DomainDebugHold.process_birth(process.pid)["state"],("T","t"))
        time.sleep(.1);self.assertNotEqual(before,counter.read_bytes())
        (cgroup/"memory.max").write_text(str(2*1024**3))
        with self.assertRaisesRegex(RuntimeError,"LIMIT_MISMATCH"):guard.sample("periodic")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux cgroup mount mapping")
    def test_memory_cgroup_mapping_requires_actual_direct_controller_membership(self):
        spec=importlib.util.spec_from_file_location("domain_memory_mapping",CONTROLLER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory()as temporary:
            mounted=Path(temporary);(mounted/"cgroup.procs").write_text(str(os.getpid()))
            info=f"20 19 0:1 /host/owned {mounted} rw - cgroup2 cgroup rw"
            self.assertEqual(mounted,module.DomainMemoryGuard.resolve_cgroup("0::/\n",info))
            self.assertEqual(mounted,module.DomainMemoryGuard.resolve_cgroup("0::/host/owned\n",info))
            child=mounted/"owned";child.mkdir();(child/"cgroup.procs").write_text(str(os.getpid()))
            (mounted/"cgroup.procs").write_text("999999999")
            info=f"20 19 0:1 / {mounted} rw - cgroup2 cgroup rw"
            self.assertEqual(child,module.DomainMemoryGuard.resolve_cgroup("0::/owned\n",info))
            (child/"cgroup.procs").write_text("999999999")
            with self.assertRaisesRegex(RuntimeError,"OWN_CGROUP_UNPROVEN"):
                module.DomainMemoryGuard.resolve_cgroup("0::/owned\n",info)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux owned debug hold")
    def test_memory_constructor_resolution_failure_leaves_usable_zero_child_hold(self):
        import threading
        spec=importlib.util.spec_from_file_location("domain_partial_memory_counter",CONTROLLER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        class UnprovenGuard(module.DomainMemoryGuard):
            @staticmethod
            def resolve_cgroup():raise RuntimeError("DOMAIN_MEMORY_OWN_CGROUP_UNPROVEN")
        with tempfile.TemporaryDirectory()as temporary:
            hold=module.DomainDebugHold(Path(temporary));self.addCleanup(os.close,hold.fd)
            with self.assertRaisesRegex(RuntimeError,"OWN_CGROUP_UNPROVEN")as failure:
                UnprovenGuard(hold,6*1024**3)
            self.assertIsNone(hold.memory_guard)
            hold.begin("DOMAIN_START_OR_RUNTIME_ERROR",(),failure.exception)
            record=json.loads((hold.directory/"FAILURE.private.json").read_text())
            self.assertEqual([],record["processes"]);self.assertFalse(record["cleanupAttempted"])
            waiter=threading.Thread(target=hold.wait_release,daemon=True);waiter.start()
            time.sleep(.05);self.assertTrue(waiter.is_alive());self.assertFalse(hold.released)
            request=hold.directory/"RELEASE_REQUEST.private.json"
            request.write_text(json.dumps({"schemaVersion":1,"action":"cleanup","contextSha256":hold.context_sha256,"nonce":hold.nonce}));request.chmod(0o600)
            waiter.join(timeout=2);self.assertFalse(waiter.is_alive());self.assertTrue(hold.released)
            self.assertEqual("DOMAIN_MEMORY_OWN_CGROUP_UNPROVEN",str(failure.exception))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux parent memory budget mapping")
    def test_memory_parent_budget_with_unbounded_task_leaf_uses_owned_container_scope(self):
        spec=importlib.util.spec_from_file_location("domain_parent_budget_counter",CONTROLLER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory()as temporary:
            mounted=Path(temporary);scope=mounted/("libpod-"+"a"*64+".scope");scope.mkdir();leaf=scope/"container";leaf.mkdir()
            (mounted/"cgroup.procs").write_text("999999999");(scope/"cgroup.procs").write_text("");(leaf/"cgroup.procs").write_text(str(os.getpid()))
            (leaf/"memory.max").write_text("max");(scope/"memory.max").write_text(str(6*1024**3))
            info=f"20 19 0:1 / {mounted} rw - cgroup2 cgroup rw"
            task=module.DomainMemoryGuard.resolve_cgroup("0::/"+scope.name+"/container\n",info)
            self.assertEqual(leaf,task);self.assertEqual(scope,module.DomainMemoryGuard.resolve_budget(task,6*1024**3,info))
            private_info=f"20 19 0:1 /{scope.name} {scope} rw - cgroup2 cgroup rw"
            self.assertEqual(scope,module.DomainMemoryGuard.resolve_budget(leaf,6*1024**3,private_info))
            (scope/"memory.max").write_text("max")
            with self.assertRaisesRegex(RuntimeError,"OWN_BUDGET_UNPROVEN"):
                module.DomainMemoryGuard.resolve_budget(task,6*1024**3,info)
            (scope/"memory.max").write_text(str(3*1024**3))
            with self.assertRaisesRegex(RuntimeError,"LIMIT_MISMATCH"):
                module.DomainMemoryGuard.resolve_budget(task,6*1024**3,info)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux private hold exception capture")
    def test_debug_hold_retains_actual_original_trace_cause_and_suppressed_context_privately(self):
        import io
        from contextlib import redirect_stdout
        spec=importlib.util.spec_from_file_location("domain_private_exception_counter",CONTROLLER)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory()as temporary:
            hold=module.DomainDebugHold(Path(temporary));self.addCleanup(os.close,hold.fd)
            console=io.StringIO();marker="synthetic-private-cause-marker"
            try:
                try:raise ValueError(marker)
                except ValueError:raise RuntimeError("DOMAIN_MEMORY_OWN_BUDGET_UNPROVEN")from None
            except RuntimeError as original:
                with redirect_stdout(console):hold.begin("DOMAIN_START_OR_RUNTIME_ERROR",(),original)
                self.assertIs(original,hold.original_error)
            private=hold.directory/"ORIGINAL_EXCEPTION.private.json";record=json.loads(private.read_text())
            self.assertEqual(0o600,private.stat().st_mode&0o777);self.assertFalse(record["chainTruncated"])
            self.assertEqual(["RuntimeError","ValueError"],[v["class"]for v in record["originalExceptionChain"]])
            self.assertIn(marker,record["originalExceptionChain"][1]["traceback"]);self.assertTrue(record["originalExceptionChain"][0]["suppressesContext"])
            self.assertNotIn(marker,console.getvalue());self.assertTrue(hold.exception_recorded)
            self.assertFalse(json.loads((hold.directory/"FAILURE.private.json").read_text())["cleanupAttempted"])

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
                    if isinstance(node, ast.FunctionDef) and node.name == "_controller_main")
        start = next(node for node in main.body
                     if isinstance(node, ast.FunctionDef) and node.name == "start_stack")
        names = ("domain_process", "assignment_processes", "assignment_agent_processes",
                 "domain_id", "generation", "stack_state", "mixer",
                 "create_permissions", "assets_permissions")
        factory = ast.parse("def bind_online(" + ",".join(names) + "):\n    pass\n").body[0]
        factory.body = [copy.deepcopy(start), ast.parse("return start_stack").body[0]]
        namespace = dict(vars(module), args=SimpleNamespace(
            http_port=port, startup_timeout_seconds=1), memory_guard=None, debug_hold=None)
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
