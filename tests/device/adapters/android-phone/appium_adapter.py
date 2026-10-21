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
from copy import deepcopy
from contextlib import contextmanager
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adapter import PhoneAdapter, main, require
from adapters.appium.adapter import AppiumAdapter, WebDriver
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
from adapters.native_navigation_replies import NativeNavigationReplies, FILE as NAVIGATION_REPLIES_FILE
from adapters.native_process_presence import NativeProcessPresence, FILE as PROCESS_PRESENCE_FILE
from adapters.pending_commit_owner import NativePendingCommitOwner, FILE as PENDING_OWNER_FILE
from adapters.native_account_origin import NativeAccountOrigin, OwnedAccountOrigin, FILE as ACCOUNT_ORIGIN_FILE
from adapters.recorded_preview_evidence import (RecordedPreviewEvidence, AndroidPreviewFiles,
    FILE as RECORDED_PREVIEW_FILE)
from adapters.native_script_observation import NativeScriptObservation, FILE as SCRIPT_EXECUTION_FILE
from adapters.token_graphics_ui import TokenGraphicsUI
from overte_phone_graphics import PhoneGraphicsIO, FILE as GRAPHICS_UI_FILE
from overte_phone_graphics_surface import PhoneGraphicsSurface
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
from adapters.script_restart_handoff import ScriptRestartHandoff
from adapters.restart_inputs import RestartInputs, run_script_restart
from adapters.android_world_render import AndroidWorldRenderReceipts
from adapters.world_render_evidence import NativeWorldRenderCapture, FILE as WORLD_RENDER_FILE
from adapters.native_graphics_subject import NativeGraphicsSubject, FILE as GRAPHICS_SUBJECT_FILE
from adapters.native_avatar_render import NativeAvatarRender, FILE as AVATAR_RENDER_FILE
from adapters.native_world_model_draws import NativeWorldModelDraws, FILE as WORLD_MODEL_DRAWS_FILE
from adapters.native_phone_scene_loads import NativePhoneSceneLoads, FILE as SCENE_LOAD_FILE
from adapters.native_phone_web_runtime import NativePhoneWebRuntime, FILE as WEB_RUNTIME_FILE
from adapters.world_render_receipts import NativeWorldReceiptInventory, NativeWorldReceiptBatchFiles, INVENTORY_FILE as WORLD_RECEIPT_FILE
from adapters.world_render_storage import NativeWorldRenderStorage
from adapters.owned_world_render import WorldRenderOwner, OwnedWorldRenderCapture
from overte_phone_script_files import PhoneScriptFileIO, FILE as SCRIPT_FILE_UI_FILE
from overte_phone_script_measurements import PhoneScriptMeasurements, fixture_scope
from overte_phone_script_scope import transfer_file_scope
from overte_phone_script_history import PhoneScriptHistory, PhoneDurableScriptMeasurements
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_observation import PhoneScriptObservation
from overte_phone_script_actions import PhoneScriptActions
from overte_phone_script_feature import PhoneScriptFeature, ScriptFixtureReader
from overte_phone_authentication_feature import PhoneAuthenticationFeature, AuthenticationFixtureReader
from overte_phone_emote_controls import PhoneEmoteIO, FILE as EMOTE_UI_FILE
from adapters.token_emote_ui import TokenEmoteUI
from adapters.native_script_roots import NativeScriptRoots, FILE as SCRIPT_ROOTS_FILE
from adapters.native_script_work import NativeScriptWork, FILE as SCRIPT_WORK_FILE, command as script_work_command
from overte_phone_graphics_feature import PhoneGraphicsFeature
from overte_phone_graphics_fixture import GraphicsFixtureReader
from feature_journeys.witness import Client as FeatureFixtureClient
from adapters.feature_fixture_access import client as adapter_fixture_client
from overte_phone_account_fixture import origin as account_fixture_origin, launch_command as account_fixture_launch
from overte_phone_account_menu import PhoneAccountMenu

SCRIPT_FEATURE_OPERATIONS={'feature.scripts.'+kind for kind in ('act','observe','cleanup')}
AUTHENTICATION_FEATURE_OPERATIONS={'feature.authentication.'+kind for kind in ('act','observe','cleanup')}
GRAPHICS_FEATURE_OPERATIONS={'feature.graphics.'+kind for kind in ('act','observe','cleanup')}


def readonly_feature_command(command):
    """Closed observations and retirement of their own measurement leases."""
    require(type(command) is dict and type(command.get('schemaVersion')) is int and command['schemaVersion']==1
            and type(command.get('commandId')) is str and re.fullmatch('[0-9a-f]{32}',command['commandId']),
            'PHONE_READ_ONLY_COMMAND_REJECTED')
    action=command.get('action')
    if action in ('feature-native-observe','feature-script-observe','feature-world-render-observe','feature-script-roots-observe'):
        require(set(command)=={'schemaVersion','commandId','action'},'PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='feature-script-work-observe':
        script_work_command(command)
    elif action=='feature-script-files':
        from adapters.native_script_files import command as validate_files
        validate_files(command)
        require(command['operation'] in ('observe','locate'),'PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='feature-process-presence':
        from adapters.native_process_presence import command as validate_presence
        validate_presence(command)
    elif action=='feature-avatar-render-observe':
        from adapters.native_avatar_render import command as validate_avatar_render
        validate_avatar_render(command)
    elif action=='feature-world-model-draws-observe':
        from adapters.native_world_model_draws import command as validate_model_draws
        validate_model_draws(command)
    elif action=='feature-graphics-subject-observe':
        from adapters.native_graphics_subject import command as validate_subject
        validate_subject(command)
    elif action=='feature-scene-load-observe':
        from adapters.native_phone_scene_loads import command as validate_scene_load
        validate_scene_load(command)
    elif action=='feature-phone-web-runtime-observe':
        from adapters.native_phone_web_runtime import command as validate_web_runtime
        validate_web_runtime(command)
    elif action=='feature-world-render-storage':
        from adapters.world_render_storage import command as validate_storage
        validate_storage(command)
    elif action=='feature-world-render-receipt':
        from adapters.world_render_receipts import command as validate_receipt
        validate_receipt(command)
    elif action=='feature-world-render-receipts':
        from adapters.world_render_receipts import inventory_command
        inventory_command(command)
    elif action=='feature-account-origin':
        from adapters.native_account_origin import command as validate_origin
        validate_origin(command)
        require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='feature-account-probe':
        from adapters.native_account_probe import command as validate_probe
        validate_probe(command) # Only read/release/inspect; no URL or credentials.
    elif action in ('phone-script-file-ui','phone-login-ui','phone-graphics-ui','phone-emote-ui'):
        require(set(command)=={'schemaVersion','commandId','action','request'}
                and type(command['request']) is dict
                and command['request']==dict(schemaVersion=1,commandId=command['commandId'],action='observe')
                and type(command['request']['schemaVersion']) is int,'PHONE_READ_ONLY_COMMAND_REJECTED')
    else:require(False,'PHONE_READ_ONLY_COMMAND_REJECTED')


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
        full_scripts=os.environ.get('OVERTE_PHONE_FEATURE_SCRIPTS','0')
        require(full_scripts in ('0','1'),'PHONE_FEATURE_SCRIPTS_CONFIGURATION_INVALID')
        if full_scripts=='1':
            require(script_enabled=='1','PHONE_FEATURE_SCRIPTS_REQUIRES_NORMAL_SCRIPTS')
            self._feature_fixture_client()
            values=sorted(set(values)|SCRIPT_FEATURE_OPERATIONS)
        full_authentication=os.environ.get('OVERTE_PHONE_FEATURE_AUTHENTICATION','0')
        require(full_authentication in ('0','1'),'PHONE_FEATURE_AUTHENTICATION_CONFIGURATION_INVALID')
        if full_authentication=='1':
            require(self.account_fixture_configuration(target) is not None,'PHONE_FEATURE_AUTHENTICATION_REQUIRES_ACCOUNT_FIXTURE_LAUNCH')
            self._feature_fixture_client()
            values=sorted(set(values)|AUTHENTICATION_FEATURE_OPERATIONS)
        full_graphics=os.environ.get('OVERTE_PHONE_FEATURE_GRAPHICS','0')
        require(full_graphics in ('0','1'),'PHONE_FEATURE_GRAPHICS_CONFIGURATION_INVALID')
        if full_graphics=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),'PHONE_FEATURE_GRAPHICS_REQUIRES_BOUND_DEBUG_TARGET')
            self._graphics_configuration()
            self._feature_fixture_client()
            values=sorted(set(values)|GRAPHICS_FEATURE_OPERATIONS)
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

    def _native_feature_observer(self, selector, *, read_only=False):
        # Internal native sources, not a complete feature.* capability. The
        # source hook is opt-in at build time and cannot be faked by an env flag.
        target = self.target(selector)
        require(self.candidate is not None and self.controlled_android_client(target),
                'PHONE_NATIVE_FEATURE_BOUND_DEBUG_TARGET_REQUIRED')
        _native, _scripts, context, check, installed = self.normal_feature_runtime(selector, read_only=read_only)
        client, session, _state = self.existing_session(selector) if read_only else self.ensure_session(selector)
        device = target['capabilities']['appium:udid']
        binding = PhoneAdapter(self.candidate)

        def guard():
            check()
            require(self.installed_identity(selector) == installed, 'PHONE_NATIVE_FEATURE_INSTALL_CHANGED')

        def send(command):
            if read_only:readonly_feature_command(command)
            guard()
            self.write_android_client_command(client, session, target, command,
                {'running': True, 'identity': context['processIdentity']})

        return NativeFeatureObservation(send,
            lambda: binding.adb.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + NATIVE_FEATURE_FILE, attempts=1),
            lambda: binding.adb.epoch_milliseconds(device), guard,
            int(context['processIdentity'].split(':')[0]))

    def _process_presence(self, selector, *, read_only=False):
        native = self._native_feature_observer(selector, read_only=read_only)
        target = self.target(selector); device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        return NativeProcessPresence(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + PROCESS_PRESENCE_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid, monotonic=native.monotonic, sleep=native.sleep)

    def _navigation_replies(self,selector):
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeNavigationReplies(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+NAVIGATION_REPLIES_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _pending_owner(self, selector, intent=None):
        _ui,_observe,context,check,installed=self.normal_feature_runtime(selector)
        native=self._native_feature_observer(selector)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        check();require(self.installed_identity(selector)==installed and native.pid==int(context['processIdentity'].split(':')[0]),
            'PHONE_PENDING_OWNER_CONTEXT_CHANGED')
        return NativePendingCommitOwner(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+PENDING_OWNER_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,intent=intent,monotonic=native.monotonic,sleep=native.sleep)

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

    def _account_origin(self, selector, *, read_only=False):
        _ui,_observe,context,check,_installed=self.normal_feature_runtime(selector,read_only=read_only)
        native=self._native_feature_observer(selector,read_only=read_only)
        original=native.read(0,require_account=True) # Actual current native Test instance, not a caller's claimed context.
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        source=NativeAccountOrigin(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+ACCOUNT_ORIGIN_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,original['instance'],monotonic=native.monotonic,sleep=native.sleep)
        check()
        result=OwnedAccountOrigin(source,self.account_origin_store(selector),context)
        result.native_admission=deepcopy(original) # An owning ledger must validate this extra original query too.
        return result

    def account_probe_store(self, selector, *, role='primary'):
        require(role in ('primary','actor'),'PHONE_ACCOUNT_PROBE_ROLE_REQUIRED')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-account-'+('actor-' if role=='actor' else '')+'probe-owner.json'))

    @staticmethod
    def _feature_fixture_client():
        try:
            return adapter_fixture_client(Path(os.environ.get('OVERTE_PHONE_FEATURE_FIXTURE_CONFIG','')),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
        except (OSError,RuntimeError,ValueError,TypeError,KeyError):
            raise ValueError('PHONE_FEATURE_FIXTURE_READER_CONFIGURATION_INVALID') from None

    def authentication_samples_store(self, selector, role, stage):
        require(role in ('primary','actor') and type(stage) is int and 0<=stage<=3,
                'PHONE_AUTHENTICATION_SOURCE_SCOPE_REQUIRED')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-authentication-'+role+'-'+str(stage)+'-samples.json'))

    def authentication_actions_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-authentication-actions.json'))

    def authentication_feature_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-authentication-feature.json'))

    def authentication_retirement_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-authentication-retirement.json'))

    def authentication_restart_store(self, selector, stage):
        require(type(stage) is int and 1<=stage<=3,'PHONE_AUTHENTICATION_RESTART_SCOPE_REQUIRED')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-authentication-restart-'+str(stage)+'.json'))

    def _authentication_actions(self, selector, client, run):
        from overte_phone_authentication_actions import PhoneAuthenticationActions
        return PhoneAuthenticationActions(self,selector,client,run)

    def _authentication_feature(self, selector, run, *, role='primary', client=None):
        if client is None:
            require(role=='primary','PHONE_AUTHENTICATION_ACTOR_REQUIRES_SEPARATE_CLIENT')
            client=self._feature_fixture_client()
        return PhoneAuthenticationFeature(self,selector,AuthenticationFixtureReader(client,run),role=role)

    def _authentication_restart_stopped(self, selector, old_binding):
        return self._feature_restart_stopped(selector,old_binding,'AUTHENTICATION')

    def _graphics_restart_stopped(self, selector, old_binding):
        return self._feature_restart_stopped(selector,old_binding,'GRAPHICS')

    def _feature_restart_stopped(self, selector, old_binding, scope):
        require(scope in ('AUTHENTICATION','GRAPHICS'),'PHONE_RESTART_SCOPE_INVALID')
        target=self.target(selector)
        require(self.snapshot_fingerprint(target)==old_binding['targetFingerprint'],
                'PHONE_'+scope+'_RESTART_TARGET_CHANGED')
        installed=self.installed_identity(selector)
        require(all(installed[key]==old_binding[key] for key in ('sourceRevision','artifactSha256')),
                'PHONE_'+scope+'_RESTART_INSTALL_CHANGED')
        client,session,state=self.existing_session(selector)
        require(session==old_binding['sessionId'] and state.get('generation')==old_binding['generation'],
                'PHONE_'+scope+'_RESTART_SESSION_CHANGED')
        status=self.query_app_state(client,session,target)
        require(type(status) is int and status in (1,2,3,4),'PHONE_'+scope+'_RESTART_OS_STATE_UNAVAILABLE')
        process=self.process_state(selector,client,session,state,target)
        running=status>=2 or process.get('running') is True
        return dict(running=running,identity=process.get('identity') if running else None)

    def _account_probe(self, selector, *, read_only=False, role='primary'):
        # Internal observation only; actual private origin provisioning is mandatory.
        _ui, _observe, context, check, _installed = self.normal_feature_runtime(selector,read_only=read_only)
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        owner=AccountProbeOwner(self.account_probe_store(selector,role=role),context,native.guard)
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

    def world_render_store(self, selector, *, role='primary'):
        require(role in ('primary','actor'),'PHONE_WORLD_RENDER_ROLE_INVALID')
        name='phone-world-render-owner.json' if role=='primary' else 'phone-world-render-actor-owner.json'
        return PrivateFeatureState(self.state_path(selector).with_name(name))

    @staticmethod
    def _graphics_configuration(metadata=None):
        try:
            from feature_journeys.evidence import rectangle
            if metadata is None:
                policy=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_GRAPHICS_IMAGE_POLICY',''))).read()
                root=Path(os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
            else:
                require(type(metadata) is dict and type(metadata.get('graphicsFeatureVersion')) is int
                        and metadata['graphicsFeatureVersion']==1,'PHONE_GRAPHICS_ORIGINAL_CONFIGURATION_REQUIRED')
                policy=metadata['imagePolicy'];root=Path(metadata['artifactRoot'])
            require(type(policy) is dict and set(policy)=={'source','marker','subject'} and policy['source']=='world-render-target',
                    'PHONE_GRAPHICS_IMAGE_POLICY_REQUIRED')
            marker=rectangle(policy['marker'],(4096,4096));subject=rectangle(policy['subject'],(4096,4096))
            require(marker[2]-marker[0]>=128 and marker[3]-marker[1]>=32
                    and not (max(marker[0],subject[0])<min(marker[2],subject[2]) and max(marker[1],subject[1])<min(marker[3],subject[3])),
                    'PHONE_GRAPHICS_IMAGE_POLICY_REQUIRED')
            PrivateFeatureState(root/'graphics-configuration-boundary.json')._parent()
            return root,deepcopy(policy)
        except (OSError,RuntimeError,ValueError,TypeError,KeyError):
            raise ValueError('PHONE_FEATURE_GRAPHICS_CONFIGURATION_INVALID') from None

    def graphics_feature_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-feature.json'))

    def graphics_retirement_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-retirement.json'))

    def _graphics_feature(self, selector, run, *, role='primary', client=None, retirement=False):
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_GRAPHICS_REQUIRES_BOUND_DEBUG_TARGET')
        if client is None:
            require(role=='primary','PHONE_GRAPHICS_ACTOR_REQUIRES_SEPARATE_CLIENT')
            client=self._feature_fixture_client()
        require(type(retirement) is bool,'PHONE_GRAPHICS_ORIGINAL_CONFIGURATION_REQUIRED')
        metadata=None
        if role=='actor' or retirement:
            metadata=self.graphics_feature_store(selector).read() or self.graphics_retirement_store(selector).read()
            require(type(metadata) is dict and metadata.get('runId')==run
                    and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
                    'PHONE_GRAPHICS_ORIGINAL_CONFIGURATION_REQUIRED')
        root,policy=self._graphics_configuration(metadata)
        return PhoneGraphicsFeature(self,selector,GraphicsFixtureReader(client,run),root,policy,role=role)

    def graphics_scene_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-scene.json'))

    def graphics_preferences_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-preferences.json'))

    def graphics_background_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-background.json'))

    def graphics_restart_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-restart.json'))

    def graphics_restart_inputs_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-restart-inputs.json'))

    def _graphics_lifecycle_status(self, selector, binding):
        # OS/process observation remains available while native/UI foreground
        # guards are correctly unavailable. No session creation or activation.
        with self.existing_input_session(selector):
            target=self.target(selector);fingerprint=self.snapshot_fingerprint(target)
            installed=self.installed_identity(selector)
            client,session,state=self.existing_session(selector)
            require(fingerprint==binding['targetFingerprint'] and session==binding['sessionId']
                    and state.get('generation')==binding['generation']
                    and all(installed[key]==binding[key] for key in ('sourceRevision','artifactSha256')),
                    'PHONE_GRAPHICS_LIFECYCLE_BINDING_CHANGED')
            before=self.query_app_state(client,session,target)
            process=self.process_state(selector,client,session,state,target)
            after=self.query_app_state(client,session,target)
            require(type(before) is int and before in (2,3,4) and after==before
                    and process.get('running') is True and process.get('identity')==binding['processIdentity']
                    and self.snapshot_fingerprint(self.target(selector))==fingerprint,
                    'PHONE_GRAPHICS_LIFECYCLE_PROCESS_OR_OS_STATE_CHANGED')
            observed={key:installed[key] for key in ('sourceRevision','artifactSha256')}
            observed.update(processIdentity=process['identity'],sessionId=session,generation=state['generation'],targetFingerprint=fingerprint)
            return dict(binding=observed,foreground=after==4,running=process['running'],appState=after)

    def _emote_lifecycle_status(self,selector,binding):
        # Reuse the original Android OS/process observer. It does not read or
        # mutate Graphics settings and remains available in the background.
        return self._graphics_lifecycle_status(selector,binding)

    def graphics_samples_store(self, selector, role, stage):
        require(role in ('primary','actor') and type(stage) is int and stage in (0,1),
                'PHONE_GRAPHICS_SOURCE_SCOPE_REQUIRED')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-'+role+'-'+str(stage)+'-samples.json'))

    def graphics_lifetime_store(self, selector, role, stage):
        require(role in ('primary','actor') and type(stage) is int and stage in (0,1),
                'PHONE_GRAPHICS_LIFETIME_SCOPE_REQUIRED')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-'+role+'-'+str(stage)+'-lifetime.json'))

    def graphics_observer_store(self, selector, role):
        require(role in ('primary','actor'),'PHONE_GRAPHICS_OBSERVER_SCOPE_REQUIRED')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-graphics-'+role+'-observer.json'))

    def _web_runtime_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_WEB_RUNTIME_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneWebRuntime(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+WEB_RUNTIME_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _avatar_render_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_AVATAR_RENDER_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeAvatarRender(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+AVATAR_RENDER_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _world_model_draws_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_MODEL_DRAWS_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeWorldModelDraws(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+WORLD_MODEL_DRAWS_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _graphics_subject_observer(self, selector, *, read_only=False):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return NativeGraphicsSubject(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],
                'files/overte-e2e/'+GRAPHICS_SUBJECT_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _scene_load_observer(self, selector, *, read_only=True):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneSceneLoads(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+SCENE_LOAD_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _world_render_capture(self, selector, *, read_only=False, role='primary', require_trace=False, require_frame_view=False):
        # Internal original-image prerequisite, not a full feature producer.
        require(type(read_only) is bool and type(require_trace) is bool and type(require_frame_view) is bool and role in ('primary','actor')
                and (role!='actor' or read_only),'PHONE_WORLD_RENDER_SCOPE_INVALID')
        _ui, _observe, context, check, _installed = self.normal_feature_runtime(selector,read_only=read_only)
        native = self._native_feature_observer(selector,read_only=read_only)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        original = AndroidWorldRenderReceipts(transport, device, target['appId'], native.guard)
        owner = WorldRenderOwner(self.world_render_store(selector,role=role), context, native.guard, role=role)
        options = dict(monotonic=native.monotonic, sleep=native.sleep)
        storage = NativeWorldRenderStorage(native.send, original.read, native.clock_ms, native.guard,
            native.pid, receipt_intent=owner.receipt_intent, **options)
        cleanup = NativeWorldReceiptInventory(native.send,
            lambda: transport.read_debug_app_file(device,target['appId'],
                'files/overte-e2e/'+WORLD_RECEIPT_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,owner.owned,lambda:storage.instance,**options)
        receipts = NativeWorldReceiptBatchFiles(original,cleanup)
        capture = NativeWorldRenderCapture(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + WORLD_RENDER_FILE, attempts=1),
            storage, native.clock_ms, native.guard, native.pid, intent=owner.intent,
            require_trace=require_trace, require_frame_view=require_frame_view, **options)
        check()
        return OwnedWorldRenderCapture(capture, storage, owner, receipts)

    def _script_execution_observer(self, selector, *, read_only=False):
        native = self._native_feature_observer(selector, read_only=read_only)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        return NativeScriptObservation(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + SCRIPT_EXECUTION_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)

    def script_files_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-files.json'))

    def _script_measurements(self, selector, run, fixture_url, *, read_only=False, fixture_state='present', retired_owner=None):
        # Actual original acquisitions only. Full run/publisher/cleanup and
        # durable cross-invocation history remain separate mandatory ownership.
        require(fixture_state in ('present','absent') and (retired_owner is None or fixture_state=='absent'),
                'PHONE_SCRIPT_FIXTURE_STATE_INVALID')
        require(fixture_state=='present' or read_only is True,'PHONE_SCRIPT_ABSENCE_REQUIRES_READ_ONLY')
        retired_owner=deepcopy(retired_owner)
        real_store=self.script_files_store(selector)
        require(retired_owner is None or real_store.read() is None,'PHONE_SCRIPT_RETIRED_SCOPE_HAS_CURRENT_OWNER')
        native = self._native_feature_observer(selector, read_only=read_only)
        _ui, observe, binding, check, _installed = self.normal_feature_runtime(selector, read_only=read_only)
        target = self.target(selector); device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        def original(name):
            return lambda: transport.read_debug_app_file(device, target['appId'], 'files/overte-e2e/' + name, attempts=1)
        def guard():
            check(); native.guard()
            require(retired_owner is None or real_store.read() is None,'PHONE_SCRIPT_RETIRED_SCOPE_HAS_CURRENT_OWNER')
        storage = NativeScriptFiles(native.send, original(SCRIPT_FIXTURE_FILE), native.clock_ms, guard, native.pid)
        class RetiredScope:
            # Original private cleanup scope only; never current file evidence.
            def read(self):return deepcopy(retired_owner)
        files = OwnedScriptFiles(storage, real_store if retired_owner is None else RetiredScope(), binding)
        require(files.owned()['runId'] == run, 'PHONE_SCRIPT_MEASUREMENTS_OWNED_RUN_REQUIRED')
        def verify():
            require(files.owned()['runId']==run,'PHONE_SCRIPT_MEASUREMENTS_OWNED_RUN_REQUIRED')
            if fixture_state=='present':return files.verify()
            location=files.locate()
            require(location['exists'] is False,'PHONE_SCRIPT_BASELINE_FILES_NOT_ABSENT')
            return location['directory']
        directory = verify()
        execution = NativeScriptObservation(native.send, original(SCRIPT_EXECUTION_FILE), native.clock_ms, guard, native.pid)
        ui = PhoneScriptFileIO(native.send, original(SCRIPT_FILE_UI_FILE), native.clock_ms, guard, native.pid)
        result=PhoneScriptMeasurements(run, directory, fixture_url, execution, ui, observe, native, verify, guard,
                                       file_instance=lambda:files.native.instance)
        # Original file envelope is private input to the full coordinator's
        # file-clock/resource join, never an expected availability result.
        result.file_observation=lambda:deepcopy(storage.last_packet)
        return result

    def script_history_store(self, selector, role, *, stage=0):
        require(role in ('primary','actor'),'PHONE_SCRIPT_HISTORY_ROLE_REQUIRED')
        require(type(stage) is int and stage in (0,1),'PHONE_SCRIPT_HISTORY_STAGE_INVALID')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-'+role+'-history'+('-restart' if stage else '')+'.json'))

    def _script_durable_measurements(self, selector, run, fixture_url, *, role, fixture_state='present', retired_owner=None, source_lock=None, stage=0):
        # Both roles acquire originals through existing-session/read-only
        # admission. Private histories and source requests are role-separated.
        require(role in ('primary','actor'),'PHONE_SCRIPT_HISTORY_ROLE_REQUIRED')
        lock_path=self.state_path(selector).with_name('phone-script-sources.lock')
        source_lock=PhoneScriptSourceLock(lock_path) if source_lock is None else source_lock
        require(isinstance(source_lock,PhoneScriptSourceLock) and source_lock.path==lock_path,
                'PHONE_SCRIPT_HISTORY_SOURCE_LOCK_REQUIRED')
        with source_lock.held():
            reader=self._script_measurements(selector,run,fixture_url,read_only=True,fixture_state=fixture_state,retired_owner=retired_owner)
            _ui,_observe,binding,check,_installed=self.normal_feature_runtime(selector,read_only=True)
            check();reader.guard()
            store=self.script_history_store(selector,role,stage=stage)
            history=PhoneScriptHistory(store,binding,run,role,reader.directory,fixture_url)
            check();reader.guard()
            return PhoneDurableScriptMeasurements(reader,history,source_lock=source_lock)

    def script_actions_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-actions.json'))

    def _script_actions(self, selector, run, fixture_url):
        return PhoneScriptActions(self,selector,run,fixture_url)

    def script_feature_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-feature.json'))

    def script_retirement_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-retirement.json'))

    def _script_feature(self, selector, run, *, role='primary', client=None):
        if client is None:
            require(role=='primary','PHONE_SCRIPT_ACTOR_REQUIRES_SEPARATE_CLIENT')
            client=self._feature_fixture_client()
        return PhoneScriptFeature(self,selector,ScriptFixtureReader(client,run),role=role)

    def account_fixture_configuration(self,target):
        enabled=os.environ.get('OVERTE_PHONE_ACCOUNT_FIXTURE','0')
        require(enabled in ('0','1'),'PHONE_ACCOUNT_FIXTURE_CONFIGURATION_INVALID')
        if enabled=='0':return None
        require(self.candidate is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target) and target.get('scene',{}).get('kind')=='android-debug-e2e'
                and target.get('capabilities',{}).get('appium:autoLaunch') is False,
                'PHONE_ACCOUNT_FIXTURE_REQUIRES_BOUND_SHELL_LAUNCHER')
        return account_fixture_origin(os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL',''))

    def start_android_e2e(self,client,session,target):
        configured=self.account_fixture_configuration(target)
        if configured is None:return super().start_android_e2e(client,session,target)
        selector=target.get('selector')
        require(type(selector) is str and self.target(selector)==target,'PHONE_ACCOUNT_FIXTURE_TARGET_CHANGED')
        with self.existing_input_session(selector):
            _client,current,_state=self.existing_session(selector)
            require(current==session,'PHONE_ACCOUNT_FIXTURE_SDK_CHANGED')
            self.installed_identity(selector)
            package=target['appId'];device=target['capabilities']['appium:udid']
            # One ordinary shell-only debug Activity launch. Its receipt proves
            # no endpoint, credentials, TLS, login or new-process function.
            PhoneAdapter(self.candidate).adb.execute(['shell',account_fixture_launch(package,
                os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL',''))],target=device,timeout=5)
            self.installed_identity(selector)

    def script_observation_store(self, selector, role, *, stage=0):
        require(role in ('primary','actor'),'PHONE_SCRIPT_OBSERVATION_ROLE_REQUIRED')
        require(type(stage) is int and stage in (0,1),'PHONE_SCRIPT_OBSERVATION_STAGE_INVALID')
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-'+role+'-observation'+('-restart' if stage else '')+'.json'))

    def _script_observation(self, selector, run, fixture_url, *, role, fixture_state='present', retired_owner=None, stage=0, source_lock=None):
        # Original existing-session readers only; no full operation/publisher.
        require(role in ('primary','actor'),'PHONE_SCRIPT_OBSERVATION_ROLE_REQUIRED')
        fixture_scope(run,fixture_url)
        lock_path=self.state_path(selector).with_name('phone-script-sources.lock')
        source_lock=PhoneScriptSourceLock(lock_path) if source_lock is None else source_lock
        require(isinstance(source_lock,PhoneScriptSourceLock) and source_lock.path==lock_path,
                'PHONE_SCRIPT_OBSERVATION_SOURCE_LOCK_REQUIRED')
        def make(lock):
            return self._script_durable_measurements(selector,run,fixture_url,role=role,
                fixture_state=fixture_state,retired_owner=retired_owner,source_lock=lock,stage=stage)
        with source_lock.held():
            ui,_observe,binding,check,installed=self.normal_feature_runtime(selector,read_only=True)
            def guard():
                check()
                require(self.installed_identity(selector)==installed,'PHONE_SCRIPT_OBSERVATION_INSTALL_CHANGED')
            return PhoneScriptObservation(self.script_observation_store(selector,role,stage=stage),binding,
                run,role,fixture_url,make,source_lock,guard,monotonic=ui.monotonic)

    def _script_files(self, selector, *, read_only=False):
        _ui, _observe, context, check, _installed = self.normal_feature_runtime(selector,read_only=read_only)
        native = self._native_feature_observer(selector,read_only=read_only)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        files = NativeScriptFiles(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + SCRIPT_FIXTURE_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)
        check()
        return OwnedScriptFiles(files, self.script_files_store(selector), context)

    def _script_file_manager(self, selector, *, read_only=False, run=None):
        ui, observe, context = self._script_file_runtime(selector,read_only=read_only)
        files = self._script_files(selector,read_only=read_only)
        if run is not None:require(files.owned()['runId']==run,'PHONE_SCRIPT_SCOPE_OWNED_RUN_REQUIRED')
        directory = files.verify()
        picker = self._script_file_picker(selector, directory,read_only=read_only)
        result = NormalScriptManager(ui, observe, self.script_store(selector), context,
            source_kind='script-file-bundle', file_owner=files, file_picker=picker)
        result.sample()
        return result  # Input/cleanup ownership only; no full Scripts capability.

    def _script_missing_manager(self, selector, *, read_only=False):
        ui, observe, binding = self._script_file_runtime(selector,read_only=read_only)
        result = NormalScriptManager(ui, observe, self.script_store(selector), binding,
            source_kind='feature-script-missing')
        result.sample()
        return result

    def _script_missing_from_files(self, selector, run):
        transfer_file_scope(run,self._script_file_manager(selector,read_only=True,run=run),self._script_execution_observer(selector,read_only=True),
                            self._script_file_io(selector,read_only=True))
        return self._script_missing_manager(selector,read_only=True)

    def _script_file_runtime(self, selector, *, read_only=False):
        native_ui, observe, context, check, installed = self.normal_feature_runtime(selector,read_only=read_only)
        target = self.target(selector)
        def guard():
            check()
            require(self.installed_identity(selector) == installed, 'PHONE_SCRIPT_FILE_MANAGER_INSTALL_CHANGED')
        native_ui.check_continuity = guard
        def original(after):
            guard(); value = observe(after); guard(); return value
        guard()
        return PhoneScriptUI(native_ui, target['appId']), original, context

    def script_restart_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-restart.json'))

    def _script_restart_handoff(self, selector):
        return ScriptRestartHandoff(self.script_restart_store(selector),
            self.script_files_store(selector), self.script_store(selector),require_membership=True)

    def _script_restart_prepare(self, selector):
        return self._script_restart_handoff(selector).prepare(
            self._script_file_manager(selector), self._script_execution_observer(selector))

    def _script_restart_adopt(self, selector):
        # Read original current sources without constructing/adopting a manager
        # from the old process record. No lifecycle/UI/script input is issued.
        ui, observe, binding = self._script_file_runtime(selector)
        handoff = self._script_restart_handoff(selector)
        files = self._script_files(selector)
        return handoff.adopt(binding, self._process_presence(selector),
            self._script_execution_observer(selector), files.native, ui, observe,
            self._script_file_picker(selector, handoff.directory()))

    def script_restart_inputs_store(self, selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-script-restart-inputs.json'))

    def _script_restart_inputs(self, selector):
        return RestartInputs(self.script_restart_inputs_store(selector),
            [self.script_restart_store(selector), self.script_files_store(selector), self.script_store(selector)])

    def _script_restart_source(self, selector):
        _ui, _observe, binding = self._script_file_runtime(selector)
        return binding, self._native_feature_observer(selector)

    def _script_restart_stopped(self, selector):
        # An independent current OS query is a pre-launch condition. The
        # handoff still needs original new-process kernel ESRCH afterwards.
        origin = self._script_restart_inputs(selector).read()['oldBinding']
        target = self.target(selector)
        require(self.snapshot_fingerprint(target) == origin['targetFingerprint'],
                'PHONE_SCRIPT_RESTART_TARGET_CHANGED')
        installed = self.installed_identity(selector)
        require(all(installed[key] == origin[key] for key in ('sourceRevision', 'artifactSha256')),
                'PHONE_SCRIPT_RESTART_INSTALL_CHANGED')
        client, session, state = self.ensure_session(selector)
        status = self.query_app_state(client, session, target)
        require(status in (1, 2, 3, 4), 'PHONE_SCRIPT_RESTART_OS_STATE_UNAVAILABLE')
        process = self.process_state(selector, client, session, state, target)
        running = status >= 2 or process.get('running') is True
        return {'running': running, 'identity': process.get('identity') if running else None}

    def _script_restart(self, selector):
        # Internal complete restart seam, not a full feature.scripts producer.
        return run_script_restart(self._script_restart_inputs(selector), self._script_restart_handoff(selector),
            lambda: self._script_restart_source(selector), lambda: self._script_restart_prepare(selector),
            lambda: self.invoke(selector, 'app.stop', {}), lambda: self._script_restart_stopped(selector),
            lambda: self.invoke(selector, 'app.launch', {}), lambda: self._script_restart_adopt(selector))

    def _script_file_picker(self, selector, directory, *, read_only=False):
        # Internal primitive only. The full area still needs staged-byte
        # ownership, persistent dialog/source cleanup and execution/effect joins.
        return TokenScriptFilePicker(self._script_file_io(selector,read_only=read_only), directory)

    def _script_manager_status(self, selector):
        from adapters.script_manager_status import manager_status
        return manager_status(self._script_file_io(selector).capture())

    def _script_ui_state(self, selector):
        from adapters.script_ui_inventory import ui_state
        return ui_state(self._script_file_io(selector).capture())

    def _script_file_io(self, selector, *, read_only=False):
        native = self._native_feature_observer(selector, read_only=read_only)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        return PhoneScriptFileIO(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + SCRIPT_FILE_UI_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)

    def _script_work(self,selector,*,read_only=True):
        require(read_only is True,'PHONE_SCRIPT_WORK_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeScriptWork(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+SCRIPT_WORK_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _script_roots(self,selector,*,read_only=False):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeScriptRoots(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+SCRIPT_ROOTS_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _emote_controls(self,selector,intent,*,receipt=None,read_only=False):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        ui,_observe,_context,check,_installed=self.normal_feature_runtime(selector,read_only=read_only)
        tablet=PhoneScriptUI(ui,target['appId']);check()
        io=PhoneEmoteIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+EMOTE_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,tablet_shown=tablet.tablet_visible,
            monotonic=native.monotonic,sleep=native.sleep)
        return TokenEmoteUI(io,intent,receipt=receipt,monotonic=native.monotonic,sleep=native.sleep)

    def _graphics_controls(self, selector, intent, *, read_only=False):
        # Internal ordinary-input component. Original render/pass/image and
        # full preference ownership/restart coordination remain mandatory.
        native = self._native_feature_observer(selector,read_only=read_only)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        io = PhoneGraphicsIO(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + GRAPHICS_UI_FILE, attempts=1),
            native.clock_ms, native.guard, native.pid)
        return TokenGraphicsUI(io, intent)

    def _graphics_surface(self, selector, run, intent, owns, lease, allow_url, *, lock, role='primary'):
        require(role=='primary' and isinstance(lock,PhoneScriptSourceLock)
                and lock.path==self.state_path(selector).with_name('phone-script-sources.lock'),
                'PHONE_GRAPHICS_INPUT_SCOPE_REQUIRED')
        lock.assert_held()
        with self.existing_input_session(selector):
            ui,_observe,_binding,_check,_installed=self.normal_feature_runtime(selector,read_only=True)
            subject=self._graphics_subject_observer(selector,read_only=True)
            graphics=self._graphics_controls(selector,lambda *_args:None)
            def serialized(check):
                def guard():
                    lock.assert_held();result=check();lock.assert_held();return result
                return guard
            ui.check_continuity=serialized(ui.check_continuity)
            subject.guard=serialized(subject.guard)
            graphics.io.guard=serialized(graphics.io.guard)
            return PhoneGraphicsSurface(ui,subject,graphics,run,intent,owns,lease,allow_url)

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

    def _login_controls(self, selector, intent, run, origin, *, read_only=False):
        # Input component only. The owner supplies actual private fixture
        # credentials and durable intent; full authentication remains closed.
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        io=PhoneLoginIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+LOGIN_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid)
        return TokenLoginUI(io,intent,run,origin)

    def _account_menu(self, selector, intent, run, origin):
        ui,_observe,binding,check,installed=self.normal_feature_runtime(selector,read_only=True)
        source=self._native_feature_observer(selector,read_only=True)
        check();source.guard()
        require(source.pid==int(binding['processIdentity'].split(':')[0])
                and self.installed_identity(selector)==installed,'PHONE_ACCOUNT_MENU_CONTEXT_CHANGED')
        return PhoneAccountMenu(ui,source,intent,run,origin)

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

    def _check_existing_input_pin(self, selector, pin, state):
        require(getattr(self,'_existing_input_scope',None) is pin and type(pin) is dict
                and set(pin)=={'selector','sessionId','generation','fingerprint','installed'}
                and type(pin['generation']) is int and pin['generation']>=0
                and selector==pin['selector'],'PHONE_EXISTING_INPUT_SCOPE_CHANGED')
        # Reject a changed target/session locally before querying another SDK
        # endpoint. No fallback calls the repairing parent implementation.
        require(self.snapshot_fingerprint(self.target(selector))==pin['fingerprint']
                and type(state) is dict and state.get('sessionId')==pin['sessionId']
                and type(state.get('generation')) is int and state['generation']==pin['generation']
                and state.get('targetFingerprint')==pin['fingerprint'],
                'PHONE_EXISTING_INPUT_SESSION_CHANGED')

    def _guarded_existing_session(self, selector, pin):
        # Keep foreign selector rejection ahead of state-path lookup.
        require(type(pin) is dict and selector==pin.get('selector'),'PHONE_EXISTING_INPUT_SCOPE_CHANGED')
        self._check_existing_input_pin(selector,pin,self.read_session(selector))
        client,session,current=self.existing_session(selector)
        require(session==pin['sessionId'] and type(current.get('generation')) is int
                and current['generation']==pin['generation']
                and current.get('targetFingerprint')==pin['fingerprint']
                and json.dumps(self.installed_identity(selector),sort_keys=True,allow_nan=False)
                    ==json.dumps(pin['installed'],sort_keys=True,allow_nan=False),
                'PHONE_EXISTING_INPUT_CANDIDATE_OR_SESSION_CHANGED')
        return client,session,current

    @contextmanager
    def existing_input_session(self, selector):
        """Pin one existing SDK session for normal input, without session repair.

        This admits input only; it never proves its function or a restart. The
        same SDK session may survive explicit app stop/launch; separate native
        lifecycle/kernel/Script proof remains mandatory for a new process.
        """
        outer=getattr(self,'_existing_input_scope',None)
        if outer is not None:
            self._guarded_existing_session(selector,outer)
            yield
            self._guarded_existing_session(selector,outer)
            return
        before=deepcopy(self.read_session(selector))
        require(type(before) is dict and type(before.get('generation')) is int
                and before['generation']>=0,'PHONE_EXISTING_INPUT_GENERATION_REQUIRED')
        _client,session,state=self.existing_session(selector)
        require(state==before,'PHONE_EXISTING_INPUT_SESSION_CHANGED')
        pin=dict(selector=selector,sessionId=session,generation=state['generation'],
                 fingerprint=state['targetFingerprint'],installed=deepcopy(self.installed_identity(selector)))
        self._existing_input_scope=pin
        try:
            self._guarded_existing_session(selector,pin)
            yield
            self._guarded_existing_session(selector,pin)
        finally:
            self._existing_input_scope=None

    def existing_session(self, selector):
        # Independent observations must never inherit ensure_session's repair,
        # deletion, installation or new-session/automatic-launch behavior.
        pin=getattr(self,'_existing_input_scope',None)
        require(pin is None or type(pin) is dict and selector==pin.get('selector'),
                'PHONE_EXISTING_INPUT_SCOPE_CHANGED')
        require(self.candidate is not None, 'PHONE_READ_ONLY_CANDIDATE_REQUIRED')
        target = self.target(selector)
        before = deepcopy(self.read_session(selector))
        if pin is not None:self._check_existing_input_pin(selector,pin,before)
        fingerprint = self.snapshot_fingerprint(target)
        require(before is not None and before.get('targetFingerprint') == fingerprint
                and type(before.get('sessionId')) is str
                and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}', before['sessionId']) is not None,
                'PHONE_READ_ONLY_EXISTING_SESSION_REQUIRED')
        installed = self.installed_identity(selector)
        if pin is not None:
            require(json.dumps(installed,sort_keys=True,allow_nan=False)
                    ==json.dumps(pin['installed'],sort_keys=True,allow_nan=False),
                    'PHONE_EXISTING_INPUT_CANDIDATE_OR_SESSION_CHANGED')
        client = WebDriver(target['serverUrl'])
        try:
            client.call('GET', '/session/' + before['sessionId'])
        except Exception:
            raise RuntimeError('PHONE_READ_ONLY_SESSION_UNAVAILABLE') from None
        require(self.snapshot_fingerprint(self.target(selector)) == fingerprint
                and self.read_session(selector) == before
                and self.installed_identity(selector) == installed,
                'PHONE_READ_ONLY_SESSION_OR_CANDIDATE_CHANGED')
        return client, before['sessionId'], before

    def normal_feature_runtime(self, selector, *, include_entities=False, read_only=False):
        require(type(read_only) is bool, 'PHONE_READ_ONLY_MODE_INVALID')
        target = self.target(selector)
        client, session, state = self.existing_session(selector) if read_only else self.ensure_session(selector)
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
        graphics_error=False
        try:
            feature=self.graphics_feature_store(selector).read() or self.graphics_retirement_store(selector).read()
            if feature is not None:self._graphics_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:graphics_error=True # Retain all unresolved ownership; base teardown is still attempted.
        authentication_error=False
        try:
            feature=self.authentication_feature_store(selector).read() or self.authentication_retirement_store(selector).read()
            if feature is not None:self._authentication_feature(selector,feature['runId']).finalize()
        except Exception:authentication_error=True # Preserve scope; all other teardown is still attempted.
        feature_error=False
        try:
            feature=self.script_feature_store(selector).read() or self.script_retirement_store(selector).read()
            if feature is not None:self._script_feature(selector,feature['runId']).finalize()
        except Exception:feature_error=True # Preserve full ownership; base teardown still runs.
        world_error=False
        for role in ('primary','actor'):
            try:
                if self.world_render_store(selector,role=role).read() is not None:
                    lock=PhoneScriptSourceLock(self.state_path(selector).with_name('phone-script-sources.lock'))
                    with lock.held():
                        if self.world_render_store(selector,role=role).read() is not None:
                            self._world_render_capture(selector,read_only=True,role=role).release()
            except Exception:world_error=True # Attempt both roles and base teardown; never forget ownership.
        chat_error=False
        try:
            owned=self.chat_capture_store(selector).read()
            if owned is not None:self._chat_capture(selector,owned['runId']).retire()
        except Exception:chat_error=True
        probe_error=False
        for role in ('primary','actor'):
            try:
                if self.account_probe_store(selector,role=role).read() is not None:
                    self._account_probe(selector,read_only=(role=='actor'),role=role).release()
            except Exception:
                probe_error=True # Attempt the other role too; keep unresolved ownership.
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
        require(not feature_error and self.script_feature_store(selector).read() is None
                and self.script_retirement_store(selector).read() is None
                and all(PrivateFeatureState(self.state_path(selector).with_name('phone-script-'+role+'-feature.json')).read() is None
                        for role in ('primary','actor')),'PHONE_SCRIPT_FEATURE_CLEANUP_INCOMPLETE')
        require(self.script_restart_inputs_store(selector).read() is None, 'PHONE_SCRIPT_RESTART_INPUTS_CLEANUP_INCOMPLETE')
        require(self.script_restart_store(selector).read() is None, 'PHONE_SCRIPT_RESTART_CLEANUP_INCOMPLETE')
        require(self.script_actions_store(selector).read() is None,'PHONE_SCRIPT_ACTIONS_CLEANUP_INCOMPLETE')
        require(all(self.script_history_store(selector,role,stage=stage).read() is None for role in ('primary','actor') for stage in (0,1)),
                'PHONE_SCRIPT_HISTORY_CLEANUP_INCOMPLETE')
        require(all(self.script_observation_store(selector,role,stage=stage).read() is None for role in ('primary','actor') for stage in (0,1)),
                'PHONE_SCRIPT_OBSERVATION_CLEANUP_INCOMPLETE')
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
        require(not world_error and all(self.world_render_store(selector,role=role).read() is None for role in ('primary','actor')),
                'PHONE_WORLD_RENDER_CLEANUP_INCOMPLETE')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-background.json')).read() is None,
                'PHONE_EMOTE_BACKGROUND_CLEANUP_INCOMPLETE')
        require(all(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-'+role+'-lifetime.json')).read() is None
                    for role in ('primary','actor')),'PHONE_EMOTE_LIFETIME_CLEANUP_INCOMPLETE')
        require(not any(self.state_path(selector).parent.glob('phone-emote-*-capture-*.json')),
                'PHONE_EMOTE_CAPTURE_CLEANUP_INCOMPLETE')
        require(all(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-'+role+'-sources.json')).read() is None
                    for role in ('primary','actor')),'PHONE_EMOTE_SOURCE_CLEANUP_INCOMPLETE')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-inputs.json')).read() is None,
                'PHONE_EMOTE_INPUT_CLEANUP_INCOMPLETE')
        require(self.graphics_restart_store(selector).read() is None and self.graphics_restart_inputs_store(selector).read() is None,
                'PHONE_GRAPHICS_RESTART_CLEANUP_INCOMPLETE')
        require(self.graphics_background_store(selector).read() is None,'PHONE_GRAPHICS_BACKGROUND_CLEANUP_INCOMPLETE')
        require(self.graphics_preferences_store(selector).read() is None,'PHONE_GRAPHICS_PREFERENCES_CLEANUP_INCOMPLETE')
        require(self.graphics_scene_store(selector).read() is None,'PHONE_GRAPHICS_SCENE_CLEANUP_INCOMPLETE')
        require(all(self.graphics_samples_store(selector,role,stage).read() is None
                    for role in ('primary','actor') for stage in (0,1)),
                'PHONE_GRAPHICS_SOURCE_CLEANUP_INCOMPLETE')
        require(all(self.graphics_lifetime_store(selector,role,stage).read() is None
                    for role in ('primary','actor') for stage in (0,1)),
                'PHONE_GRAPHICS_LIFETIME_CLEANUP_INCOMPLETE')
        require(all(self.graphics_observer_store(selector,role).read() is None for role in ('primary','actor')),
                'PHONE_GRAPHICS_OBSERVER_CLEANUP_INCOMPLETE')
        require(not probe_error and all(self.account_probe_store(selector,role=role).read() is None for role in ('primary','actor')),
                'PHONE_ACCOUNT_PROBE_CLEANUP_INCOMPLETE')
        require(not origin_error and self.account_origin_store(selector).read() is None,
                'PHONE_ACCOUNT_ORIGIN_CLEANUP_INCOMPLETE')
        require(all(self.authentication_samples_store(selector,role,stage).read() is None
                    for role in ('primary','actor') for stage in range(4)),
                'PHONE_AUTHENTICATION_SOURCE_CLEANUP_INCOMPLETE')
        require(self.authentication_actions_store(selector).read() is None
                and all(self.authentication_restart_store(selector,stage).read() is None for stage in range(1,4)),
                'PHONE_AUTHENTICATION_INPUT_CLEANUP_INCOMPLETE')
        require(not authentication_error and self.authentication_feature_store(selector).read() is None and self.authentication_retirement_store(selector).read() is None
                and all(PrivateFeatureState(self.state_path(selector).with_name('phone-authentication-'+role+'-feature.json')).read() is None
                        for role in ('primary','actor')),'PHONE_AUTHENTICATION_FEATURE_CLEANUP_INCOMPLETE')
        require(not graphics_error and self.graphics_feature_store(selector).read() is None
                and self.graphics_retirement_store(selector).read() is None,'PHONE_GRAPHICS_FEATURE_CLEANUP_INCOMPLETE')
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
        pin=getattr(self,'_existing_input_scope',None)
        if pin is not None:
            return self._guarded_existing_session(selector,pin)
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
        if operation in ('app.launch','scene.load'):
            self.account_fixture_configuration(self.target(selector))
        if operation in SCRIPT_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),
                    'PHONE_SCRIPT_FEATURE_NOT_ENABLED')
            return getattr(self._script_feature(selector,values['runId']),operation.rsplit('.',1)[1])(values)
        if operation in AUTHENTICATION_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),
                    'PHONE_AUTHENTICATION_FEATURE_NOT_ENABLED')
            return getattr(self._authentication_feature(selector,values['runId']),operation.rsplit('.',1)[1])(values)
        if operation in GRAPHICS_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),
                    'PHONE_GRAPHICS_FEATURE_NOT_ENABLED')
            return getattr(self._graphics_feature(selector,values['runId']),operation.rsplit('.',1)[1])(values)
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
