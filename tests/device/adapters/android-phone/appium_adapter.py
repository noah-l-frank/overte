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
from adapters.native_chat_history import NativeChatHistory, FILE as CHAT_HISTORY_FILE
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
from overte_phone_assets_controls import PhoneAssetsIO, FILE as ASSETS_UI_FILE
from adapters.token_assets_ui import TokenAssetsUI
from overte_phone_create_source import PhoneCreateSource, FILE as CREATE_SOURCE_FILE
from overte_phone_create_files import PhoneCreateFiles, FILE as CREATE_FILES_FILE
from overte_phone_create_marker import NativePhoneCreateFixture, FILE as CREATE_FIXTURE_FILE, input_command as create_fixture_input_command
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
from adapters.native_phone_avatar_configuration import NativePhoneAvatarConfiguration, FILE as AVATAR_CONFIGURATION_FILE
from adapters.native_phone_touch_state import NativePhoneTouchState, FILE as TOUCH_STATE_FILE
from adapters.native_phone_emote_fixture import NativePhoneEmoteFixture, FILE as EMOTE_FIXTURE_FILE, input_command as emote_fixture_input_command
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
from adapters.native_animation_inventory import NativeAnimationInventory, FILE as ANIMATION_INVENTORY_FILE
from adapters.native_script_work import NativeScriptWork, FILE as SCRIPT_WORK_FILE, command as script_work_command
from overte_phone_navigation_feature import PhoneNavigationFeature
from overte_phone_navigation_fixture import NavigationFixtureReader
from overte_phone_avatar_people_feature import PhoneAvatarPeopleFeature,image_policy as avatar_people_image_policy
from overte_phone_avatar_people_fixture import AvatarPeopleFixtureReader
from overte_phone_navigation_native import PhoneNavigationIO,PhoneNavigationView,UI_FILE as NAVIGATION_UI_FILE,VIEW_FILE as NAVIGATION_VIEW_FILE
from overte_phone_navigation_marker import NativePhoneNavigationMarker,FILE as NAVIGATION_MARKER_FILE
from overte_phone_graphics_feature import PhoneGraphicsFeature
from overte_phone_graphics_fixture import GraphicsFixtureReader
from feature_journeys.witness import Client as FeatureFixtureClient
from adapters.feature_fixture_access import client as adapter_fixture_client
from overte_phone_account_fixture import origin as account_fixture_origin, launch_command as account_fixture_launch
from overte_phone_account_menu import PhoneAccountMenu

SCRIPT_FEATURE_OPERATIONS={'feature.scripts.'+kind for kind in ('act','observe','cleanup')}
AUTHENTICATION_FEATURE_OPERATIONS={'feature.authentication.'+kind for kind in ('act','observe','cleanup')}
GRAPHICS_FEATURE_OPERATIONS={'feature.graphics.'+kind for kind in ('act','observe','cleanup')}
CREATE_FEATURE_OPERATIONS={'feature.create.'+kind for kind in ('act','observe','cleanup')}
ASSETS_FEATURE_OPERATIONS={'feature.assets.'+kind for kind in ('act','observe','cleanup')}
EMOTE_FEATURE_OPERATIONS={'feature.emotes.'+kind for kind in ('act','observe','cleanup')}
WORLD_WEB_FEATURE_OPERATIONS={'feature.world-web.'+kind for kind in ('act','observe','cleanup')}
TABLET_WEB_FEATURE_OPERATIONS={'feature.tablet-web.'+kind for kind in ('act','observe','cleanup')}
TABLET_FOUNDATION_OPERATIONS={'tablet.open','tablet.close'}
CHAT_FEATURE_OPERATIONS={'feature.chat.'+kind for kind in ('act','observe','cleanup')}
AUDIO_FEATURE_OPERATIONS={'feature.audio.'+kind for kind in ('act','observe','cleanup')}
NAVIGATION_FEATURE_OPERATIONS={'feature.world-navigation.'+kind for kind in ('act','observe','cleanup')}
WEB_REFERENCE_OPERATIONS={'web.reference.'+kind for kind in ('open','close','play','pause','seek')}
AVATAR_PEOPLE_FEATURE_OPERATIONS={'feature.avatar-people.'+kind for kind in ('act','observe','cleanup')}
LIFECYCLE_INPUT_FEATURE_OPERATIONS={'feature.lifecycle-input.'+kind for kind in ('act','observe','cleanup')}
COLLABORATION_OPERATIONS={'collaboration.edit','collaboration.snapshot'}


def readonly_feature_command(command):
    """Closed observations and retirement of their own measurement leases."""
    require(type(command) is dict and type(command.get('schemaVersion')) is int and command['schemaVersion']==1
            and type(command.get('commandId')) is str and re.fullmatch('[0-9a-f]{32}',command['commandId']),
            'PHONE_READ_ONLY_COMMAND_REJECTED')
    action=command.get('action')
    if action in ('feature-native-observe','feature-script-observe','feature-world-render-observe','feature-script-roots-observe','feature-animation-inventory-observe'):
        require(set(command)=={'schemaVersion','commandId','action'},'PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='feature-pending-commit-owner':
        from adapters.pending_commit_owner import command as pending_command
        pending_command(command);require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='feature-chat-history':
        from adapters.native_chat_history import command as validate_chat_history
        validate_chat_history(command);require(command['operation']=='inspect','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-lifecycle-editor-observe':
        from overte_phone_lifecycle_editor import command as validate_lifecycle_editor
        validate_lifecycle_editor(command)
    elif action=='phone-lifecycle-world-input':
        from overte_phone_lifecycle_world import command as validate_lifecycle_world
        validate_lifecycle_world(command);require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='feature-chat-view-observe':
        from adapters.native_chat_view import command as validate_chat_view
        validate_chat_view(command)
    elif action=='feature-chat-observe':
        from adapters.native_chat_observation import command as validate_chat_receive
        validate_chat_receive(command);require(command['operation']=='inspect','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-avatar-people-observe':
        from overte_phone_avatar_people_native import command as validate_avatar_people
        validate_avatar_people(command)
    elif action in ('phone-avatar-people-ui','phone-snapshot-ui'):
        request=command.get('request')
        require(set(command)=={'schemaVersion','commandId','action','request'} and type(request) is dict and type(request.get('schemaVersion')) is int
            and request==dict(schemaVersion=1,commandId=command['commandId'],action='observe'),'PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-snapshot-cancel':
        from overte_phone_snapshot_cancel import command as validate_snapshot_cancel
        validate_snapshot_cancel(command)
        require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-snapshot-settings':
        from overte_phone_snapshot_settings import command as validate_snapshot_settings
        validate_snapshot_settings(command)
        require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-navigation-view-observe':
        from overte_phone_navigation_native import command as validate_navigation
        validate_navigation(command)
    elif action=='feature-navigation-replies':
        from adapters.native_navigation_replies import command as validate_navigation_replies
        validate_navigation_replies(command)
    elif action=='phone-navigation-marker-observe':
        from overte_phone_navigation_marker import command as validate_navigation_marker
        validate_navigation_marker(command)
    elif action=='phone-navigation-ui':
        require(set(command)=={'schemaVersion','commandId','action','request'} and command['request']==dict(schemaVersion=1,commandId=command['commandId'],action='observe'),'PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-audio-fixture':
        from overte_phone_audio_source import command as validate_audio_source
        validate_audio_source(command);require(command['request']['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='voice-test':
        from voice_contract import command as validate_voice
        require(set(command)=={'schemaVersion','commandId','action','request'},'PHONE_READ_ONLY_COMMAND_REJECTED')
        validate_voice(command['request']);require(command['request']==dict(schemaVersion=1,commandId=command['commandId'],action='status'),'PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action in ('feature-recorded-audio-observe','feature-recorded-audio-files'):
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
    elif action=='phone-emote-fixture-observe':
        from adapters.native_phone_emote_fixture import command as validate_emote_fixture
        validate_emote_fixture(command)
    elif action=='phone-touch-state-observe':
        from adapters.native_phone_touch_state import command as validate_touch_state
        validate_touch_state(command)
    elif action=='phone-avatar-configuration-observe':
        from adapters.native_phone_avatar_configuration import command as validate_avatar_configuration
        validate_avatar_configuration(command)
    elif action=='feature-avatar-render-observe':
        from adapters.native_avatar_render import command as validate_avatar_render
        validate_avatar_render(command)
    elif action=='feature-world-model-draws-observe':
        from adapters.native_world_model_draws import command as validate_model_draws
        validate_model_draws(command)
    elif action=='phone-assets-uploads':
        from overte_phone_assets_uploads import command as validate_assets_uploads
        validate_assets_uploads(command)
        require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-assets-files':
        from overte_phone_assets_files import command as validate_assets_files
        validate_assets_files(command)
        require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-create-files':
        from overte_phone_create_files import command as validate_create_files
        validate_create_files(command)
        require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-create-fixture-observe':
        from overte_phone_create_marker import command as validate_create_marker
        validate_create_marker(command)
    elif action in ('phone-assets-observe','phone-assets-download','phone-assets-resolve'):
        from overte_phone_assets_source import command as validate_assets_source
        validate_assets_source(command)
    elif action=='phone-create-observe':
        from overte_phone_create_source import command as validate_create_source
        validate_create_source(command)
    elif action=='feature-graphics-subject-observe':
        from adapters.native_graphics_subject import command as validate_subject
        validate_subject(command)
    elif action=='feature-scene-load-observe':
        from adapters.native_phone_scene_loads import command as validate_scene_load
        validate_scene_load(command)
    elif action=='phone-snapshot-files-observe':
        from overte_phone_snapshot_capture_source import command as validate_capture_files
        validate_capture_files(command)
    elif action=='phone-snapshot-observe':
        from overte_phone_snapshot_source import command as validate_snapshot
        validate_snapshot(command)
    elif action=='phone-snapshot-handoff':
        from overte_phone_snapshot_handoff import command as validate_handoff
        validate_handoff(command);require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action=='phone-snapshot-upload-observe':
        from overte_phone_snapshot_upload_source import command as validate_snapshot_upload
        validate_snapshot_upload(command)
    elif action=='phone-snapshot-readback':
        from overte_phone_snapshot_readbacks import command as validate_readback
        validate_readback(command)
        require(command['operation'] in ('observe','read','inspect-destinations','inspect-shares'),'PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action in ('phone-world-web','phone-tablet-web','phone-web-reference'):
        from overte_phone_world_web_source import command as validate_world_web
        validate_world_web(command)
        require(command['operation']=='observe','PHONE_READ_ONLY_COMMAND_REJECTED')
    elif action in ('feature-phone-web-runtime-observe','feature-phone-web-reference-runtime-observe'):
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
    elif action in ('phone-script-file-ui','phone-login-ui','phone-graphics-ui','phone-emote-ui','phone-create-ui','phone-audio-ui','phone-assets-ui'):
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
        collaboration=os.environ.get('OVERTE_ANDROID_E2E_COLLABORATION','0')
        require(collaboration in ('0','1'),'PHONE_COLLABORATION_CONFIGURATION_INVALID')
        if collaboration=='1':
            self._collaboration_configuration(target)
            values=sorted(set(values)|COLLABORATION_OPERATIONS)
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
        full_navigation=os.environ.get('OVERTE_PHONE_FEATURE_WORLD_NAVIGATION','0')
        require(full_navigation in ('0','1'),'PHONE_FEATURE_WORLD_NAVIGATION_CONFIGURATION_INVALID')
        if full_navigation=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),'PHONE_FEATURE_WORLD_NAVIGATION_REQUIRES_BOUND_DEBUG_TARGET')
            self._navigation_configuration();self._feature_fixture_client()
            values=sorted(set(values)|NAVIGATION_FEATURE_OPERATIONS)
        full_lifecycle=os.environ.get('OVERTE_PHONE_FEATURE_LIFECYCLE_INPUT','0')
        require(full_lifecycle in ('0','1'),'PHONE_FEATURE_LIFECYCLE_INPUT_CONFIGURATION_INVALID')
        if full_lifecycle=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_LIFECYCLE_INPUT_REQUIRES_BOUND_DEBUG_TARGET')
            require(os.environ.get('OVERTE_ANDROID_E2E_TEXT_INPUT')=='1' and os.environ.get('OVERTE_E2E_VOICE_TESTS')=='1'
                and target.get('scene',{}).get('kind')=='android-debug-e2e'
                and isinstance(target.get('controls',{}).get('move',{}).get('forward'),dict),
                'PHONE_FEATURE_LIFECYCLE_INPUT_REQUIRES_FOUNDATIONS')
            self._lifecycle_input_configuration();self._feature_fixture_client()
            values=sorted(set(values)|TABLET_FOUNDATION_OPERATIONS)
            require({'app.foreground','app.launch','app.process','lifecycle.background','probe.snapshot','scene.load','input.move',
                'tablet.open','tablet.close','text.dismiss','text.focus','text.snapshot','text.type'}<=set(values),
                'PHONE_FEATURE_LIFECYCLE_INPUT_REQUIRES_FOUNDATIONS')
            values=sorted(set(values)|LIFECYCLE_INPUT_FEATURE_OPERATIONS)
        full_avatar=os.environ.get('OVERTE_PHONE_FEATURE_AVATAR_PEOPLE','0')
        require(full_avatar in ('0','1'),'PHONE_FEATURE_AVATAR_PEOPLE_CONFIGURATION_INVALID')
        if full_avatar=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_AVATAR_PEOPLE_REQUIRES_BOUND_DEBUG_TARGET')
            require(self.account_fixture_configuration(target) is not None,'PHONE_FEATURE_AVATAR_PEOPLE_REQUIRES_ACCOUNT_FIXTURE_LAUNCH')
            self._avatar_people_configuration();client=self._feature_fixture_client()
            require(urlsplit(client.url).scheme=='https','PHONE_FEATURE_AVATAR_PEOPLE_REQUIRES_TLS')
            values=sorted(set(values)|AVATAR_PEOPLE_FEATURE_OPERATIONS)
        full_graphics=os.environ.get('OVERTE_PHONE_FEATURE_GRAPHICS','0')
        require(full_graphics in ('0','1'),'PHONE_FEATURE_GRAPHICS_CONFIGURATION_INVALID')
        if full_graphics=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),'PHONE_FEATURE_GRAPHICS_REQUIRES_BOUND_DEBUG_TARGET')
            self._graphics_configuration()
            self._feature_fixture_client()
            values=sorted(set(values)|GRAPHICS_FEATURE_OPERATIONS)
        full_emotes=os.environ.get('OVERTE_PHONE_FEATURE_EMOTES','0')
        require(full_emotes in ('0','1'),'PHONE_FEATURE_EMOTES_CONFIGURATION_INVALID')
        if full_emotes=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),'PHONE_FEATURE_EMOTES_REQUIRES_BOUND_DEBUG_TARGET')
            self._emote_configuration()
            self._feature_fixture_client()
            values=sorted(set(values)|EMOTE_FEATURE_OPERATIONS)
        full_world_web=os.environ.get('OVERTE_PHONE_FEATURE_WORLD_WEB','0')
        require(full_world_web in ('0','1'),'PHONE_FEATURE_WORLD_WEB_CONFIGURATION_INVALID')
        if full_world_web=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_WORLD_WEB_REQUIRES_BOUND_DEBUG_TARGET')
            self._world_web_configuration();self._feature_fixture_client()
            values=sorted(set(values)|WORLD_WEB_FEATURE_OPERATIONS|WEB_REFERENCE_OPERATIONS)
        full_tablet_web=os.environ.get('OVERTE_PHONE_FEATURE_TABLET_WEB','0')
        require(full_tablet_web in ('0','1'),'PHONE_FEATURE_TABLET_WEB_CONFIGURATION_INVALID')
        if full_tablet_web=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_TABLET_WEB_REQUIRES_BOUND_DEBUG_TARGET')
            self._tablet_web_configuration();self._feature_fixture_client()
            values=sorted(set(values)|TABLET_WEB_FEATURE_OPERATIONS|WEB_REFERENCE_OPERATIONS|TABLET_FOUNDATION_OPERATIONS)
        reference_enabled=os.environ.get('OVERTE_PHONE_NORMAL_WEB_REFERENCE','0')
        full_chat=os.environ.get('OVERTE_PHONE_FEATURE_CHAT','0')
        require(full_chat in ('0','1'),'PHONE_FEATURE_CHAT_CONFIGURATION_INVALID')
        if full_chat=='1':
            require(self.candidate is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_CHAT_BOUND_DEBUG_TARGET_REQUIRED')
            self._chat_configuration();self._feature_fixture_client();values=sorted(set(values)|CHAT_FEATURE_OPERATIONS)
        full_audio=os.environ.get('OVERTE_PHONE_FEATURE_AUDIO','0')
        require(full_audio in ('0','1'),'PHONE_FEATURE_AUDIO_CONFIGURATION_INVALID')
        if full_audio=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_AUDIO_REQUIRES_BOUND_DEBUG_TARGET')
            require(os.environ.get('OVERTE_E2E_VOICE_TESTS')=='1' and os.environ.get('OVERTE_E2E_RECORDED_PREVIEW_TESTS')=='1'
                and {'permission.snapshot','permission.set','sound.play','voice.exchange'}<=set(values),'PHONE_AUDIO_MANDATORY_FOUNDATIONS_REQUIRED')
            self._audio_configuration();self._feature_fixture_client()
            values=sorted(set(values)|AUDIO_FEATURE_OPERATIONS|{'audio.mute'})
        require(reference_enabled in ('0','1'),'PHONE_WEB_REFERENCE_CONFIGURATION_INVALID')
        if reference_enabled=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_WEB_REFERENCE_REQUIRES_BOUND_DEBUG_TARGET')
            values=sorted(set(values)|WEB_REFERENCE_OPERATIONS)
        full_assets=os.environ.get('OVERTE_PHONE_FEATURE_ASSETS','0')
        require(full_assets in ('0','1'),'PHONE_FEATURE_ASSETS_CONFIGURATION_INVALID')
        if full_assets=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(target),'PHONE_FEATURE_ASSETS_REQUIRES_BOUND_DEBUG_TARGET')
            self._assets_configuration();self._feature_fixture_client()
            values=sorted(set(values)|ASSETS_FEATURE_OPERATIONS)
        full_create=os.environ.get('OVERTE_PHONE_FEATURE_CREATE','0')
        require(full_create in ('0','1'),'PHONE_FEATURE_CREATE_CONFIGURATION_INVALID')
        if full_create=='1':
            require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),'PHONE_FEATURE_CREATE_REQUIRES_BOUND_DEBUG_TARGET')
            self._create_configuration();self._feature_fixture_client()
            values=sorted(set(values)|CREATE_FEATURE_OPERATIONS)
        create_enabled = os.environ.get('OVERTE_PHONE_NORMAL_CREATE', '0')
        require(create_enabled in ('0', '1'), 'PHONE_NORMAL_CREATE_CONFIGURATION_INVALID')
        if create_enabled == '1':
            require(getattr(self, 'candidate', None) is not None
                    and target.get('appId') == 'io.github.noah_be.overte.phone'
                    and self.controlled_android_client(target),
                    'PHONE_NORMAL_CREATE_REQUIRES_BOUND_DEBUG_TARGET')
            values = sorted(set(values) | CREATE_OPERATIONS)
        return values

    def _collaboration_configuration(self,target):
        from overte_phone_collaboration import configuration
        require(self.candidate is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_COLLABORATION_BOUND_DEBUG_TARGET_REQUIRED')
        return configuration(os.environ)

    def _collaboration(self,selector):
        from overte_phone_collaboration import PhoneCollaboration,CollaborationControl,FILE
        target=self.target(selector);config=self._collaboration_configuration(target)
        _ui,_observe,context,check,installed=self.normal_feature_runtime(selector,read_only=True)
        client,session,_state=self.existing_session(selector)
        device=target['capabilities']['appium:udid'];adb=PhoneAdapter(self.candidate).adb
        def guard():
            check();require(self.installed_identity(selector)==installed,'PHONE_COLLABORATION_INSTALL_CHANGED')
        def enter():
            guard()
            with self.existing_input_session(selector):self.invoke(selector,'navigation.enter-domain',dict(url=config['domainUrl']))
            guard()
        return PhoneCollaboration(PrivateFeatureState(self.state_path(selector).with_name('phone-collaboration.json')),
            context,config['domainId'],guard,lambda:self.probe_snapshot(client,session,target),
            lambda:adb.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            lambda:adb.epoch_milliseconds(device),CollaborationControl(config),enter)

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

    def _navigation_replies(self,selector,*,read_only=False):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeNavigationReplies(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+NAVIGATION_REPLIES_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _pending_owner(self, selector, intent=None, *, read_only=False):
        require(type(read_only) is bool and (not read_only or intent is None),'PHONE_PENDING_OWNER_READONLY_INPUT')
        _ui,_observe,context,check,installed=self.normal_feature_runtime(selector,read_only=read_only)
        native=self._native_feature_observer(selector,read_only=read_only)
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

    def _chat_view(self,selector,*,read_only=False):
        _ui,_observe,context,check,installed=self.normal_feature_runtime(selector,read_only=read_only)
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        check();require(self.installed_identity(selector)==installed and native.pid==int(context['processIdentity'].split(':')[0]),
            'PHONE_CHAT_VIEW_CONTEXT_CHANGED')
        return NativeChatView(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CHAT_VIEW_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _chat_receive(self,selector,*,read_only=True):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeChatObservation(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CHAT_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _chat_history(self,selector,*,read_only=True):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeChatHistory(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CHAT_HISTORY_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    @staticmethod
    def _chat_configuration(metadata=None):
        from overte_phone_chat_peer import configuration
        from overte_phone_chat_measurements import source_pins
        value=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_CHAT_CONFIGURATION',''))).read() if metadata is None else metadata['configuration']
        require(type(value) is dict and set(value)=={'chatFeatureVersion','artifactRoot','peer'} and type(value['chatFeatureVersion']) is int
            and value['chatFeatureVersion']==1,'PHONE_CHAT_CONFIGURATION_REQUIRED')
        root=Path(value['artifactRoot']);require(root.is_absolute() and str(root)==value['artifactRoot'],'PHONE_CHAT_ARTIFACT_ROOT_REQUIRED')
        PrivateFeatureState(root/'chat-boundary.json')._parent();configuration(value['peer']);source_pins();return deepcopy(value)

    def chat_feature_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('phone-chat-feature.json'))
    def chat_retirement_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('phone-chat-retirement.json'))

    def _chat_peer(self,selector,run,config,*,read_only=True,attach_files=True):
        from overte_phone_chat_peer import PhoneChatPeer
        from overte_phone_chat_measurements import source_pins
        _ui,_observe,binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True);guard()
        native=self._native_feature_observer(selector,read_only=True)
        return PhoneChatPeer(config,self.state_path(selector),binding,run,read_only=read_only,attach_files=attach_files,
            script_sha256=source_pins()['peer']['utf8Sha256'],clock_ms=native.clock_ms,monotonic=native.monotonic,sleep=native.sleep)

    def _chat_feature(self,selector,run,*,role='primary',client=None,retirement=False):
        from overte_phone_chat_feature import PhoneChatFeature
        from feature_journeys.phase_fixture import PhaseFixtureReader
        target=self.target(selector)
        require(self.candidate is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_CHAT_BOUND_DEBUG_TARGET_REQUIRED')
        if client is None:
            require(role=='primary','PHONE_CHAT_ACTOR_REQUIRES_SEPARATE_CLIENT');client=self._feature_fixture_client()
        metadata=self.chat_feature_store(selector).read() or self.chat_retirement_store(selector).read()
        if role=='actor':require(metadata is not None and metadata['runId']==run,'PHONE_CHAT_ORIGINAL_OWNER_REQUIRED')
        config=self._chat_configuration(metadata)
        return PhoneChatFeature(self,selector,PhaseFixtureReader(client,run,'chat'),config,role=role)

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

    def _recorded_preview_evidence(self, selector, *, read_only=False):
        native = self._native_feature_observer(selector,read_only=read_only)
        target = self.target(selector)
        device = target['capabilities']['appium:udid']
        transport = PhoneAdapter(self.candidate).adb
        return RecordedPreviewEvidence(native.send,
            lambda: transport.read_debug_app_file(device, target['appId'],
                'files/overte-e2e/' + RECORDED_PREVIEW_FILE, attempts=1),
            AndroidPreviewFiles(transport, device, target['appId'], native.guard),
            native.clock_ms, native.guard, native.pid)

    def _audio_source(self,selector,*,read_only=False):
        from overte_phone_audio_source import PhoneAudioSource,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneAudioSource(native,lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),read_only=read_only)

    def audio_feature_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('phone-audio-feature.json'))
    def audio_retirement_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('phone-audio-retirement.json'))
    def audio_mute_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('phone-audio-mute.json'))

    @staticmethod
    def _audio_configuration(metadata=None):
        from overte_phone_audio_peer import configuration
        if metadata is None:
            path=os.environ.get('OVERTE_PHONE_AUDIO_CONFIGURATION');require(type(path) is str and bool(path),'PHONE_AUDIO_CONFIGURATION_REQUIRED')
            value=PrivateFeatureState(Path(path)).read()
        else:value=metadata['configuration']
        value=configuration(value)
        require(value['artifactRoot']==os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR')
            and value['peerState']==os.environ.get('OVERTE_E2E_VOICE_PEER_STATE'),'PHONE_AUDIO_ORIGINAL_CONFIGURATION_CHANGED')
        return value

    def _audio_feature(self,selector,run,*,role='primary',client=None,retirement=False):
        from overte_phone_audio_feature import PhoneAudioFeature
        from overte_phone_audio_fixture import AudioFixtureReader
        target=self.target(selector);require(self.candidate is not None and target.get('appId')=='io.github.noah_be.overte.phone' and self.controlled_android_client(target),'PHONE_AUDIO_BOUND_DEBUG_TARGET_REQUIRED')
        if client is None:require(role=='primary','PHONE_AUDIO_ACTOR_REQUIRES_SEPARATE_CLIENT');client=self._feature_fixture_client()
        metadata=self.audio_feature_store(selector).read() or self.audio_retirement_store(selector).read()
        if metadata is not None:require(metadata['runId']==run and metadata['fixtureUrl']==client.url+'/runs/'+run+'/','PHONE_AUDIO_ORIGINAL_SCOPE_CHANGED')
        elif role=='actor' or retirement:require(False,'PHONE_AUDIO_ORIGINAL_OWNER_REQUIRED')
        config=self._audio_configuration(metadata)
        return PhoneAudioFeature(self,selector,AudioFixtureReader(client,run),config,role=role)

    def _audio_voice_status(self,selector):
        from adapters.voice_transport import exchange
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return exchange(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='status'),native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/voice-result.json',attempts=1),native.guard)

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

    def assets_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-assets-feature.json'))

    @staticmethod
    def _assets_configuration(*,actor=False):
        try:
            from overte_phone_assets_feature import configuration
            name='OVERTE_PHONE_ASSETS_ACTOR_CONFIGURATION' if actor else 'OVERTE_PHONE_ASSETS_CONFIGURATION'
            return configuration(PrivateFeatureState(Path(os.environ.get(name,''))).read(),actor=actor)
        except (OSError,RuntimeError,ValueError,TypeError,KeyError):
            raise ValueError('PHONE_FEATURE_ASSETS_CONFIGURATION_INVALID') from None

    def _assets_feature(self,selector,run,*,retirement=False):
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_assets_feature import PhoneAssetsFeature
        from overte_phone_script_history import unpack
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target) and type(retirement) is bool,'PHONE_FEATURE_ASSETS_REQUIRES_BOUND_DEBUG_TARGET')
        client=self._feature_fixture_client();metadata=self.assets_feature_store(selector).read()
        parent=PrivateFeatureState(self.state_path(selector).with_name('phone-assets-retirement.json')).read()
        if parent is not None:
            require(retirement,'PHONE_ASSETS_RETIREMENT_ALREADY_STARTED');original=unpack(parent['payload'])[0]['owner']
            require(metadata is None or metadata==original,'PHONE_ASSETS_ORIGINAL_CONFIGURATION_REQUIRED');metadata=original
        if retirement and metadata is None:
            from overte_phone_assets_retirement import completed_archive
            raw=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_ASSETS_CONFIGURATION',''))).read()
            require(type(raw) is dict and type(raw.get('artifactRoot')) is str,'PHONE_ASSETS_ORIGINAL_CONFIGURATION_REQUIRED')
            _ui,_service,binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True)
            metadata=completed_archive(Path(raw['artifactRoot']),binding,run,guard)['owner']
        if metadata is not None:require(metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
            'PHONE_ASSETS_ORIGINAL_CONFIGURATION_REQUIRED')
        # Live readonly credentials remain in the external private config. Only
        # their hashes occur in durable original headers.
        if retirement:
            raw=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_ASSETS_CONFIGURATION',''))).read()
            require(type(raw) is dict and type(raw.get('originalsReadToken')) is str,'PHONE_ASSETS_ORIGINAL_READER_CREDENTIAL_REQUIRED')
            config=dict(metadata['configuration'],originalsReadToken=raw['originalsReadToken'])
        else:config=self._assets_configuration()
        feature=PhoneAssetsFeature(self,selector,PhaseFixtureReader(client,run,'assets'),config,original_configuration=retirement)
        if metadata is not None:require(metadata['configuration']==feature.public_configuration(),'PHONE_ASSETS_ORIGINAL_CONFIGURATION_REQUIRED')
        return feature

    def _assets_actor(self,selector,run,*,client):
        from feature_journeys.witness import Client
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_assets_feature import PhoneAssetsFeature
        from overte_phone_assets_actor import PhoneAssetsActor
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target) and isinstance(client,Client),'PHONE_ASSETS_ACTOR_REQUIRES_BOUND_TARGET')
        metadata=self.assets_feature_store(selector).read()
        require(type(metadata) is dict and metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
            'PHONE_ASSETS_ACTOR_ORIGINAL_RUN_REQUIRED')
        feature=PhoneAssetsFeature(self,selector,PhaseFixtureReader(client,run,'assets'),self._assets_configuration(actor=True),role='actor')
        require(metadata['configuration']==feature.public_configuration(),'PHONE_ASSETS_ACTOR_ORIGINAL_CONFIGURATION_REQUIRED')
        return PhoneAssetsActor(feature)

    def create_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-create-feature.json'))

    @staticmethod
    def _create_configuration():
        try:
            from overte_phone_create_feature import configuration
            value=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_CREATE_CONFIGURATION',''))).read()
            return configuration(value)
        except (OSError,RuntimeError,ValueError,TypeError,KeyError):
            raise ValueError('PHONE_FEATURE_CREATE_CONFIGURATION_INVALID') from None

    def _create_feature(self,selector,run,*,retirement=False):
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_create_feature import PhoneCreateFeature
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_FEATURE_CREATE_REQUIRES_BOUND_DEBUG_TARGET')
        require(type(retirement) is bool,'PHONE_CREATE_ORIGINAL_CONFIGURATION_REQUIRED')
        client=self._feature_fixture_client();metadata=self.create_feature_store(selector).read()
        parent=PrivateFeatureState(self.state_path(selector).with_name('phone-create-retirement.json')).read()
        if parent is not None:
            from overte_phone_script_history import unpack
            require(retirement,'PHONE_CREATE_RETIREMENT_ALREADY_STARTED')
            original=unpack(parent['payload'])[0]['owner']
            require(metadata is None or metadata==original,'PHONE_CREATE_ORIGINAL_CONFIGURATION_REQUIRED');metadata=original
        if retirement:require(metadata is not None,'PHONE_CREATE_ORIGINAL_CONFIGURATION_REQUIRED')
        if metadata is not None:require(metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
            'PHONE_CREATE_ORIGINAL_CONFIGURATION_REQUIRED')
        return PhoneCreateFeature(self,selector,PhaseFixtureReader(client,run,'create'),metadata['configuration'] if retirement else self._create_configuration(),original_configuration=retirement)

    def _create_actor(self,selector,run,*,client):
        from feature_journeys.witness import Client
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_create_feature import PhoneCreateFeature
        from overte_phone_create_actor import PhoneCreateActor
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target) and isinstance(client,Client),'PHONE_CREATE_ACTOR_REQUIRES_BOUND_TARGET')
        metadata=self.create_feature_store(selector).read()
        require(type(metadata) is dict and metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
            'PHONE_CREATE_ACTOR_ORIGINAL_RUN_REQUIRED')
        return PhoneCreateActor(PhoneCreateFeature(self,selector,PhaseFixtureReader(client,run,'create'),metadata['configuration'],role='actor'))

    def emote_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-emote-run.json'))

    @staticmethod
    def _emote_configuration(metadata=None):
        try:
            from adapters.emote_admission import policy as admission_policy
            from adapters.native_phone_emote_fixture import input_command
            from feature_journeys.evidence import rectangle
            from overte_phone_emote_actor import image_policy
            if metadata is None:
                value=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_EMOTE_CONFIGURATION',''))).read()
                require(type(value) is dict and set(value)=={'emoteAdapterConfigurationVersion','imageExtent','markerRoi','imagePolicy','admissionPolicy'}
                    and type(value['emoteAdapterConfigurationVersion']) is int and value['emoteAdapterConfigurationVersion']==1,
                    'PHONE_EMOTE_PRIVATE_CONFIGURATION_REQUIRED')
                root=Path(os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
            else:
                require(type(metadata) is dict and type(metadata.get('emoteRunVersion')) is int
                    and metadata['emoteRunVersion']==6,'PHONE_EMOTE_ORIGINAL_CONFIGURATION_REQUIRED')
                value=metadata;root=Path(metadata['artifactRoot'])
            extent=deepcopy(value['imageExtent']);marker_roi=deepcopy(value['markerRoi'])
            input_command(dict(schemaVersion=1,commandId='a'*32,action='phone-emote-fixture-input',operation='prepare',
                runId='a'*32,fixtureUrl='http://fixture.test/feature-fixture/v1/runs/'+'a'*32+'/',ticket='a'*32,
                imageExtent=extent,markerRoi=marker_roi))
            policy=image_policy(value['imagePolicy']);marker=rectangle(policy['marker'],tuple(extent));subject=rectangle(policy['subject'],tuple(extent))
            require(marker[2]-marker[0]>=128 and marker[3]-marker[1]>=32
                and not (max(marker[0],subject[0])<min(marker[2],subject[2]) and max(marker[1],subject[1])<min(marker[3],subject[3])),
                'PHONE_EMOTE_IMAGE_POLICY_REQUIRED')
            admission=admission_policy(value['admissionPolicy'])
            PrivateFeatureState(root/'emote-configuration-boundary.json')._parent()
            return root,extent,marker_roi,policy,admission
        except (OSError,RuntimeError,ValueError,TypeError,KeyError):
            raise ValueError('PHONE_FEATURE_EMOTES_CONFIGURATION_INVALID') from None

    def _emote_feature(self,selector,run,*,retirement=False):
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_emote_run import PhoneEmoteRun
        from overte_phone_emote_feature import PhoneEmoteFeature
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_FEATURE_EMOTES_REQUIRES_BOUND_DEBUG_TARGET')
        require(type(retirement) is bool,'PHONE_EMOTE_ORIGINAL_CONFIGURATION_REQUIRED')
        client=self._feature_fixture_client();metadata=self.emote_feature_store(selector).read()
        parent=PrivateFeatureState(self.state_path(selector).with_name('phone-emote-retirement.json')).read()
        if parent is not None:
            require(retirement and type(parent) is dict,'PHONE_EMOTE_RETIREMENT_ALREADY_STARTED')
            original=parent.get('runHeader')
            require(metadata is None or metadata==original,'PHONE_EMOTE_ORIGINAL_CONFIGURATION_REQUIRED')
            metadata=original
        if retirement:require(metadata is not None,'PHONE_EMOTE_ORIGINAL_CONFIGURATION_REQUIRED')
        if metadata is not None:
            require(type(metadata) is dict and metadata.get('runId')==run
                and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/', 'PHONE_EMOTE_ORIGINAL_CONFIGURATION_REQUIRED')
        root,extent,marker,policy,admission=self._emote_configuration(metadata)
        owner=PhoneEmoteRun(self,selector,PhaseFixtureReader(client,run,'emotes'),root,extent,marker,
            admission=admission,image_policy=policy)
        return PhoneEmoteFeature(owner,policy)

    def _emote_actor(self,selector,run,*,client,image_policy):
        from feature_journeys.witness import Client
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_emote_run import PhoneEmoteRun
        from overte_phone_emote_actor import PhoneEmoteActor
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target) and isinstance(client,Client),'PHONE_EMOTE_ACTOR_REQUIRES_BOUND_TARGET')
        metadata=self.emote_feature_store(selector).read()
        require(type(metadata) is dict and metadata.get('runId')==run
            and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/','PHONE_EMOTE_ACTOR_ORIGINAL_RUN_REQUIRED')
        owner=PhoneEmoteRun(self,selector,PhaseFixtureReader(client,run,'emotes'),metadata['artifactRoot'],
            metadata['imageExtent'],metadata['markerRoi'],admission=metadata.get('admissionPolicy'),image_policy=metadata.get('imagePolicy'))
        return PhoneEmoteActor(owner,image_policy)

    @staticmethod
    def _navigation_configuration(metadata=None):
        from feature_journeys.evidence import rectangle
        if metadata is None:
            config=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_NAVIGATION_IMAGE_POLICY',''))).read()
            root=Path(os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
        else:
            require(type(metadata) is dict and type(metadata.get('navigationFeatureVersion')) is int
                and metadata['navigationFeatureVersion']==1,'PHONE_NAVIGATION_ORIGINAL_CONFIGURATION_REQUIRED')
            config=metadata['imagePolicy'];root=Path(metadata['artifactRoot'])
        require(type(config) is dict and set(config)=={'imageExtent','markerRoi','imagePolicy'},'PHONE_NAVIGATION_IMAGE_POLICY_REQUIRED')
        extent=config['imageExtent']
        require(type(extent) is list and len(extent)==2 and all(type(v) is int and 240<=v<=4096 for v in extent),'PHONE_NAVIGATION_IMAGE_POLICY_REQUIRED')
        outer=rectangle(config['markerRoi'],extent);policy=config['imagePolicy']
        require(type(policy) is dict and set(policy)=={'source','marker','subject'} and policy['source']=='world-render-target','PHONE_NAVIGATION_IMAGE_POLICY_REQUIRED')
        marker=rectangle(policy['marker'],extent);subject=rectangle(policy['subject'],extent)
        w,h=outer[2]-outer[0],outer[3]-outer[1]
        require(w>=160 and h>=40 and w*h<=.1*extent[0]*extent[1]
            and marker==tuple(round(v) for v in (outer[0]+w*4/160,outer[1]+h*4/40,outer[0]+w*132/160,outer[1]+h*36/40))
            and not (max(outer[0],subject[0])<min(outer[2],subject[2]) and max(outer[1],subject[1])<min(outer[3],subject[3])),
            'PHONE_NAVIGATION_IMAGE_POLICY_REQUIRED')
        PrivateFeatureState(root/'navigation-configuration-boundary.json')._parent()
        return root,deepcopy(config)

    def navigation_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-navigation-feature.json'))

    def navigation_retirement_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-navigation-retirement.json'))

    def _navigation_feature(self,selector,run,*,role='primary',client=None,retirement=False):
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_NAVIGATION_REQUIRES_BOUND_DEBUG_TARGET')
        if client is None:
            require(role=='primary','PHONE_NAVIGATION_ACTOR_REQUIRES_SEPARATE_CLIENT');client=self._feature_fixture_client()
        metadata=None
        if role=='actor' or retirement:
            metadata=self.navigation_feature_store(selector).read() or self.navigation_retirement_store(selector).read()
            require(type(metadata) is dict and metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
                'PHONE_NAVIGATION_ORIGINAL_CONFIGURATION_REQUIRED')
        root,policy=self._navigation_configuration(metadata)
        return PhoneNavigationFeature(self,selector,NavigationFixtureReader(client,run),root,policy,role=role)

    def _navigation_probe(self,selector,after=0):
        from navigation_observation import project_probe
        from contracts import validate_operation_result
        with self.existing_input_session(selector):
            return project_probe(validate_operation_result('probe.snapshot',self.invoke(selector,'probe.snapshot',
                {'afterSampleSequence':after} if after else {})))

    def lifecycle_input_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-lifecycle-input-feature.json'))

    def lifecycle_input_retirement_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-lifecycle-input-retirement.json'))

    def lifecycle_input_completed_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-lifecycle-input-completed.json'))

    @classmethod
    def _lifecycle_input_configuration(cls,metadata=None):
        if metadata is None:
            policy=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_LIFECYCLE_INPUT_IMAGE_POLICY',''))).read()
            root=Path(os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
        else:
            require(type(metadata) is dict and type(metadata.get('lifecycleInputFeatureVersion')) is int
                and metadata['lifecycleInputFeatureVersion']==1,'PHONE_LIFECYCLE_INPUT_ORIGINAL_CONFIGURATION_REQUIRED')
            policy=metadata['imagePolicy'];root=Path(metadata['artifactRoot'])
        # Reuse the exact external original world-render/marker ROI contract.
        return cls._navigation_configuration(dict(navigationFeatureVersion=1,imagePolicy=policy,artifactRoot=str(root)))

    def _lifecycle_input_feature(self,selector,run,*,role='primary',client=None,retirement=False):
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_lifecycle_feature import PhoneLifecycleInputFeature
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_LIFECYCLE_INPUT_REQUIRES_BOUND_DEBUG_TARGET')
        if client is None:
            require(role=='primary','PHONE_LIFECYCLE_INPUT_ACTOR_REQUIRES_SEPARATE_CLIENT');client=self._feature_fixture_client()
        metadata=None
        if role=='actor' or retirement:
            metadata=self.lifecycle_input_feature_store(selector).read() or self.lifecycle_input_retirement_store(selector).read() or self.lifecycle_input_completed_store(selector).read()
            require(type(metadata) is dict and metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
                'PHONE_LIFECYCLE_INPUT_ORIGINAL_CONFIGURATION_REQUIRED')
        root,policy=self._lifecycle_input_configuration(metadata)
        return PhoneLifecycleInputFeature(self,selector,PhaseFixtureReader(client,run,'lifecycle-input'),root,policy,role=role)

    def _avatar_people_controls(self,selector,*,read_only=False):
        from overte_phone_avatar_people_native import PhoneAvatarPeopleIO,UI_FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneAvatarPeopleIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def avatar_people_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-avatar-people-feature.json'))

    def avatar_people_retirement_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-avatar-people-retirement.json'))

    @staticmethod
    def _avatar_people_configuration(metadata=None):
        if metadata is None:
            policy=PrivateFeatureState(Path(os.environ.get('OVERTE_PHONE_AVATAR_PEOPLE_IMAGE_POLICY',''))).read()
            root=Path(os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
        else:
            from overte_phone_script_history import unpack
            require(type(metadata) is dict and type(metadata.get('avatarPeopleFeatureVersion')) is int
                and metadata['avatarPeopleFeatureVersion']==1,'PHONE_AVATAR_PEOPLE_ORIGINAL_CONFIGURATION_REQUIRED')
            rows=unpack(metadata['payload']);require(len(rows)==1,'PHONE_AVATAR_PEOPLE_ORIGINAL_CONFIGURATION_REQUIRED')
            if metadata['kind']=='retirement':
                from overte_phone_avatar_people_feature import read_blob
                owner=read_blob(metadata['artifactRoot'],metadata['runId'],rows[0]['owner'])
            else:owner=rows[0]
            policy=owner['policy'];root=Path(metadata['artifactRoot'])
        policy=avatar_people_image_policy(policy)
        PrivateFeatureState(root/'avatar-people-configuration-boundary.json')._parent()
        return root,policy

    def _avatar_people_feature(self,selector,run,*,role='primary',client=None,retirement=False,peer_selector=None,peer_policy=None):
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_AVATAR_PEOPLE_REQUIRES_BOUND_DEBUG_TARGET')
        if client is None:
            require(role=='primary','PHONE_AVATAR_PEOPLE_ACTOR_REQUIRES_SEPARATE_CLIENT');client=self._feature_fixture_client()
        metadata=None
        if role=='actor' or retirement:
            metadata=self.avatar_people_feature_store(selector).read() or self.avatar_people_retirement_store(selector).read()
            require(type(metadata) is dict and metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
                'PHONE_AVATAR_PEOPLE_ORIGINAL_CONFIGURATION_REQUIRED')
        if role=='actor':
            peer=self.target(peer_selector)
            require(peer_selector!=selector and peer.get('appId')=='io.github.noah_be.overte.phone'
                and self.controlled_android_client(peer),'PHONE_AVATAR_PEOPLE_REQUIRES_INDEPENDENT_PHONE')
            avatar_people_image_policy(peer_policy)
        root,policy=self._avatar_people_configuration(metadata)
        return PhoneAvatarPeopleFeature(self,selector,AvatarPeopleFixtureReader(client,run),root,policy,
            role=role,peer_selector=peer_selector,peer_policy=peer_policy)

    def _avatar_people_source(self,selector,*,read_only=True):
        from overte_phone_avatar_people_native import PhoneAvatarPeopleObservation,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneAvatarPeopleObservation(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _navigation_controls(self,selector,*,read_only=False):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneNavigationIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+NAVIGATION_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _navigation_view(self,selector,*,read_only=False):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneNavigationView(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+NAVIGATION_VIEW_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _navigation_marker(self,selector,*,read_only=True):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneNavigationMarker(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+NAVIGATION_MARKER_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _navigation_marker_input(self,selector,request):
        from overte_phone_navigation_marker import input_command
        input_command(request)
        # The existing private file exchange is used once; this is a controlled
        # test fixture input, never a product observation or a UI shortcut.
        reader=self._navigation_view(selector);reader.send(deepcopy(request))
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        started=previous=reader.monotonic()
        for attempt in range(51):
            reader.guard();raw=transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+NAVIGATION_MARKER_FILE,attempts=1)
            try:value=json.loads(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=reader.monotonic();require(previous<=now and now-started<5,'PHONE_NAVIGATION_MARKER_INPUT_TIMEOUT');previous=now
            if type(value) is dict and value.get('commandId')==request['commandId']:
                require(reader.guard() is not False,'PHONE_NAVIGATION_MARKER_GUARD_LOST');return value
            if attempt<50:reader.sleep(.1)
        require(False,'PHONE_NAVIGATION_MARKER_INPUT_TIMEOUT')

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

    def web_reference_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-web-reference.json'))

    def web_reference_retired_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-web-reference-retired.json'))

    def web_reference_manager_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-web-reference-manager.json'))

    def _web_reference(self,selector):
        from overte_phone_web_reference import PhoneWebReference
        return PhoneWebReference(self,selector)

    def _web_reference_manager(self,selector):
        native,observe,binding,_guard,_installed=self.normal_feature_runtime(selector,read_only=True)
        return NormalScriptManager(PhoneScriptUI(native,'io.github.noah_be.overte.phone'),observe,
            self.web_reference_manager_store(selector),binding,source_kind='feature-web-reference')

    def _web_reference_tablet(self,selector,operation):
        from adapters.normal_ui import Locator
        require(operation in ('open','close'),'PHONE_WEB_REFERENCE_TABLET_OPERATION_INVALID')
        native,_observe,_binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True)
        ui=PhoneScriptUI(native,'io.github.noah_be.overte.phone')
        if operation=='close':
            if ui.tablet_visible():
                if native.available(ui.resource('nav.home')):native.click(ui.resource('nav.home'))
                ui.close_tablet()
            ui.wait_tablet_absent();guard();return {'performed':True}
        require(not ui.tablet_visible(),'PHONE_WEB_REFERENCE_FOREIGN_TABLET_OPEN')
        ui.open_tablet();entry=Locator('accessibility id','WEB TEST')
        if native.available(ui.resource('nav.home')):native.click(ui.resource('nav.home'))
        if not native.available(entry):
            for page in range(1,9):
                button=ui.resource('tabletPage.'+str(page))
                if native.available(button):native.click(button)
                if native.available(entry):break
        native.click(entry);guard();return {'performed':True}

    def world_web_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-world-web-feature.json'))

    def world_web_retirement_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-world-web-retirement.json'))

    def world_web_manager_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-world-web-manager.json'))

    def _world_web_configuration(self,metadata=None):
        from overte_phone_world_web_source import fixture
        if metadata is None:
            path=os.environ.get('OVERTE_PHONE_WORLD_WEB_CONFIGURATION')
            require(type(path) is str and bool(path),'PHONE_WORLD_WEB_CONFIGURATION_REQUIRED')
            value=PrivateFeatureState(Path(path)).read()
            require(type(value) is dict and set(value)=={'worldWebConfigurationVersion','artifactRoot','foreignFixtureUrl'}
                and type(value['worldWebConfigurationVersion']) is int and value['worldWebConfigurationVersion']==1,
                'PHONE_WORLD_WEB_CONFIGURATION_INVALID')
        else:value=metadata
        root=Path(value['artifactRoot']);PrivateFeatureState(root/'world-web-configuration-boundary.json')._parent()
        if metadata is None and 'OVERTE_DEVICE_ARTIFACT_DIR' in os.environ:
            require(root==Path(os.environ['OVERTE_DEVICE_ARTIFACT_DIR']),'PHONE_WORLD_WEB_ARTIFACT_ROOT_CHANGED')
        foreign=value['foreignFixtureUrl'];fixture('a'*32,foreign+'/runs/'+'a'*32+'/')
        return root,foreign

    def _world_web_feature(self,selector,run,*,role='primary',client=None,retirement=False):
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_world_web_feature import PhoneWorldWebFeature
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_WORLD_WEB_REQUIRES_BOUND_DEBUG_TARGET')
        if client is None:
            require(role=='primary','PHONE_WORLD_WEB_ACTOR_REQUIRES_SEPARATE_CLIENT');client=self._feature_fixture_client()
        metadata=self.world_web_feature_store(selector).read() or self.world_web_retirement_store(selector).read()
        if metadata is not None:
            require(metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
                'PHONE_WORLD_WEB_ORIGINAL_CONFIGURATION_REQUIRED')
        elif role=='actor' or retirement:require(False,'PHONE_WORLD_WEB_ORIGINAL_CONFIGURATION_REQUIRED')
        root,foreign=self._world_web_configuration(metadata)
        return PhoneWorldWebFeature(self,selector,PhaseFixtureReader(client,run,'world-web'),root,foreign,role=role)

    def _world_web_io(self,selector,*,read_only=True):
        from overte_phone_world_web_source import PhoneWorldWebIO,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneWorldWebIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _world_web_clock(self,selector):
        return self._native_feature_observer(selector,read_only=True).clock_ms()

    def _world_web_manager(self,selector):
        native,observe,binding,_guard,_installed=self.normal_feature_runtime(selector,read_only=True)
        return NormalScriptManager(PhoneScriptUI(native,'io.github.noah_be.overte.phone'),observe,
            self.world_web_manager_store(selector),binding,source_kind='feature-world-web')

    def tablet_controls_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-tablet-controls.json'))

    def _tablet_controls(self,selector):
        from overte_phone_tablet_controls import PhoneTabletControls
        native,_observe,binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True)
        return PhoneTabletControls(PhoneScriptUI(native,'io.github.noah_be.overte.phone'),self.tablet_controls_store(selector),binding,guard)

    def normal_tablet_control(self,selector,operation):
        from overte_phone_script_lock import PhoneScriptSourceLock
        lock=PhoneScriptSourceLock(self.state_path(selector).with_name('phone-script-sources.lock'))
        with lock.held(),self.existing_input_session(selector):
            return getattr(self._tablet_controls(selector),operation.rsplit('.',1)[1])()

    def tablet_web_feature_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-tablet-web-feature.json'))

    def tablet_web_retirement_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-tablet-web-retirement.json'))

    def tablet_web_manager_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('phone-tablet-web-manager.json'))

    def _tablet_web_configuration(self,metadata=None):
        from overte_phone_world_web_source import fixture
        if metadata is None:
            path=os.environ.get('OVERTE_PHONE_TABLET_WEB_CONFIGURATION')
            require(type(path) is str and bool(path),'PHONE_TABLET_WEB_CONFIGURATION_REQUIRED')
            value=PrivateFeatureState(Path(path)).read()
            require(type(value) is dict and set(value)=={'tabletWebConfigurationVersion','artifactRoot','foreignFixtureUrl'}
                and type(value['tabletWebConfigurationVersion']) is int and value['tabletWebConfigurationVersion']==1,
                'PHONE_TABLET_WEB_CONFIGURATION_INVALID')
        else:value=metadata
        root=Path(value['artifactRoot']);PrivateFeatureState(root/'tablet-web-configuration-boundary.json')._parent()
        if metadata is None and 'OVERTE_DEVICE_ARTIFACT_DIR' in os.environ:
            require(root==Path(os.environ['OVERTE_DEVICE_ARTIFACT_DIR']),'PHONE_TABLET_WEB_ARTIFACT_ROOT_CHANGED')
        foreign=value['foreignFixtureUrl'];fixture('a'*32,foreign+'/runs/'+'a'*32+'/')
        return root,foreign

    def _tablet_web_feature(self,selector,run,*,role='primary',client=None,retirement=False):
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from overte_phone_tablet_web_feature import PhoneTabletWebFeature
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_TABLET_WEB_REQUIRES_BOUND_DEBUG_TARGET')
        if client is None:
            require(role=='primary','PHONE_TABLET_WEB_ACTOR_REQUIRES_SEPARATE_CLIENT');client=self._feature_fixture_client()
        metadata=self.tablet_web_feature_store(selector).read() or self.tablet_web_retirement_store(selector).read()
        if metadata is not None:
            require(metadata.get('runId')==run and metadata.get('fixtureUrl')==client.url+'/runs/'+run+'/',
                'PHONE_TABLET_WEB_ORIGINAL_CONFIGURATION_REQUIRED')
        elif role=='actor' or retirement:require(False,'PHONE_TABLET_WEB_ORIGINAL_CONFIGURATION_REQUIRED')
        root,foreign=self._tablet_web_configuration(metadata)
        return PhoneTabletWebFeature(self,selector,PhaseFixtureReader(client,run,'tablet-web'),root,foreign,role=role)

    def _tablet_web_io(self,selector,*,read_only=True):
        from overte_phone_tablet_web_source import PhoneTabletWebIO
        from overte_phone_world_web_source import FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneTabletWebIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _tablet_web_clock(self,selector):
        return self._native_feature_observer(selector,read_only=True).clock_ms()

    def _tablet_web_manager(self,selector):
        native,observe,binding,_guard,_installed=self.normal_feature_runtime(selector,read_only=True)
        return NormalScriptManager(PhoneScriptUI(native,'io.github.noah_be.overte.phone'),observe,
            self.tablet_web_manager_store(selector),binding,source_kind='feature-tablet-web')

    def _tablet_web_entry(self,selector,label,*,initial):
        from adapters.normal_ui import Locator
        require(label in ('WEB TEST','INLINE TEST') and type(initial) is bool,'PHONE_TABLET_WEB_ENTRY_INVALID')
        native,_observe,_binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True)
        ui=PhoneScriptUI(native,'io.github.noah_be.overte.phone')
        if initial:
            require(not ui.tablet_visible(),'PHONE_TABLET_WEB_FOREIGN_TABLET_OPEN');ui.open_tablet()
        else:require(ui.tablet_visible(),'PHONE_TABLET_WEB_OWNED_TABLET_MISSING')
        if native.available(ui.resource('nav.home')):native.click(ui.resource('nav.home'))
        entry=Locator('accessibility id',label)
        if not native.available(entry):
            for page in range(1,9):
                button=ui.resource('tabletPage.'+str(page))
                if native.available(button):native.click(button)
                if native.available(entry):break
        native.click(entry);guard();return {'performed':True}

    def _tablet_web_close(self,selector):
        return self._web_reference_tablet(selector,'close')

    def _web_runtime_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_WEB_RUNTIME_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneWebRuntime(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+WEB_RUNTIME_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _emote_fixture_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_EMOTE_FIXTURE_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneEmoteFixture(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+EMOTE_FIXTURE_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _emote_fixture_input(self, selector, command, *, lock, intent):
        require(self.candidate is not None and self.controlled_android_client(self.target(selector)),
                'PHONE_EMOTE_FIXTURE_BOUND_DEBUG_TARGET_REQUIRED')
        require(isinstance(lock,PhoneScriptSourceLock) and lock.path==self.state_path(selector).with_name('phone-script-sources.lock')
                and callable(intent),'PHONE_EMOTE_FIXTURE_INPUT_REQUIRES_DURABLE_OWNER')
        command=deepcopy(emote_fixture_input_command(command));lock.assert_held()
        with self.existing_input_session(selector):
            _ui,_service,binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True)
            client,session,_state=self.existing_session(selector);target=self.target(selector)
            guard();self._guarded_existing_session(selector,self._existing_input_scope);lock.assert_held()
            require(intent(deepcopy(command),deepcopy(binding)) is not False,'PHONE_EMOTE_FIXTURE_INTENT_NOT_RECORDED')
            guard();self._guarded_existing_session(selector,self._existing_input_scope);lock.assert_held()
            self.write_android_client_command(client,session,target,command,{'running':True,'identity':binding['processIdentity']})
            guard();self._guarded_existing_session(selector,self._existing_input_scope);lock.assert_held()
            return {'performed':True} # Never fixture readiness, pixels or cleanup.

    def _create_fixture_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_CREATE_FIXTURE_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneCreateFixture(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CREATE_FIXTURE_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _create_fixture_input(self, selector, command, *, lock, intent):
        require(self.candidate is not None and self.controlled_android_client(self.target(selector)),
                'PHONE_CREATE_FIXTURE_BOUND_DEBUG_TARGET_REQUIRED')
        require(isinstance(lock,PhoneScriptSourceLock) and lock.path==self.state_path(selector).with_name('phone-script-sources.lock')
                and callable(intent),'PHONE_CREATE_FIXTURE_INPUT_REQUIRES_DURABLE_OWNER')
        command=deepcopy(create_fixture_input_command(command));lock.assert_held()
        with self.existing_input_session(selector):
            _ui,_service,binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True)
            client,session,_state=self.existing_session(selector);target=self.target(selector)
            guard();self._guarded_existing_session(selector,self._existing_input_scope);lock.assert_held()
            require(intent(deepcopy(command),deepcopy(binding)) is not False,'PHONE_CREATE_FIXTURE_INTENT_NOT_RECORDED')
            guard();self._guarded_existing_session(selector,self._existing_input_scope);lock.assert_held()
            self.write_android_client_command(client,session,target,command,{'running':True,'identity':binding['processIdentity']})
            guard();self._guarded_existing_session(selector,self._existing_input_scope);lock.assert_held()
            return {'performed':True} # Never fixture readiness, pixels or cleanup.

    def _touch_state_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_TOUCH_STATE_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneTouchState(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+TOUCH_STATE_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _avatar_configuration_observer(self, selector, *, read_only=True):
        require(read_only is True,'PHONE_AVATAR_CONFIGURATION_REQUIRES_EXISTING_READ_ONLY_SESSION')
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativePhoneAvatarConfiguration(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+AVATAR_CONFIGURATION_FILE,attempts=1),
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

    def _create_files(self, selector, *, read_only=True):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return PhoneCreateFiles(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],
                'files/overte-e2e/'+CREATE_FILES_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _assets_uploads(self,selector,*,read_only=True):
        from overte_phone_assets_uploads import PhoneAssetsUploads,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneAssetsUploads(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _assets_files(self,selector,*,read_only=True,stage=None):
        from overte_phone_assets_files import PhoneAssetsFiles,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneAssetsFiles(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep,stage=stage)

    def _assets_source(self,selector,*,download=False,resolve=False,read_only=True):
        from overte_phone_assets_source import PhoneAssetsSource,FILE,DOWNLOAD_FILE,RESOLVE_FILE
        require(type(download) is bool and type(resolve) is bool and not(download and resolve) and type(read_only) is bool,'PHONE_ASSETS_READ_SCOPE_INVALID')
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        name=DOWNLOAD_FILE if download else RESOLVE_FILE if resolve else FILE
        return PhoneAssetsSource(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+name,attempts=1),
            native.clock_ms,native.guard,native.pid,download=download,resolve=resolve,monotonic=native.monotonic,sleep=native.sleep)

    def _create_source(self, selector, *, read_only=True):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return PhoneCreateSource(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],
                'files/overte-e2e/'+CREATE_SOURCE_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _lifecycle_editor(self,selector,*,read_only=True,intent=None):
        from overte_phone_lifecycle_editor import PhoneLifecycleEditorSource,FILE
        require(type(read_only) is bool and (not read_only or intent is None),'PHONE_LIFECYCLE_EDITOR_SCOPE_INVALID')
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneLifecycleEditorSource(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,intent=intent,monotonic=native.monotonic,sleep=native.sleep)

    def _lifecycle_world(self,selector,*,read_only=True,intent=None):
        from overte_phone_lifecycle_world import PhoneLifecycleWorldSource,FILE
        require(type(read_only) is bool and (not read_only or intent is None),'PHONE_LIFECYCLE_WORLD_SCOPE_INVALID')
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneLifecycleWorldSource(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,intent=intent,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_upload_source(self,selector):
        from overte_phone_snapshot_upload_source import PhoneSnapshotUploadSource,FILE
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotUploadSource(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_documents(self,selector,run,arm,receiver_apk_sha256,application_binding,resolution,authority,*,read_only=True,binding=None):
        from overte_phone_snapshot_documents import PhoneSnapshotDocuments,SnapshotDocumentsTransport
        from overte_phone_snapshot_documents_ui import resolution as validate_resolution
        validate_resolution(resolution)
        scope=self._snapshot_system_context(selector,application_binding,resolution,authority)
        target=self.target(selector);device=target['capabilities']['appium:udid'];adb=PhoneAdapter(self.candidate).adb
        transport=SnapshotDocumentsTransport(adb,device,receiver_apk_sha256,scope.guard,read_only=read_only)
        return PhoneSnapshotDocuments(transport,lambda:adb.epoch_milliseconds(device),scope.guard,run,arm,
            read_only=read_only,binding=binding)

    def _snapshot_phone_uid(self,selector,application_binding,resolution,authority):
        from adapters.native_feature_observation import need,number
        import shlex
        import time
        scope=self._snapshot_system_context(selector,application_binding,resolution,authority)
        target=self.target(selector);device=target['capabilities']['appium:udid'];adb=PhoneAdapter(self.candidate).adb
        scope.guard();start=time.monotonic();requested=adb.epoch_milliseconds(device)
        raw=adb.execute(['shell',shlex.join(['run-as',target['appId'],'id','-u'])],target=device,timeout=5)
        need(type(raw) is str and re.fullmatch('[1-9][0-9]{0,9}',raw.strip()))
        scope.guard();captured=adb.epoch_milliseconds(device);now=time.monotonic()
        need(type(requested) is int and type(captured) is int and 0<=captured-requested<=1500 and number(now,start,1e15) and now-start<=1.5)
        return dict(snapshotPhoneUidVersion=1,uid=int(raw.strip()),requestedEpochMs=requested,capturedEpochMs=captured)

    def _snapshot_system_documents(self,selector,run,arm,receiver_apk_sha256,application_binding,handoff_resolution,authority,*,binding):
        from overte_phone_snapshot_documents import PhoneSnapshotDocuments,SnapshotDocumentsTransport
        require(type(binding) is dict and binding.get('runId')==run and binding.get('armId')==arm,
            'PHONE_SNAPSHOT_ORIGINAL_DOCUMENT_BINDING_REQUIRED')
        scope=self._snapshot_system_context(selector,application_binding,handoff_resolution,authority)
        target=self.target(selector);device=target['capabilities']['appium:udid'];adb=PhoneAdapter(self.candidate).adb
        transport=SnapshotDocumentsTransport(adb,device,receiver_apk_sha256,scope.guard,read_only=True)
        return PhoneSnapshotDocuments(transport,lambda:adb.epoch_milliseconds(device),scope.guard,run,arm,
            read_only=True,binding=binding)

    def _snapshot_document_resolution(self,selector):
        from overte_phone_snapshot_documents_ui import SnapshotDocumentResolution
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);transport=PhoneAdapter(self.candidate).adb
        return SnapshotDocumentResolution(transport,target['capabilities']['appium:udid'],native.guard,native.clock_ms,
            monotonic=native.monotonic)

    def _snapshot_document_ui(self,selector,binding,resolution,intent,authority):
        from overte_phone_snapshot_documents_ui import PhoneSnapshotDocumentsUI,resolution as validate_resolution
        from adapters.normal_ui import NativeUI
        validate_resolution(resolution);scope=self._snapshot_system_context(selector,binding,resolution,authority)
        client,session,_state=self.existing_session(selector);target=self.target(selector)
        transport=PhoneAdapter(self.candidate).adb;device=target['capabilities']['appium:udid']
        return PhoneSnapshotDocumentsUI(NativeUI(client,session,scope.guard),intent,
            lambda:transport.epoch_milliseconds(device),resolution['component'])

    def _snapshot_share_resolution(self,selector):
        from overte_phone_snapshot_resolution import SnapshotChooserResolution
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);transport=PhoneAdapter(self.candidate).adb
        return SnapshotChooserResolution(transport,target['capabilities']['appium:udid'],native.guard,native.clock_ms,
            monotonic=native.monotonic)

    def _snapshot_system_context(self,selector,binding,resolution,authority):
        from overte_phone_snapshot_system_context import SnapshotSystemContext
        from overte_phone_snapshot_system_ui import component
        target=self.target(selector)
        require(getattr(self,'candidate',None) is not None and target.get('appId')=='io.github.noah_be.overte.phone'
            and self.controlled_android_client(target),'PHONE_SNAPSHOT_SYSTEM_BOUND_DEBUG_TARGET_REQUIRED')
        client,session,_state=self.existing_session(selector)
        require(session==binding['sessionId'],'PHONE_SNAPSHOT_SYSTEM_ORIGINAL_SESSION_REQUIRED')
        def current():
            base='/session/'+session
            return component(client.call('GET',base+'/appium/device/current_package'),
                client.call('GET',base+'/appium/device/current_activity'))
        if type(resolution) is dict and 'snapshotDocumentResolutionVersion' in resolution:
            from overte_phone_snapshot_documents_ui import SnapshotDocumentContext
            scope=SnapshotDocumentContext(binding,resolution,lambda:self._graphics_lifecycle_status(selector,binding),current,authority)
        else:scope=SnapshotSystemContext(binding,resolution,lambda:self._graphics_lifecycle_status(selector,binding),current,authority)
        scope.guard()
        return scope

    def _snapshot_share_ui(self,selector,binding,resolution,intent,authority):
        from overte_phone_snapshot_system_ui import PhoneSnapshotSystemUI
        from adapters.normal_ui import NativeUI
        scope=self._snapshot_system_context(selector,binding,resolution,authority)
        client,session,_state=self.existing_session(selector);target=self.target(selector)
        transport=PhoneAdapter(self.candidate).adb;device=target['capabilities']['appium:udid']
        return PhoneSnapshotSystemUI(NativeUI(client,session,scope.guard),intent,
            lambda:transport.epoch_milliseconds(device),resolution['component'])

    def _snapshot_system_consumer(self,selector,run,arm,receiver_apk_sha256,application_binding,resolution,authority,*,read_only=True,binding=None):
        from overte_phone_snapshot_consumer import PhoneSnapshotConsumer,SnapshotConsumerTransport
        scope=self._snapshot_system_context(selector,application_binding,resolution,authority)
        target=self.target(selector);device=target['capabilities']['appium:udid'];adb=PhoneAdapter(self.candidate).adb
        transport=SnapshotConsumerTransport(adb,device,receiver_apk_sha256,scope.guard,read_only=read_only)
        return PhoneSnapshotConsumer(transport.read,transport.binary,transport.control,transport.identity,
            lambda:adb.epoch_milliseconds(device),scope.guard,run,arm,read_only=read_only,binding=binding)

    def _snapshot_platform(self,selector):
        from overte_phone_snapshot_platform import PhoneSnapshotPlatform
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotPlatform(lambda:transport.prop(device,'ro.build.version.sdk'),native.guard,native.clock_ms,
            monotonic=native.monotonic)

    def _snapshot_handoff_control(self,selector,*,read_only=False):
        from overte_phone_snapshot_handoff import PhoneSnapshotHandoffControl,CONTROL_FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotHandoffControl(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CONTROL_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_handoff_source(self,selector,application_binding,resolution,authority,handoff_binding):
        from overte_phone_snapshot_handoff import PhoneSnapshotHandoff,FILE,binding as validate_binding
        validate_binding(handoff_binding)
        scope=self._snapshot_system_context(selector,application_binding,resolution,authority)
        require(handoff_binding['processId']==int(application_binding['processIdentity'].split(':')[0]),
            'PHONE_SNAPSHOT_HANDOFF_ORIGINAL_PID_REQUIRED')
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotHandoff(
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            lambda:transport.epoch_milliseconds(device),scope.guard,handoff_binding)

    def _snapshot_measurements(self,selector):
        from overte_phone_snapshot_measurements import PhoneSnapshotMeasurements
        native=self._native_feature_observer(selector,read_only=True)
        return PhoneSnapshotMeasurements(self._script_roots(selector,read_only=True),
            self._script_execution_observer(selector,read_only=True),self._snapshot_source(selector),
            native.guard,native.clock_ms,native.pid,monotonic=native.monotonic)

    def _snapshot_system_files(self,selector,artifact_root,owner_path,application_binding,resolution,authority,handoff_source):
        from overte_phone_snapshot_capture_files import CaptureFileTransport,PhoneSnapshotCaptureFiles
        from overte_phone_snapshot_system_files import SnapshotSystemFileSource
        from overte_phone_snapshot_handoff import PhoneSnapshotHandoff
        scope=self._snapshot_system_context(selector,application_binding,resolution,authority)
        require(isinstance(handoff_source,PhoneSnapshotHandoff)
            and handoff_source.owner['processId']==int(application_binding['processIdentity'].split(':')[0]),
            'PHONE_SNAPSHOT_PASSIVE_FILE_ORIGINAL_SOURCE_REQUIRED')
        # Reuse this role's original reader, retaining every nested sequence
        # floor across the file-owner reads and the final measurement group.
        source=SnapshotSystemFileSource(handoff_source)
        target=self.target(selector);binding={key:application_binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')}
        transport=CaptureFileTransport(PhoneAdapter(self.candidate).adb,target['capabilities']['appium:udid'],target['appId'],
            binding,scope.guard,artifact_root)
        return PhoneSnapshotCaptureFiles(transport,source,application_binding,owner_path,read_only=True)

    def _snapshot_system_platform(self,selector,application_binding,resolution,authority):
        from overte_phone_snapshot_platform import PhoneSnapshotPlatform
        scope=self._snapshot_system_context(selector,application_binding,resolution,authority)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotPlatform(lambda:transport.prop(device,'ro.build.version.sdk'),scope.guard,
            lambda:transport.epoch_milliseconds(device))

    def _snapshot_source(self,selector):
        from overte_phone_snapshot_source import PhoneSnapshotSource,FILE
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotSource(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_capture_file_source(self,selector,*,read_only=True):
        from overte_phone_snapshot_capture_source import PhoneSnapshotCaptureFileSource,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotCaptureFileSource(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,read_only=read_only,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_readbacks(self,selector,*,read_only=True):
        from overte_phone_snapshot_readbacks import PhoneSnapshotReadbacks,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotReadbacks(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_capture_files(self,selector,artifact_root,owner_path,*,read_only=False):
        from overte_phone_snapshot_capture_files import CaptureFileTransport,PhoneSnapshotCaptureFiles
        _ui,_observe,binding,guard,_installed=self.normal_feature_runtime(selector,read_only=read_only)
        target=self.target(selector);context={key:binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')}
        transport=CaptureFileTransport(PhoneAdapter(self.candidate).adb,target['capabilities']['appium:udid'],
            target['appId'],context,guard,artifact_root)
        return PhoneSnapshotCaptureFiles(transport,self._snapshot_capture_file_source(selector,read_only=read_only),
            binding,owner_path,read_only=read_only)

    def _snapshot_cancel(self,selector,*,read_only=True):
        from overte_phone_snapshot_cancel import PhoneSnapshotCancel,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotCancel(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_settings(self,selector,*,read_only=True):
        from overte_phone_snapshot_settings import PhoneSnapshotSettings,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotSettings(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep,read_only=read_only)

    def _snapshot_consumer(self,selector,run,arm,receiver_apk_sha256,*,read_only=True,binding=None):
        from overte_phone_snapshot_consumer import PhoneSnapshotConsumer,SnapshotConsumerTransport
        # A separate prepared fixture APK pin is mandatory. No fixture install,
        # implicit package discovery or successful Chooser result is inferred.
        native=self._native_feature_observer(selector,read_only=True)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=SnapshotConsumerTransport(PhoneAdapter(self.candidate).adb,device,
            receiver_apk_sha256,native.guard,read_only=read_only)
        return PhoneSnapshotConsumer(transport.read,transport.binary,transport.control,
            transport.identity,native.clock_ms,native.guard,run,arm,read_only=read_only,binding=binding,
            monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_saved_files(self,selector,run,artifact_root):
        from overte_phone_snapshot_saved_files import PhoneSnapshotSavedFiles
        _ui,_observe,binding,guard,_installed=self.normal_feature_runtime(selector,read_only=True)
        target=self.target(selector);context={key:binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')}
        return PhoneSnapshotSavedFiles(PhoneAdapter(self.candidate).adb,target['capabilities']['appium:udid'],
            target['appId'],context,guard,artifact_root,self._snapshot_readbacks(selector),run)

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

    def _animation_inventory(self,selector,*,read_only=False):
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return NativeAnimationInventory(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+ANIMATION_INVENTORY_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,monotonic=native.monotonic,sleep=native.sleep)

    def _snapshot_normal_controls(self,selector,intent,*,read_only=False):
        from overte_phone_snapshot_ui import PhoneSnapshotControls
        ui,_observe,_binding,guard,_installed=self.normal_feature_runtime(selector,read_only=read_only)
        target=self.target(selector);guard()
        io=self._snapshot_controls(selector,intent,read_only=read_only)
        return PhoneSnapshotControls(io,PhoneScriptUI(ui,target['appId']),intent,
            monotonic=io.monotonic,sleep=io.sleep)

    def _snapshot_controls(self,selector,intent,*,read_only=False):
        from overte_phone_snapshot_controls import PhoneSnapshotIO,FILE
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid'];transport=PhoneAdapter(self.candidate).adb
        return PhoneSnapshotIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,intent=intent,monotonic=native.monotonic,sleep=native.sleep)

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

    def _assets_controls(self, selector, intent, *, read_only=False):
        # Internal original-input component; complete public capability remains off.
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        io=PhoneAssetsIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+ASSETS_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid)
        return TokenAssetsUI(io,intent)

    def _create_controls(self, selector, intent, *, read_only=False):
        # Internal normal-input component. The caller owns the panel/entities
        # and persists intent; this never enables feature.create capabilities.
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        native_ui,_observe,_context,check,_installed=self.normal_feature_runtime(selector,read_only=read_only)
        ui=PhoneScriptUI(native_ui,target['appId'])
        check()
        io=PhoneCreateIO(native.send,
            lambda:transport.read_debug_app_file(device,target['appId'],'files/overte-e2e/'+CREATE_UI_FILE,attempts=1),
            native.clock_ms,native.guard,native.pid,tablet_shown=ui.tablet_visible)
        return TokenCreateUI(io,intent)

    def _chat_controls(self, selector, intent, run, *, read_only=False):
        # Input component only. The caller owns source/profile/settings/peer
        # intent; normal input effects never enable full Chat capabilities.
        native=self._native_feature_observer(selector,read_only=read_only)
        target=self.target(selector);device=target['capabilities']['appium:udid']
        transport=PhoneAdapter(self.candidate).adb
        native_ui,_observe,_context,check,_installed=self.normal_feature_runtime(selector,read_only=read_only)
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

    def _audio_controls(self, selector, intent, *, read_only=False):
        # Internal ordinary-input prerequisite. Caller must persist ownership;
        # no full Audio capability is advertised by this component.
        native = self._native_feature_observer(selector,read_only=read_only)
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

    def _snapshot_foundation(self,selector,root,binding,guard):
        from overte_phone_snapshot_foundation import PhoneSnapshotFoundation
        return PhoneSnapshotFoundation(self,selector,root,binding,guard)

    @staticmethod
    def snapshot_fingerprint(target):
        return hashlib.sha256(json.dumps(target, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def normal_snapshot(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        retained=PrivateFeatureState(self.state_path(selector).with_name('phone-snapshot-foundation.json')).read()
        require(operation=='snapshot.close' and retained is not None or operation in self.advertised_capabilities(target), 'PHONE_NORMAL_SNAPSHOT_NOT_ENABLED')
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
        full_context=context | {'sessionId': session, 'generation': state['generation'], 'targetFingerprint': fingerprint}
        # One separate foundation scope owns original files and settings. It is
        # never reused as the extended Journey's run or detached file authority.
        mode='1' if operation=='snapshot.close' and retained is not None else os.environ.get('OVERTE_PHONE_FEATURE_SNAPSHOTS','0')
        require(mode in ('0','1'),'PHONE_FEATURE_SNAPSHOTS_CONFIGURATION_INVALID')
        foundation=None
        if mode=='1' or retained is not None:
            root=retained['artifactRoot'] if retained is not None else os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR','')
            foundation=self._snapshot_foundation(selector,root,full_context,check);files=foundation
        else:
            binding=PhoneAdapter(self.candidate)
            files=AndroidSnapshotFiles(binding.adb,target['capabilities']['appium:udid'],target['appId'],context,check,
                os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
        flow = PhoneSnapshot(PhoneSnapshotUI(client, session, check), files, self.snapshot_store(selector),full_context)
        result = foundation.invoke(flow,operation,arguments) if foundation is not None else flow.invoke(operation,arguments)
        check()
        require(self.installed_identity(selector) == installed, 'PHONE_NORMAL_SNAPSHOT_INSTALL_CHANGED')
        return result

    def cleanup(self, selector):
        chat_feature_error=False
        try:
            metadata=self.chat_feature_store(selector).read() or self.chat_retirement_store(selector).read()
            if metadata is not None:self._chat_feature(selector,metadata['runId'],retirement=True).finalize()
        except Exception:chat_feature_error=True
        lifecycle_input_error=False
        try:
            feature=self.lifecycle_input_feature_store(selector).read() or self.lifecycle_input_retirement_store(selector).read()
            if feature is not None:self._lifecycle_input_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:lifecycle_input_error=True
        audio_error=False
        try:
            metadata=self.audio_feature_store(selector).read() or self.audio_retirement_store(selector).read()
            if metadata is not None:self._audio_feature(selector,metadata['runId'],retirement=True).finalize()
            from overte_phone_audio_mute import PhoneAudioMute
            if self.audio_mute_store(selector).read() is not None:PhoneAudioMute(self,selector,self.audio_mute_store(selector)).cleanup()
        except Exception:audio_error=True
        reference_error=False
        try:
            if self.web_reference_store(selector).read() is not None or self.web_reference_retired_store(selector).read() is not None:self._web_reference(selector).cleanup()
        except Exception:reference_error=True
        avatar_people_error=False
        try:
            feature=self.avatar_people_feature_store(selector).read() or self.avatar_people_retirement_store(selector).read()
            if feature is not None:self._avatar_people_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:avatar_people_error=True
        world_web_error=False
        try:
            feature=self.world_web_feature_store(selector).read() or self.world_web_retirement_store(selector).read()
            if feature is not None:self._world_web_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:world_web_error=True
        tablet_controls_error=False
        try:
            if self.tablet_controls_store(selector).read() is not None:self.normal_tablet_control(selector,'tablet.close')
        except Exception:tablet_controls_error=True
        tablet_web_error=False
        try:
            feature=self.tablet_web_feature_store(selector).read() or self.tablet_web_retirement_store(selector).read()
            if feature is not None:self._tablet_web_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:tablet_web_error=True
        navigation_error=False
        try:
            feature=self.navigation_feature_store(selector).read() or self.navigation_retirement_store(selector).read()
            if feature is not None:self._navigation_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:navigation_error=True
        assets_error=False
        try:
            metadata=self.assets_feature_store(selector).read() or PrivateFeatureState(self.state_path(selector).with_name('phone-assets-retirement.json')).read()
            if metadata is not None:self._assets_feature(selector,metadata['runId'],retirement=True).finalize()
        except Exception:assets_error=True
        create_error=False
        try:
            feature=self.create_feature_store(selector).read() or PrivateFeatureState(self.state_path(selector).with_name('phone-create-retirement.json')).read()
            if feature is not None:self._create_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:create_error=True # Preserve unresolved originals and attempt base teardown.
        emote_error=False
        try:
            feature=self.emote_feature_store(selector).read() or PrivateFeatureState(self.state_path(selector).with_name('phone-emote-retirement.json')).read()
            if feature is not None:self._emote_feature(selector,feature['runId'],retirement=True).finalize()
        except Exception:emote_error=True # Keep every unresolved owner; base teardown is still attempted.
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
        foundation_error=False
        foundation_store=PrivateFeatureState(self.state_path(selector).with_name('phone-snapshot-foundation.json'))
        if foundation_store.read() is not None:
            try:self.normal_snapshot(selector,'snapshot.close',{})
            except Exception:foundation_error=True
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
        require(not foundation_error and foundation_store.read() is None,'PHONE_SNAPSHOT_FOUNDATION_CLEANUP_INCOMPLETE')
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
        require(not chat_feature_error and all(PrivateFeatureState(self.state_path(selector).with_name(name)).read() is None
            for name in ('phone-chat-feature.json','phone-chat-retirement.json','phone-chat-primary.json','phone-chat-actor.json',
                         'phone-chat-peer-capture.json','phone-chat-peer-files.json')),'PHONE_CHAT_FEATURE_CLEANUP_INCOMPLETE')
        require(not chat_error and self.chat_capture_store(selector).read() is None,
                'PHONE_CHAT_CAPTURE_CLEANUP_INCOMPLETE')
        require(not world_error and all(self.world_render_store(selector,role=role).read() is None for role in ('primary','actor')),
                'PHONE_WORLD_RENDER_CLEANUP_INCOMPLETE')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-scene.json')).read() is None,
                'PHONE_EMOTE_SCENE_OWNERSHIP_REMAINS')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-view.json')).read() is None,
                'PHONE_EMOTE_VIEW_OWNERSHIP_REMAINS')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-background.json')).read() is None,
                'PHONE_EMOTE_BACKGROUND_CLEANUP_INCOMPLETE')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-namespaces.json')).read() is None,
                'PHONE_EMOTE_NAMESPACE_CLEANUP_INCOMPLETE')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-cleanup-inputs.json')).read() is None,
                'PHONE_EMOTE_CLEANUP_INPUT_OWNERSHIP_REMAINS')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-actor-lifecycle.json')).read() is None,
                'PHONE_EMOTE_ACTOR_OWNERSHIP_PENDING')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-failures.json')).read() is None,
                'PHONE_EMOTE_FAILURE_OWNERSHIP_PENDING')
        require(all(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-'+role+'-role.json')).read() is None
                for role in ('primary','actor')),'PHONE_EMOTE_ROLE_OWNERSHIP_PENDING')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-run.json')).read() is None,
                'PHONE_EMOTE_RUN_OWNERSHIP_REMAINS')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-retirement.json')).read() is None,
                'PHONE_EMOTE_RETIREMENT_OWNERSHIP_REMAINS')
        require(all(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-'+role+'-admission.json')).read() is None
                    for role in ('primary','actor')),'PHONE_EMOTE_ADMISSION_OWNERSHIP_REMAINS')
        require(all(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-'+role+'-lifetime.json')).read() is None
                    for role in ('primary','actor')),'PHONE_EMOTE_LIFETIME_CLEANUP_INCOMPLETE')
        require(not any(self.state_path(selector).parent.glob('phone-emote-*-capture-*.json')),
                'PHONE_EMOTE_CAPTURE_CLEANUP_INCOMPLETE')
        require(not any(self.state_path(selector).parent.glob('phone-emote-*-observation-*.json')),
                'PHONE_EMOTE_OBSERVATION_CLEANUP_INCOMPLETE')
        require(all(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-'+role+'-sources.json')).read() is None
                    for role in ('primary','actor')),'PHONE_EMOTE_SOURCE_CLEANUP_INCOMPLETE')
        require(not any(self.state_path(selector).parent.glob('phone-emote-*-sources-segment-*.json')),
                'PHONE_EMOTE_SOURCE_CLEANUP_INCOMPLETE')
        require(PrivateFeatureState(self.state_path(selector).with_name('phone-emote-inputs.json')).read() is None,
                'PHONE_EMOTE_INPUT_CLEANUP_INCOMPLETE')
        require(not any(self.state_path(selector).parent.glob('phone-emote-inputs-segment-*.json')),
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
        require(not reference_error and self.web_reference_store(selector).read() is None
            and self.web_reference_manager_store(selector).read() is None and self.web_reference_retired_store(selector).read() is None,'PHONE_WEB_REFERENCE_CLEANUP_INCOMPLETE')
        require(not world_web_error and self.world_web_feature_store(selector).read() is None
                and self.world_web_retirement_store(selector).read() is None and self.world_web_manager_store(selector).read() is None
                and all(PrivateFeatureState(self.state_path(selector).with_name('phone-world-web-'+role+'.json')).read() is None
                    for role in ('primary','actor')),'PHONE_WORLD_WEB_FEATURE_CLEANUP_INCOMPLETE')
        require(not tablet_controls_error and self.tablet_controls_store(selector).read() is None,'PHONE_TABLET_CONTROLS_CLEANUP_INCOMPLETE')
        require(not tablet_web_error and self.tablet_web_feature_store(selector).read() is None
                and self.tablet_web_retirement_store(selector).read() is None and self.tablet_web_manager_store(selector).read() is None
                and all(PrivateFeatureState(self.state_path(selector).with_name('phone-tablet-web-'+role+'.json')).read() is None
                    for role in ('primary','actor')),'PHONE_TABLET_WEB_FEATURE_CLEANUP_INCOMPLETE')
        require(not authentication_error and self.authentication_feature_store(selector).read() is None and self.authentication_retirement_store(selector).read() is None
                and all(PrivateFeatureState(self.state_path(selector).with_name('phone-authentication-'+role+'-feature.json')).read() is None
                        for role in ('primary','actor')),'PHONE_AUTHENTICATION_FEATURE_CLEANUP_INCOMPLETE')
        require(not navigation_error and self.navigation_feature_store(selector).read() is None and self.navigation_retirement_store(selector).read() is None
            and all(PrivateFeatureState(self.state_path(selector).with_name('phone-navigation-'+role+'-feature.json')).read() is None for role in ('primary','actor')),
            'PHONE_NAVIGATION_FEATURE_CLEANUP_INCOMPLETE')
        require(not lifecycle_input_error and self.lifecycle_input_feature_store(selector).read() is None and self.lifecycle_input_retirement_store(selector).read() is None
            and all(PrivateFeatureState(self.state_path(selector).with_name('phone-lifecycle-input-'+role+'.json')).read() is None for role in ('primary','actor')),
            'PHONE_LIFECYCLE_INPUT_FEATURE_CLEANUP_INCOMPLETE')
        require(not avatar_people_error and self.avatar_people_feature_store(selector).read() is None and self.avatar_people_retirement_store(selector).read() is None
            and all(PrivateFeatureState(self.state_path(selector).with_name('phone-avatar-people-'+role+'-feature.json')).read() is None for role in ('primary','actor')),
            'PHONE_AVATAR_PEOPLE_FEATURE_CLEANUP_INCOMPLETE')
        require(not graphics_error and self.graphics_feature_store(selector).read() is None
                and self.graphics_retirement_store(selector).read() is None,'PHONE_GRAPHICS_FEATURE_CLEANUP_INCOMPLETE')
        require(not assets_error and self.assets_feature_store(selector).read() is None
            and PrivateFeatureState(self.state_path(selector).with_name('phone-assets-retirement.json')).read() is None
            and all(PrivateFeatureState(self.state_path(selector).with_name('phone-assets-'+kind+'.json')).read() is None
                for kind in ('primary-originals','actor-originals','actor-lifecycle'))
            and all(PrivateFeatureState(self.state_path(selector).with_name('phone-assets-files-owner-'+str(stage)+'.json')).read() is None for stage in range(1,7)),
            'PHONE_ASSETS_FEATURE_CLEANUP_INCOMPLETE')
        require(not create_error and self.create_feature_store(selector).read() is None
            and PrivateFeatureState(self.state_path(selector).with_name('phone-create-retirement.json')).read() is None
            and all(PrivateFeatureState(self.state_path(selector).with_name('phone-create-'+kind+'.json')).read() is None for kind in ('primary-originals','actor-originals','actor-lifecycle','files-owner')),'PHONE_CREATE_FEATURE_CLEANUP_INCOMPLETE')
        require(not audio_error and self.audio_feature_store(selector).read() is None and self.audio_retirement_store(selector).read() is None
            and self.audio_mute_store(selector).read() is None and all(PrivateFeatureState(self.state_path(selector).with_name('phone-audio-'+role+'.json')).read() is None for role in ('primary','actor')),'PHONE_AUDIO_FEATURE_CLEANUP_INCOMPLETE')
        require(not emote_error,'PHONE_EMOTE_FEATURE_CLEANUP_INCOMPLETE')
        return result

    def normal_navigation(self, selector, operation, values):
        arguments = validate_operation_arguments(operation, values)
        target = self.target(selector)
        require(operation in self.advertised_capabilities(target), 'PHONE_NORMAL_NAVIGATION_NOT_ENABLED')
        if operation=='scene.load':
            from overte_phone_navigation_scene import configuration,provider as validate_provider
            configuration(target.get('controls',{}).get('normalNavigation'),arguments['url'],os.environ.get('OVERTE_E2E_SCENE_URL',''))
            require(self.candidate is not None and self.controlled_android_client(target) and target.get('scene',{}).get('kind')=='android-debug-e2e',
                'PHONE_NORMAL_SCENE_BOUND_DEBUG_TARGET_REQUIRED')
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
        if operation=='scene.load':
            if os.environ.get('OVERTE_PHONE_FEATURE_WORLD_NAVIGATION','0')=='1':
                import time
                from urllib.parse import urlsplit
                source=self._feature_fixture_client();run=uuid.uuid4().hex
                reader=self._navigation_view(selector,read_only=True)
                before=reader.read(run);provider=source.request('/navigation-provider');after=reader.read(run)
                validate_provider(provider,arguments['url'],installed['sourceRevision'],int(time.time()*1000))
                origin=urlsplit(source.url);origin=origin.scheme+'://'+origin.netloc
                require(all(row['source']['endpoint'].rstrip('/')==origin and row['source']['protocolSignature']==provider['inputs']['protocolSignature']
                    for row in (before,after)),'PHONE_NORMAL_SCENE_ORIGINAL_PROVIDER_MISMATCH')
            result=flow.load_scene(arguments['url'])
        else:result = flow.invoke(operation, arguments)
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

    def _invoke_feature(self,selector,operation,values,factory):
        from overte_phone_feature_dispatch import invoke
        return invoke(operation,values,factory,self._feature_fixture_client)

    def invoke(self, selector, operation, values):
        PhoneAdapter.require_bound_operation(self, operation, values)
        if operation in COLLABORATION_OPERATIONS:
            validate_operation_arguments(operation,values)
            require(os.environ.get('OVERTE_ANDROID_E2E_COLLABORATION','0')=='1','PHONE_COLLABORATION_NOT_ENABLED')
            return self._collaboration(selector).invoke(operation,values)
        if operation in LIFECYCLE_INPUT_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values);require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_LIFECYCLE_INPUT_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._lifecycle_input_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in ('app.launch','scene.load'):
            self.account_fixture_configuration(self.target(selector))
        if operation=='scene.load' and values.get('url')!='overte-e2e://fixture/scene' and self.target(selector).get('controls',{}).get('normalNavigation') is not None:
            return self.normal_navigation(selector,operation,values)
        if operation in AVATAR_PEOPLE_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_AVATAR_PEOPLE_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._avatar_people_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in CHAT_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values);require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_CHAT_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._chat_feature(selector,values['runId'],retirement=retired))
        if operation in NAVIGATION_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_NAVIGATION_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._navigation_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in AUDIO_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values);require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_AUDIO_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._audio_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation=='audio.mute' and os.environ.get('OVERTE_PHONE_FEATURE_AUDIO','0')=='1':
            from overte_phone_audio_mute import PhoneAudioMute
            arguments=validate_operation_arguments(operation,values);require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_AUDIO_CONTROLS_NOT_ENABLED')
            return PhoneAudioMute(self,selector,self.audio_mute_store(selector)).act(arguments['muted'])
        if operation in SCRIPT_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),
                    'PHONE_SCRIPT_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._script_feature(selector,values['runId']))
        if operation in AUTHENTICATION_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),
                    'PHONE_AUTHENTICATION_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._authentication_feature(selector,values['runId']))
        if operation in GRAPHICS_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),
                    'PHONE_GRAPHICS_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._graphics_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in WEB_REFERENCE_OPERATIONS:
            values=validate_operation_arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_WEB_REFERENCE_NOT_ENABLED')
            return self._web_reference(selector).invoke(operation,values)
        if operation in WORLD_WEB_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_WORLD_WEB_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._world_web_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in TABLET_FOUNDATION_OPERATIONS and (os.environ.get('OVERTE_PHONE_FEATURE_TABLET_WEB','0')=='1'
                or os.environ.get('OVERTE_PHONE_FEATURE_LIFECYCLE_INPUT','0')=='1'):
            validate_operation_arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_TABLET_CONTROLS_NOT_ENABLED')
            return self.normal_tablet_control(selector,operation)
        if operation in TABLET_WEB_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_TABLET_WEB_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._tablet_web_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in ASSETS_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_ASSETS_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._assets_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in CREATE_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),'PHONE_CREATE_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._create_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
        if operation in EMOTE_FEATURE_OPERATIONS:
            from feature_journeys.contract import arguments
            arguments(operation,values)
            require(operation in self.advertised_capabilities(self.target(selector)),
                    'PHONE_EMOTE_FEATURE_NOT_ENABLED')
            return self._invoke_feature(selector,operation,values,lambda retired:self._emote_feature(selector,values['runId'],**({'retirement':True} if retired else {})))
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
