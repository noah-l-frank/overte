#!/usr/bin/env python3
"""Extend the strict iOS Appium contract with real native/client operations.

The injected Wi-Fi driver provides bounded DVT process observation and signals.
HTTP is only the command delivery channel: client receipts and fresh probes
verify execution, and the portable modules verify the resulting behavior.
"""
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import uuid

from ios.adapters.appium_adapter import AppiumAdapter
from adapters.common import fail
from contracts import validate_operation_arguments, validate_operation_result
from ios.adapters import native_ui, native_integration, native_primary, native_upgrade, native_permission, native_consent, native_crash
from adapters.collaboration_observation import actor_receipt, portable_observation
from adapters.normal_ui import NativeUI
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.script_restart_handoff import ScriptRestartHandoff
from adapters.restart_inputs import RestartInputs, run_script_restart
from ios.adapters import appium_adapter as ios_backend
from ios.adapters.normal_input import NativeInput
from ios.adapters import normal_navigation
from ios.adapters import normal_snapshot
from ios.adapters import normal_scripts
from scripts_observation import OPERATIONS as SCRIPT_OPERATIONS
from adapters.normal_feature_state import PrivateFeatureState, need
from ios.adapters.snapshot_files import SnapshotFiles
from ios.adapters.feature_observation import FeatureObservation
from navigation_observation import OPERATIONS as NORMAL_NAVIGATION_OPERATIONS, viewpoint_urls


class IOSNativeMixin:
    CLIENT_OPERATIONS = frozenset({
        "asset.load", "audio.mute", "navigation.enter-domain", "setting.set",
    })
    NATIVE_OPERATIONS = frozenset({
        "app.crash", "app.stop", "app.version", "lifecycle.background",
    })

    COLLABORATION_OPERATIONS = frozenset({"collaboration.edit", "collaboration.snapshot"})
    INTEGRATION_OPERATIONS = frozenset({"text.focus", "text.type", "text.snapshot", "text.dismiss", "render.snapshot"})

    def __init__(self):
        super().__init__("ios")

    def _feature_observer(self, selector, client, session, state, target):
        # Component transport only. It deliberately contributes no feature.*
        # capabilities and cannot replace canonical installed-code binding.
        self.assert_ios_process_identity(selector, client, session, state, target)
        return FeatureObservation(client, session, target,
                                  lambda: self.native_process(client, session, target))

    def _native_feature_observer(self, selector, client, session, state, target):
        return self._feature_observer(selector, client, session, state, target).native_observer()

    def _recorded_preview_evidence(self, selector, client, session, state, target):
        return self._feature_observer(selector, client, session, state, target).recorded_preview_observer()

    def _script_execution_observer(self, selector, client, session, state, target):
        return self._feature_observer(selector, client, session, state, target).script_execution_observer()

    @classmethod
    def advertised_capabilities(cls, target):
        values = set(super().advertised_capabilities(target))
        if (target.get("platform") == "ios" and target.get("physical") is True
                and target.get("testBuild")
                and target.get("probe") == {"kind": "ios-documents"}):
            values |= cls.CLIENT_OPERATIONS | cls.NATIVE_OPERATIONS
            if native_consent.enabled(target):
                values.add("entity-script.review")
            if native_integration.enabled(target):
                values |= cls.INTEGRATION_OPERATIONS
            if native_primary.enabled(target):
                values.add("input.primary")
            if native_upgrade.configuration(target) is not None:
                values |= {"app.install", "app.upgrade"}
            if native_permission.enabled(target):
                values |= {"permission.snapshot", "permission.set"}
            if cls.collaboration_configuration(target) is not None:
                values |= cls.COLLABORATION_OPERATIONS
            if normal_navigation.configuration(target) is not None:
                values |= NORMAL_NAVIGATION_OPERATIONS
            if normal_snapshot.configuration(target) is not None:
                values |= normal_snapshot.OPERATIONS
            if normal_scripts.configuration(target) is not None:
                values |= SCRIPT_OPERATIONS
        return sorted(values)

    def script_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('normal-scripts.json'))

    def _script_runtime(self, selector):
        target = self.target(selector)
        need(normal_scripts.configuration(target) is not None)
        client, session, state = self.ensure_session(selector)
        fingerprint = hashlib.sha256(json.dumps(target, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        need(state.get('targetFingerprint') == fingerprint)
        generation = state['generation']
        def continuity():
            self.assert_ios_process_identity(selector, client, session, state, target)
            current = self.read_session(selector)
            need(current is not None and current.get('sessionId') == session
                 and current.get('generation') == generation and current.get('targetFingerprint') == fingerprint
                 and hashlib.sha256(json.dumps(self.target(selector), sort_keys=True,
                     separators=(',', ':')).encode()).hexdigest() == fingerprint)
        def process():
            continuity()
            return self.native_process(client, session, target)
        continuity()
        native = NativeInput(client, session, target, process)
        observer = FeatureObservation(client, session, target, process)
        return normal_scripts.runtime(NativeUI(client, session, continuity), native, observer, session, state)

    def _scripts(self, selector):
        return normal_scripts.manager(*self._script_runtime(selector), self.script_store(selector))

    def script_files_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('normal-script-files.json'))

    def _script_files(self, selector):
        ui, _observe, binding = self._script_runtime(selector)
        return self._bound_script_files(selector, ui, binding)

    def _bound_script_files(self, selector, ui, binding):
        from adapters.native_script_files import OwnedScriptFiles
        native = ui.io.native
        # Reuse the actual session/fingerprint/PID continuity closure, rather
        # than creating a process-only component reader for persistent files.
        observer = FeatureObservation(native.client, native.session, native.target, native.observe_process)
        return OwnedScriptFiles(observer.script_fixture_files(), self.script_files_store(selector),
                                binding, component_only=True)

    def _script_file_manager(self, selector):
        ui, observe, binding = self._script_runtime(selector)
        files = self._bound_script_files(selector, ui, binding)
        directory = files.verify()
        return normal_scripts.manager(ui, observe, binding, self.script_store(selector),
            file_owner=files, file_picker=TokenScriptFilePicker(ui.io, directory))

    def _script_missing_manager(self, selector):
        ui, observe, binding = self._script_runtime(selector)
        result = normal_scripts.NormalScriptManager(ui, observe, self.script_store(selector), binding,
            source_kind='feature-script-missing', component_only=True)
        result.sample()
        return result

    def _script_manager_status(self, selector):
        from adapters.script_manager_status import manager_status
        ui, _observe, _binding = self._script_runtime(selector)
        return manager_status(ui.io.capture())

    def script_restart_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('normal-script-restart.json'))

    def _script_restart_handoff(self, selector):
        return ScriptRestartHandoff(self.script_restart_store(selector), self.script_files_store(selector),
            self.script_store(selector), component_only=True)

    def _script_restart_prepare(self, selector):
        manager = self._script_file_manager(selector)
        native = manager.ui.io.native
        observer = FeatureObservation(native.client, native.session, native.target, native.observe_process)
        return self._script_restart_handoff(selector).prepare(manager, observer.script_execution_observer())

    def _script_restart_adopt(self, selector):
        # Retain the explicit component scope and original installed-source
        # guards. No manager is reconstructed until both ownership records have
        # been transferred using actual current empty execution/UI observations.
        ui, observe, binding = self._script_runtime(selector)
        native = ui.io.native
        observer = FeatureObservation(native.client, native.session, native.target, native.observe_process)
        handoff = self._script_restart_handoff(selector)
        return handoff.adopt(binding, observer.process_presence(), observer.script_execution_observer(),
            self._bound_script_files(selector, ui, binding).native, ui, observe,
            TokenScriptFilePicker(ui.io, handoff.directory()))

    def script_restart_inputs_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('normal-script-restart-inputs.json'))

    def _script_restart_inputs(self, selector):
        return RestartInputs(self.script_restart_inputs_store(selector),
            [self.script_restart_store(selector), self.script_files_store(selector), self.script_store(selector)],
            component_only=True)

    def _script_restart_source(self, selector):
        ui, _observe, binding = self._script_runtime(selector)
        native = ui.io.native
        observer = FeatureObservation(native.client, native.session, native.target, native.observe_process)
        return binding, observer.native_observer()

    def _script_restart_session(self, selector):
        # An existing session only: do not create/launch/install while checking
        # the stopped side of the restart boundary.
        origin = self._script_restart_inputs(selector).read()['oldBinding']
        target = self.target(selector); state = self.read_session(selector)
        need(state is not None and type(state.get('sessionId')) is str
             and state.get('generation') == origin['generation']
             and state.get('targetFingerprint') == origin['targetFingerprint']
             and hashlib.sha256(json.dumps(target, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                == origin['targetFingerprint'])
        return ios_backend.WebDriver(target['serverUrl']), state, target

    def _script_restart_stopped(self, selector):
        client, state, target = self._script_restart_session(selector)
        process = self.native_process(client, state['sessionId'], target)
        if process is None:
            self.reset_launch_state(selector, state)  # Host flags after original absence only.
        return {'running': process is not None, 'identity': str(process['pid']) if process is not None else None}

    def _script_restart(self, selector):
        return run_script_restart(self._script_restart_inputs(selector), self._script_restart_handoff(selector),
            lambda: self._script_restart_source(selector), lambda: self._script_restart_prepare(selector),
            lambda: self.invoke(selector, 'app.stop', {}), lambda: self._script_restart_stopped(selector),
            lambda: self.invoke(selector, 'app.launch', {}), lambda: self._script_restart_adopt(selector))

    def _graphics_controls(self, selector, intent):
        from adapters.token_graphics_ui import TokenGraphicsUI
        from ios.adapters.normal_graphics import IOSGraphicsIO
        manager = self._scripts(selector)
        return TokenGraphicsUI(IOSGraphicsIO(manager.ui.io),intent)

    def _native_source_scope(self,selector):
        # Original raw native readers need the qualified session/process but no
        # Scripts profile or editor. Canonical assert_ios_process_identity also
        # preserves its installed-bundle/source/candidate binding on every I/O.
        target=self.target(selector)
        need(target.get('platform')=='ios' and target.get('physical') is True
             and target.get('probe')=={'kind':'ios-documents'} and type(target.get('testBuild')) is dict)
        client,session,state=self.ensure_session(selector)
        fingerprint=hashlib.sha256(json.dumps(target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        generation=state['generation']
        need(type(generation) is int and generation>=0 and state.get('sessionId')==session
             and state.get('targetFingerprint')==fingerprint)
        def process():
            current=self.read_session(selector)
            need(current is not None and current.get('sessionId')==session and current.get('generation')==generation
                 and current.get('targetFingerprint')==fingerprint
                 and hashlib.sha256(json.dumps(self.target(selector),sort_keys=True,separators=(',',':')).encode()).hexdigest()==fingerprint)
            self.assert_ios_process_identity(selector,client,session,state,target)
            return self.native_process(client,session,target)
        return FeatureObservation(client,session,target,process)

    def _process_presence(self, selector):
        return self._native_source_scope(selector).process_presence()

    def _navigation_replies(self,selector):
        return self._native_source_scope(selector).navigation_replies()

    def _pending_owner(self,selector,intent=None):
        manager=self._scripts(selector);native=manager.ui.io.native
        return FeatureObservation(native.client,native.session,native.target,native.observe_process).pending_owner(intent)

    def _web_dom(self,selector):
        manager=self._scripts(selector);native=manager.ui.io.native
        return FeatureObservation(native.client,native.session,native.target,native.observe_process).web_dom()

    def _chat_view(self,selector):
        manager=self._scripts(selector);native=manager.ui.io.native
        return FeatureObservation(native.client,native.session,native.target,native.observe_process).chat_view()

    def chat_capture_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('chat-capture-owner.json'))

    def _chat_capture(self,selector,run):
        from adapters.native_chat_observation import ChatCaptureOwner
        manager=self._scripts(selector);native=manager.ui.io.native
        observer=FeatureObservation(native.client,native.session,native.target,native.observe_process)
        owner=ChatCaptureOwner(self.chat_capture_store(selector),manager.binding,observer.guard,component_only=True)
        return observer.chat_capture(owner,run)

    def account_origin_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('account-origin-owner.json'))

    def _account_origin(self, selector):
        manager=self._scripts(selector);native=manager.ui.io.native
        observer=FeatureObservation(native.client,native.session,native.target,native.observe_process)
        return observer.account_origin(self.account_origin_store(selector),manager.binding)

    def account_probe_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('account-probe-owner.json'))

    def _account_probe(self, selector):
        from adapters.native_account_probe import AccountProbeOwner
        manager=self._scripts(selector);native=manager.ui.io.native
        observer=FeatureObservation(native.client,native.session,native.target,native.observe_process)
        owner=AccountProbeOwner(self.account_probe_store(selector),manager.binding,observer.guard,ios=True,component_only=True)
        return observer.account_probe(owner)

    def world_render_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('world-render-owner.json'))

    def _world_render_capture(self, selector):
        from adapters.owned_world_render import WorldRenderOwner
        manager=self._scripts(selector)
        native=manager.ui.io.native
        observer=FeatureObservation(native.client,native.session,native.target,native.observe_process)
        owner=WorldRenderOwner(self.world_render_store(selector),manager.binding,observer.guard,component_only=True)
        return observer.world_render_capture(owner)

    def private_login_input_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('private-login-input-owner.json'))

    def _private_login_input(self,selector,run):
        from adapters.private_login_input import PrivateLoginInput
        from ios.adapters.private_login_transport import IOSPrivateLoginTransport
        manager=self._scripts(selector);native=manager.ui.io.native
        observer=FeatureObservation(native.client,native.session,native.target,native.observe_process)
        return PrivateLoginInput(IOSPrivateLoginTransport(observer),self.private_login_input_store(selector),manager.binding,run)

    def _create_controls(self,selector,intent):
        from adapters.token_create_ui import TokenCreateUI
        from ios.adapters.create_controls import IOSCreateIO
        manager=self._scripts(selector) # Canonical installed-code gate remains unchanged.
        return TokenCreateUI(IOSCreateIO(manager.ui.io),intent)

    def _chat_controls(self,selector,intent,run):
        from adapters.token_chat_ui import TokenChatUI
        from ios.adapters.chat_controls import IOSChatIO
        manager=self._scripts(selector) # Explicit component scope; canonical gate is unchanged.
        return TokenChatUI(IOSChatIO(manager.ui.io),intent,run)

    def _login_controls(self,selector,intent,run,origin):
        from adapters.token_login_ui import TokenLoginUI
        from ios.adapters.normal_login import IOSLoginIO
        manager=self._scripts(selector)
        return TokenLoginUI(IOSLoginIO(manager.ui.io,self._private_login_input(selector,run)),intent,run,origin)

    def _audio_controls(self, selector, intent):
        from adapters.token_audio_ui import TokenAudioUI
        from ios.adapters.normal_audio import IOSAudioIO
        manager = self._scripts(selector)
        return TokenAudioUI(IOSAudioIO(manager.ui.io), intent)

    def _script_file_picker(self, selector, directory):
        from adapters.token_script_file_ui import TokenScriptFilePicker
        ui, _observe, _binding = self._script_runtime(selector)
        return TokenScriptFilePicker(ui.io, directory)

    def cleanup(self, selector):
        chat_error=False
        try:
            owned=self.chat_capture_store(selector).read()
            if owned is not None:self._chat_capture(selector,owned['runId']).retire()
        except Exception:chat_error=True
        private_error=False
        try:
            owned=self.private_login_input_store(selector).read()
            if owned is not None:self._private_login_input(selector,owned['runId']).retire()
        except Exception:private_error=True
        probe_error=False
        try:
            if self.account_probe_store(selector).read() is not None:self._account_probe(selector).release()
        except Exception:probe_error=True
        origin_error=False
        try:
            if self.account_origin_store(selector).read() is not None:self._account_origin(selector).release()
        except Exception:origin_error=True
        store, script_error = self.script_store(selector), False
        try:
            owned = store.read()
            if owned is not None:
                scripts = self._scripts(selector)
                if owned['loadAttempted']:
                    scripts.invoke('scripts.manager.open', {})
                    scripts.invoke('scripts.stop', {'url': owned['source']})
                scripts.invoke('scripts.manager.close', {})
        except Exception:
            script_error = True
        # Always reach original native/session teardown if owned-source cleanup
        # fails, including when candidate inputs or installed binding are lost.
        result = super().cleanup(selector)
        need(not chat_error and not script_error and not private_error and not probe_error and not origin_error and store.read() is None
             and self.chat_capture_store(selector).read() is None
             and self.private_login_input_store(selector).read() is None
             and self.script_restart_store(selector).read() is None
             and self.script_restart_inputs_store(selector).read() is None
             and self.script_files_store(selector).read() is None and self.account_probe_store(selector).read() is None
             and self.account_origin_store(selector).read() is None)
        return result

    @staticmethod
    def native_process(client, session, target):
        value = client.execute(session, "mobile: overteProcessInfo",
                               {"bundleId": target["appId"]})
        if value is None:
            return None
        if (not isinstance(value, dict) or set(value) != {"bundleId", "pid", "foreground"}
                or value["bundleId"] != target["appId"]
                or type(value["pid"]) is not int or value["pid"] <= 0
                or type(value["foreground"]) is not bool):
            fail("native iOS process observation is invalid")
        return value

    def process_state(self, selector, client, session, state, target):
        process = self.native_process(client, session, target)
        if process is None:
            return {"running": False, "identity": None}
        identity = str(process["pid"])
        if state.get("processIdentity") not in (None, identity):
            raise RuntimeError("ASSERTION: iOS process restarted unexpectedly")
        state["processIdentity"] = identity
        self.save_session(selector, state)
        return {"running": True, "identity": identity}

    def assert_ios_process_identity(self, selector, client, session, state, target):
        # One fresh DVT observation verifies bundle, executable, PID and
        # foreground state together. No process facts are cached between calls.
        process = self.native_process(client, session, target)
        if process is None or process["foreground"] is not True:
            raise RuntimeError("ASSERTION: iOS application is not foregrounded")
        identity = str(process["pid"])
        expected = state.get("processIdentity")
        if expected is not None and expected != identity:
            raise RuntimeError("ASSERTION: iOS application process restarted during the E2E sequence")
        if expected is None:
            state["processIdentity"] = identity
            self.save_session(selector, state)
        return identity

    def command(self, selector, client, session, state, target, action, **arguments):
        identity = self.assert_ios_process_identity(selector, client, session, state, target)
        command_id = "ios-" + uuid.uuid4().hex
        payload = {"schemaVersion": 1, "commandId": command_id,
                   "action": action, **arguments}
        origin = target["testBuild"]["fixtureOrigin"]
        self.controlled_http_url(origin, "iOS fixture command origin")
        request = Request(origin + "/e2e-client-command.json",
                          data=json.dumps(payload).encode(), method="POST",
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            content = response.read(4097)
            if response.status != 200 or len(content) > 4096:
                fail("owned fixture did not accept the exact client command")
        if json.loads(content) != payload:
            fail("owned fixture changed the client command")
        remote = (f"@{target['appId']}:documents/"
                  f"{target['testBuild']['resultsDirectory']}/"
                  f"ios-client-command-{command_id[4:]}-result.json")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.assert_ios_process_identity(selector, client, session, state, target) != identity:
                fail("iOS client command crossed process identities")
            encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
            try:
                observed = json.loads(base64.b64decode(encoded, validate=True))
            except (ValueError, UnicodeError):
                time.sleep(0.05)
                continue
            if (isinstance(observed, dict) and set(observed) == {
                    "schemaVersion", "commandId", "sampleEpochMs"}
                    and type(observed["schemaVersion"]) is int and observed["schemaVersion"] == 1
                    and observed["commandId"] == command_id
                    and type(observed["sampleEpochMs"]) in (int, float)
                    and -1000 <= time.time() * 1000 - observed["sampleEpochMs"] <= 5000):
                if self.assert_ios_process_identity(
                        selector, client, session, state, target) != identity:
                    fail("iOS client command receipt crossed process identities")
                return command_id
            time.sleep(0.1)
        fail("fresh iOS client execution receipt was not observed")

    def review_entity_script(self, selector, client, session, state, target):
        identity = self.assert_ios_process_identity(selector, client, session, state, target)
        origin = target["testBuild"]["fixtureOrigin"]
        source = origin + "/scripted_interactable.js"
        scene = origin + target["testBuild"]["scenePath"]
        was_visible = self.probe_snapshot(selector, client, session, state, target)["tablet"]["open"]
        self.invoke(selector, "tablet.open", {})
        remote = f"@{target['appId']}:documents/{target['testBuild']['resultsDirectory']}/ios-entity-consent-result.json"
        try:
            for operation in ("review", "allow"):
                command_id = self.command(selector, client, session, state, target,
                    "entity-script-consent", operation=operation, source=source)
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
                    try:
                        document = json.loads(base64.b64decode(encoded, validate=True))
                    except (ValueError, UnicodeError):
                        time.sleep(0.1)
                        continue
                    if isinstance(document, dict) and document.get("commandId") == command_id:
                        native_consent.observation(document, int(identity), command_id, operation, source, scene)
                        # Validate the one-shot native receipt when it is read,
                        # before an independent Instruments process query can
                        # consume its three-second freshness window.
                        if self.assert_ios_process_identity(selector, client, session, state, target) != identity:
                            fail("entity consent crossed process identities")
                        break
                    time.sleep(0.1)
                else:
                    fail("fresh production entity consent dialog execution was not observed")
            return {"performed": True}
        finally:
            if not was_visible:
                self.invoke(selector, "tablet.close", {})

    def crash_ios_client(self, selector, client, session, state, target):
        identity = self.assert_ios_process_identity(selector, client, session, state, target)
        command_id = "ios-" + uuid.uuid4().hex
        payload = {"schemaVersion": 1, "commandId": command_id, "action": "native-crash"}
        origin = target["testBuild"]["fixtureOrigin"]
        self.controlled_http_url(origin, "native crash fixture origin")
        request = Request(origin + "/e2e-client-command.json", data=json.dumps(payload).encode(),
                          method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            content = response.read(4097)
            if response.status != 200 or len(content) > 4096 or json.loads(content) != payload:
                fail("owned fixture did not accept the exact native crash command")
        remote = f"@{target['appId']}:documents/{target['testBuild']['resultsDirectory']}/ios-crash-result.json"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
            try:
                document = json.loads(base64.b64decode(encoded, validate=True))
            except (ValueError, UnicodeError):
                time.sleep(0.1)
                continue
            if isinstance(document, dict) and document.get("commandId") == command_id:
                native_crash.observation(document, int(identity), command_id)
                break
            time.sleep(0.1)
        else:
            fail("actual native abort firing receipt was not observed")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            process = self.native_process(client, session, target)
            if process is None:
                self.reset_launch_state(selector, state)
                return {"crashed": True}
            if str(process["pid"]) != identity:
                fail("native crash unexpectedly replaced the configured process")
            time.sleep(0.1)
        fail("native abort firing did not terminate the original process")

    def reset_launch_state(self, selector, state):
        for key in ("processIdentity", "iosE2ELaunchCompleted", "iosE2ESceneUrl"):
            state.pop(key, None)
        self.save_session(selector, state)

    def launch_ios_test_build(self, selector, client, session, state, target, scene_url=None,
                              *, reactivate=False):
        new_process = state.get("iosE2ELaunchCompleted") is not True
        launched_at = int(time.time() * 1000)
        super().launch_ios_test_build(selector, client, session, state, target, scene_url,
                                     reactivate=reactivate)
        if not new_process:
            return
        # Documents survives process restarts. Wait for this launch's first
        # actual observation instead of returning a previous process's file
        # while its replacement script is still starting. This bounded wait
        # applies only at launch; normal stale observations remain failures.
        identity = self.assert_ios_process_identity(selector, client, session, state, target)
        self.wait_first_ios_probe(selector, client, session, state, target, identity, launched_at)

    def wait_first_ios_probe(self, selector, client, session, state, target, identity, launched_at):
        remote = f"@{target['appId']}:documents/{target['testBuild']['resultsDirectory']}/overte-probe.json"
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.assert_ios_process_identity(selector, client, session, state, target) != identity:
                fail("first iOS observation crossed launch process identities")
            encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
            try:
                observed = json.loads(base64.b64decode(encoded, validate=True))
            except (ValueError, UnicodeError):
                time.sleep(0.1)
                continue
            epoch = observed.get("sampleEpochMs") if isinstance(observed, dict) else None
            if type(epoch) is int and epoch >= launched_at:
                self.validate_probe(observed)
                self.assert_ios_process_identity(selector, client, session, state, target)
                return
            time.sleep(0.1)
        fail("this iOS launch did not produce a fresh first probe observation")

    @staticmethod
    def native_ui_enabled(target):
        value = target.get("nativeUiObservation")
        return (value == {"kind": "uikit-documents", "version": 1}
                and type(value.get("version")) is int)

    def native_ui_snapshot(self, client, session, target):
        process = self.native_process(client, session, target)
        if process is None or not process["foreground"]:
            fail("native UIKit observation requires the configured foreground process")
        origin = target["testBuild"]["fixtureOrigin"]
        self.controlled_http_url(origin, "iOS fixture command origin")
        def request_snapshot(timeout=5):
            command_id = "ios-" + uuid.uuid4().hex
            payload = {"schemaVersion": 1, "commandId": command_id,
                       "action": "native-ui-snapshot"}
            request = Request(origin + "/e2e-client-command.json",
                              data=json.dumps(payload).encode(), method="POST",
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=timeout) as response:
                content = response.read(4097)
                if response.status != 200 or len(content) > 4096 or json.loads(content) != payload:
                    fail("owned fixture did not accept the exact native UIKit snapshot request")
            return command_id
        command_id = request_snapshot()
        remote = (f"@{target['appId']}:documents/"
                  f"{target['testBuild']['resultsDirectory']}/ios-native-ui-request-result.json")
        deadline = time.monotonic() + 5
        last_rejection = None
        while time.monotonic() < deadline:
            encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
            retry_native_capture = False
            try:
                receipt = json.loads(base64.b64decode(encoded, validate=True))
                if (not isinstance(receipt, dict) or set(receipt) != {
                        "schemaVersion", "commandId", "observation"}
                        or type(receipt["schemaVersion"]) is not int or receipt["schemaVersion"] != 1
                        or receipt["commandId"] != command_id):
                    raise ValueError("native UIKit snapshot did not match this request")
                observation = receipt["observation"]
                # A native scene transition can produce valid:false. The
                # client retains that exact sample once per nonce, so rereading
                # it cannot observe readiness. Request another actual sample
                # within the same deadline; never accept the invalid sample.
                if isinstance(observation, dict) and set(observation) == {
                        "schemaVersion", "valid", "sampleEpochMs", "processId", "elements"}:
                    epoch = observation["sampleEpochMs"]
                    retry_native_capture = (
                        type(observation["schemaVersion"]) is int and observation["schemaVersion"] == 1
                        and observation["valid"] is False
                        and type(observation["processId"]) is int and observation["processId"] == process["pid"]
                        and observation["elements"] == []
                        and type(epoch) in (int, float) and math.isfinite(epoch)
                        and -1000 <= time.time() * 1000 - epoch <= 3000)
                document = native_ui.validate(observation, process["pid"])
            except (ValueError, UnicodeError) as error:
                last_rejection = error
                if retry_native_capture:
                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        command_id = request_snapshot(timeout=min(5, remaining))
                time.sleep(0.1)
                continue
            after = self.native_process(client, session, target)
            if after != process:
                raise RuntimeError("ASSERTION: native UIKit observation crossed process or foreground identities")
            return document
        raise RuntimeError("fresh native UIKit accessibility observation was not available") from last_rejection

    def ios_tablet_observation(self, selector, client, session, state, target):
        if not self.native_ui_enabled(target):
            return super().ios_tablet_observation(selector, client, session, state, target)
        self.assert_ios_process_identity(selector, client, session, state, target)
        document = self.native_ui_snapshot(client, session, target)
        return self.parse_ios_tablet_source(native_ui.source(document))

    def click_accessibility(self, client, session, identifier):
        target = getattr(self, "_native_ui_target", None)
        if target is None or not self.native_ui_enabled(target):
            return super().click_accessibility(client, session, identifier)
        document = self.native_ui_snapshot(client, session, target)
        matches = [e for e in document["elements"] if e["identifier"] == identifier
                   and e["visible"] and e["enabled"]]
        if len(matches) != 1:
            fail("native UIKit activation requires one observed visible enabled control")
        frame = matches[0]["frame"]
        x, y = round(frame["x"] + frame["width"] / 2), round(frame["y"] + frame["height"] / 2)
        body = {"actions": [{"type": "pointer", "id": "overte-native-widget", "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "origin": "viewport", "x": x, "y": y},
                {"type": "pointerDown", "button": 0}, {"type": "pause", "duration": 80},
                {"type": "pointerUp", "button": 0}]}]}
        try:
            client.call("POST", f"/session/{session}/actions", body)
        finally:
            client.call("DELETE", f"/session/{session}/actions")

    @classmethod
    def collaboration_configuration(cls, target):
        config = target.get("collaboration")
        if config is None:
            return None
        if (not isinstance(config, dict) or set(config) != {"kind", "stateUrl", "editUrl", "token", "domainId", "domainUrl"}
                or config["kind"] != "owned-domain"
                or any(not isinstance(value, str) for value in config.values())
                or not isinstance(config["token"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{40,128}", config["token"])
                or not isinstance(config["domainId"], str)
                or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", config["domainId"])
                or config["domainId"] == "00000000-0000-0000-0000-000000000000"):
            fail("independent iOS collaboration configuration is invalid")
        for kind in ("state", "edit"):
            parsed = urlsplit(config[kind + "Url"])
            if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port
                    or parsed.username or parsed.password or parsed.query or parsed.fragment
                    or parsed.path != "/v1/collaboration-" + kind):
                fail("independent iOS collaboration control must be on the owned loopback fixture")
        if self_origin := cls.controlled_http_url(config["stateUrl"], "actor state origin"):
            if self_origin != cls.controlled_http_url(config["editUrl"], "actor edit origin"):
                fail("independent actor state and edit must use one owned control server")
        domain = urlsplit(config["domainUrl"])
        fixture = urlsplit(target["testBuild"]["fixtureOrigin"])
        if (domain.scheme != "hifi" or domain.hostname != fixture.hostname or not domain.port
                or domain.username or domain.password):
            fail("independent collaboration domain must be on the owned lab host")
        return config

    def collaboration_request(self, target, kind, payload=None):
        config = self.collaboration_configuration(target)
        if config is None:
            fail("independent iOS collaboration is not configured")
        request = Request(config[kind + "Url"], data=None if payload is None else json.dumps(payload).encode(),
                          headers={"X-Overte-E2E-Token": config["token"], "Content-Type": "application/json"},
                          method="GET" if payload is None else "POST")
        try:
            with urlopen(request, timeout=5) as response:
                body = response.read(4097)
                if response.status != 200 or len(body) > 4096:
                    fail("independent actor response exceeded its contract")
                result = json.loads(body)
                if kind == "state":
                    actor_receipt(result)
                return result
        except HTTPError as error:
            if kind == "state" and error.code == 503:
                return None
            fail("independent actor rejected the requested operation")
        except (URLError, OSError, ValueError):
            fail("independent actor control is unavailable or malformed")

    def collaboration_snapshot(self, selector, client, session, state, target):
        config = self.collaboration_configuration(target)
        identity = self.assert_ios_process_identity(selector, client, session, state, target)
        probe = self.probe_snapshot(selector, client, session, state, target)
        if str(probe["domain"]["id"]).strip("{}").lower() != config["domainId"] or not probe["domain"]["connected"]:
            self.command(selector, client, session, state, target, "navigate", url=config["domainUrl"])
        remote = f"@{target['appId']}:documents/{target['testBuild']['resultsDirectory']}/e2e-collaboration-observation.json"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            actor = self.collaboration_request(target, "state")
            probe = self.probe_snapshot(selector, client, session, state, target)
            encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
            try:
                observed = json.loads(base64.b64decode(encoded, validate=True))
                portable = portable_observation(observed, actor, time.time() * 1000, probe) if actor else None
            except (ValueError, UnicodeError):
                portable = None
            if portable and probe["domain"]["connected"] and str(probe["domain"]["id"]).strip("{}").lower() == config["domainId"]:
                if self.assert_ios_process_identity(selector, client, session, state, target) != identity:
                    fail("collaboration crossed process identities")
                return portable
            self.assert_ios_process_identity(selector, client, session, state, target)
            time.sleep(0.1)
        fail("independent native actor and replicated client entity did not match")

    def native_text_command(self, selector, client, session, state, target, action):
        identity = self.assert_ios_process_identity(selector, client, session, state, target)
        command_id = "ios-" + uuid.uuid4().hex
        payload = {"schemaVersion": 1, "commandId": command_id,
                   "action": "text-fixture", "operation": action}
        origin = target["testBuild"]["fixtureOrigin"]
        self.controlled_http_url(origin, "native text fixture origin")
        request = Request(origin + "/e2e-client-command.json", data=json.dumps(payload).encode(),
                          method="POST", headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            body = response.read(4097)
            if response.status != 200 or len(body) > 4096 or json.loads(body) != payload:
                fail("owned fixture did not accept the exact native text command")
        remote = f"@{target['appId']}:documents/{target['testBuild']['resultsDirectory']}/ios-text-observation.json"
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.assert_ios_process_identity(selector, client, session, state, target) != identity:
                fail("native text command crossed process identities")
            encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
            try:
                observed = native_integration.text(json.loads(base64.b64decode(encoded, validate=True)), int(identity), command_id)
            except (ValueError, UnicodeError):
                time.sleep(0.1)
                continue
            self.assert_ios_process_identity(selector, client, session, state, target)
            return observed
        fail("fresh actual native text execution was not observed")

    def native_render_snapshot(self, selector, client, session, state, target):
        identity = self.assert_ios_process_identity(selector, client, session, state, target)
        remote = f"@{target['appId']}:documents/{target['testBuild']['resultsDirectory']}/ios-render-observation.json"
        encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
        document = native_integration.render(json.loads(base64.b64decode(encoded, validate=True)), int(identity))
        # A native presentation counter alone cannot prove visible pixels.
        # Classify a contemporaneous physical screenshot of the world surface.
        from io import BytesIO
        from PIL import Image
        image_data = base64.b64decode(client.call("GET", f"/session/{session}/screenshot"), validate=True)
        if not image_data or len(image_data) > 24 * 1024 * 1024:
            fail("native render screenshot exceeded its byte bound")
        with Image.open(BytesIO(image_data)) as image:
            if image.width * image.height > 24 * 1024 * 1024:
                fail("native render screenshot exceeded its pixel bound")
            # Exclude edge controls and status bars; require scene pixels in
            # the central world region, rather than a lit toolbar on black.
            crop = image.crop((image.width // 4, image.height // 4,
                               image.width * 3 // 4, image.height * 3 // 4)).convert("RGB")
            crop.thumbnail((128, 128))
            pixels = list(crop.getdata())
            non_black = sum(max(pixel) > 12 for pixel in pixels)
            black = non_black < max(1, len(pixels) // 100)
        self.assert_ios_process_identity(selector, client, session, state, target)
        return {"schemaVersion": 1, "backend": document["backend"],
                "hardwareAccelerated": document["hardwareAccelerated"],
                "surfaceVisible": document["surfaceVisible"], "blackFrame": black,
                "frameSequence": document["frameSequence"]}

    def invoke(self, selector, operation, values):
        if operation in SCRIPT_OPERATIONS:
            try:
                arguments = validate_operation_arguments(operation, values)
                return self._scripts(selector).invoke(operation, arguments)
            except Exception:
                raise RuntimeError('Normal iOS Script component operation failed') from None
        if operation in NORMAL_NAVIGATION_OPERATIONS:
            target = self.target(selector)
            profile = normal_navigation.configuration(target)
            if profile is None or operation not in self.advertised_capabilities(target):
                fail("normal iOS navigation requires its explicit native UI component profile")
            arguments = validate_operation_arguments(operation, values)
            if operation == 'places.goto' and arguments['url'] not in set(viewpoint_urls(profile['sceneUrl']).values()):
                fail("normal iOS navigation requires its exact owned scene viewpoint")
            client, session, state = self.ensure_session(selector)
            def continuity():
                self.assert_ios_process_identity(selector, client, session, state, target)
            def process():
                observed = self.native_process(client, session, target)
                if (observed is None or observed['foreground'] is not True
                        or str(observed['pid']) != state.get('processIdentity')):
                    fail("normal iOS navigation crossed its foreground process")
                return observed
            continuity()
            ui = NativeUI(client, session, continuity)
            native = NativeInput(client, session, target, process)
            flow = normal_navigation.IOSNavigation(ui, native, profile, state,
                lambda: self.save_session(selector, state))
            return flow.invoke(operation, arguments)
        if operation in normal_snapshot.OPERATIONS:
            target = self.target(selector)
            profile = normal_snapshot.configuration(target)
            if profile is None or operation not in self.advertised_capabilities(target):
                fail("normal iOS SNAP requires its explicit native input/file component profile")
            arguments = validate_operation_arguments(operation, values)
            artifact_directory = os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR')
            if not artifact_directory:
                fail("normal iOS SNAP requires the private module artifact directory")
            client, session, state = self.ensure_session(selector)
            def continuity():
                self.assert_ios_process_identity(selector, client, session, state, target)
            def process():
                observed = self.native_process(client, session, target)
                if (observed is None or observed['foreground'] is not True
                        or str(observed['pid']) != state.get('processIdentity')):
                    fail("normal iOS SNAP crossed its foreground process")
                return observed
            continuity()
            native = NativeInput(client, session, target, process)
            observed = native.capture()
            files = SnapshotFiles(client, session, target, process, observed['instance'], artifact_directory)
            flow = normal_snapshot.IOSSnapshot(NativeUI(client, session, continuity), native, files, profile, state,
                lambda: self.save_session(selector, state))
            return flow.invoke(operation, arguments)
        if operation in {"accessibility.snapshot", "tablet.open", "tablet.close", "tablet.activate", "tablet.snapshot"}:
            target = self.target(selector)
            if self.native_ui_enabled(target):
                self._native_ui_target = target
                try:
                    if operation == "accessibility.snapshot":
                        if values != {}:
                            fail("native UIKit accessibility observation does not accept arguments")
                        client, session, state = self.ensure_session(selector)
                        self.assert_ios_process_identity(selector, client, session, state, target)
                        return {"source": native_ui.source(self.native_ui_snapshot(client, session, target)), "artifact": None}
                    return super().invoke(selector, operation, values)
                finally:
                    del self._native_ui_target
        extended = self.CLIENT_OPERATIONS | self.NATIVE_OPERATIONS | self.INTEGRATION_OPERATIONS | self.COLLABORATION_OPERATIONS | {"app.process", "input.primary", "scene.load", "scene.reload", "app.install", "app.upgrade", "permission.snapshot", "permission.set", "entity-script.review"}
        if operation not in extended:
            return super().invoke(selector, operation, values)
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        if operation not in self.advertised_capabilities(target):
            fail("iOS native operation requires a physical observed test client")
        # Reject foreign fixture assets before creating a device session.
        if operation == "asset.load":
            if self.controlled_http_url(arguments["url"], "asset URL") != self.controlled_http_url(
                    target["testBuild"]["fixtureOrigin"], "fixture origin"):
                fail("iOS asset must belong to the owned fixture")
        if operation == "navigation.enter-domain":
            parsed = urlsplit(arguments["url"])
            fixture = urlsplit(target["testBuild"]["fixtureOrigin"])
            if parsed.hostname != fixture.hostname:
                fail("iOS navigation must remain on the owned lab host")
        upgrade = native_upgrade.configuration(target) if operation in {"app.install", "app.upgrade"} else None
        if upgrade is not None:
            if operation == "app.install" and arguments["path"] != upgrade["source"]["path"]:
                fail("native install requires the exact prepared source artifact")
            if operation == "app.upgrade" and arguments != {
                    "fromVersion":upgrade["source"]["version"],"toVersion":upgrade["candidate"]["version"]}:
                fail("native upgrade requires the exact prepared version pair")
        client, session, state = self.ensure_session(selector)
        if operation == "entity-script.review":
            return self.review_entity_script(selector, client, session, state, target)
        if operation in {"permission.snapshot", "permission.set"}:
            identity = self.assert_ios_process_identity(selector, client, session, state, target)
            if operation == "permission.snapshot":
                observed = self.invoke(selector, "voice.exchange", {
                    "schemaVersion": 1, "commandId": "ios-" + uuid.uuid4().hex,
                    "action": "status"})
                if self.assert_ios_process_identity(selector, client, session, state, target) != identity:
                    fail("native microphone observation crossed process identities")
                return native_permission.audio_snapshot(observed)
            receipt = client.execute(session, "mobile: overteMicrophonePermission", arguments)
            observed = native_permission.observation(receipt, identity)
            if str(receipt["processAfter"]) != identity or receipt["stoppedByOperatingSystem"]:
                actual = self.native_process(client, session, target)
                if actual is None or actual["pid"] != receipt["processAfter"] or not actual["foreground"]:
                    fail("native permission recovery did not restore the observed configured process")
                # Actual iPadOS Settings revocation terminates the configured
                # process. Re-establish a fresh native probe, and disclose that
                # lifecycle boundary only for an observed permission change.
                self.reset_launch_state(selector, state)
                # The driver already restored this exact process with the
                # controlled argv. Adopting it must not terminate it again.
                state["processIdentity"] = str(actual["pid"])
                self.wait_first_ios_probe(selector, client, session, state, target,
                                          str(actual["pid"]), receipt["recoveryLaunchEpochMs"])
                state["iosE2ELaunchCompleted"] = True
                state["iosE2ESceneUrl"] = target["testBuild"]["fixtureOrigin"] + target["testBuild"]["scenePath"]
                self.save_session(selector, state)
                if (operation == "permission.set" and receipt["stoppedByOperatingSystem"]
                        and str(receipt["processAfter"]) != identity
                        and observed["state"] == arguments["state"]):
                    return validate_operation_result("permission.set", {"performed": True,
                        "recovery": {"kind": "ios-settings-process-restart",
                            "permissionId": "microphone", "processBefore": receipt["processBefore"],
                            "processAfter": receipt["processAfter"], "stoppedByOperatingSystem": True}})
                raise RuntimeError("ASSERTION: iOS microphone permission change restarted the application")
            self.assert_ios_process_identity(selector, client, session, state, target)
            if operation == "permission.snapshot":
                return observed
            if observed["state"] != arguments["state"]:
                fail("native microphone switch did not become the requested state")
            return {"performed": True}
        if upgrade is not None:
            if operation == "app.upgrade":
                observed = self.probe_snapshot(selector,client,session,state,target)
                if observed["build"]["version"] != arguments["fromVersion"]:
                    fail("native upgrade did not start in the independently observed source version")
                client.execute(session,"mobile: terminateApp",{"bundleId":target["appId"]})
            if self.native_process(client,session,target) is not None:
                fail("native installation requires the configured application process to be stopped")
            role = "source" if operation == "app.install" else "candidate"
            receipt = client.execute(session,"mobile: overteInstallArtifact",{"role":role})
            if receipt != {"installed":True,"sha256":upgrade[role]["sha256"]}:
                fail("native installation service did not acknowledge the exact prepared package")
            self.reset_launch_state(selector,state)
            if operation == "app.install":
                return {"installed":True}
            self.launch_ios_test_build(selector,client,session,state,target,reactivate=True)
            actual = self.probe_snapshot(selector,client,session,state,target)
            if actual["build"]["version"] != arguments["toVersion"]:
                fail("native installed candidate did not report the requested version")
            return {"applied":True}
        if operation in {"scene.load", "scene.reload"}:
            url = arguments["url"]
            self.launch_ios_test_build(selector, client, session, state, target, url)
            # launch_ios_test_build deliberately preserves an existing process.
            # Therefore even scene.load must deliver a real scene command;
            # relaunch validation alone leaves an existing domain unchanged.
            nonce = self.request_ios_scene_reload(selector, client, session, state, target, url)
            return {"requested": True, "verification": "fixture-markers", "commandId": nonce}
        if operation == "input.primary":
            identity = self.assert_ios_process_identity(selector, client, session, state, target)
            try:
                nonce = self.command(selector, client, session, state, target, "primary-view", operation="prepare")
                remote = f"@{target['appId']}:documents/{target['testBuild']['resultsDirectory']}/ios-primary-observation.json"
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    self.assert_ios_process_identity(selector, client, session, state, target)
                    encoded = client.execute(session, "mobile: pullFile", {"remotePath": remote})
                    try:
                        point = native_primary.point(json.loads(base64.b64decode(encoded, validate=True)), nonce)
                    except (ValueError, UnicodeError):
                        time.sleep(0.1)
                        continue
                    self.tap_fractional_point(client, session, point, "independently picked world entity")
                    if self.assert_ios_process_identity(selector, client, session, state, target) != identity:
                        fail("world interaction crossed process identities")
                    return {"performed": True}
                fail("controlled world entity was not independently picked in the viewport")
            finally:
                self.command(selector, client, session, state, target, "primary-view", operation="restore")
        if operation in self.COLLABORATION_OPERATIONS:
            observed = self.collaboration_snapshot(selector, client, session, state, target)
            if operation == "collaboration.snapshot":
                return observed
            if arguments["entityName"] != observed["entityName"]:
                fail("collaboration edit requires the independently observed fixture entity")
            self.collaboration_request(target, "edit", {"schemaVersion": 1, **arguments})
            self.assert_ios_process_identity(selector, client, session, state, target)
            return {"performed": True}
        if operation in self.INTEGRATION_OPERATIONS:
            self.assert_ios_process_identity(selector, client, session, state, target)
            if operation == "render.snapshot":
                return self.native_render_snapshot(selector, client, session, state, target)
            if operation == "text.type":
                before = self.native_text_command(selector, client, session, state, target, "snapshot")
                if not before["focused"]:
                    fail("native keyboard input requires the controlled focused field")
                # XCTest sends actual native keyboard events. No assignment to
                # field values or submit counters is available in the bridge.
                client.execute(session, "mobile: overteTypeText", arguments)
                self.assert_ios_process_identity(selector, client, session, state, target)
                return {"performed": True}
            action = {"text.focus": "focus", "text.snapshot": "snapshot", "text.dismiss": "dismiss"}[operation]
            observed = self.native_text_command(selector, client, session, state, target, action)
            return observed if operation == "text.snapshot" else {"performed": True}
        if operation == "app.process":
            return self.process_state(selector, client, session, state, target)
        if operation == "app.stop":
            client.execute(session, "mobile: terminateApp", {"bundleId": target["appId"]})
            if self.native_process(client, session, target) is not None:
                fail("configured iOS process did not stop")
            self.reset_launch_state(selector, state)
            return {"stopped": True}
        if operation == "app.crash":
            if native_crash.enabled(target):
                return self.crash_ios_client(selector, client, session, state, target)
            self.assert_ios_process_identity(selector, client, session, state, target)
            client.execute(session, "mobile: overteAbortApp", {"bundleId": target["appId"]})
            if self.native_process(client, session, target) is not None:
                fail("configured iOS process did not exit after SIGABRT")
            self.reset_launch_state(selector, state)
            return {"crashed": True}
        if operation == "app.version":
            snapshot = self.probe_snapshot(selector, client, session, state, target)
            return {"schemaVersion": 1, "version": snapshot["build"]["version"]}
        if operation == "lifecycle.background":
            before = self.native_process(client, session, target)
            if before is None or not before["foreground"]:
                fail("native background requires the configured foreground process")
            client.execute(session, "mobile: backgroundApp", {"seconds": -1})
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                after = self.native_process(client, session, target)
                if after is None or after["pid"] != before["pid"]:
                    raise RuntimeError("ASSERTION: iOS background lost the original process")
                if not after["foreground"]:
                    return {"backgrounded": True}
                time.sleep(0.1)
            fail("iOS background transition was not observed")
        if operation == "navigation.enter-domain":
            self.command(selector, client, session, state, target, "navigate", **arguments)
            return {"requested": True}
        if operation == "asset.load":
            self.command(selector, client, session, state, target, "asset-load", **arguments)
            return {"requested": True}
        if operation == "setting.set":
            self.command(selector, client, session, state, target, "set-safe-setting", **arguments)
        elif operation == "audio.mute":
            self.command(selector, client, session, state, target, "set-audio-mute", **arguments)
        else:
            fail("unsupported extended iOS operation")
        return {"performed": True}


class IOSAdapter(IOSNativeMixin, AppiumAdapter):
    """Unbound component entrypoint; canonical native binding supplies its own base."""
