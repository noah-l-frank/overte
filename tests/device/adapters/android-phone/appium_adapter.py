#!/usr/bin/env python3
"""Phone Appium caller of the same verified installed-APK binding."""
# SPDX-License-Identifier: Apache-2.0
import ipaddress
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import uuid
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapter import PhoneAdapter, main, require
from adapters.appium.adapter import AppiumAdapter
from contracts import validate_operation_arguments
from adapters.normal_ui import NativeUI
from adapters.phone_navigation import PhoneNavigation
from navigation_observation import OPERATIONS as NAVIGATION_OPERATIONS
from adapters.android_snapshot_files import AndroidSnapshotFiles
from overte_phone_snapshot import (PhoneSnapshot, PhoneSnapshotUI, PrivateSnapshotState,
                                   OPERATIONS as SNAPSHOT_OPERATIONS)
from overte_phone_script_ui import PhoneScriptUI
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import (NormalScriptManager, read_native_diagnostic,
                                            DIAGNOSTIC_FILE)
from scripts_observation import OPERATIONS as SCRIPT_OPERATIONS
from create_observation import OPERATIONS as CREATE_OPERATIONS
from overte_phone_create_ui import PhoneCreateUI
from adapters.normal_create import NormalCreate
from adapters.native_feature_observation import NativeFeatureObservation, FILE as NATIVE_FEATURE_FILE
from adapters.native_account_probe import (NativeAccountProbe, AccountProbeOwner, OwnedAccountProbe,
    FILE as ACCOUNT_PROBE_FILE)
from adapters.native_chat_observation import NativeChatObservation, ChatCaptureOwner, OwnedChatCapture, FILE as CHAT_FILE
from adapters.native_chat_view import NativeChatView, FILE as CHAT_VIEW_FILE
from adapters.native_web_dom import NativeWebDOMObservation, FILE as WEB_DOM_FILE
from adapters.native_account_origin import NativeAccountOrigin, OwnedAccountOrigin, FILE as ACCOUNT_ORIGIN_FILE
from adapters.recorded_preview_evidence import (RecordedPreviewEvidence, AndroidPreviewFiles,
    FILE as RECORDED_PREVIEW_FILE)
from adapters.native_script_observation import NativeScriptObservation, FILE as SCRIPT_EXECUTION_FILE
from adapters.token_graphics_ui import TokenGraphicsUI
from overte_phone_graphics import PhoneGraphicsIO, FILE as GRAPHICS_UI_FILE
from adapters.token_chat_ui import TokenChatUI
from overte_phone_chat_controls import PhoneChatIO, FILE as CHAT_UI_FILE
from adapters.token_create_ui import TokenCreateUI
from overte_phone_create_controls import PhoneCreateIO, FILE as CREATE_UI_FILE
from adapters.token_login_ui import TokenLoginUI
from overte_phone_login import PhoneLoginIO, FILE as LOGIN_UI_FILE
from adapters.token_audio_ui import TokenAudioUI
from overte_phone_audio import PhoneAudioIO, FILE as AUDIO_UI_FILE
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.native_script_files import NativeScriptFiles, OwnedScriptFiles, FILE as SCRIPT_FIXTURE_FILE
from adapters.android_world_render import AndroidWorldRenderReceipts
from adapters.world_render_evidence import NativeWorldRenderCapture, FILE as WORLD_RENDER_FILE
from adapters.world_render_storage import NativeWorldRenderStorage
from adapters.owned_world_render import WorldRenderOwner, OwnedWorldRenderCapture
from overte_phone_script_files import PhoneScriptFileIO, FILE as SCRIPT_FILE_UI_FILE


class PhoneAppiumAdapter(AppiumAdapter):
    def __init__(self, candidate=None):
        super().__init__("android")
        self.candidate = candidate

    def selected_target(self, requested, action):
        require(type(requested) is str and bool(requested), "PHONE_APPIUM_TARGET_REQUIRED")
        self.target(requested)
        return requested

    def cleanup_target(self, requested):
        return self.selected_target(requested, "cleanup")

    def installed_identity(self, selector):
        target = self.target(selector)
        capabilities = target["capabilities"]
        device = capabilities.get("appium:udid")
        require(target.get("appId") == "io.github.noah_be.overte.phone" and type(target.get("physical")) is bool,
                "PHONE_APPIUM_PACKAGE_AND_DEVICE_CLASS_REQUIRED")
        require(capabilities.get("appium:appPackage") == "io.github.noah_be.overte.phone",
                "PHONE_APPIUM_PACKAGE_MAPPING_REQUIRED")
        require(type(device) is str and bool(device) and device.lower() != "auto"
                and "appium:avd" not in capabilities
                and target.get("process", {}).get("kind") == "adb"
                and target["process"].get("selector") in (None, device),
                "PHONE_APPIUM_ADB_BINDING_REQUIRED")
        # Local ADB cannot prove which application a remote grid selected.
        # Keep bound mode local; the original adapter retains remote diagnostics.
        host = urlsplit(target["serverUrl"]).hostname
        local = host == "localhost"
        if not local:
            try:
                local = ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
        require(local, "PHONE_APPIUM_LOCAL_SERVER_REQUIRED")
        if "appium:app" in capabilities:
            # A capability-driven installation is still a candidate installation,
            # never an unrestricted URL/filename trusted on configuration alone.
            PhoneAdapter.require_bound_operation(self, "app.install", {"path": capabilities["appium:app"]})
        binding = PhoneAdapter(self.candidate)
        if target["physical"]:
            self.attest_android_phone_profile(target)
        else:
            # PH-003 is specifically x86_64 virtual smoke, never an ARM64 claim.
            # Read the selected target; its private configuration is expectation,
            # not evidence that a physical phone is an emulator (or vice versa).
            binding.adb.require_connected(device)
            sdk = binding.adb.prop(device, "ro.build.version.sdk")
            gles = binding.adb.prop(device, "ro.opengles.version")
            require(binding.adb.prop(device, "ro.kernel.qemu") == "1"
                    and binding.adb.prop(device, "ro.product.cpu.abi") == "x86_64"
                    and sdk.isdigit() and int(sdk) >= 26
                    and gles.isdigit() and int(gles) >= 196610,
                    "PHONE_APPIUM_X86_64_EMULATOR_REQUIRED")
        return binding.installed_identity(device)

    def describe(self, selector):
        result = super().describe(selector)
        if self.candidate is not None:
            result["executionIdentity"] = self.installed_identity(selector)
            if self.target(selector)["physical"] is False:
                result["role"] = "phone-emulator-e2e"
        return result

    def advertised_capabilities(self, target):
        values = super().advertised_capabilities(target)
        if (getattr(self, 'candidate', None) is not None
                and self.controlled_android_client(target)
                and target.get('controls', {}).get('normalNavigation') is not None):
            values = sorted(set(values) | NAVIGATION_OPERATIONS)
        if (os.environ.get('OVERTE_PHONE_NORMAL_SNAPSHOT') == '1'
                and getattr(self, 'candidate', None) is not None
                and target.get('appId') == 'io.github.noah_be.overte.phone'
                and self.controlled_android_client(target)):
            values = sorted(set(values) | SNAPSHOT_OPERATIONS)
        script_enabled = os.environ.get('OVERTE_PHONE_NORMAL_SCRIPTS', '0')
        require(script_enabled in ('0', '1'), 'PHONE_NORMAL_SCRIPTS_CONFIGURATION_INVALID')
        if script_enabled == '1':
            require(getattr(self, 'candidate', None) is not None
                    and target.get('appId') == 'io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),
                    'PHONE_NORMAL_SCRIPTS_REQUIRES_BOUND_DEBUG_TARGET')
            values = sorted(set(values) | SCRIPT_OPERATIONS)
        create_enabled = os.environ.get('OVERTE_PHONE_NORMAL_CREATE', '0')
        require(create_enabled in ('0', '1'), 'PHONE_NORMAL_CREATE_CONFIGURATION_INVALID')
        if create_enabled == '1':
            require(getattr(self, 'candidate', None) is not None
                    and target.get('appId') == 'io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),
                    'PHONE_NORMAL_CREATE_REQUIRES_BOUND_DEBUG_TARGET')
            values = sorted(set(values) | CREATE_OPERATIONS)
        return values

    def script_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-session.json'))

    def _native_feature_observer(self, selector):
        # Internal native sources, not a complete feature.* capability. The
        # source hook is opt-in at build time and cannot be faked by an env flag.
        target = self.target(selector)
        require(self.candidate is not None and self.controlled_android_client(target),
                'PHONE_NATIVE_FEATURE_BOUND_DEBUG_TARGET_REQUIRED')
        _native, _scripts, context, check, installed = self.normal_feature_runtime(selector)
        client, session, _state = self.ensure_session(selector)
        device = target['capabilities']['appium:udid']
        binding = PhoneAdapter(self.candidate)

        def guard():
            check()
            require(self.installed_identity(selector) == installed, 'PHONE_NATIVE_FEATURE_INSTALL_CHANGED')

        def send(command):
            guard()
            self.write_android_client_command(client, session, target, command,
                {'running': True, 'identity': context['processIdentity']})

        return NativeFeatureObservation(send,
            lambda: binding.adb.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + NATIVE_FEATURE_FILE, attempts=1),
            lambda: binding.adb.epoch_milliseconds(device), guard,
            int(context['processIdentity'].split(':')[0]))

    def _web_dom(self,selector):
        _ui,_observe,context,check,installed=self.normal_feature_runtime(selector)
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        check();require(self.installed_identity(selector)==installed and native.pid==int(context['processIdentity'].split(':')[0]),
            'PHONE_WEB_DOM_CONTEXT_CHANGED')
        return NativeWebDOMObservation(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+WEB_DOM_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _chat_view(self,selector):
        _ui,_observe,context,check,installed=self.normal_feature_runtime(selector)
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        check();require(self.installed_identity(selector)==installed and native.pid==int(context['processIdentity'].split(':')[0]),
            'PHONE_CHAT_VIEW_CONTEXT_CHANGED')
        return NativeChatView(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CHAT_VIEW_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def chat_capture_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-chat-capture-owner.json'))

    def _chat_capture(self,selector,run):
        _ui,_observe,context,check,installed=self.normal_feature_runtime(selector)
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        owner=ChatCaptureOwner(self.chat_capture_store(selector),context,native.guard)
        reader=NativeChatObservation(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CHAT_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)
        check();require(self.installed_identity(selector)==installed and native.pid==int(context['processIdentity'].split(':')[0]),
            'PHONE_CHAT_CAPTURE_CONTEXT_CHANGED')
        return OwnedChatCapture(reader,owner,run)

    def account_origin_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-account-origin-owner.json'))

    def _account_origin(self, selector):
        _ui,_observe,context,check,_installed=self.normal_feature_runtime(selector)
        native=self._native_feature_observer(selector)
        original=native.read(0,require_account=True) # Actual current native Test instance, not a caller's claimed context.
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        source=NativeAccountOrigin(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+ACCOUNT_ORIGIN_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,original['instance'],monotonic=native.monotonic,sleep=native.sleep)
        check()
        return OwnedAccountOrigin(source,self.account_origin_store(selector),context)

    def account_probe_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-account-probe-owner.json'))

    def _account_probe(self, selector):
        # Internal observation only; actual private origin provisioning is mandatory.
        _ui, _observe, context, check, _installed = self.normal_feature_runtime(selector)
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        owner=AccountProbeOwner(self.account_probe_store(selector),context,native.guard)
        probe=NativeAccountProbe(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+ACCOUNT_PROBE_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,intent=owner.intent,monotonic=native.monotonic,sleep=native.sleep)
        check()
        return OwnedAccountProbe(probe,owner)

    def _recorded_preview_evidence(self, selector):
        native = self._native_feature_observer(selector)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        return RecordedPreviewEvidence(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + RECORDED_PREVIEW_FILE, attempts=1),
            AndroidPreviewFiles(transport, device, target['appId'], native.guard),
            native.clock_ms, native.guard, native.pid)

    def world_render_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-world-render-owner.json'))

    def _world_render_capture(self, selector):
        # Internal original-image prerequisite, not a full feature producer.
        _ui, _observe, context, check, _installed = self.normal_feature_runtime(selector)
        native = self._native_feature_observer(selector)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        receipts = AndroidWorldRenderReceipts(transport, device, target['appId'], native.guard)
        owner = WorldRenderOwner(self.world_render_store(selector), context, native.guard)
        options = dict(monotonic=native.monotonic, sleep=native.sleep)
        storage = NativeWorldRenderStorage(native.send, receipts.read, native.clock_ms, native.guard,
            native.pid, receipt_intent=owner.receipt_intent, **options)
        capture = NativeWorldRenderCapture(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + WORLD_RENDER_FILE, attempts=1),
            storage, native.clock_ms, native.guard, native.pid, intent=owner.intent, **options)
        check()
        return OwnedWorldRenderCapture(capture, storage, owner, receipts)

    def _script_execution_observer(self, selector):
        native = self._native_feature_observer(selector)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        return NativeScriptObservation(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + SCRIPT_EXECUTION_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)

    def script_files_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-files.json'))

    def _script_files(self, selector):
        _ui, _observe, context, check, _installed = self.normal_feature_runtime(selector)
        native = self._native_feature_observer(selector)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        files = NativeScriptFiles(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + SCRIPT_FIXTURE_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)
        check()
        return OwnedScriptFiles(files, self.script_files_store(selector), context)

    def _script_file_picker(self, selector, directory):
        # Internal primitive only. The full area still needs staged-byte
        # ownership, persistent dialog/source cleanup and execution/effect joins.
        native = self._native_feature_observer(selector)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        io = PhoneScriptFileIO(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + SCRIPT_FILE_UI_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)
        return TokenScriptFilePicker(io, directory)

    def _graphics_controls(self, selector, intent):
        # Internal ordinary-input component. Original render/pass/image and
        # full preference ownership/restart coordination remain mandatory.
        native = self._native_feature_observer(selector)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        io = PhoneGraphicsIO(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + GRAPHICS_UI_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)
        return TokenGraphicsUI(io, intent)

    def _create_controls(self, selector, intent):
        # Internal normal-input component. The caller owns the panel/entities
        # and persists intent; this never enables feature.create capabilities.
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        native_ui,_observe,_context,check,_installed=self.normal_feature_runtime(selector)
        ui=PhoneScriptUI(native_ui,target['appId'])
        check()
        io=PhoneCreateIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CREATE_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,tablet_shown=ui.tablet_visible)
        return TokenCreateUI(io,intent)

    def _chat_controls(self, selector, intent, run):
        # Input component only. The caller owns source/profile/settings/peer
        # intent; normal input effects never enable full Chat capabilities.
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        native_ui,_observe,_context,check,_installed=self.normal_feature_runtime(selector)
        ui=PhoneScriptUI(native_ui,target['appId']);check()
        io=PhoneChatIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CHAT_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,tablet_shown=ui.tablet_visible)
        return TokenChatUI(io,intent,run)

    def _login_controls(self, selector, intent, run, origin):
        # Input component only. The owner supplies actual private fixture
        # credentials and durable intent; full authentication remains closed.
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        io=PhoneLoginIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+LOGIN_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid)
        return TokenLoginUI(io,intent,run,origin)

    def _audio_controls(self, selector, intent):
        # Internal ordinary-input prerequisite. Caller must persist ownership;
        # no full Audio capability is advertised by this component.
        native = self._native_feature_observer(selector)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        io = PhoneAudioIO(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + AUDIO_UI_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)
        return TokenAudioUI(io, intent)

    def normal_scripts(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        require(operation in self.advertised_capabilities(target), 'PHONE_NORMAL_SCRIPTS_NOT_ENABLED')
        native, observe, context, check, installed = self.normal_feature_runtime(selector)
        flow = NormalScriptManager(PhoneScriptUI(native, target['appId']),
                                   observe, self.script_store(selector), context)
        # An enabled flag alone is insufficient: fail before UI input if the
        # selected installed candidate lacks the real diagnostic producer.
        flow.sample()
        result = flow.invoke(operation, arguments)
        check()
        require(self.installed_identity(selector) == installed, 'PHONE_NORMAL_SCRIPTS_INSTALL_CHANGED')
        return result

    def create_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-create-session.json'))

    def create_script_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-create-observer-session.json'))

    def normal_create(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        require(operation in self.advertised_capabilities(target), 'PHONE_NORMAL_CREATE_NOT_ENABLED')
        native, observe, context, check, installed = self.normal_feature_runtime(selector, include_entities=True)
        ui = PhoneCreateUI(native, target['appId'])
        scripts = NormalScriptManager(ui, observe, self.create_script_store(selector), context,
                                      source_kind='create-observer')
        flow = NormalCreate(ui, scripts, self.create_store(selector), context)
        try:
            result = flow.invoke(operation, arguments)
        except Exception:
            # A failed read-only preflight may have saved a sequence but owns
            # no input or source. Do not leave that metadata as cleanup work.
            if (flow.previous is None and not scripts.state['tabletOwned']
                    and not scripts.state['dialogOwned'] and scripts.state['source'] is None):
                scripts.store.discard(scripts.previous)
            raise
        check()
        require(self.installed_identity(selector) == installed, 'PHONE_NORMAL_CREATE_INSTALL_CHANGED')
        return result

    def normal_feature_runtime(self, selector, *, include_entities=False):
        target = self.target(selector)
        client, session, state = self.ensure_session(selector)
        installed = self.installed_identity(selector)
        process = self.process_state(selector, client, session, state, target)
        require(process.get('running') is True and isinstance(process.get('identity'), str)
                and re.fullmatch(r'[1-9][0-9]{0,9}:[0-9]{1,20}', process['identity']) is not None,
                'PHONE_NORMAL_SCRIPTS_PID_AND_START_TICKS_REQUIRED')
        fingerprint = self.snapshot_fingerprint(target)
        require(state.get('targetFingerprint') == fingerprint, 'PHONE_NORMAL_SCRIPTS_SESSION_TARGET_CHANGED')

        def check():
            current = self.read_session(selector)
            require(self.snapshot_fingerprint(self.target(selector)) == fingerprint
                    and current is not None and current.get('sessionId') == session
                    and current.get('generation') == state.get('generation')
                    and current.get('targetFingerprint') == fingerprint
                    and self.query_app_state(client, session, target) == 4
                    and self.process_state(selector, client, session, state, target) == process,
                    'PHONE_NORMAL_SCRIPTS_PROCESS_OR_SESSION_CHANGED')

        check()
        binding = PhoneAdapter(self.candidate)
        device = target['capabilities']['appium:udid']
        def observe(after):
            command_id = uuid.uuid4().hex
            self.write_android_client_command(client, session, target, {
                'schemaVersion': 1, 'commandId': command_id, 'action': 'normal-feature-observe',
                'includeAvatarEntities': include_entities}, process)
            return read_native_diagnostic(
                lambda: binding.adb.read_debug_app_file(device, target['appId'],
                                                        'files/overte-e2e/' + DIAGNOSTIC_FILE, attempts=1),
                lambda: binding.adb.epoch_milliseconds(device), check, after, expected_request=command_id)

        context = {key: installed[key] for key in ('sourceRevision', 'artifactSha256')}
        context.update(processIdentity=process['identity'], sessionId=session,
                       generation=state['generation'], targetFingerprint=fingerprint)
        return NativeUI(client, session, check), observe, context, check, installed

    def snapshot_store(self, selector):
        return PrivateSnapshotState(self.state_path(selector).with_name('phone-snapshot-session.json'))

    @staticmethod
    def snapshot_fingerprint(target):
        return hashlib.sha256(json.dumps(target, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def normal_snapshot(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        require(operation in self.advertised_capabilities(target), 'PHONE_NORMAL_SNAPSHOT_NOT_ENABLED')
        client, session, state = self.ensure_session(selector)
        installed = self.installed_identity(selector)
        process = self.process_state(selector, client, session, state, target)
        require(process.get('running') is True and isinstance(process.get('identity'), str)
                and re.fullmatch(r'[1-9][0-9]{0,9}:[0-9]{1,20}', process['identity']) is not None,
                'PHONE_NORMAL_SNAPSHOT_PID_AND_START_TICKS_REQUIRED')
        fingerprint = self.snapshot_fingerprint(target)
        require(state.get('targetFingerprint') == fingerprint, 'PHONE_NORMAL_SNAPSHOT_SESSION_TARGET_CHANGED')

        def check():
            current = self.read_session(selector)
            require(self.snapshot_fingerprint(self.target(selector)) == fingerprint
                    and current is not None and current.get('sessionId') == session
                    and current.get('generation') == state.get('generation')
                    and current.get('targetFingerprint') == fingerprint
                    and self.query_app_state(client, session, target) == 4
                    and self.process_state(selector, client, session, state, target) == process,
                    'PHONE_NORMAL_SNAPSHOT_PROCESS_OR_SESSION_CHANGED')

        check()
        context = {key: installed[key] for key in ('sourceRevision', 'artifactSha256')}
        context.update(processIdentity=process['identity'])
        binding = PhoneAdapter(self.candidate)
        files = AndroidSnapshotFiles(binding.adb, target['capabilities']['appium:udid'],
            target['appId'], context, check, os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR', ''))
        flow = PhoneSnapshot(PhoneSnapshotUI(client, session, check), files, self.snapshot_store(selector),
            context | {'sessionId': session, 'generation': state['generation'], 'targetFingerprint': fingerprint})
        result = flow.invoke(operation, arguments)
        check()
        require(self.installed_identity(selector) == installed, 'PHONE_NORMAL_SNAPSHOT_INSTALL_CHANGED')
        return result

    def cleanup(self, selector):
        chat_error=False
        try:
            owned=self.chat_capture_store(selector).read()
            if owned is not None:self._chat_capture(selector,owned['runId']).retire()
        except Exception:chat_error=True
        probe_error=False
        try:
            if self.account_probe_store(selector).read() is not None:
                self._account_probe(selector).release()
        except Exception:
            probe_error=True # Base teardown must still run; keep unresolved native ownership.
        origin_error=False
        try:
            if self.account_origin_store(selector).read() is not None:
                self._account_origin(selector).release()
        except Exception:
            origin_error=True
        create_store = self.create_store(selector)
        create_owned = create_store.read()
        create_error = None
        if create_owned is not None:
            try:
                self.normal_create(selector, 'create.reference.close', {'scriptUrl': create_owned['scriptUrl']})
            except Exception:
                create_error = True
        elif self.create_script_store(selector).read() is not None:
            create_error = True  # Unjoined source intent is never silently discarded.
        script_store = self.script_store(selector)
        script_owned = script_store.read()
        script_error = None
        if script_owned is not None:
            try:
                # Preserve source intent if candidate/process ownership can no
                # longer be established. Stopping the app is still attempted
                # below, but does not prove removal from persisted script state.
                if script_owned.get('loadAttempted'):
                    self.normal_scripts(selector, 'scripts.manager.open', {})
                    self.normal_scripts(selector, 'scripts.stop', {'url': script_owned['source']})
                self.normal_scripts(selector, 'scripts.manager.close', {})
            except Exception:
                script_error = True
        store = self.snapshot_store(selector)
        owned = store.read()
        if owned is not None:
            # Recovery must still work after candidate invalidation. Restrict it
            # to the unchanged private target and independently confirm stop;
            # shared Appium cleanup alone tolerates terminateApp errors.
            target = self.target(selector)
            device = target.get('capabilities', {}).get('appium:udid')
            require(target.get('appId') == 'io.github.noah_be.overte.phone'
                    and target.get('capabilities', {}).get('appium:appPackage') == target['appId']
                    and self.controlled_android_client(target)
                    and isinstance(device, str) and bool(device) and device.lower() != 'auto'
                    and target['process'].get('selector') in (None, device)
                    and self.snapshot_fingerprint(target) == owned['targetFingerprint'],
                    'PHONE_NORMAL_SNAPSHOT_CLEANUP_TARGET_CHANGED')
            binding = PhoneAdapter(None)
            binding.adb.require_connected(device)
            binding.adb.shell(device, 'am', 'force-stop', target['appId'])
            binding.wait_for_process_stopped(device)
        result = super().cleanup(selector)
        if owned is not None:
            require(result == {'cleaned': True}, 'PHONE_NORMAL_SNAPSHOT_CLEANUP_INCOMPLETE')
            store.discard()
        # A stopped process is not proof that persistent fixture files are gone.
        require(self.script_files_store(selector).read() is None, 'PHONE_SCRIPT_FILES_CLEANUP_INCOMPLETE')
        require(script_error is None and script_store.read() is None,
                'PHONE_NORMAL_SCRIPTS_CLEANUP_INCOMPLETE')
        require(create_error is None and create_store.read() is None
                and self.create_script_store(selector).read() is None,
                'PHONE_NORMAL_CREATE_CLEANUP_INCOMPLETE')
        require(not chat_error and self.chat_capture_store(selector).read() is None,
                'PHONE_CHAT_CAPTURE_CLEANUP_INCOMPLETE')
        require(not probe_error and self.account_probe_store(selector).read() is None,
                'PHONE_ACCOUNT_PROBE_CLEANUP_INCOMPLETE')
        require(not origin_error and self.account_origin_store(selector).read() is None,
                'PHONE_ACCOUNT_ORIGIN_CLEANUP_INCOMPLETE')
        return result

    def normal_navigation(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        require(operation in self.advertised_capabilities(target), 'PHONE_NORMAL_NAVIGATION_NOT_ENABLED')
        client, session, state = self.ensure_session(selector)
        installed = self.installed_identity(selector)
        process = self.process_state(selector, client, session, state, target)
        require(process.get('running') is True and isinstance(process.get('identity'), str)
                and bool(process['identity']), 'PHONE_NORMAL_NAVIGATION_PROCESS_REQUIRED')

        def check():
            require(self.query_app_state(client, session, target) == 4
                    and self.process_state(selector, client, session, state, target) == process,
                    'PHONE_NORMAL_NAVIGATION_PROCESS_CHANGED')

        ui = NativeUI(client, session, check)
        flow = PhoneNavigation(ui, target['controls']['normalNavigation'], state,
            installed, process['identity'], lambda: self.save_session(selector, state))
        result = flow.invoke(operation, arguments)
        check()
        require(self.installed_identity(selector) == installed, 'PHONE_NORMAL_NAVIGATION_INSTALL_CHANGED')
        return result

    def ensure_session(self, selector):
        if self.candidate is not None:
            self.installed_identity(selector)
        result = super().ensure_session(selector)
        if self.candidate is not None:
            # Appium session creation can itself install an app from capabilities.
            # Recheck before any requested operation executes, not just at the
            # enclosing runner's initial/final describe boundaries.
            self.installed_identity(selector)
        return result

    def invoke(self, selector, operation, values):
        PhoneAdapter.require_bound_operation(self, operation, values)
        if operation.startswith('places.'):
            return self.normal_navigation(selector, operation, values)
        if operation in SNAPSHOT_OPERATIONS:
            return self.normal_snapshot(selector, operation, values)
        if operation in SCRIPT_OPERATIONS:
            return self.normal_scripts(selector, operation, values)
        if operation in CREATE_OPERATIONS:
            return self.normal_create(selector, operation, values)
        result = super().invoke(selector, operation, values)
        if self.candidate is not None and operation == "app.install":
            self.installed_identity(selector)
        return result


if __name__ == "__main__":
    raise SystemExit(main(adapter_class=PhoneAppiumAdapter))
