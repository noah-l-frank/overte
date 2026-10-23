#!/usr/bin/env python3
"""Device-free proofs for world interaction and domain roundtrip scenarios."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest


DEVICE_ROOT = Path(__file__).resolve().parents[1]


class InteractionAndDomainRecoveryTest(unittest.TestCase):
    def controlled_domain_environment(self, *, unavailable=False):
        state = {"online": False, "starts": 0, "requests": []}

        class Control(BaseHTTPRequestHandler):
            def do_POST(self):
                command = json.loads(self.rfile.read(
                    int(self.headers["Content-Length"])))
                if (self.path != "/v1/domain-state"
                        or self.headers.get("X-Overte-E2E-Token") != "self-test-only"
                        or command != {"schemaVersion": 1, "action": "online"}):
                    self.send_error(400)
                    return
                state["requests"].append("online")
                if unavailable:
                    self.send_error(503)
                    return
                if not state["online"]:
                    state["starts"] += 1
                    state["online"] = True
                body = json.dumps({"schemaVersion": 1, "state": "online",
                                   "generation": state["starts"]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Control)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        domain_id = "11111111-2222-4333-8444-555555555555"
        return state, {
            "OVERTE_E2E_SCENE_URL": "http://fixture.invalid/scene.json",
            "OVERTE_E2E_DOMAIN_URL": "hifi://127.0.0.1:40102/0,2,4/0,0,0,1",
            "OVERTE_E2E_DOMAIN_HOST": "127.0.0.1",
            "OVERTE_E2E_DOMAIN_ID": domain_id,
            "OVERTE_E2E_DOMAIN_MARKERS_JSON": json.dumps(json.loads(
                (DEVICE_ROOT / "fixture/domain-manifest.json").read_text())["requiredMarkers"]),
            "OVERTE_MOCK_E2E_DOMAIN_ID": domain_id,
            "OVERTE_E2E_DOMAIN_CONTROL_URL": (
                f"http://127.0.0.1:{server.server_port}/v1/domain-state"),
            "OVERTE_E2E_DOMAIN_CONTROL_TOKEN": "self-test-only",
        }

    def test_domain_navigation_starts_stopped_fixture_and_reuses_online_stack(self):
        state, environment = self.controlled_domain_environment()
        temporary, _root, output, result = self.run_suite("domain-recovery", environment)
        try:
            self.assertEqual(0, result.returncode, result.stdout)
            self.assertEqual(["online", "online"], state["requests"])
            self.assertEqual(1, state["starts"])
            for module in ("domain-enter", "domain-roundtrip"):
                receipt = json.loads((output / "modules" / module / "domain-prerequisite.json").read_text())
                self.assertEqual({"schemaVersion": 1, "state": "online", "generation": 1}, receipt)
        finally:
            temporary.cleanup()

    def test_domain_controller_failure_blocks_navigation_as_infrastructure(self):
        state, environment = self.controlled_domain_environment(unavailable=True)
        temporary, root, output, result = self.run_suite("domain-smoke", environment)
        try:
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertEqual(["online"], state["requests"])
            self.assertEqual(0, json.loads((root / "state.json").read_text()).get("domainEnterCount", 0))
            summary = json.loads((output / "summary.json").read_text())
            entry = next(item for item in summary["results"] if item["id"] == "domain-enter")
            self.assertEqual("error", entry["status"])
            self.assertFalse((output / "modules/domain-enter/domain-navigation-result.json").exists())
        finally:
            temporary.cleanup()

    def run_suite(self, suite: str, environment: dict[str, str], module_ids=None):
        temporary = tempfile.TemporaryDirectory(prefix=f"overte-{suite}-")
        root = Path(temporary.name)
        output = root / "results"
        env = os.environ.copy()
        env.update({
            "OVERTE_MOCK_E2E_STATE": str(root / "state.json"),
            "OVERTE_DEVICE_LAUNCH_SETTLE_SECONDS": "0",
            "OVERTE_DEVICE_LOCK_ROOT": str(root / "locks"),
            "OVERTE_E2E_POLL_SECONDS": "0.05",
            **environment,
        })
        catalog = DEVICE_ROOT / "catalog.json"
        if module_ids is not None:
            document = json.loads(catalog.read_text())
            lookup = {m["id"]: m for m in document["modules"]}
            document["modules"] = [lookup[identifier] for identifier in module_ids]
            for module in document["modules"]:
                module["command"][0] = str(DEVICE_ROOT / module["command"][0])
            catalog = root / "regression-first-catalog.json"
            catalog.write_text(json.dumps(document))
        result = subprocess.run([
            sys.executable, str(DEVICE_ROOT / "run.py"),
            "--adapter-manifest", str(DEVICE_ROOT / "adapters/mock/adapter.json"),
            "--catalog", str(catalog),
            "--suite", suite, "--allow-virtual", "--require-complete",
            "--output-dir", str(output),
        ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
           env=env, check=False)
        return temporary, root, output, result

    def test_crash_recovery_rebinds_a_process_local_probe_sequence(self):
        temporary, root, output, result = self.run_suite("crash-recovery-under-load", {
            "OVERTE_E2E_SCENE_URL": "http://fixture.invalid/scene.json",
            "OVERTE_DEVICE_LAUNCH_SETTLE_SECONDS": "0",
        })
        try:
            self.assertEqual(0, result.returncode, result.stdout)
            state = json.loads((root / "state.json").read_text())
            self.assertEqual(2, state["launchCount"])
            receipt = json.loads((output / "modules/crash-recovery-under-load/crash-recovery.json").read_text())
            self.assertTrue(receipt["processChanged"])
            self.assertTrue(receipt["sceneReady"])
        finally:
            temporary.cleanup()

    def test_world_interaction_observes_one_fresh_entity_press(self):
        temporary, root, output, result = self.run_suite("interaction-smoke", {
            "OVERTE_E2E_SCENE_URL": "http://fixture.invalid/scene.json",
        })
        try:
            self.assertEqual(0, result.returncode, result.stdout)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                ["launch-smoke", "scene", "world-interaction"],
                [item["id"] for item in summary["results"]],
            )
            before = json.loads((output / "modules/world-interaction/interaction-before.json")
                                .read_text(encoding="utf-8"))
            after = json.loads((output / "modules/world-interaction/interaction-after.json")
                               .read_text(encoding="utf-8"))
            self.assertEqual(before["interaction"]["pressCount"] + 1,
                             after["interaction"]["pressCount"])
            self.assertEqual("OVERTE_E2E_INTERACTABLE",
                             after["interaction"]["lastEntityName"])
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(1, state["launchCount"])
            self.assertEqual(1, state["interactionCount"])
        finally:
            temporary.cleanup()

    def test_world_interaction_rejects_missing_and_duplicate_effects(self):
        for failure in ("primary-interaction-missing", "primary-interaction-duplicate"):
            with self.subTest(failure=failure):
                temporary, _root, output, result = self.run_suite("interaction-smoke", {
                    "OVERTE_E2E_SCENE_URL": "http://fixture.invalid/scene.json",
                    "OVERTE_E2E_TIMEOUT_SECONDS": "1",
                    "OVERTE_MOCK_E2E_FAILURES": failure,
                })
                try:
                    self.assertEqual(1, result.returncode, result.stdout)
                    summary = json.loads((output / "summary.json").read_text(
                        encoding="utf-8"))
                    interaction = next(item for item in summary["results"]
                                       if item["id"] == "world-interaction")
                    self.assertEqual("failed", interaction["status"])
                finally:
                    temporary.cleanup()

    def test_domain_roundtrip_preserves_process_and_reconnects_content(self):
        manifest = json.loads(
            (DEVICE_ROOT / "fixture/domain-manifest.json").read_text(encoding="utf-8"))
        domain_id = "11111111-2222-4333-8444-555555555555"
        temporary, root, output, result = self.run_suite("domain-recovery", {
            "OVERTE_E2E_SCENE_URL": "http://fixture.invalid/scene.json",
            "OVERTE_E2E_DOMAIN_URL": "hifi://127.0.0.1:40102/0,2,4/0,0,0,1",
            "OVERTE_E2E_DOMAIN_HOST": "127.0.0.1",
            "OVERTE_E2E_DOMAIN_ID": domain_id,
            "OVERTE_E2E_DOMAIN_MARKERS_JSON": json.dumps(manifest["requiredMarkers"]),
            "OVERTE_MOCK_E2E_DOMAIN_ID": domain_id,
        })
        try:
            self.assertEqual(0, result.returncode, result.stdout)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                ["launch-smoke", "domain-enter", "domain-roundtrip"],
                [item["id"] for item in summary["results"]],
            )
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(1, state["launchCount"])
            self.assertEqual(2, state["domainEnterCount"])
            self.assertEqual(1, state["sceneLoadCount"])
            evidence = json.loads((output / "modules/domain-roundtrip/domain-roundtrip.json")
                                  .read_text(encoding="utf-8"))
            self.assertTrue(evidence["processStable"])
            self.assertTrue(evidence["serverlessObserved"])
            self.assertGreaterEqual(evidence["stableReconnectSamples"], 3)
        finally:
            temporary.cleanup()

    def test_roundtrip_can_run_before_the_previously_passed_domain_enter(self):
        manifest = json.loads((DEVICE_ROOT / "fixture/domain-manifest.json").read_text())
        domain_id = "11111111-2222-4333-8444-555555555555"
        temporary, root, output, result = self.run_suite("domain-recovery", {
            "OVERTE_E2E_SCENE_URL": "http://fixture.invalid/scene.json",
            "OVERTE_E2E_DOMAIN_URL": "hifi://127.0.0.1:40282/0,2,4/0,0,0,1",
            "OVERTE_E2E_DOMAIN_HOST": "127.0.0.1",
            "OVERTE_E2E_DOMAIN_ID": domain_id,
            "OVERTE_E2E_DOMAIN_MARKERS_JSON": json.dumps(manifest["requiredMarkers"]),
            "OVERTE_MOCK_E2E_DOMAIN_ID": domain_id,
        }, ["launch-smoke", "domain-roundtrip", "domain-enter"])
        try:
            self.assertEqual(0,result.returncode,result.stdout)
            summary=json.loads((output / "summary.json").read_text())
            self.assertEqual(["launch-smoke","domain-roundtrip","domain-enter"],
                             [m["id"] for m in summary["results"]])
            proof=json.loads((output / "modules/domain-roundtrip/domain-roundtrip.json").read_text())
            self.assertTrue(proof["processStable"] and proof["serverlessObserved"])
            self.assertEqual(domain_id,proof["domainId"])
            self.assertEqual(1,json.loads((root / "state.json").read_text())["launchCount"])
        finally:
            temporary.cleanup()

    def test_domain_roundtrip_rejects_process_restart_during_reentry(self):
        manifest = json.loads(
            (DEVICE_ROOT / "fixture/domain-manifest.json").read_text(encoding="utf-8"))
        domain_id = "11111111-2222-4333-8444-555555555555"
        temporary, _root, output, result = self.run_suite("domain-recovery", {
            "OVERTE_E2E_SCENE_URL": "http://fixture.invalid/scene.json",
            "OVERTE_E2E_DOMAIN_URL": "hifi://127.0.0.1:40102/0,2,4/0,0,0,1",
            "OVERTE_E2E_DOMAIN_HOST": "127.0.0.1",
            "OVERTE_E2E_DOMAIN_ID": domain_id,
            "OVERTE_E2E_DOMAIN_MARKERS_JSON": json.dumps(manifest["requiredMarkers"]),
            "OVERTE_MOCK_E2E_DOMAIN_ID": domain_id,
            "OVERTE_MOCK_E2E_FAILURES": "domain-reentry-process-restart",
        })
        try:
            self.assertEqual(1, result.returncode, result.stdout)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            roundtrip = next(item for item in summary["results"]
                             if item["id"] == "domain-roundtrip")
            self.assertEqual("failed", roundtrip["status"])
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
